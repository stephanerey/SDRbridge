#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from validate_pass_contract import load_lots, load_yaml, validate_passes
except Exception as exc:  # pragma: no cover - import failure is reported in main.
    load_lots = None
    load_yaml = None
    validate_passes = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


DEFAULT_MAX_GOAL_COMMAND_CHARS = 1000
DEFAULT_HARD_LIMIT = 4000
EXECUTABLE_STATUSES = {"validated", "in_progress", "repair", "reopened"}
PLANNING_STATUSES = {"planned"}
FINAL_STATUS_RULES = {
    "done": "Aucune validation/E2E utilisateur restante, tous les gates requis passent.",
    "user_testing": "La passe est techniquement prete et attend les E2E ou la validation utilisateur.",
    "repair": "Une couverture, verification ou exigence reste incomplete mais reparable.",
    "blocked": "Une stop condition SR bloque la suite.",
}


def relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_list(value) -> list:
    return value if isinstance(value, list) else []


def find_pass(passes: list, pass_id: str) -> dict:
    matches = [item for item in passes if isinstance(item, dict) and item.get("pass_id") == pass_id]
    if not matches:
        raise ValueError(f"pass_id {pass_id!r} not found")
    if len(matches) > 1:
        raise ValueError(f"pass_id {pass_id!r} is duplicated")
    return matches[0]


def validate_goal_command(command: str, max_chars: int, hard_limit: int) -> list[str]:
    errors = []
    length = len(command)
    if length > hard_limit:
        errors.append(f"goal command length {length} exceeds hard_limit {hard_limit}")
    if length > max_chars:
        errors.append(f"goal command length {length} exceeds max_goal_command_chars {max_chars}")
    return errors


def build_goal_command(pass_id: str, output_rel: str, max_chars: int, hard_limit: int) -> str:
    candidates = [
        (
            f"/goal Executer la passe {pass_id} selon {output_rel}. "
            "Stopper uniquement sur les stop conditions SR. "
            "Ne pas declarer termine avant Pass Completion Gate."
        ),
        f"/goal Executer {pass_id} selon {output_rel}. Fin = Pass Completion Gate SR.",
        f"/goal Executer {pass_id}; source {output_rel}.",
    ]
    for command in candidates:
        if not validate_goal_command(command, max_chars, hard_limit):
            return command
    raise ValueError("; ".join(validate_goal_command(candidates[-1], max_chars, hard_limit)))


def lot_section(lot_id: str, lot: dict | None) -> str:
    if not lot:
        return f"### {lot_id}\n\n- status: unknown\n- objective: lot absent de SR_LOTS.yaml\n"
    lines = [
        f"### {lot_id}",
        "",
        f"- title: {lot.get('title', '')}",
        f"- status: {lot.get('status', '')}",
        f"- objective: {lot.get('objective', '')}",
        f"- validated_request_ids: {as_list(lot.get('validated_request_ids'))}",
        f"- depends_on: {as_list(lot.get('depends_on'))}",
        "",
        "Acceptance criteria:",
    ]
    criteria = as_list(lot.get("acceptance_criteria"))
    lines.extend(f"- {item}" for item in criteria) if criteria else lines.append("- none declared")
    lines.append("")
    lines.append("Verification commands:")
    commands = as_list(lot.get("verification_commands"))
    lines.extend(f"- `{item}`" for item in commands) if commands else lines.append("- none declared")
    lines.append("")
    lines.append("Stop conditions:")
    stops = as_list(lot.get("stop_conditions"))
    lines.extend(f"- {item}" for item in stops) if stops else lines.append("- inherit pass stop conditions")
    return "\n".join(lines)


