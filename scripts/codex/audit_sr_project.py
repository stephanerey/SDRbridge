#!/usr/bin/env python3
"""Small read-only audit of the SR 4.1 operating surface."""
import argparse
import json
from pathlib import Path

from sr_route_check import check as check_routes

REMOVED_SKILLS = {
    "aurora-planning-with-files",
    "aurora-repomap-maintainer",
    "aurora-review-diff",
    "aurora-tdd",
    "aurora-terminal-token-optimizer",
}


def load_yaml(path: Path) -> dict:
    try:
        import yaml
        value = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def pass_contract_errors(path: Path, lots: Path) -> list[str]:
    """Compatibility helper used by the legacy contract audit suite."""
    if not path.exists():
        return []
    try:
        from validate_pass_contract import load_lots, load_yaml as load_pass_yaml, validate_passes
        data = load_pass_yaml(path)
        lots_by_id = load_lots(lots) if lots.exists() else None
    except Exception as exc:
        return [str(exc)]
    passes = data.get("passes")
    if not isinstance(passes, list):
        return ["passes must be a list"]
    return validate_passes(passes, lots_by_id) if passes else []


def audit(root: Path) -> tuple[list[str], list[str]]:
    root = root.resolve()
    source = (root / "core/SR_METHOD.md").exists()
    prefix = Path("core") if source else Path("docs/codex")
    agents = root / ("core/AGENTS.template.md" if source else "AGENTS.md")
    profile_path = root / ("core/PROJECT_PROFILE.template.yaml" if source else "docs/codex/PROJECT_PROFILE.yaml")
    mcp_path = root / ("core/MCP_POLICY.template.yaml" if source else "docs/codex/MCP_POLICY.yaml")
    task_state = root / ("tasks/_TEMPLATE/task_state.yaml" if source else "docs/codex/tasks/_TEMPLATE/task_state.yaml")
    errors: list[str] = []
    warnings: list[str] = []

    for path in (agents, profile_path, mcp_path, task_state, root / prefix / "SR_ROUTES.json"):
        if not path.exists():
            errors.append(f"missing required file: {path.relative_to(root)}")
    errors.extend(check_routes(root))

    if agents.exists():
        lines = len(agents.read_text(encoding="utf-8", errors="ignore").splitlines())
        if lines > 120:
            warnings.append(f"AGENTS kernel exceeds target: {lines} lines")

    profile = load_yaml(profile_path)
    mode = ((profile.get("knowledge") or {}).get("mode")) if isinstance(profile.get("knowledge"), dict) else None
    if mode not in {"core", "nexus_kg"}:
        errors.append("knowledge.mode must be core or nexus_kg")
    methods = ((profile.get("skills") or {}).get("method", [])) if isinstance(profile.get("skills"), dict) else []
    if not isinstance(methods, list):
        errors.append("skills.method must be a list")
        methods = []
    for name in sorted(REMOVED_SKILLS.intersection(methods)):
        errors.append(f"removed cognitive skill remains declared: {name}")
    if len(methods) > 4:
        warnings.append(f"default method skill catalog exceeds target: {len(methods)}")

    mcp = load_yaml(mcp_path)
    if mode == "core" and mcp.get("mode") != "core":
        errors.append("core knowledge mode requires core MCP policy")
    if mode == "nexus_kg" and not mcp_path.exists():
        errors.append("nexus_kg mode requires MCP_POLICY.yaml")

    skill_root = root / ("skills-method" if source else "docs/codex/skills-method")
    for name in sorted(REMOVED_SKILLS):
        if (skill_root / name / "SKILL.md").exists():
            warnings.append(f"obsolete locally modified skill preserved but inactive: {name}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit SR Method 4.1 project policy")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    errors, warnings = audit(root)
    result = {"root": str(root), "errors": errors, "warnings": warnings, "ok": not errors}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif errors:
        for item in errors:
            print(f"- {item}")
    else:
        print("OK: SR Method 4.1 project policy is coherent")
        for item in warnings:
            print(f"WARNING: {item}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
