#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path


REQUIRED_LOT_FIELDS = [
    "lot_id",
    "title",
    "status",
    "objective",
    "acceptance_criteria",
    "verification_commands",
    "stop_conditions",
]

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
    "deferred",
    "superseded",
}
VALID_GATE_STATUSES = {"pending", "pass", "fail", "not_applicable"}
VALID_RECONCILIATION_STATUSES = {"not_required", "pending", "completed", "blocked"}
EXECUTABLE_LOT_STATUSES = {"planned", "validated", "in_progress", "repair", "reopened"}
DESIGN_EVIDENCE_READY_STATUSES = {"pass", "not_applicable"}


def parse_simple_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None
    if yaml:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data or {}
    return parse_template_subset(path)


def parse_template_subset(path: Path) -> dict:
    """Very small YAML subset parser for this pack's sr_lots template.

    It is intentionally limited: it extracts top-level `lots` entries and common
    scalar/list fields so the validator can run without PyYAML.
    """
    lots = []
    version = None
    current = None
    current_list_key = None
    current_object_key = None
    current_object_list_key = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if current is None and stripped.startswith("version:"):
            version = value_after_colon(stripped)
            continue
        if stripped.startswith("- lot_id:"):
            if current:
                lots.append(current)
            current = {"lot_id": value_after_colon(stripped)}
            current_list_key = None
            current_object_key = None
            current_object_list_key = None
            continue
        if current is None:
            continue
        if raw.startswith("    ") and ":" in stripped and not stripped.startswith("- "):
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                current[key] = parse_scalar(value)
                current_list_key = None
                current_object_key = None
                current_object_list_key = None
            else:
                if key in {"dependency_reconciliation", "global_impact", "design_evidence"}:
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
        lots.append(current)
    result = {"lots": lots}
    if version is not None:
        result["version"] = version
    return result


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        return value[1:-1]
    return value


def parse_scalar(value: str):
    value = strip_quotes(value)
    if value == "[]":
        return []
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    return value


def value_after_colon(value: str) -> str:
    return parse_scalar(value.split(":", 1)[1].strip())


def version_at_least(value: str, minimum: str) -> bool:
    def parts(raw: str) -> list[int]:
        result = []
        for item in str(raw).split("."):
            try:
                result.append(int(item))
            except ValueError:
                result.append(0)
        return result

    left = parts(value)
    right = parts(minimum)
    size = max(len(left), len(right))
    left.extend([0] * (size - len(left)))
    right.extend([0] * (size - len(right)))
    return left >= right


def validate_lot(
    lot: dict,
    index: int,
    enforce_design_evidence: bool = False,
    enforce_requirement_registry: bool = False,
) -> list[str]:
    errors = []
    prefix = f"lot[{index}]"
    for field in REQUIRED_LOT_FIELDS:
        if field not in lot or lot[field] in (None, "", []):
            errors.append(f"{prefix}: missing or empty {field}")
    status = lot.get("status")
    if status and status not in VALID_STATUSES:
        errors.append(f"{prefix}: invalid status {status!r}")
    for list_field in ("acceptance_criteria", "verification_commands", "stop_conditions"):
        if list_field in lot and not isinstance(lot[list_field], list):
            errors.append(f"{prefix}: {list_field} must be a list")
    request_ids = lot.get("validated_request_ids")
    if enforce_requirement_registry:
        if not isinstance(request_ids, list) or not request_ids:
            errors.append(f"{prefix}: validated_request_ids must be a non-empty list for SR_LOTS 0.4+")
        elif not all(isinstance(value, str) and value.strip() for value in request_ids):
            errors.append(f"{prefix}: validated_request_ids must contain non-empty strings")
        elif len(request_ids) != len(set(request_ids)):
            errors.append(f"{prefix}: validated_request_ids must not contain duplicates")
    elif request_ids is not None and not isinstance(request_ids, list):
        errors.append(f"{prefix}: validated_request_ids must be a list when present")
    if lot.get("allowed_paths") and not isinstance(lot.get("allowed_paths"), list):
        errors.append(f"{prefix}: allowed_paths must be a list when present")
    if lot.get("forbidden_paths") and not isinstance(lot.get("forbidden_paths"), list):
        errors.append(f"{prefix}: forbidden_paths must be a list when present")
    for list_field in ("depends_on", "blocked_by", "impacts", "impacted_by", "supersedes"):
        if list_field in lot and not isinstance(lot[list_field], list):
            errors.append(f"{prefix}: {list_field} must be a list when present")
    if "superseded_by" in lot and lot["superseded_by"] is not None and not isinstance(lot["superseded_by"], str):
        errors.append(f"{prefix}: superseded_by must be null or a string when present")
    reconciliation = lot.get("dependency_reconciliation")
    if reconciliation is not None:
        if not isinstance(reconciliation, dict):
            errors.append(f"{prefix}: dependency_reconciliation must be an object")
        else:
            if reconciliation.get("status") not in VALID_RECONCILIATION_STATUSES:
                errors.append(f"{prefix}: dependency_reconciliation.status must be one of {sorted(VALID_RECONCILIATION_STATUSES)}")
            for list_field in ("reviewed_lots", "classifications", "open_questions"):
                if not isinstance(reconciliation.get(list_field), list):
                    errors.append(f"{prefix}: dependency_reconciliation.{list_field} must be a list")
    global_impact = lot.get("global_impact")
    if global_impact is not None:
        if not isinstance(global_impact, dict):
            errors.append(f"{prefix}: global_impact must be an object")
        else:
            required = global_impact.get("required")
            if not isinstance(required, bool):
                errors.append(f"{prefix}: global_impact.required must be boolean")
            status = global_impact.get("status")
            if status not in VALID_GATE_STATUSES:
                errors.append(f"{prefix}: global_impact.status must be one of {sorted(VALID_GATE_STATUSES)}")
            for list_field in ("surfaces_reviewed", "impacted_lots", "new_lots_to_create", "lots_to_reopen_or_block", "open_questions"):
                if not isinstance(global_impact.get(list_field), list):
                    errors.append(f"{prefix}: global_impact.{list_field} must be a list")
            recommendation = global_impact.get("sequencing_recommendation")
            if not isinstance(recommendation, str) or not recommendation.strip():
                errors.append(f"{prefix}: global_impact.sequencing_recommendation must be a non-empty string")
            if required is True:
                if status == "not_applicable":
                    errors.append(f"{prefix}: global_impact.status cannot be not_applicable when required is true")
                if not global_impact.get("surfaces_reviewed"):
                    errors.append(f"{prefix}: global_impact.surfaces_reviewed must not be empty when required is true")
    errors.extend(validate_design_evidence(lot, index, enforce_design_evidence=enforce_design_evidence))
    return errors


