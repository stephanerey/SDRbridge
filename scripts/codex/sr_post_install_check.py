#!/usr/bin/env python3
"""Read-mostly post-install verification for SR Method 4.1."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_VERSION = "4.1.0"
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
        value = yaml.safe_load(path.read_text()) if path.exists() else {}
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def run(root: Path, command: list[str]) -> dict:
    try:
        result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=120)
        return {"command": command, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "returncode": 124, "stdout": "", "stderr": str(exc)}


def check(root: Path) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    required = [
        "AGENTS.md",
        "docs/codex/PROJECT_PROFILE.yaml",
        "docs/codex/MCP_POLICY.yaml",
        "docs/codex/SR_PACK_VERSION.json",
        "docs/codex/SR_METHOD.md",
        "docs/codex/SR_BOOTSTRAP.md",
        "docs/codex/SR_ROUTES.json",
        "docs/codex/SKILL_DIGEST.md",
        "docs/codex/TOKEN_OPTIMIZATION.md",
        "docs/codex/UPGRADE_TEST_PLAN.md",
        "docs/codex/tasks/_TEMPLATE/task_state.yaml",
        "scripts/codex/sr_install_transaction.py",
        "scripts/codex/verify_codex_pack.py",
    ]
    for rel in required:
        if not (root / rel).exists():
            errors.append(f"missing required file: {rel}")
    try:
        version = json.loads((root / "docs/codex/SR_PACK_VERSION.json").read_text()).get("version")
        if version != EXPECTED_VERSION:
            errors.append(f"version {version!r} != {EXPECTED_VERSION!r}")
    except Exception as exc:
        errors.append(f"invalid version metadata: {exc}")

    profile = load_yaml(root / "docs/codex/PROJECT_PROFILE.yaml")
    mode = profile.get("knowledge", {}).get("mode") if isinstance(profile.get("knowledge"), dict) else None
    if mode not in {"core", "nexus_kg"}:
        errors.append("knowledge.mode must be core or nexus_kg")
    if mode == "nexus_kg" and not (root / "docs/codex/MCP_POLICY.yaml").exists():
        errors.append("nexus_kg mode requires MCP_POLICY.yaml")
    methods = profile.get("skills", {}).get("method", []) if isinstance(profile.get("skills"), dict) else []
    for name in REMOVED_SKILLS.intersection(methods if isinstance(methods, list) else []):
        errors.append(f"removed cognitive skill remains declared: {name}")
    for name in REMOVED_SKILLS:
        if (root / "docs/codex/skills-method" / name / "SKILL.md").exists():
            warnings.append(f"obsolete locally modified skill preserved but not declared: {name}")

    agents = root / "AGENTS.md"
    if agents.exists() and len(agents.read_text().splitlines()) > 120:
        warnings.append(f"AGENTS.md exceeds the 120-line target: {len(agents.read_text().splitlines())}")
    return errors, warnings


def ensure_gitignore(root: Path) -> list[str]:
    path = root / ".gitignore"
    text = path.read_text() if path.exists() else ""
    if ".playwright/.auth/" in text:
        return []
    path.write_text(text.rstrip() + "\n# SR local authentication state\n.playwright/.auth/\n")
    return ["added .playwright/.auth/ to .gitignore"]


def main() -> int:
    parser = argparse.ArgumentParser(description="SR post-install check")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fix-safe", action="store_true")
    parser.add_argument("--write-report", action="store_true", help="Persist a short verification report")
    parser.add_argument("--no-report", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    fixed = ensure_gitignore(root) if args.fix_safe else []
    errors, warnings = check(root)
    commands = []
    for command in (
        [sys.executable, "scripts/codex/verify_codex_pack.py"],
        [sys.executable, "scripts/codex/audit_sr_project.py", "--root", ".", "--json"],
        [sys.executable, "scripts/codex/audit_sr_task_contracts.py", "--root", ".", "--json"],
        [sys.executable, "scripts/codex/validate_release_docs.py", "--root", ".", "--json"],
    ):
        result = run(root, command)
        commands.append(result)
        if result["returncode"] != 0:
            errors.append(f"command failed ({result['returncode']}): {' '.join(command)}")
            detail = (result["stderr"] or result["stdout"]).strip()
            if detail:
                warnings.append(detail[:1200])

    result = {
        "root": str(root),
        "expected_version": EXPECTED_VERSION,
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "fixed": fixed,
        "commands": [{"command": item["command"], "returncode": item["returncode"]} for item in commands],
    }
    if args.write_report and not args.no_report:
        now = datetime.now(timezone.utc)
        report = root / "docs/codex/tasks" / f"{now:%Y-%m-%d}_sr-post-install-check" / "verification.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            "# SR Post Install Check\n\n"
            f"- created_at: {now.isoformat()}\n- status: {'OK' if result['ok'] else 'ERROR'}\n"
            f"- errors: {len(errors)}\n- warnings: {len(warnings)}\n"
        )
        result["report_path"] = str(report)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif result["ok"]:
        print("OK: SR Method 4.1 post-install check passed")
    else:
        for error in errors:
            print(f"- {error}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