def build_goal_markdown(
    pass_item: dict,
    lots_by_id: dict[str, dict],
    passes_file: str,
    lots_file: str,
    max_chars: int,
    hard_limit: int,
    command: str,
) -> str:
    pass_id = pass_item["pass_id"]
    lots = as_list(pass_item.get("lots"))
    e2e = pass_item.get("e2e_strategy") if isinstance(pass_item.get("e2e_strategy"), dict) else {}
    preflight = pass_item.get("preflight") if isinstance(pass_item.get("preflight"), dict) else {}
    now = datetime.now(timezone.utc).isoformat()
    sections = [
        "# Pass Runtime Goal",
        "",
        f"- generated_at: {now}",
        f"- pass_id: {pass_id}",
        f"- pass_status: {pass_item.get('status')}",
        f"- source_passes: `{passes_file}`",
        f"- source_lots: `{lots_file}`",
        f"- max_goal_command_chars: {max_chars}",
        f"- hard_limit: {hard_limit}",
        f"- goal_command_chars: {len(command)}",
        "",
        "## Goal Command",
        "",
        "```text",
        command,
        "```",
        "",
        "## Objective",
        "",
        f"Executer la passe `{pass_id}` selon les sources SR. Le goal est un artefact runtime derive; il ne remplace jamais `SR_PASSES.yaml`, `SR_LOTS.yaml` ou les `sr_contract.json` des lots.",
        "",
        "## Execution Order",
        "",
    ]
    sections.extend(f"{index}. `{lot_id}`" for index, lot_id in enumerate(lots, start=1))
    sections.extend(
        [
            "",
            "## Lots",
            "",
            "\n\n".join(lot_section(lot_id, lots_by_id.get(lot_id)) for lot_id in lots),
            "",
            "## Preflight",
            "",
        ]
    )
    for key in (
        "required_before_start",
        "secrets_required",
        "external_actions_required",
        "human_validation_required",
        "migrations_required",
        "open_questions",
    ):
        items = as_list(preflight.get(key))
        sections.append(f"### {key}")
        sections.extend(f"- {item}" for item in items) if items else sections.append("- none")
        sections.append("")
    sections.extend(
        [
            "## E2E Strategy",
            "",
            f"- mode: {e2e.get('mode')}",
            "",
        ]
    )
    for item in as_list(e2e.get("items")):
        sections.append(f"- {item}")
    if e2e.get("mode") == "grouped_at_pass_end":
        sections.extend(
            [
                "",
                "Codex ne doit pas demander d'E2E utilisateur apres chaque lot. Les preuves automatisees sont accumulees par lot, puis une checklist E2E groupee est produite a la fin de la passe.",
            ]
        )
    sections.extend(
        [
            "",
            "## Pass Completion Gate",
            "",
            "La passe atteint son statut SR final correct, pas necessairement `done`, quand Codex produit une table de couverture de passe et met a jour les fichiers SR requis.",
            "",
        ]
    )
    for status, rule in FINAL_STATUS_RULES.items():
        sections.append(f"- `{status}`: {rule}")
    sections.extend(
        [
            "",
            "`done` est interdit si des E2E utilisateur ou une validation humaine restent requis. Dans ce cas, la sortie correcte est `user_testing` avec checklist E2E concrete.",
            "",
            "## Stop Conditions",
            "",
        ]
    )
    stop_on = as_list(pass_item.get("stop_on"))
    sections.extend(f"- {item}" for item in stop_on) if stop_on else sections.append("- inherit SR stop conditions")
    sections.extend(
        [
            "- nouvelle validation humaine requise",
            "- dependance invalide ou non satisfaite",
            "- secret, action externe ou migration non disponible/non valide",
            "- risque high/critical non valide",
            "- gate rouge sans reparation defendable",
            "- budget contexte a risque sans prompt de reprise",
            "",
            "## Non Regression Rules",
            "",
            "- Ne pas elargir ni reduire silencieusement le scope valide.",
            "- Charger tous les requirement_id ouverts des contrats parents et les conserver jusqu'a leur decision finale.",
            "- Un retour sur une exigence existante rouvre le lot d'origine; ne pas creer un micro-lot par defaut.",
            "- `user_testing` exige que toutes les implementations techniques soient completes; sinon utiliser `repair`.",
            "- Ne pas executer une passe `proposed`.",
            "- Ne pas enchainer une passe suivante sans validation utilisateur explicite.",
            "- Valider `SR_PASSES.yaml` avec `validate_pass_contract.py` avant et apres execution si la passe est utilisee ou modifiee.",
        ]
    )
    return "\n".join(sections).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a bounded Codex /goal command and pass_runtime_goal.md for a SR pass.")
    parser.add_argument("--root", default=".", help="Project root")
    parser.add_argument("--pass-id", required=True, help="Pass identifier from SR_PASSES.yaml")
    parser.add_argument("--passes-file", default="docs/codex/SR_PASSES.yaml")
    parser.add_argument("--lots-file", default="docs/codex/SR_LOTS.yaml")
    parser.add_argument("--output", required=True, help="Output pass_runtime_goal.md path")
    parser.add_argument("--max-goal-command-chars", type=int, default=DEFAULT_MAX_GOAL_COMMAND_CHARS)
    parser.add_argument("--hard-limit", type=int, default=DEFAULT_HARD_LIMIT)
    parser.add_argument("--allow-planned", action="store_true", help="Allow planned passes for dry-run goal preparation")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if IMPORT_ERROR is not None:
        print(f"Pass runtime goal errors:\n- validator import failed: {IMPORT_ERROR}", file=sys.stderr)
        return 1
    if args.max_goal_command_chars <= 0 or args.hard_limit <= 0:
        print("Pass runtime goal errors:\n- limits must be positive", file=sys.stderr)
        return 1
    if args.max_goal_command_chars > args.hard_limit:
        print("Pass runtime goal errors:\n- max_goal_command_chars must be <= hard_limit", file=sys.stderr)
        return 1

    root = Path(args.root).resolve()
    passes_path = root / args.passes_file
    lots_path = root / args.lots_file
    output_path = root / args.output
    errors: list[str] = []

    try:
        passes_data = load_yaml(passes_path)
        lots_by_id = load_lots(lots_path)
        passes = passes_data.get("passes")
        if not isinstance(passes, list) or not passes:
            raise ValueError("SR_PASSES.yaml must contain a non-empty passes list")
        pass_errors = validate_passes(passes, lots_by_id)
        if pass_errors:
            errors.extend(pass_errors)
        pass_item = find_pass(passes, args.pass_id)
        status = pass_item.get("status")
        allowed_statuses = set(EXECUTABLE_STATUSES)
        if args.allow_planned:
            allowed_statuses |= PLANNING_STATUSES
        if status not in allowed_statuses:
            errors.append(
                f"pass {args.pass_id!r} status {status!r} is not allowed for runtime goal "
                f"(allowed: {sorted(allowed_statuses)})"
            )
        output_rel = relpath(output_path, root)
        command = build_goal_command(args.pass_id, output_rel, args.max_goal_command_chars, args.hard_limit)
        errors.extend(validate_goal_command(command, args.max_goal_command_chars, args.hard_limit))
        if not errors:
            markdown = build_goal_markdown(
                pass_item,
                lots_by_id,
                args.passes_file,
                args.lots_file,
                args.max_goal_command_chars,
                args.hard_limit,
                command,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown, encoding="utf-8")
    except Exception as exc:
        errors.append(str(exc))
        command = ""

    result = {
        "ok": not errors,
        "pass_id": args.pass_id,
        "output": relpath(output_path, root),
        "goal_command": command,
        "goal_command_chars": len(command),
        "max_goal_command_chars": args.max_goal_command_chars,
        "hard_limit": args.hard_limit,
        "errors": errors,
    }
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif errors:
        print("Pass runtime goal errors:")
        for error in errors:
            print(f"- {error}")
    else:
        print(f"OK: pass runtime goal written to {result['output']}")
        print(f"goal_command_chars: {result['goal_command_chars']}")
        print(result["goal_command"])
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
