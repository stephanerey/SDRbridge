#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

try:
    from validate_lot_contract import parse_simple_yaml
except Exception:
    parse_simple_yaml = None


VALID_STATUSES = {
    "proposed",
    "planned",
    "validated",
    "in_progress",
    "done",
    "user_testing",
    "repair",
    "reopened",
    "blocked",
    "superseded",
}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_E2E_MODES = {"per_lot", "grouped_at_pass_end", "not_required"}
REQUIRED_PASS_FIELDS = ["pass_id", "title", "status", "lots", "preflight", "e2e_strategy", "stop_on"]
FINISHED_DEPENDENCY_STATUSES = {"done", "user_testing"}
EXECUTABLE_PASS_STATUSES = {"validated", "in_progress", "repair", "reopened"}


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None
    if yaml:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    text = path.read_text(encoding="utf-8")
    if "\npasses:" in f"\n{text}":
        return parse_pass_subset(text)
    if parse_simple_yaml is None:
        raise ValueError("PyYAML unavailable and fallback parser unavailable")
    return parse_simple_yaml(path)


def parse_scalar(value: str):
    value = value.strip()
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        value = value[1:-1]
    if value == "[]":
        return []
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    return value


def parse_pass_subset(text: str) -> dict:
    passes = []
    current = None
    current_list_key = None
    current_object_key = None
    current_object_list_key = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("- pass_id:"):
            if current:
                passes.append(current)
            current = {"pass_id": parse_scalar(stripped.split(":", 1)[1].strip())}
            current_list_key = None
            current_object_key = None
            current_object_list_key = None
            continue
        if current is None:
            continue
        if raw.startswith("    ") and not raw.startswith("      ") and ":" in stripped and not stripped.startswith("- "):
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                current[key] = parse_scalar(value)
                current_list_key = None
                current_object_key = None
                current_object_list_key = None
            else:
                if key in {"sequencing", "preflight", "e2e_strategy", "gates"}:
                    current[key] = {}
                    current_object_key = key
                    current_object_list_key = None
                    current_list_key = None
                else:
                    current[key] = []
                    current_list_key = key
                    current_object_key = None
                    current_object_list_key = None
            continue
        if raw.startswith("      ") and current_object_key and ":" in stripped and not stripped.startswith("- "):
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            target = current.setdefault(current_object_key, {})
            if value:
                target[key] = parse_scalar(value)
                current_object_list_key = None
            else:
                target[key] = []
                current_object_list_key = key
            continue
        if raw.startswith("        - ") and current_object_key and current_object_list_key:
            target = current.setdefault(current_object_key, {})
            target.setdefault(current_object_list_key, []).append(parse_scalar(stripped[2:].strip()))
            continue
        if raw.startswith("      - ") and current_list_key:
            current.setdefault(current_list_key, []).append(parse_scalar(stripped[2:].strip()))
    if current:
        passes.append(current)
    return {"passes": passes}


def load_lots(path: Path) -> dict[str, dict]:
    data = load_yaml(path)
    lots = data.get("lots")
    if not isinstance(lots, list):
        raise ValueError(f"{path}: missing lots list")
    result = {}
    for lot in lots:
        if isinstance(lot, dict) and isinstance(lot.get("lot_id"), str):
            result[lot["lot_id"]] = lot
    return result


def as_list(value) -> list:
    return value if isinstance(value, list) else []


def has_dependency_override(overrides: list, lot_id: str, dependency: str) -> bool:
    return any(isinstance(value, str) and lot_id in value and dependency in value for value in overrides)


def build_pass_lot_index(passes: list) -> tuple[dict[str, dict], list[str]]:
    lot_index: dict[str, dict] = {}
    errors: list[str] = []
    seen_pass_ids = set()
    for pass_index, item in enumerate(passes):
        if not isinstance(item, dict):
            continue
        pass_id = item.get("pass_id")
        if not isinstance(pass_id, str) or not pass_id.strip():
            continue
        if pass_id in seen_pass_ids:
            errors.append(f"pass[{pass_index}]: ambiguous global pass order because pass_id {pass_id!r} is duplicated")
        seen_pass_ids.add(pass_id)
        lots = item.get("lots")
        if not isinstance(lots, list):
            continue
        for lot_position, lot_id in enumerate(lots):
            if not isinstance(lot_id, str):
                continue
            previous = lot_index.get(lot_id)
            if previous:
                if previous["pass_index"] != pass_index:
                    errors.append(
                        f"lot {lot_id!r} appears in multiple passes: "
                        f"{previous['pass_id']!r} and {pass_id!r}; duplicate lots are not supported"
                    )
                continue
            lot_index[lot_id] = {
                "pass_id": pass_id,
                "pass_index": pass_index,
                "lot_index": lot_position,
            }
    return lot_index, errors


