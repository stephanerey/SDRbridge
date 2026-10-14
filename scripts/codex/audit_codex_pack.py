#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from validate_release_docs import audit as audit_release_docs
from sr_route_check import check as check_routes

TARGET_VERSION = "4.1.0"
REMOVED_SKILLS = (
    "aurora-planning-with-files",
    "aurora-repomap-maintainer",
    "aurora-review-diff",
    "aurora-tdd",
    "aurora-terminal-token-optimizer",
)


def read_version(root: Path) -> str:
    for rel in ("docs/codex/SR_PACK_VERSION.json", "core/SR_PACK_VERSION.json"):
        path = root / rel
        if path.exists():
            try:
                return json.loads(path.read_text()).get("version", "unknown")
            except Exception:
                return "unreadable"
    return "unknown"


def audit(root: Path) -> tuple[list[str], list[str]]:
    source = (root / "core/SR_METHOD.md").exists()
    prefix = Path("core") if source else Path("docs/codex")
    required = [
        prefix / "SR_METHOD.md",
        prefix / "SR_BOOTSTRAP.md",
        prefix / "SR_ROUTES.json",
        prefix / "SKILL_DIGEST.md",
        prefix / "TOKEN_OPTIMIZATION.md",
        prefix / ("MCP_POLICY.template.yaml" if source else "MCP_POLICY.yaml"),
        prefix / "UPGRADE_TEST_PLAN.md",
    ]
    missing = [str(path) for path in required if not (root / path).exists()]
    stale = []
    if read_version(root) != TARGET_VERSION:
        stale.append(f"installed version {read_version(root)!r} != target {TARGET_VERSION!r}")
    skill_root = root / ("skills-method" if source else "docs/codex/skills-method")
    for name in REMOVED_SKILLS:
        if (skill_root / name / "SKILL.md").exists():
            stale.append(f"removed cognitive skill still present: {name}")
    stale.extend(check_routes(root))
    stale.extend(f"release docs: {item}" for item in audit_release_docs(root))
    return missing, stale


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit an SR Method 4.1 source or installation")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    missing, stale = audit(root)
    result = {"root": str(root), "installed_version": read_version(root), "target_version": TARGET_VERSION, "missing": missing, "stale": stale, "ok": not missing and not stale}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif result["ok"]:
        print("OK: SR Method 4.1 source or installation is coherent")
    else:
        for item in missing + stale:
            print(f"- {item}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
