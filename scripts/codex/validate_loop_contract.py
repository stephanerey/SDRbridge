#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

import sr_completion_rules as completion


VALID_TASK_TYPES = {"feature", "bugfix", "upgrade", "realign", "documentation", "analysis", "maintenance", "method"}
VALID_STATUS_DECISIONS = {"done", "user_testing", "repair", "blocked", "not_applicable"}
VALID_CONTEXT_STATUS = {"green", "yellow", "orange", "red", "unknown", "stale", "ambiguous", "not_checked"}
VALID_NEXT_PROMPT = {"created", "updated", "not_required", "missing"}
VALID_TRANSITION_DECISIONS = {
    "continue_current",
    "recommend_new_conversation",
    "stop_for_new_conversation",
    "not_applicable",
}
VALID_RESUME_MODES = {
    "not_required",
    "strict_resume",
    "resume_and_continue",
}
VALID_PLAIN_RESUME_DEFAULTS = {
    "strict_resume",
    "resume_and_continue",
    "not_applicable",
}
VALID_GATE_STATUSES = {"pending", "pass", "fail", "not_applicable"}
VALID_COMPLETION_STATUSES = {"fait", "partiel", "non fait", "bloque", "hors perimetre valide", "requires_e2e"}
BLOCKING_COMPLETION_STATUSES = {"partiel", "non fait", "bloque", "requires_e2e"}
VALID_PROPAGATION_RISK_LEVELS = {"low", "medium", "high", "critical", "not_applicable"}
VALID_PROPAGATION_COMPATIBILITY = {
    "full_propagation",
    "compatibility_shim",
    "two_step_migration",
    "not_required",
}
VALID_PROPAGATION_DECISIONS = {"pass", "repair", "blocked", "not_applicable"}
SUPPORTED_SCHEMA_VERSIONS = {"1.0", "1.1"}


def load_contract(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"missing file: {path}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json: {exc}")
    if not isinstance(data, dict):
        raise ValueError("contract root must be an object")
    return data


def require_object(data: dict, key: str, errors: list[str]) -> dict:
    value = data.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key} must be an object")
        return {}
    return value


def require_list(data: dict, key: str, errors: list[str]) -> list:
    value = data.get(key)
    if not isinstance(value, list):
        errors.append(f"{key} must be a list")
        return []
    return value


def non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_backlog_mutation_gate(data: dict, memory: dict, errors: list[str]) -> None:
    gate = data.get("backlog_mutation_gate")
    if gate is None:
        return
    if not isinstance(gate, dict):
        errors.append("backlog_mutation_gate must be an object")
        return
    status = gate.get("status")
    if status not in VALID_GATE_STATUSES:
        errors.append(f"backlog_mutation_gate.status must be one of {sorted(VALID_GATE_STATUSES)}")
    for key in ("structural_change_detected", "mutation_required", "sr_inbox_updated", "sr_lots_updated"):
        if not isinstance(gate.get(key), bool):
            errors.append(f"backlog_mutation_gate.{key} must be boolean")
    for key in ("affected_lots", "created_lots", "reopened_lots", "blocked_lots", "superseded_lots"):
        if not isinstance(gate.get(key), list):
            errors.append(f"backlog_mutation_gate.{key} must be a list")
    if not non_empty_string(gate.get("decision")):
        errors.append("backlog_mutation_gate.decision must be a non-empty string")
    if gate.get("mutation_required") is True:
        updated = gate.get("sr_inbox_updated") is True or gate.get("sr_lots_updated") is True
        if not updated and not non_empty_string(gate.get("not_updated_reason")):
            errors.append("backlog_mutation_gate.not_updated_reason is required when mutation_required is true and no backlog file was updated")
    if gate.get("sr_lots_updated") is True and memory.get("sr_lots_updated") is not True:
        errors.append("backlog_mutation_gate.sr_lots_updated true requires memory_updates.sr_lots_updated true")