def validate_external_dependency(
    pass_item: dict,
    pass_index: int,
    lot_id: str,
    dependency: str,
    lots_by_id: dict[str, dict],
    pass_lot_index: dict[str, dict] | None,
) -> str | None:
    dependency_lot = lots_by_id.get(dependency)
    dependency_position = pass_lot_index.get(dependency) if pass_lot_index else None
    status = pass_item.get("status")
    if dependency_position:
        dependency_pass_index = dependency_position["pass_index"]
        dependency_pass_id = dependency_position["pass_id"]
        if dependency_pass_index < pass_index:
            if status in EXECUTABLE_PASS_STATUSES and (
                not dependency_lot or dependency_lot.get("status") not in FINISHED_DEPENDENCY_STATUSES
            ):
                return (
                    f"pass[{pass_index}]: lot {lot_id!r} depends on unfinished lot {dependency!r} "
                    f"in earlier pass {dependency_pass_id!r}"
                )
            return None
        if dependency_pass_index > pass_index:
            return (
                f"pass[{pass_index}]: lot {lot_id!r} depends on lot {dependency!r} "
                f"in later pass {dependency_pass_id!r}"
            )
        return (
            f"pass[{pass_index}]: lot {lot_id!r} depends on lot {dependency!r} "
            "outside its local pass order but indexed in the same pass"
        )
    if dependency_lot and dependency_lot.get("status") not in FINISHED_DEPENDENCY_STATUSES:
        return f"pass[{pass_index}]: lot {lot_id!r} depends on unfinished lot {dependency!r} outside pass"
    return None


