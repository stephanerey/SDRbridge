#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_WINDOW = 258400
VALID_OK_STATUSES = {"green", "yellow"}
VALID_RISK_STATUSES = {"orange", "red"}
VALID_UNRELIABLE_STATUSES = {"unknown", "stale", "ambiguous"}
BUDGET_THRESHOLDS = {
    "context_yellow_percent": 70,
    "context_orange_percent": 82,
    "context_red_percent": 92,
    "uncached_yellow_tokens": 12000,
    "uncached_orange_tokens": 24000,
    "uncached_red_tokens": 48000,
    "low_cache_ratio_percent": 50,
    "low_cache_min_context_percent": 55,
    "user_turns_orange": 20,
    "lots_yellow": 2,
    "lots_orange": 3,
}


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def resolve_path_text(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(Path(value).expanduser().resolve())
    except Exception:
        return str(value)


def iter_session_files(limit: int = 80) -> list[Path]:
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    root = home / "sessions"
    if not root.exists():
        return []
    return sorted(root.glob("**/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def empty_usage() -> dict[str, int]:
    return {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "uncached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
    }


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, int]:
    raw = usage or {}
    input_tokens = int(raw.get("input_tokens") or 0)
    cached = int(raw.get("cached_input_tokens") or 0)
    cached = max(0, min(cached, input_tokens))
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached,
        "uncached_input_tokens": max(0, input_tokens - cached),
        "output_tokens": int(raw.get("output_tokens") or 0),
        "reasoning_output_tokens": int(raw.get("reasoning_output_tokens") or 0),
        "total_tokens": int(raw.get("total_tokens") or 0),
    }


def session_summary(path: Path, root: Path) -> dict[str, Any] | None:
    context_window = None
    last_usage = empty_usage()
    total_usage = empty_usage()
    last_rate_limits: dict[str, Any] | None = None
    last_token_at: datetime | None = None
    compactions = 0
    user_turns = 0
    session_cwd: str | None = None
    session_created_at: datetime | None = None
    token_events = 0
    root_text = str(root.resolve())

    try:
        # Stream records rather than retaining the entire session in memory.
        lines = path.open(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    for line in lines:
        try:
            item = json.loads(line)
        except Exception:
            continue
        timestamp = parse_ts(item.get("timestamp"))
        payload = item.get("payload") or {}
        item_type = item.get("type")
        payload_type = payload.get("type")

        if item_type == "session_meta":
            meta = payload or {}
            session_created_at = parse_ts(meta.get("timestamp")) or timestamp or session_created_at
            session_cwd = resolve_path_text(meta.get("cwd")) or session_cwd

        if item_type == "turn_context":
            session_cwd = resolve_path_text(payload.get("cwd")) or session_cwd
            context_window = payload.get("model_context_window") or context_window

        if item_type == "event_msg" and payload_type == "task_started":
            context_window = payload.get("model_context_window") or context_window

        if item_type == "event_msg" and payload_type == "token_count":
            info = payload.get("info") or {}
            usage = info.get("last_token_usage") or {}
            if usage:
                last_usage = normalize_usage(usage)
                total_usage = normalize_usage(info.get("total_token_usage") or {})
                last_rate_limits = payload.get("rate_limits") or None
                last_token_at = timestamp or last_token_at
                token_events += 1

        if item_type in {"compacted", "context_compacted"} or (
            item_type == "event_msg" and payload_type in {"context_compacted", "compacted"}
        ):
            compactions += 1
            user_turns = 0

        if item_type == "event_msg" and payload_type == "user_message":
            user_turns += 1

    lines.close()
    if not session_cwd:
        return None

    cwd_matches = session_cwd == root_text
    return {
        "session_file": str(path),
        "session_cwd": session_cwd,
        "cwd_matches_root": cwd_matches,
        "session_created_at": iso_or_none(session_created_at),
        "last_token_at": iso_or_none(last_token_at),
        "last_token_at_dt": last_token_at,
        "context_window": int(context_window or DEFAULT_WINDOW),
        "last_token_usage": last_usage,
        "total_token_usage": total_usage,
        "rate_limits": last_rate_limits,
        "last_input_tokens": last_usage["input_tokens"],
        "cached_input_tokens": last_usage["cached_input_tokens"],
        "uncached_input_tokens": last_usage["uncached_input_tokens"],
        "cache_ratio": round((last_usage["cached_input_tokens"] / last_usage["input_tokens"]) * 100, 2)
        if last_usage["input_tokens"]
        else 0.0,
        "compactions_seen": compactions,
        "user_turns_since_last_compact": user_turns,
        "token_events": token_events,
    }


def budget_for(report: dict[str, Any], context_percent: float, lots_done: int) -> dict[str, Any]:
    uncached = int(report.get("uncached_input_tokens") or 0)
    cache_ratio = float(report.get("cache_ratio") or 0.0)
    user_turns = int(report.get("user_turns_since_last_compact") or 0)

    signals: list[str] = []
    if context_percent >= BUDGET_THRESHOLDS["context_red_percent"]:
        signals.append("context_window_red")
    elif context_percent >= BUDGET_THRESHOLDS["context_orange_percent"]:
        signals.append("context_window_orange")
    elif context_percent >= BUDGET_THRESHOLDS["context_yellow_percent"]:
        signals.append("context_window_yellow")

    if uncached >= BUDGET_THRESHOLDS["uncached_red_tokens"]:
        signals.append("uncached_red")
    elif uncached >= BUDGET_THRESHOLDS["uncached_orange_tokens"]:
        signals.append("uncached_orange")
    elif uncached >= BUDGET_THRESHOLDS["uncached_yellow_tokens"]:
        signals.append("uncached_yellow")

    if (
        context_percent >= BUDGET_THRESHOLDS["low_cache_min_context_percent"]
        and cache_ratio < BUDGET_THRESHOLDS["low_cache_ratio_percent"]
    ):
        signals.append("low_cache_ratio")
    if user_turns >= BUDGET_THRESHOLDS["user_turns_orange"]:
        signals.append("many_user_turns")
    if lots_done >= BUDGET_THRESHOLDS["lots_orange"]:
        signals.append("many_lots_orange")
    elif lots_done >= BUDGET_THRESHOLDS["lots_yellow"]:
        signals.append("many_lots_yellow")

    if "context_window_red" in signals:
        status = "red"
        action = "stop_before_next_lot"
    elif any(
        s in signals
        for s in (
            "context_window_orange",
            "uncached_red",
            "uncached_orange",
            "many_user_turns",
            "many_lots_orange",
        )
    ):
        status = "orange"
        action = "finish_current_lot_then_create_next_session_prompt"
    elif any(s in signals for s in ("context_window_yellow", "uncached_yellow", "low_cache_ratio", "many_lots_yellow")):
        status = "yellow"
        action = "update_next_session_prompt_if_lot_is_significant"
    else:
        status = "green"
        action = "continue"

    return {
        "status": status,
        "recommended_action": action,
        "signals": signals,
        "thresholds": BUDGET_THRESHOLDS,
        "rule": "separate_token_dimensions_v2",
        "notes": [
            "context_percent estimates active context pressure from the last input and never discounts cached tokens",
            "uncached_input_tokens is a separate workload and cost signal",
            "cached_input_tokens and cache_ratio report reuse without pretending to compress context",
            "output and reasoning are reported separately and are not folded into an invented score",
        ],
    }


def unreliable_report(root: Path, status: str, action: str, reason: str, *, candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "root": str(root),
        "session_file": None,
        "session_cwd": None,
        "session_selected_by": "none",
        "selection_reliable": False,
        "selection_reason": reason,
        "context_window": DEFAULT_WINDOW,
        "last_input_tokens": 0,
        "cached_input_tokens": 0,
        "uncached_input_tokens": 0,
        "cache_ratio": 0.0,
        "last_token_usage": empty_usage(),
        "compactions_seen": 0,
        "user_turns_since_last_compact": 0,
        "context_percent": 0,
        "status": status,
        "recommended_action": action,
        "candidate_count": len(candidates or []),
        "candidate_sessions": summarize_candidates(candidates or []),
    }


def rate_limit_used_percent(rate_limits: dict[str, Any] | None, key: str) -> float | None:
    if not rate_limits:
        return None
    value = ((rate_limits.get(key) or {}).get("used_percent"))
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_count(value: Any) -> str:
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return "0"
    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:.1f}m"
    if abs(number) >= 1_000:
        return f"{number / 1_000:.1f}k"
    return str(number)


def compact_report(result: dict[str, Any]) -> str:
    rate_limits = result.get("rate_limits") or {}
    primary = rate_limit_used_percent(rate_limits, "primary")
    secondary = rate_limit_used_percent(rate_limits, "secondary")
    rl = "n/a"
    if primary is not None or secondary is not None:
        rl = f"{primary if primary is not None else 'n/a'}/{secondary if secondary is not None else 'n/a'}"
    signals = ((result.get("budget") or {}).get("signals") or [])
    signals_text = ",".join(signals) if signals else "none"
    return " ".join(
        [
            f"context={result.get('status')}",
            f"action={result.get('recommended_action')}",
            "basis=context|uncached|cache|output|turns|lots",
            f"context_pressure={result.get('context_percent')}%",
            f"uncached={format_count(result.get('uncached_input_tokens'))}",
            f"cached={result.get('cache_ratio')}%",
            f"signals={signals_text}",
            f"output={format_count((result.get('last_token_usage') or {}).get('output_tokens'))}",
            f"reasoning={format_count((result.get('last_token_usage') or {}).get('reasoning_output_tokens'))}",
            f"rl={rl}",
            f"reliable={str(result.get('selection_reliable')).lower()}",
        ]
    )


def summarize_candidates(candidates: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    out = []
    for candidate in candidates[:limit]:
        out.append(
            {
                "session_file": candidate.get("session_file"),
                "session_cwd": candidate.get("session_cwd"),
                "last_token_at": candidate.get("last_token_at"),
                "last_input_tokens": candidate.get("last_input_tokens"),
                "cached_input_tokens": candidate.get("cached_input_tokens"),
                "uncached_input_tokens": candidate.get("uncached_input_tokens"),
                "cache_ratio": candidate.get("cache_ratio"),
                "user_turns_since_last_compact": candidate.get("user_turns_since_last_compact"),
            }
        )
    return out


def select_session(
    root: Path,
    *,
    limit: int,
    max_age_minutes: int,
    ambiguous_window_minutes: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    scanned = []
    for path in iter_session_files(limit=limit):
        summary = session_summary(path, root)
        if summary:
            scanned.append(summary)

    matching = [s for s in scanned if s.get("cwd_matches_root")]
    matching = [s for s in matching if s.get("last_token_at_dt") is not None]
    matching.sort(key=lambda s: s["last_token_at_dt"], reverse=True)

    if not matching:
        return None, unreliable_report(
            root,
            "unknown",
            "context_budget_unknown_create_next_session_prompt_if_task_is_long",
            "no session with turn_context/session cwd exactly matching root",
            candidates=scanned,
        )

    latest = matching[0]
    now = datetime.now(timezone.utc)
    age_minutes = round((now - latest["last_token_at_dt"].astimezone(timezone.utc)).total_seconds() / 60, 2)
    latest["session_age_minutes"] = age_minutes

    if age_minutes > max_age_minutes:
        return None, unreliable_report(
            root,
            "stale",
            "context_budget_stale_start_or_resume_with_strict_prompt",
            f"latest matching session is stale: {age_minutes} minutes old",
            candidates=matching,
        )

    ambiguous = [
        s
        for s in matching[1:]
        if abs((latest["last_token_at_dt"] - s["last_token_at_dt"]).total_seconds()) <= ambiguous_window_minutes * 60
    ]
    if ambiguous:
        return None, unreliable_report(
            root,
            "ambiguous",
            "context_budget_ambiguous_use_explicit_next_session_prompt",
            f"{len(ambiguous) + 1} matching sessions within {ambiguous_window_minutes} minutes",
            candidates=[latest] + ambiguous,
        )

    latest["session_selected_by"] = "latest_token_count_with_exact_cwd"
    latest["selection_reliable"] = True
    latest["selection_reason"] = "exact cwd match and latest non-stale token_count event"
    latest["candidate_count"] = len(matching)
    latest["candidate_sessions"] = summarize_candidates(matching)
    return latest, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="Repository root")
    ap.add_argument("--lots-done", type=int, default=0, help="Lots executed in the current pass")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--compact", action="store_true", help="Print one compact machine-readable line")
    ap.add_argument("--limit", type=int, default=80, help="Recent session files to inspect")
    ap.add_argument("--max-age-minutes", type=int, default=720, help="Return stale if latest exact-cwd session is older")
    ap.add_argument(
        "--ambiguous-window-minutes",
        type=int,
        default=15,
        help="Return ambiguous if several exact-cwd sessions have token events in this window",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()

    report, unreliable = select_session(
        root,
        limit=max(1, args.limit),
        max_age_minutes=max(1, args.max_age_minutes),
        ambiguous_window_minutes=max(0, args.ambiguous_window_minutes),
    )
    if unreliable is not None:
        result = {**unreliable, "lots_done_current_pass": args.lots_done}
    else:
        assert report is not None
        window = report["context_window"] or DEFAULT_WINDOW
        raw_percent = round((report["last_input_tokens"] / window) * 100, 2) if window else 0
        budget = budget_for(report, raw_percent, args.lots_done)
        result = {
            "root": str(root),
            **{k: v for k, v in report.items() if k != "last_token_at_dt"},
            "context_percent": raw_percent,
            "status": budget["status"],
            "recommended_action": budget["recommended_action"],
            "budget": budget,
            "lots_done_current_pass": args.lots_done,
            "thresholds": BUDGET_THRESHOLDS,
        }

    result["measurement_semantics"] = {
        "context_percent": "last recorded input divided by window; pressure estimate, not a live occupancy probe",
        "cache": "compute reuse measured separately; cached tokens still occupy context",
        "cache_write": "unavailable unless the telemetry producer exposes it",
        "output_and_reasoning": "reported separately; never folded into a synthetic context score",
        "tool_results": "unavailable in token telemetry; bound at capture time",
        "billing": "not calculated; model rates and cache-write accounting are external",
    }
    if args.compact:
        print(compact_report(result))
    elif args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Context budget: {result['status']}")
        print(f"root: {result['root']}")
        print(f"selection_reliable: {result.get('selection_reliable')}")
        print(f"selection_reason: {result.get('selection_reason')}")
        print(f"session_file: {result.get('session_file')}")
        print(f"session_cwd: {result.get('session_cwd')}")
        print(f"last_token_at: {result.get('last_token_at')}")
        print(f"context_pressure: {result['last_input_tokens']}/{result['context_window']} tokens ({result['context_percent']}%)")
        print(f"cached_input_tokens: {result['cached_input_tokens']} ({result['cache_ratio']}%)")
        print(f"uncached_input_tokens: {result['uncached_input_tokens']}")
        if result.get("budget"):
            print(f"budget_rule: {result['budget']['rule']}")
            print(f"budget_signals: {', '.join(result['budget']['signals']) or 'none'}")
        print(f"user_turns_since_last_compact: {result['user_turns_since_last_compact']}")
        print(f"compactions_seen: {result['compactions_seen']}")
        print(f"recommended_action: {result['recommended_action']}")

    status = result["status"]
    if status in VALID_OK_STATUSES:
        return 0
    if status in VALID_RISK_STATUSES:
        return 2
    if status in VALID_UNRELIABLE_STATUSES:
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
