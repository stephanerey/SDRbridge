#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def candidate_files(root: Path) -> list[Path]:
    bases = [root / "docs/codex/tasks", root / "tasks", root / ".handoffs"]
    files: list[Path] = []
    for base in bases:
        if not base.exists():
            continue
        for path in base.glob("**/NEXT_SESSION_PROMPT.md"):
            if not path.is_file():
                continue
            if "_TEMPLATE" in path.parts:
                continue
            files.append(path)
    return files


def score(path: Path) -> tuple[float, str]:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0
    return (mtime, str(path))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--prompt", help="Explicit prompt path within root; overrides discovery")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    files = sorted(candidate_files(root), key=score, reverse=True)
    explicit = None
    if args.prompt:
        explicit = (root / args.prompt).resolve()
        if not explicit.is_relative_to(root) or not explicit.is_file():
            ap.error("explicit prompt must be an existing file within root")
        files = [explicit] + [p for p in files if p.resolve() != explicit]
    files = [p for p in files if p.resolve().is_relative_to(root)]
    items = []
    for path in files[: max(args.limit, 1)]:
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            rel = str(path)
        items.append({"path": rel, "mtime": path.stat().st_mtime})
    ambiguous = len(files) > 1 and explicit is None
    selected = items[0] if items and not ambiguous else None
    result = {"root": str(root), "found": bool(items), "latest": items[0] if items else None,
              "selected": selected, "ambiguous": ambiguous, "candidate_count": len(files),
              "selection_reason": "explicit" if explicit else "ambiguous" if ambiguous else "single_or_absent",
              "candidates": items}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if not items:
            print("No NEXT_SESSION_PROMPT.md found")
        else:
            if ambiguous:
                print("Ambiguous resume: choose an explicit --prompt; mtime is not task authority.")
            else:
                print(f"Selected NEXT_SESSION_PROMPT.md: {items[0]['path']}")
            if len(items) > 1:
                print("Other candidates:")
                for item in items[1:]:
                    print(f"- {item['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