def validate_pass(
    item: dict,
    index: int,
    lots_by_id: dict[str, dict] | None,
    pass_lot_index: dict[str, dict] | None = None,
) -> list[str]:
    errors = []
    prefix = f"pass[{index}]"
    for field in REQUIRED_PASS_FIELDS:
        if field not in item or item[field] in (None, "", []):
            errors.append(f"{prefix}: missing or empty {field}")
    status = item.get("status")
    if status and status not in VALID_STATUSES:
        errors.append(f"{prefix}: invalid status {status!r}")
    priority = item.get("priority")
    if priority is not None and priority not in VALID_PRIORITIES:
        errors.append(f"{prefix}: invalid priority {priority!r}")
    lots = item.get("lots")
    if lots is not None and not isinstance(lots, list):
        errors.append(f"{prefix}: lots must be a list")
        lots = []
    if isinstance(lots, list) and len(lots) != len(set(lots)):
        errors.append(f"{prefix}: lots must not contain duplicates")

    preflight = item.get("preflight")
    if preflight is not None:
        if not isinstance(preflight, dict):
            errors.append(f"{prefix}: preflight must be an object")
        else:
            for key in (
                "required_before_start",
                "secrets_required",
                "external_actions_required",
                "human_validation_required",
                "migrations_required",
                "open_questions",
            ):
                if key in preflight and not isinstance(preflight[key], list):
                    errors.append(f"{prefix}: preflight.{key} must be a list")

    sequencing = item.get("sequencing", {})
    if sequencing is not None and not isinstance(sequencing, dict):
        errors.append(f"{prefix}: sequencing must be an object")
        sequencing = {}
    overrides = as_list(sequencing.get("dependency_overrides")) if isinstance(sequencing, dict) else []
    if overrides and not all(isinstance(value, str) and value.strip() for value in overrides):
        errors.append(f"{prefix}: sequencing.dependency_overrides must contain non-empty strings")

    e2e = item.get("e2e_strategy")
    if e2e is not None:
        if not isinstance(e2e, dict):
            errors.append(f"{prefix}: e2e_strategy must be an object")
        else:
            mode = e2e.get("mode")
            if mode not in VALID_E2E_MODES:
                errors.append(f"{prefix}: e2e_strategy.mode must be one of {sorted(VALID_E2E_MODES)}")
            items = e2e.get("items")
            if items is not None and not isinstance(items, list):
                errors.append(f"{prefix}: e2e_strategy.items must be a list")
            if mode != "not_required" and not items:
                errors.append(f"{prefix}: e2e_strategy.items must not be empty unless mode is not_required")

    for list_field in ("shared_sources", "stop_on", "notes"):
        if list_field in item and not isinstance(item[list_field], list):
            errors.append(f"{prefix}: {list_field} must be a list")
    request_ids = item.get("validated_request_ids")
    if request_ids is not None:
        if not isinstance(request_ids, list) or not request_ids:
            errors.append(f"{prefix}: validated_request_ids must be a non-empty list when present")
        elif not all(isinstance(value, str) and value.strip() for value in request_ids):
            errors.append(f"{prefix}: validated_request_ids must contain non-empty strings")
        elif len(request_ids) != len(set(request_ids)):
            errors.append(f"{prefix}: validated_request_ids must not contain duplicates")

    if lots_by_id is not None and isinstance(lots, list):
        lot_positions = {lot_id: pos for pos, lot_id in enumerate(lots)}
        for lot_id in lots:
            if lot_id not in lots_by_id:
                errors.append(f"{prefix}: lots references unknown lot_id {lot_id!r}")
                continue
            lot = lots_by_id[lot_id]
            lot_status = lot.get("status")
            if item.get("status") in EXECUTABLE_PASS_STATUSES and lot_status in {"blocked", "proposed", "superseded"}:
                errors.append(f"{prefix}: executable pass includes non-executable lot {lot_id!r} with status {lot_status!r}")
            for dependency in as_list(lot.get("depends_on")):
                if dependency in lot_positions and lot_positions[dependency] > lot_positions[lot_id]:
                    if not has_dependency_override(overrides, lot_id, dependency):
                        errors.append(f"{prefix}: lot {lot_id!r} appears before dependency {dependency!r}")
                elif dependency not in lot_positions:
                    error = validate_external_dependency(item, index, lot_id, dependency, lots_by_id, pass_lot_index)
                    if error:
                        errors.append(error)
        lot_statuses = [lots_by_id[lot_id].get("status") for lot_id in lots if lot_id in lots_by_id]
        if status == "done" and any(lot_status != "done" for lot_status in lot_statuses):
            errors.append(f"{prefix}: status done requires every lot to be done; found {lot_statuses}")
        if status == "user_testing":
            incompatible = sorted({value for value in lot_statuses if value not in {"done", "user_testing"}})
            if incompatible:
                errors.append(
                    f"{prefix}: status user_testing is incompatible with lot statuses {incompatible}; repair or incomplete lots must reopen the pass"
                )
        if status == "repair" and not any(value in {"repair", "reopened"} for value in lot_statuses):
            errors.append(f"{prefix}: status repair requires at least one repair or reopened lot")
        if status == "reopened" and not any(value in {"repair", "reopened"} for value in lot_statuses):
            errors.append(f"{prefix}: status reopened requires at least one repair or reopened lot")
    return errors


def validate_passes(passes: list, lots_by_id: dict[str, dict] | None) -> list[str]:
    errors = []
    seen = set()
    pass_lot_index, index_errors = build_pass_lot_index(passes)
    errors.extend(index_errors)
    for index, item in enumerate(passes):
        if not isinstance(item, dict):
            errors.append(f"pass[{index}]: must be an object")
            continue
        pass_id = item.get("pass_id")
        if pass_id in seen:
            errors.append(f"pass[{index}]: duplicate pass_id {pass_id!r}")
        seen.add(pass_id)
        errors.extend(validate_pass(item, index, lots_by_id, pass_lot_index))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a SR_PASSES.yaml file.")
    parser.add_argument("--file", required=True, help="Path to SR_PASSES.yaml")
    parser.add_argument("--lots-file", help="Path to SR_LOTS.yaml for reference checks")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"missing file: {path}", file=sys.stderr)
        return 1
    try:
        data = load_yaml(path)
        lots_by_id = load_lots(Path(args.lots_file)) if args.lots_file else None
    except Exception as exc:
        print(f"Pass contract errors:\n- {exc}", file=sys.stderr)
        return 1

    passes = data.get("passes")
    if not isinstance(passes, list):
        print("SR_PASSES must contain a `passes` list", file=sys.stderr)
        return 1

    errors = validate_passes(passes, lots_by_id)

    if errors:
        print("Pass contract errors:")
        for error in errors:
            print(f"- {error}")
        return 1
    if not passes:
        print("OK: empty pass registry valid; define product passes through pass planning")
        return 0
    print(f"OK: {len(passes)} pass(es) valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