def validate_global_impact_gate(data: dict, errors: list[str]) -> None:
    gate = data.get("global_impact_gate")
    if gate is None:
        return
    if not isinstance(gate, dict):
        errors.append("global_impact_gate must be an object")
        return
    required = gate.get("required")
    if not isinstance(required, bool):
        errors.append("global_impact_gate.required must be boolean")
    status = gate.get("status")
    if status not in VALID_GATE_STATUSES:
        errors.append(f"global_impact_gate.status must be one of {sorted(VALID_GATE_STATUSES)}")
    for key in (
        "surfaces_reviewed",
        "impacted_lots",
        "new_lots_to_create",
        "lots_to_reopen_or_block",
        "assumptions",
        "open_questions",
    ):
        if not isinstance(gate.get(key), list):
            errors.append(f"global_impact_gate.{key} must be a list")
    if not non_empty_string(gate.get("sequencing_recommendation")):
        errors.append("global_impact_gate.sequencing_recommendation must be a non-empty string")
    if required is True:
        if status == "not_applicable":
            errors.append("global_impact_gate.status cannot be not_applicable when required is true")
        if not gate.get("surfaces_reviewed"):
            errors.append("global_impact_gate.surfaces_reviewed must not be empty when required is true")


def validate_lot_completion_gate(data: dict, e2e_items: list, errors: list[str]) -> None:
    gate = data.get("lot_completion_gate")
    if not isinstance(gate, dict):
        errors.append("lot_completion_gate must be an object")
        return
    status = gate.get("status")
    if status not in VALID_GATE_STATUSES:
        errors.append(f"lot_completion_gate.status must be one of {sorted(VALID_GATE_STATUSES)}")
    if "validated_scope_source" in gate and not non_empty_string(gate.get("validated_scope_source")):
        errors.append("lot_completion_gate.validated_scope_source must be a non-empty string when present")
    for key in ("scope_reduction_requested", "scope_reduction_validated_by_user", "ui_ux_required"):
        if key in gate and not isinstance(gate.get(key), bool):
            errors.append(f"lot_completion_gate.{key} must be boolean")
    if gate.get("scope_reduction_requested") is True and gate.get("scope_reduction_validated_by_user") is not True:
        errors.append("lot_completion_gate scope reduction requires explicit user validation")

    coverage_table = gate.get("coverage_table")
    if not isinstance(coverage_table, list):
        errors.append("lot_completion_gate.coverage_table must be a list")
        coverage_table = []
    for index, row in enumerate(coverage_table):
        prefix = f"lot_completion_gate.coverage_table[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if not non_empty_string(row.get("requirement_id")):
            errors.append(f"{prefix}.requirement_id must be a non-empty string")
        if not non_empty_string(row.get("requirement")):
            errors.append(f"{prefix}.requirement must be a non-empty string")
        if row.get("status") not in VALID_COMPLETION_STATUSES:
            errors.append(f"{prefix}.status must be one of {sorted(VALID_COMPLETION_STATUSES)}")
        if not isinstance(row.get("proof"), list):
            errors.append(f"{prefix}.proof must be a list")
        if "comment" in row and not isinstance(row.get("comment"), str):
            errors.append(f"{prefix}.comment must be a string when present")

    visual_evidence = gate.get("visual_evidence")
    if not isinstance(visual_evidence, list):
        errors.append("lot_completion_gate.visual_evidence must be a list")
        visual_evidence = []
    decision = gate.get("decision")
    if decision not in VALID_STATUS_DECISIONS:
        errors.append(f"lot_completion_gate.decision must be one of {sorted(VALID_STATUS_DECISIONS)}")

    status_decision = data.get("status_decision")
    if decision in VALID_STATUS_DECISIONS and status_decision in VALID_STATUS_DECISIONS and decision != status_decision:
        errors.append(
            f"lot_completion_gate.decision {decision!r} contradicts status_decision {status_decision!r}"
        )
    incomplete_rows = [
        row.get("requirement_id", f"#{index}")
        for index, row in enumerate(coverage_table)
        if isinstance(row, dict) and row.get("status") in {"partiel", "non fait", "bloque"}
    ]
    if status_decision == "user_testing" and incomplete_rows:
        errors.append(
            "status_decision user_testing is incompatible with partial, missing or blocked implementation rows; "
            f"use repair or blocked: {incomplete_rows}"
        )
    if status_decision == "user_testing" and status not in {"pending", "pass"}:
        errors.append(
            f"status_decision user_testing requires lot_completion_gate.status pending or pass, not {status!r}"
        )
    if status_decision == "repair" and status != "fail":
        errors.append("status_decision repair requires lot_completion_gate.status fail")

    if data.get("status_decision") == "done":
        if status != "pass":
            errors.append("status_decision done requires lot_completion_gate.status pass")
        if not coverage_table:
            errors.append("status_decision done requires lot_completion_gate.coverage_table")
        blocking_rows = [
            row.get("requirement_id", f"#{index}")
            for index, row in enumerate(coverage_table)
            if isinstance(row, dict) and row.get("status") in BLOCKING_COMPLETION_STATUSES
        ]
        if blocking_rows:
            errors.append(f"status_decision done is incompatible with incomplete lot_completion_gate rows: {blocking_rows}")
        if gate.get("ui_ux_required") is True and not visual_evidence and not e2e_items:
            errors.append("status_decision done with UI/UX requirements requires lot_completion_gate.visual_evidence or e2e_user_tests.items")


