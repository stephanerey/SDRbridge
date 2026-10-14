#!/usr/bin/env python3
import json
from pathlib import Path

from validate_release_docs import audit as audit_release_docs
from sr_route_check import check as check_routes

TARGET_VERSION = "4.1.0"
REMOVED_SKILLS = {
    "aurora-planning-with-files",
    "aurora-repomap-maintainer",
    "aurora-review-diff",
    "aurora-tdd",
    "aurora-terminal-token-optimizer",
}


def main() -> int:
    root = Path(".").resolve()
    source_mode = (root / "core/SR_BOOTSTRAP.md").exists()
    prefix = Path("core") if source_mode else Path("docs/codex")
    required = [
        prefix / "SR_PACK_VERSION.json",
        prefix / "SR_METHOD.md",
        prefix / "SR_BOOTSTRAP.md",
        prefix / "SR_ROUTES.json",
        prefix / "SKILL_DIGEST.md",
        prefix / "TOKEN_OPTIMIZATION.md",
        prefix / ("MCP_POLICY.template.yaml" if source_mode else "MCP_POLICY.yaml"),
        prefix / "UPGRADE_TEST_PLAN.md",
        Path("core/AGENTS.template.md") if source_mode else Path("AGENTS.md"),
        Path("tasks/_TEMPLATE/task_state.yaml") if source_mode else Path("docs/codex/tasks/_TEMPLATE/task_state.yaml"),
        Path("scripts/codex/sr_install_transaction.py"),
    ]
    errors = [f"missing required file: {path}" for path in required if not (root / path).exists()]
    version_path = root / prefix / "SR_PACK_VERSION.json"
    try:
        version = json.loads(version_path.read_text())["version"]
        if version != TARGET_VERSION:
            errors.append(f"version {version!r} != {TARGET_VERSION!r}")
    except Exception as exc:
        errors.append(f"invalid version metadata: {exc}")

    skill_root = root / ("skills-method" if source_mode else "docs/codex/skills-method")
    for name in REMOVED_SKILLS:
        if (skill_root / name / "SKILL.md").exists():
            errors.append(f"removed cognitive skill still present: {name}")

    agents = root / ("core/AGENTS.template.md" if source_mode else "AGENTS.md")
    if agents.exists() and len(agents.read_text().splitlines()) > 120:
        errors.append(f"AGENTS kernel exceeds 120 lines: {agents}")

    errors.extend(check_routes(root))
    errors.extend(f"release docs: {item}" for item in audit_release_docs(root))
    if errors:
        print("SR pack verification errors:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK: SR Method 4.1 pack is coherent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
