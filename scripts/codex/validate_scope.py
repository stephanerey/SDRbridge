#!/usr/bin/env python3
import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

from validate_lot_contract import parse_simple_yaml


def changed_files(base: str | None) -> list[str]:
    cmd = ["git", "diff", "--name-only"]
    if base:
        cmd.insert(2, base)
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        text=True,
        capture_output=True,
        check=False,
    )
    if untracked.returncode == 0:
        files.extend(line.strip() for line in untracked.stdout.splitlines() if line.strip())
    return sorted(set(files))


def match_any(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        pattern = pattern.replace("\\", "/")
        if fnmatch.fnmatch(normalized, pattern):
            return True
        if pattern.endswith("/**") and normalized.startswith(pattern[:-3]):
            return True
        if pattern.endswith("/**/*") and normalized.startswith(pattern[:-5]):
            return True
    return False


def find_lot(lots_file: Path, lot_id: str) -> dict:
    data = parse_simple_yaml(lots_file)
    for lot in data.get("lots", []):
        if isinstance(lot, dict) and lot.get("lot_id") == lot_id:
            return lot
    print(f"lot not found: {lot_id}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lots-file", required=True)
    ap.add_argument("--lot-id", required=True)
    ap.add_argument("--base", default=None, help="Optional git diff base ref")
    args = ap.parse_args()
    lot = find_lot(Path(args.lots_file), args.lot_id)
    allowed = lot.get("allowed_paths") or ["**"]
    forbidden = lot.get("forbidden_paths") or []
    if not isinstance(allowed, list) or not isinstance(forbidden, list):
        print("allowed_paths and forbidden_paths must be lists", file=sys.stderr)
        return 1
    files = changed_files(args.base)
    out_of_scope = [f for f in files if not match_any(f, allowed)]
    forbidden_hits = [f for f in files if match_any(f, forbidden)]
    if out_of_scope or forbidden_hits:
        print("Scope gate failed")
        if out_of_scope:
            print("Out of allowed_paths:")
            for f in out_of_scope:
                print(f"- {f}")
        if forbidden_hits:
            print("Forbidden paths touched:")
            for f in forbidden_hits:
                print(f"- {f}")
        return 1
    print(f"OK: scope valid for {len(files)} changed file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