def validate_propagation_gate(data: dict, errors: list[str], warnings: list[str]) -> None:
    gate = data.get("propagation_gate")
    if gate is None:
        warnings.append("propagation_gate missing; accepted as legacy contract")
        return
    if not isinstance(gate, dict):
        errors.append("propagation_gate must be an object")
        return

    required = gate.get("required")
    if not isinstance(required, bool):
        errors.append("propagation_gate.required must be boolean")
        required = False
    status = gate.get("status")
    if status not in VALID_GATE_STATUSES:
        errors.append(f"propagation_gate.status must be one of {sorted(VALID_GATE_STATUSES)}")
    risk_level = gate.get("risk_level")
    if risk_level not in VALID_PROPAGATION_RISK_LEVELS:
        errors.append(f"propagation_gate.risk_level must be one of {sorted(VALID_PROPAGATION_RISK_LEVELS)}")
    compatibility = gate.get("compatibility_strategy")
    if compatibility not in VALID_PROPAGATION_COMPATIBILITY:
        errors.append(f"propagation_gate.compatibility_strategy must be one of {sorted(VALID_PROPAGATION_COMPATIBILITY)}")
    decision = gate.get("decision")
    if decision not in VALID_PROPAGATION_DECISIONS:
        errors.append(f"propagation_gate.decision must be one of {sorted(VALID_PROPAGATION_DECISIONS)}")
    for key in ("preflight_done", "human_validation_required", "human_validation_received"):
        if not isinstance(gate.get(key), bool):
            errors.append(f"propagation_gate.{key} must be boolean")
    for key in (
        "changed_symbols",
        "affected_surfaces",
        "consumers_identified",
        "reference_searches",
        "remaining_references",
        "ignored_references",
        "verification",
    ):
        if not isinstance(gate.get(key), list):
            errors.append(f"propagation_gate.{key} must be a list")

    if required is True and status == "not_applicable":
        errors.append("propagation_gate.status cannot be not_applicable when required is true")
    if required is not True:
        return

    is_done_or_pass = data.get("status_decision") == "done" or status == "pass" or decision == "pass"
    if not is_done_or_pass:
        return

    if status != "pass":
        errors.append("status_decision done requires propagation_gate.status pass when propagation is required")
    if decision != "pass":
        errors.append("status_decision done requires propagation_gate.decision pass when propagation is required")
    if gate.get("preflight_done") is not True:
        errors.append("propagation_gate.preflight_done must be true when propagation is required")
    if gate.get("human_validation_required") is True and gate.get("human_validation_received") is not True:
        errors.append("propagation_gate human validation required but not received")
    if not gate.get("changed_symbols"):
        errors.append("propagation_gate.changed_symbols must not be empty when propagation is required")
    if not gate.get("reference_searches"):
        errors.append("propagation_gate.reference_searches must not be empty when propagation is required")
    if gate.get("remaining_references") and not gate.get("ignored_references"):
        errors.append("propagation_gate.remaining_references require ignored_references justification")
    if risk_level in {"high", "critical"}:
        if not gate.get("affected_surfaces"):
            errors.append("high/critical propagation requires propagation_gate.affected_surfaces")
        if not gate.get("consumers_identified"):
            errors.append("high/critical propagation requires propagation_gate.consumers_identified")
        if not gate.get("verification"):
            errors.append("high/critical propagation requires propagation_gate.verification")


