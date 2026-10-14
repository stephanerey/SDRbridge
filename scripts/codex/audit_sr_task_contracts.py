#!/usr/bin/env python3
"""Audit SR contracts and legacy task memories; flag registries needing normalization."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

try:
    import validate_sr_contract
except Exception:
    validate_sr_contract = None


LEGACY_FILES = (
    "task_plan.md",
    "findings.md",
    "progress.md",
    "decisions.md",
    "verification.md",
    "gate_report.md",
    "loop_contract.json",
)

LEGACY_LOT_COMPLETION_GATE_CUTOFF = date(2026, 8, 8)
LEGACY_LOT_COMPLETION_GATE_ERRORS = {
    "missing required key: lot_completion_gate",
    "status done requires gates.lot_completion pass",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def task_dirs(root: Path, task: str | None = None) -> list[Path]:
    base = root / "docs/codex/tasks"
    if task:
        candidate = Path(task)
        if not candidate.is_absolute():
            candidate = root / task
        return [candidate]
    if not base.exists():
        return []
    return sorted(path for path in base.iterdir() if path.is_dir() and path.name != "_TEMPLATE")


def has_legacy_memory(path: Path) -> bool:
    return any((path / name).exists() for name in LEGACY_FILES)


def first_non_empty_line(path: Path) -> str | None:
    for line in read_text(path).splitlines():
        value = line.strip().strip("#").strip()
        if value:
            return value
    return None


def infer_lot_id(path: Path) -> str:
    text = "\n".join(read_text(path / name) for name in ("task_plan.md", "gate_report.md", "progress.md"))
    for raw in text.replace("`", " ").replace('"', " ").split():
        if raw.startswith("SR-") and len(raw) > 3:
            return raw.strip(".,:;()[]")
    return path.name.upper().replace("-", "_")


def infer_objective(path: Path) -> str:
    for name in ("task_plan.md", "progress.md", "gate_report.md"):
        title = first_non_empty_line(path / name)
        if title:
            return f"Contrat SR 3.0.0 retro-cree depuis la memoire legacy: {title}."
    return "Contrat SR 3.0.0 retro-cree depuis une memoire legacy."


def legacy_files(path: Path) -> list[str]:
    return [name for name in LEGACY_FILES if (path / name).exists()]


def task_date(path: Path) -> date | None:
    prefix = path.name[:10]
    try:
        return date.fromisoformat(prefix)
    except ValueError:
        return None


def is_pre_lot_completion_gate_legacy(path: Path, errors: list[str]) -> bool:
    parsed = task_date(path)
    if parsed is None or parsed >= LEGACY_LOT_COMPLETION_GATE_CUTOFF:
        return False
    return bool(errors) and set(errors).issubset(LEGACY_LOT_COMPLETION_GATE_ERRORS)


def contract_template(path: Path) -> dict:
    files = legacy_files(path)
    today = date.today().isoformat()
    return {
        "schema_version": "3.0.0",
        "task_id": path.name,
        "lot_id": infer_lot_id(path),
        "task_type": "realign",
        "status": "planned",
        "objective": infer_objective(path),
        "validated_requests": [
            {
                "id": "REQ-LEGACY-001",
                "source": f"audit_sr_task_contracts.py {today}",
                "requirement_type": "realign",
                "status": "todo",
                "coverage": "Relire la memoire legacy et confirmer manuellement les intentions utilisateur avant de marquer le contrat done.",
                "files": files,
                "verification": [],
                "notes": [
                    "Contrat cree en mode migration controlee.",
                    "Les fichiers legacy sont conserves.",
                ],
            }
        ],
        "lot_completion_gate": {
            "status": "pending",
            "validated_scope_source": f"audit_sr_task_contracts.py {today}",
            "scope_reduction_requested": False,
            "scope_reduction_validated_by_user": False,
            "coverage_table": [
                {
                    "requirement_id": "REQ-LEGACY-001",
                    "requirement": "Relire la memoire legacy et confirmer les intentions utilisateur.",
                    "status": "non fait",
                    "proof": files,
                    "comment": "Contrat de migration initialise, non cloturable en done sans reprise SR."
                }
            ],
            "ui_ux_required": False,
            "visual_evidence": [],
            "decision": "planned"
        },
        "scope": {
            "in": ["audit de memoire legacy"],
            "out": ["suppression des fichiers legacy", "modification applicative"],
            "allowed_paths": [str(path.relative_to(path.parents[3])) + "/**"] if len(path.parents) >= 4 else [],
            "forbidden_paths": [".env", ".env.*", ".git/**"],
        },
        "product_truth": {
            "required": True,
            "items": [
                "Ce contrat est une base de realignement, pas une preuve que le lot legacy est done.",
                "Les fichiers legacy restent historiques.",
            ],
        },
        "propagation": {
            "required": False,
            "status": "not_applicable",
            "trigger": "not_applicable",
            "risk_level": "not_applicable",
            "preflight": {
                "done": False,
                "summary": "Contrat legacy initialise sans changement de symbole ou contrat partage.",
                "human_validation_required": False,
                "human_validation_received": False,
            },
            "changed_symbols": [],
            "affected_surfaces": [],
            "consumers_checked": [],
            "reference_searches": [],
            "remaining_references": [],
            "ignored_references": [],
            "compatibility_strategy": "not_required",
            "verification": [],
            "decision": "not_applicable",
        },
        "evidence": {
            "sources_read": files,
            "code_files_read": [],
            "tests_or_logs": [],
        },
        "ui_validation": {
            "required": False,
            "routes": [],
            "test_readiness": {
                "status": "not_applicable",
                "auth_required": False,
                "auth_mode": "none",
                "state_available": None,
                "state_valid": None,
                "login_redirect_detected": False,
                "blocked_reason": None,
            },
            "visual_evidence": {
                "status": "not_applicable",
                "routes": [],
                "viewports": [],
                "screenshots": [],
                "report_file": None,
                "console_errors": 0,
                "page_errors": 0,
                "request_failed": 0,
                "horizontal_overflow_detected": False,
                "unexpected_login_redirect": False,
            },
        },
        "skills": {
            "method": ["aurora-lot-runner"],
            "domain": [],
        },
        "plan": [
            "Relire les fichiers legacy.",
            "Identifier les intentions utilisateur validees.",
            "Mettre a jour validated_requests avec les statuts exacts.",
            "Valider le contrat avant reprise du lot.",
        ],
        "findings": [],
        "decisions": [
            "Contrat cree sans supprimer les fichiers legacy."
        ],
        "implementation": {
            "app_code_changed": False,
            "changed_files": [str(path / "sr_contract.json")],
        },
        "verification": {
            "commands_run": [],
            "commands_failed": [],
            "not_run_reason": "Contrat initial a completer apres lecture humaine ou reprise SR stricte.",
        },
        "gates": {
            "evidence": "pending",
            "scope": "pending",
            "product_truth": "pass",
            "lot_completion": "pending",
            "propagation": "not_applicable",
            "ui_test_readiness": "not_applicable",
            "ui_visual_evidence": "not_applicable",
            "verification": "pending",
            "self_evaluation": "pending",
            "context_budget": "not_applicable",
        },
        "e2e": {
            "required": True,
            "items": [
                "Verifier que les intentions legacy ont ete retranscrites dans validated_requests avant cloture."
            ],
        },
        "context": {
            "status": "not_checked",
            "report_path": None,
        },
        "transition": {
            "decision": "not_applicable",
            "reason": "Contrat legacy initialise, reprise manuelle requise.",
            "next_session_prompt_required": False,
            "next_session_prompt_path": None,
            "next_user_prompt": None,
        },
    }


def validate_contract(path: Path) -> tuple[bool, list[str], list[str]]:
    if validate_sr_contract is None:
        return False, ["validate_sr_contract import unavailable"], []
    try:
        data = validate_sr_contract.load_contract(path)
    except ValueError as exc:
        return False, [str(exc)], []
    errors, warnings = validate_sr_contract.validate(data, contract_path=path)
    requests = data.get("validated_requests")
    if data.get("schema_version") == "3.0.0" and isinstance(requests, list) and len(requests) == 1:
        request = requests[0] if isinstance(requests[0], dict) else {}
        combined = " ".join(
            str(request.get(key, "")) for key in ("id", "source", "coverage")
        ).lower()
        if not any("generic" in warning and "normalize" in warning for warning in warnings) and (
            request.get("id") == "REQ-LEGACY-001" or any(
                marker in combined for marker in ("tous les lots", "cinq lots", "five lots", "multi-lot")
            )
        ):
            warnings.append(
                "legacy validated_requests registry is generic; normalize it manually into stable per-lot and per-criterion "
                "requirements before resuming or closing the scope"
            )
    return not errors, errors, warnings


def inspect_task(path: Path, write: bool, overwrite: bool) -> dict:
    contract = path / "sr_contract.json"
    legacy = legacy_files(path)
    item = {
        "task": str(path),
        "legacy_files": legacy,
        "has_legacy_memory": bool(legacy),
        "has_sr_contract": contract.exists(),
        "created": False,
        "legacy_compat": False,
        "valid": None,
        "errors": [],
        "warnings": [],
    }
    if not path.exists() or not path.is_dir():
        item["errors"].append("task directory missing")
        return item
    if not has_legacy_memory(path) and not contract.exists():
        item["warnings"].append("no legacy memory or sr_contract.json found")
        return item
    if write and (overwrite or not contract.exists()):
        contract.write_text(json.dumps(contract_template(path), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        item["created"] = True
        item["has_sr_contract"] = True
    if contract.exists():
        valid, errors, warnings = validate_contract(contract)
        if not valid and is_pre_lot_completion_gate_legacy(path, errors):
            item["legacy_compat"] = True
            item["valid"] = True
            item["warnings"].extend(
                [
                    "legacy contract accepted before Lot Completion Gate cutoff; "
                    "missing lot_completion_gate is downgraded to warning for upgrade compatibility"
                ]
                + errors
                + warnings
            )
            return item
        item["valid"] = valid
        item["errors"].extend(errors)
        item["warnings"].extend(warnings)
    return item


def audit(root: Path, write: bool = False, overwrite: bool = False, task: str | None = None) -> dict:
    items = [inspect_task(path, write, overwrite) for path in task_dirs(root, task)]
    missing = [item for item in items if item["has_legacy_memory"] and not item["has_sr_contract"]]
    invalid = [item for item in items if item["has_sr_contract"] and item["valid"] is False]
    created = [item for item in items if item["created"]]
    return {
        "root": str(root),
        "write": write,
        "overwrite": overwrite,
        "total_tasks": len(items),
        "legacy_tasks": sum(1 for item in items if item["has_legacy_memory"]),
        "with_sr_contract": sum(1 for item in items if item["has_sr_contract"]),
        "missing_sr_contract": len(missing),
        "invalid_sr_contract": len(invalid),
        "created": len(created),
        "items": items,
        "ok": not invalid,
    }


def print_human(result: dict) -> None:
    print(f"SR task contract audit: {result['root']}")
    print(f"tasks: {result['total_tasks']}")
    print(f"legacy_tasks: {result['legacy_tasks']}")
    print(f"with_sr_contract: {result['with_sr_contract']}")
    print(f"missing_sr_contract: {result['missing_sr_contract']}")
    print(f"invalid_sr_contract: {result['invalid_sr_contract']}")
    print(f"created: {result['created']}")
    for item in result["items"]:
        if item["errors"] or item["warnings"] or not item["has_sr_contract"]:
            print(f"- {item['task']}")
            if item["legacy_files"]:
                print(f"  legacy: {', '.join(item['legacy_files'])}")
            print(f"  sr_contract: {'yes' if item['has_sr_contract'] else 'no'}")
            if item["valid"] is not None:
                print(f"  valid: {item['valid']}")
            for error in item["errors"]:
                print(f"  error: {error}")
            for warning in item["warnings"]:
                print(f"  warning: {warning}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit SR contracts or create compatible 3.0.0 migration contracts.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--task", help="Limit to one task directory, relative to root or absolute.")
    parser.add_argument("--write", action="store_true", help="Create missing sr_contract.json files.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing sr_contract.json files; requires --write.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.overwrite and not args.write:
        print("--overwrite requires --write", file=sys.stderr)
        return 2
    result = audit(Path(args.root).resolve(), write=args.write, overwrite=args.overwrite, task=args.task)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_human(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