def validate_design_evidence(lot: dict, index: int, enforce_design_evidence: bool = False) -> list[str]:
    errors = []
    prefix = f"lot[{index}]"
    status = lot.get("status")
    evidence = lot.get("design_evidence")
    is_executable = status in EXECUTABLE_LOT_STATUSES

    if evidence is None:
        if is_executable and enforce_design_evidence:
            errors.append(f"{prefix}: design_evidence is required for executable lot status {status!r}")
        return errors

    if not isinstance(evidence, dict):
        errors.append(f"{prefix}: design_evidence must be an object")
        return errors

    evidence_status = evidence.get("status")
    if evidence_status not in VALID_GATE_STATUSES:
        errors.append(f"{prefix}: design_evidence.status must be one of {sorted(VALID_GATE_STATUSES)}")

    code_read_required = evidence.get("code_read_required")
    if code_read_required is not None and not isinstance(code_read_required, bool):
        errors.append(f"{prefix}: design_evidence.code_read_required must be boolean when present")

    for list_field in (
        "candidate_files",
        "confirmed_files_read",
        "symbols_or_routes_checked",
        "tests_or_logs_checked",
        "assumptions_remaining",
        "open_questions",
    ):
        if list_field in evidence and not isinstance(evidence[list_field], list):
            errors.append(f"{prefix}: design_evidence.{list_field} must be a list")

    ceiling = evidence.get("status_ceiling_if_not_pass")
    if ceiling is not None and ceiling not in VALID_STATUSES:
        errors.append(f"{prefix}: design_evidence.status_ceiling_if_not_pass must be a valid lot status")

    if not is_executable:
        return errors

    if evidence_status not in DESIGN_EVIDENCE_READY_STATUSES:
        errors.append(
            f"{prefix}: executable lot status {status!r} requires design_evidence.status "
            f"to be one of {sorted(DESIGN_EVIDENCE_READY_STATUSES)}"
        )

    if evidence_status == "not_applicable":
        reason = evidence.get("not_applicable_reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{prefix}: design_evidence.not_applicable_reason is required when status is not_applicable")

    if code_read_required is True and evidence_status == "pass" and not evidence.get("confirmed_files_read"):
        errors.append(
            f"{prefix}: design_evidence.confirmed_files_read must not be empty when code_read_required is true"
        )
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="Path to SR_LOTS.yaml")
    args = ap.parse_args()
    path = Path(args.file)
    if not path.exists():
        print(f"missing file: {path}", file=sys.stderr)
        return 1
    data = parse_simple_yaml(path)
    version = str(data.get("version") or "")
    enforce_design_evidence = version_at_least(version, "0.3")
    enforce_requirement_registry = version_at_least(version, "0.4")
    lots = data.get("lots")
    if not isinstance(lots, list) or not lots:
        print("SR_LOTS must contain a non-empty `lots` list", file=sys.stderr)
        return 1
    errors = []
    seen = set()
    for i, lot in enumerate(lots):
        if not isinstance(lot, dict):
            errors.append(f"lot[{i}]: must be an object")
            continue
        lot_id = lot.get("lot_id")
        if lot_id in seen:
            errors.append(f"lot[{i}]: duplicate lot_id {lot_id!r}")
        seen.add(lot_id)
        errors.extend(
            validate_lot(
                lot,
                i,
                enforce_design_evidence=enforce_design_evidence,
                enforce_requirement_registry=enforce_requirement_registry,
            )
        )
    for i, lot in enumerate(lots):
        if not isinstance(lot, dict):
            continue
        for field in ("depends_on", "blocked_by", "supersedes"):
            refs = lot.get(field, []) if isinstance(lot.get(field), list) else []
            for ref in refs:
                if ref not in seen:
                    errors.append(f"lot[{i}]: {field} references unknown lot_id {ref!r}")
        superseded_by = lot.get("superseded_by")
        if superseded_by and superseded_by not in seen:
            errors.append(f"lot[{i}]: superseded_by references unknown lot_id {superseded_by!r}")
    if errors:
        print("Lot contract errors:")
        for err in errors:
            print(f"- {err}")
        return 1
    print(f"OK: {len(lots)} lot(s) valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