def validate_requirement_registry(
    data: dict, errors: list[str], warnings: list[str], contract_path: Path | None
) -> None:
    registry = require_object(data, "requirement_registry", errors)
    if not registry:
        return
    sr_contract_path = registry.get("sr_contract_path")
    if sr_contract_path is not None and not non_empty_string(sr_contract_path):
        errors.append("requirement_registry.sr_contract_path must be null or a non-empty string")
    for key in ("open_requirement_ids", "reopened_lot_ids", "user_feedback"):
        values = registry.get(key)
        if not isinstance(values, list) or not all(non_empty_string(item) for item in values):
            errors.append(f"requirement_registry.{key} must contain only non-empty strings")
    if not non_empty_string(registry.get("next_coherent_scope")):
        errors.append("requirement_registry.next_coherent_scope must be a non-empty string")
    if sr_contract_path is None:
        if data.get("status_decision") != "not_applicable":
            errors.append("requirement_registry.sr_contract_path is required for an active loop contract")
        return
    if contract_path is None:
        warnings.append("requirement_registry inheritance was not checked because contract_path is unavailable")
        return
    linked_path = (contract_path.parent / sr_contract_path).resolve()
    try:
        linked = load_contract(linked_path)
    except ValueError as exc:
        errors.append(f"requirement_registry.sr_contract_path cannot be loaded: {exc}")
        return
    requests = linked.get("validated_requests")
    if linked.get("schema_version") != "3.1.0" or not isinstance(requests, list):
        errors.append("requirement_registry.sr_contract_path must reference a 3.1.0 SR contract")
        return
    expected_open = completion.open_requirement_ids(requests)
    if registry.get("open_requirement_ids") != expected_open:
        errors.append(f"requirement_registry.open_requirement_ids must equal SR contract open requirements {expected_open!r}")
    linked_status = completion.derive_contract_decision(requests)
    if data.get("status_decision") != linked_status:
        errors.append(
            f"status_decision {data.get('status_decision')!r} contradicts linked SR contract derived status {linked_status!r}"
        )


def validate(data: dict, contract_path: Path | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for key in (
        "schema_version",
        "task_id",
        "task_type",
        "status_decision",
        "evidence_gate",
        "lot_completion_gate",
        "implementation",
        "verification",
        "e2e_user_tests",
        "memory_updates",
        "context_budget",
        "conversation_transition",
        "resume_protocol",
    ):
        if key not in data:
            errors.append(f"missing required key: {key}")

    if data.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(f"schema_version must be one of {sorted(SUPPORTED_SCHEMA_VERSIONS)}")
    elif data.get("schema_version") == "1.1":
        if "requirement_registry" not in data:
            errors.append("missing required key: requirement_registry")
        else:
            validate_requirement_registry(data, errors, warnings, contract_path)

    task_type = data.get("task_type")
    if task_type not in VALID_TASK_TYPES:
        errors.append(f"task_type must be one of {sorted(VALID_TASK_TYPES)}")

    status_decision = data.get("status_decision")
    if status_decision not in VALID_STATUS_DECISIONS:
        errors.append(f"status_decision must be one of {sorted(VALID_STATUS_DECISIONS)}")

    evidence = require_object(data, "evidence_gate", errors)
    sources_read = require_list(evidence, "sources_read", errors) if evidence else []
    if evidence and evidence.get("done") is not True:
        errors.append("evidence_gate.done must be true for non-trivial tasks")
    if evidence and not sources_read and task_type not in {"upgrade", "documentation"}:
        errors.append("evidence_gate.sources_read must not be empty")

    implementation = require_object(data, "implementation", errors)
    changed_files = require_list(implementation, "changed_files", errors) if implementation else []
    app_code_changed = implementation.get("app_code_changed") if implementation else None
    if app_code_changed is not None and not isinstance(app_code_changed, bool):
        errors.append("implementation.app_code_changed must be boolean")
    if app_code_changed and not changed_files:
        errors.append("implementation.changed_files must not be empty when app_code_changed is true")
    if task_type == "upgrade" and app_code_changed:
        errors.append("task_type upgrade must not change app code")

    verification = require_object(data, "verification", errors)
    commands_run = require_list(verification, "commands_run", errors) if verification else []
    commands_failed = require_list(verification, "commands_failed", errors) if verification else []
    not_run_reason = verification.get("not_run_reason") if verification else None
    if app_code_changed and not commands_run and not not_run_reason:
        errors.append("verification.commands_run or verification.not_run_reason is required when app code changed")
    if status_decision == "done" and commands_failed and not not_run_reason:
        errors.append("status_decision done requires failed commands to be justified")

    e2e = require_object(data, "e2e_user_tests", errors)
    e2e_items = require_list(e2e, "items", errors) if e2e else []
    e2e_required = e2e.get("required") if e2e else None
    if e2e_required is not None and not isinstance(e2e_required, bool):
        errors.append("e2e_user_tests.required must be boolean")
    if (status_decision == "user_testing" or e2e_required is True) and not e2e_items:
        errors.append("e2e_user_tests.items must not be empty when user testing is required")
    validate_lot_completion_gate(data, e2e_items, errors)
    validate_propagation_gate(data, errors, warnings)

    memory = require_object(data, "memory_updates", errors)
    if memory:
        for key in ("sr_lots_updated", "current_state_updated", "task_memory_updated", "gate_report_updated"):
            if key in memory and not isinstance(memory[key], bool):
                errors.append(f"memory_updates.{key} must be boolean")
        if memory.get("task_memory_updated") is not True:
            errors.append("memory_updates.task_memory_updated must be true for non-trivial tasks")
        if (
            task_type in {"upgrade", "realign"}
            and status_decision in {"done", "user_testing"}
            and memory.get("current_state_updated") is not True
        ):
            errors.append("task_type upgrade/realign requires memory_updates.current_state_updated true")
        if memory.get("gate_report_updated") is not True and task_type not in {"analysis"}:
            warnings.append("memory_updates.gate_report_updated is false")

    validate_backlog_mutation_gate(data, memory, errors)
    validate_global_impact_gate(data, errors)
    backlog_gate = data.get("backlog_mutation_gate")
    impact_gate = data.get("global_impact_gate")
    if isinstance(backlog_gate, dict) and isinstance(impact_gate, dict):
        if backlog_gate.get("structural_change_detected") is True and impact_gate.get("required") is not True:
            errors.append("structural backlog changes require global_impact_gate.required true")

    context = require_object(data, "context_budget", errors)
    context_status = None
    next_prompt = None
    if context:
        if context.get("checked") is not True:
            errors.append("context_budget.checked must be true")
        context_status = context.get("status")
        if context_status not in VALID_CONTEXT_STATUS:
            errors.append(f"context_budget.status must be one of {sorted(VALID_CONTEXT_STATUS)}")
        next_prompt = context.get("next_session_prompt")
        if next_prompt not in VALID_NEXT_PROMPT:
            errors.append(f"context_budget.next_session_prompt must be one of {sorted(VALID_NEXT_PROMPT)}")
        if context_status in {"orange", "red", "stale", "ambiguous"} and next_prompt not in {"created", "updated"}:
            errors.append("orange/red/stale/ambiguous context requires next_session_prompt created or updated")

    transition = require_object(data, "conversation_transition", errors)
    if transition:
        decision = transition.get("decision")
        if decision not in VALID_TRANSITION_DECISIONS:
            errors.append(f"conversation_transition.decision must be one of {sorted(VALID_TRANSITION_DECISIONS)}")
        reason = transition.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append("conversation_transition.reason must be a non-empty string")
        path = transition.get("next_session_prompt_path")
        if path is not None and (not isinstance(path, str) or not path.strip()):
            errors.append("conversation_transition.next_session_prompt_path must be null or a non-empty string")
        user_message_required = transition.get("user_message_required")
        if user_message_required is not None and not isinstance(user_message_required, bool):
            errors.append("conversation_transition.user_message_required must be boolean")

        if context_status in {"orange", "red", "stale", "ambiguous"} and decision != "stop_for_new_conversation":
            errors.append("orange/red/stale/ambiguous context requires conversation_transition.decision stop_for_new_conversation")
        if context_status == "yellow" and decision == "continue_current":
            warnings.append("yellow context should usually recommend a new conversation before a long next task")
        if next_prompt in {"created", "updated"} and not path:
            errors.append("conversation_transition.next_session_prompt_path is required when next_session_prompt is created or updated")
        if decision in {"recommend_new_conversation", "stop_for_new_conversation"} and next_prompt not in {"created", "updated"}:
            errors.append("new conversation decisions require next_session_prompt created or updated")
        if decision == "stop_for_new_conversation" and user_message_required is not True:
            errors.append("stop_for_new_conversation requires conversation_transition.user_message_required true")

    resume = require_object(data, "resume_protocol", errors)
    if resume:
        required = resume.get("required")
        if not isinstance(required, bool):
            errors.append("resume_protocol.required must be boolean")
        mode = resume.get("mode")
        if mode not in VALID_RESUME_MODES:
            errors.append(f"resume_protocol.mode must be one of {sorted(VALID_RESUME_MODES)}")
        next_user_prompt = resume.get("next_user_prompt")
        if next_user_prompt is not None and (not isinstance(next_user_prompt, str) or not next_user_prompt.strip()):
            errors.append("resume_protocol.next_user_prompt must be null or a non-empty string")
        plain_resume_default = resume.get("default_on_plain_resume")
        if plain_resume_default not in VALID_PLAIN_RESUME_DEFAULTS:
            errors.append(f"resume_protocol.default_on_plain_resume must be one of {sorted(VALID_PLAIN_RESUME_DEFAULTS)}")
        must_not_code = resume.get("must_not_code_before_user_validation")
        if must_not_code is not None and not isinstance(must_not_code, bool):
            errors.append("resume_protocol.must_not_code_before_user_validation must be boolean")

        if decision in {"recommend_new_conversation", "stop_for_new_conversation"}:
            if required is not True:
                errors.append("new conversation decisions require resume_protocol.required true")
            if mode not in {"strict_resume", "resume_and_continue"}:
                errors.append("new conversation decisions require resume_protocol.mode strict_resume or resume_and_continue")
            if not next_user_prompt:
                errors.append("new conversation decisions require resume_protocol.next_user_prompt")
            if plain_resume_default != "strict_resume":
                errors.append("new conversation decisions require default_on_plain_resume strict_resume")
        if decision == "stop_for_new_conversation":
            if mode != "strict_resume":
                errors.append("stop_for_new_conversation requires resume_protocol.mode strict_resume")
            if must_not_code is not True:
                errors.append("stop_for_new_conversation requires must_not_code_before_user_validation true")
        if mode == "strict_resume" and next_user_prompt:
            lowered = next_user_prompt.lower()
            if "ne code pas" not in lowered and "attends" not in lowered:
                warnings.append("strict resume prompt should explicitly say not to code or to wait for validation")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a SR loop contract JSON file.")
    parser.add_argument("--file", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    path = Path(args.file)
    try:
        data = load_contract(path)
        errors, warnings = validate(data, contract_path=path)
    except ValueError as exc:
        errors, warnings = [str(exc)], []

    result = {"file": str(path), "ok": not errors, "errors": errors, "warnings": warnings}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"SR loop contract: {path}")
        if errors:
            print("Errors:")
            for item in errors:
                print(f"- {item}")
        if warnings:
            print("Warnings:")
            for item in warnings:
                print(f"- {item}")
        if not errors:
            print("OK: SR loop contract passed")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
