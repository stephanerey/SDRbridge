#!/usr/bin/env python3
"""Validate SR living task contracts (legacy 3.0.0 and strict 3.1.0)."""
import argparse
import json
import re
import sys
from pathlib import Path

import sr_completion_rules as completion


SCHEMA_VERSION = "3.1.0"
SUPPORTED_SCHEMA_VERSIONS = {"3.0.0", SCHEMA_VERSION}
VALID_TASK_TYPES = {"feature", "bugfix", "upgrade", "realign", "documentation", "analysis", "maintenance", "method"}
VALID_STATUSES = {"planned", "doing", "user_testing", "repair", "done", "blocked", "cancelled"}
VALID_REQUEST_STATUSES = {"todo", "doing", "done", "requires_e2e", "blocked", "moved_to_new_lot", "cancelled"}
VALID_GATE_STATUSES = {"pending", "pass", "fail", "not_applicable"}
VALID_COMPLETION_STATUSES = {"fait", "partiel", "non fait", "bloque", "hors perimetre valide", "requires_e2e"}
BLOCKING_COMPLETION_STATUSES = {"partiel", "non fait", "bloque", "requires_e2e"}
VALID_CONTEXT_STATUSES = {"green", "yellow", "orange", "red", "unknown", "stale", "ambiguous", "not_checked"}
VALID_TRANSITIONS = {"continue_current", "recommend_new_conversation", "stop_for_new_conversation", "not_applicable"}
VALID_PROPAGATION_RISK_LEVELS = {"low", "medium", "high", "critical", "not_applicable"}
VALID_PROPAGATION_COMPATIBILITY = {
    "full_propagation",
    "compatibility_shim",
    "two_step_migration",
    "not_required",
}
VALID_PROPAGATION_DECISIONS = {"pass", "repair", "blocked", "not_applicable"}
VALID_UI_READINESS_STATUSES = {"pending", "pass", "fail", "blocked", "not_applicable"}
VALID_UI_VISUAL_STATUSES = {"pending", "pass", "repair", "blocked", "not_applicable"}
VALID_REQUIREMENT_TYPES = {
    "product",
    "ui",
    "ui_ux",
    "ux",
    "technical",
    "security",
    "exclusion",
    "acceptance",
    "documentation",
    "method",
    "other",
}
VALID_SOURCE_KINDS = {"user_validation", "user_feedback", "contract", "handoff", "migration", "other"}
COMPLETION_WORDS = re.compile(
    r"\b(termin(?:e|ee|ees|es|é|ée|ées|és)|complet(?:e|es)?|livr(?:e|ee|ees|es|é|ée|ées|és)|"
    r"impl[eé]ment(?:e|ee|ees|es|é|ée|ées|és)|implemented|delivered|finished|done)\b",
    re.IGNORECASE,
)
QUALIFICATION_WORDS = re.compile(
    r"\b(non|pas|incomplet(?:e|es)?|partiel(?:le|les)?|reste|restent|en attente|"
    r"techniquement complet(?:e|es)?|preuve(?:s)? manquante(?:s)?|a reparer|à réparer)\b",
    re.IGNORECASE,
)


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


def validate_backlog_mutation(data: dict, errors: list[str]) -> dict:
    mutation = data.get("backlog_mutation")
    if mutation is None:
        return {}
    if not isinstance(mutation, dict):
        errors.append("backlog_mutation must be an object")
        return {}
    status = mutation.get("status")
    if status not in VALID_GATE_STATUSES:
        errors.append(f"backlog_mutation.status must be one of {sorted(VALID_GATE_STATUSES)}")
    for key in ("structural_change_detected", "mutation_required", "sr_inbox_updated", "sr_lots_updated"):
        if not isinstance(mutation.get(key), bool):
            errors.append(f"backlog_mutation.{key} must be boolean")
    for key in ("affected_lots", "created_lots", "reopened_lots", "blocked_lots", "superseded_lots"):
        if not isinstance(mutation.get(key), list):
            errors.append(f"backlog_mutation.{key} must be a list")
    if not non_empty_string(mutation.get("decision")):
        errors.append("backlog_mutation.decision must be a non-empty string")
    if mutation.get("mutation_required") is True:
        updated = mutation.get("sr_inbox_updated") is True or mutation.get("sr_lots_updated") is True
        if not updated and not non_empty_string(mutation.get("not_updated_reason")):
            errors.append("backlog_mutation.not_updated_reason is required when mutation_required is true and no backlog file was updated")
    return mutation


def validate_global_impact(data: dict, errors: list[str]) -> dict:
    impact = data.get("global_impact")
    if impact is None:
        return {}
    if not isinstance(impact, dict):
        errors.append("global_impact must be an object")
        return {}
    required = impact.get("required")
    if not isinstance(required, bool):
        errors.append("global_impact.required must be boolean")
    status = impact.get("status")
    if status not in VALID_GATE_STATUSES:
        errors.append(f"global_impact.status must be one of {sorted(VALID_GATE_STATUSES)}")
    for key in (
        "surfaces_reviewed",
        "impacted_lots",
        "new_lots_to_create",
        "lots_to_reopen_or_block",
        "assumptions",
        "open_questions",
    ):
        if not isinstance(impact.get(key), list):
            errors.append(f"global_impact.{key} must be a list")
    if not non_empty_string(impact.get("sequencing_recommendation")):
        errors.append("global_impact.sequencing_recommendation must be a non-empty string")
    if required is True:
        if status == "not_applicable":
            errors.append("global_impact.status cannot be not_applicable when required is true")
        if not impact.get("surfaces_reviewed"):
            errors.append("global_impact.surfaces_reviewed must not be empty when required is true")
    return impact


def validate_requests(data: dict, errors: list[str]) -> list:
    requests = require_list(data, "validated_requests", errors)
    seen = set()
    for index, request in enumerate(requests):
        prefix = f"validated_requests[{index}]"
        if not isinstance(request, dict):
            errors.append(f"{prefix} must be an object")
            continue
        request_id = request.get("id")
        if not non_empty_string(request_id):
            errors.append(f"{prefix}.id must be a non-empty string")
        elif request_id in seen:
            errors.append(f"{prefix}.id is duplicated: {request_id}")
        else:
            seen.add(request_id)
        if request.get("status") not in VALID_REQUEST_STATUSES:
            errors.append(f"{prefix}.status must be one of {sorted(VALID_REQUEST_STATUSES)}")
        if "requirement_type" in request and not non_empty_string(request.get("requirement_type")):
            errors.append(f"{prefix}.requirement_type must be a non-empty string when present")
        for key in ("source", "coverage"):
            if not non_empty_string(request.get(key)):
                errors.append(f"{prefix}.{key} must be a non-empty string")
        for key in ("files", "verification"):
            value = request.get(key)
            if not isinstance(value, list):
                errors.append(f"{prefix}.{key} must be a list")
        if "notes" in request and not isinstance(request["notes"], list):
            errors.append(f"{prefix}.notes must be a list when present")
    return requests


def _validate_string_list(value: object, path: str, errors: list[str]) -> list:
    if not isinstance(value, list):
        errors.append(f"{path} must be a list")
        return []
    if not all(non_empty_string(item) for item in value):
        errors.append(f"{path} must contain only non-empty strings")
    return value


def validate_requests_v31(data: dict, errors: list[str]) -> list:
    requests = require_list(data, "validated_requests", errors)
    seen: set[str] = set()
    for index, request in enumerate(requests):
        prefix = f"validated_requests[{index}]"
        if not isinstance(request, dict):
            errors.append(f"{prefix} must be an object")
            continue
        request_id = request.get("id")
        if not non_empty_string(request_id):
            errors.append(f"{prefix}.id must be a non-empty stable identifier")
        elif request_id in seen:
            errors.append(f"{prefix}.id is duplicated: {request_id}")
        else:
            seen.add(request_id)

        source = request.get("source")
        if not isinstance(source, dict):
            errors.append(f"{prefix}.source must be an object")
        else:
            if source.get("kind") not in VALID_SOURCE_KINDS:
                errors.append(f"{prefix}.source.kind must be one of {sorted(VALID_SOURCE_KINDS)}")
            if not non_empty_string(source.get("reference")):
                errors.append(f"{prefix}.source.reference must be a non-empty string")
        if request.get("requirement_type") not in VALID_REQUIREMENT_TYPES:
            errors.append(f"{prefix}.requirement_type must be one of {sorted(VALID_REQUIREMENT_TYPES)}")
        if not non_empty_string(request.get("requirement")):
            errors.append(f"{prefix}.requirement must be a non-empty string")

        origin = request.get("origin")
        if not isinstance(origin, dict):
            errors.append(f"{prefix}.origin must be an object")
        else:
            if not non_empty_string(origin.get("lot_id")):
                errors.append(f"{prefix}.origin.lot_id must be a non-empty string")
            if origin.get("pass_id") is not None and not non_empty_string(origin.get("pass_id")):
                errors.append(f"{prefix}.origin.pass_id must be null or a non-empty string")

        implementation_status = request.get("implementation_status")
        if implementation_status not in completion.VALID_IMPLEMENTATION_STATUSES:
            errors.append(
                f"{prefix}.implementation_status must be one of {sorted(completion.VALID_IMPLEMENTATION_STATUSES)}"
            )
        evidence_status = request.get("evidence_status")
        if evidence_status not in completion.VALID_EVIDENCE_STATUSES:
            errors.append(f"{prefix}.evidence_status must be one of {sorted(completion.VALID_EVIDENCE_STATUSES)}")

        for key in ("affected_files", "affected_components", "remaining_work", "remaining_tests"):
            _validate_string_list(request.get(key), f"{prefix}.{key}", errors)
        history = request.get("history")
        if not isinstance(history, list):
            errors.append(f"{prefix}.history must be a list")
        elif not all(isinstance(item, dict) for item in history):
            errors.append(f"{prefix}.history must contain objects")

        expected = request.get("expected_evidence")
        if not isinstance(expected, list):
            errors.append(f"{prefix}.expected_evidence must be a list")
            expected = []
        for evidence_index, item in enumerate(expected):
            evidence_prefix = f"{prefix}.expected_evidence[{evidence_index}]"
            if not isinstance(item, dict):
                errors.append(f"{evidence_prefix} must be an object")
                continue
            if item.get("kind") not in completion.VALID_EVIDENCE_KINDS:
                errors.append(f"{evidence_prefix}.kind must be one of {sorted(completion.VALID_EVIDENCE_KINDS)}")
            if not isinstance(item.get("required"), bool):
                errors.append(f"{evidence_prefix}.required must be boolean")
            if not non_empty_string(item.get("description")):
                errors.append(f"{evidence_prefix}.description must be a non-empty string")

        obtained = request.get("obtained_evidence")
        if not isinstance(obtained, list):
            errors.append(f"{prefix}.obtained_evidence must be a list")
            obtained = []
        for evidence_index, item in enumerate(obtained):
            evidence_prefix = f"{prefix}.obtained_evidence[{evidence_index}]"
            if not isinstance(item, dict):
                errors.append(f"{evidence_prefix} must be an object")
                continue
            if item.get("kind") not in completion.VALID_EVIDENCE_KINDS:
                errors.append(f"{evidence_prefix}.kind must be one of {sorted(completion.VALID_EVIDENCE_KINDS)}")
            if item.get("status") not in completion.VALID_OBTAINED_EVIDENCE_STATUSES:
                errors.append(
                    f"{evidence_prefix}.status must be one of {sorted(completion.VALID_OBTAINED_EVIDENCE_STATUSES)}"
                )
            if not non_empty_string(item.get("reference")):
                errors.append(f"{evidence_prefix}.reference must be a non-empty string")

        blocked_reason = request.get("blocked_reason")
        if blocked_reason is not None and not non_empty_string(blocked_reason):
            errors.append(f"{prefix}.blocked_reason must be null or a non-empty string")
        disposition = request.get("disposition")
        if disposition is not None:
            if not isinstance(disposition, dict):
                errors.append(f"{prefix}.disposition must be null or an object")
            else:
                disposition_type = disposition.get("type")
                if disposition_type not in completion.VALID_DISPOSITIONS:
                    errors.append(f"{prefix}.disposition.type must be one of {sorted(completion.VALID_DISPOSITIONS)}")
                if not non_empty_string(disposition.get("reason")):
                    errors.append(f"{prefix}.disposition.reason must be a non-empty string")
                if not non_empty_string(disposition.get("decision_source")):
                    errors.append(f"{prefix}.disposition.decision_source must be a non-empty string")
                if disposition_type == "moved_to_new_lot" and not non_empty_string(disposition.get("target_lot_id")):
                    errors.append(f"{prefix}.disposition.target_lot_id is required for moved_to_new_lot")

        derived_evidence = completion.derive_evidence_status(request)
        if evidence_status != derived_evidence:
            errors.append(
                f"{prefix}.evidence_status {evidence_status!r} contradicts derived evidence_status {derived_evidence!r}"
            )
        derived_decision = completion.derive_request_decision(request)
        if request.get("decision") != derived_decision:
            errors.append(f"{prefix}.decision {request.get('decision')!r} contradicts derived decision {derived_decision!r}")
        if derived_decision == "repair" and not request.get("remaining_work"):
            errors.append(f"{prefix}.remaining_work must identify incomplete implementation or technical verification work")
        if derived_decision == "user_testing" and not request.get("remaining_tests"):
            errors.append(f"{prefix}.remaining_tests must identify the missing E2E or human validation")
    return requests


def request_requires_ui_evidence(request: dict) -> bool:
    request_type = str(request.get("requirement_type", "")).lower()
    text = " ".join(str(request.get(key, "")) for key in ("id", "source", "coverage")).lower()
    return request_type in {"ui", "ui_ux", "design", "ux"} or bool(
        re.search(r"\b(ui|ux|design|ecran|écran|page|interface|visuel)\b", text)
    )


def validate_lot_completion_gate(data: dict, requests: list, errors: list[str]) -> dict:
    gate = data.get("lot_completion_gate")
    if gate is None:
        return {}
    if not isinstance(gate, dict):
        errors.append("lot_completion_gate must be an object")
        return {}
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

    request_ids = {
        request.get("id")
        for request in requests
        if isinstance(request, dict) and non_empty_string(request.get("id"))
    }
    covered_ids = set()
    coverage_by_id: dict[str, dict] = {}
    for index, row in enumerate(coverage_table):
        prefix = f"lot_completion_gate.coverage_table[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        requirement_id = row.get("requirement_id")
        if not non_empty_string(requirement_id):
            errors.append(f"{prefix}.requirement_id must be a non-empty string")
        else:
            covered_ids.add(requirement_id)
            if requirement_id not in coverage_by_id:
                coverage_by_id[requirement_id] = row
        if not non_empty_string(row.get("requirement")):
            errors.append(f"{prefix}.requirement must be a non-empty string")
        if row.get("status") not in VALID_COMPLETION_STATUSES:
            errors.append(f"{prefix}.status must be one of {sorted(VALID_COMPLETION_STATUSES)}")
        if not isinstance(row.get("proof"), list):
            errors.append(f"{prefix}.proof must be a list")
        if "comment" in row and not isinstance(row.get("comment"), str):
            errors.append(f"{prefix}.comment must be a string when present")

    missing_ids = sorted(request_ids - covered_ids)
    if data.get("status") in {"done", "user_testing", "repair"} and missing_ids:
        errors.append(f"lot_completion_gate.coverage_table must cover all validated_requests: missing {missing_ids}")

    visual_evidence = gate.get("visual_evidence")
    if not isinstance(visual_evidence, list):
        errors.append("lot_completion_gate.visual_evidence must be a list")
        visual_evidence = []
    decision = gate.get("decision")
    if decision not in VALID_STATUSES:
        errors.append(f"lot_completion_gate.decision must be one of {sorted(VALID_STATUSES)}")

    contract_status = data.get("status")
    if contract_status in {"done", "user_testing", "repair", "blocked"} and decision != contract_status:
        errors.append(
            f"lot_completion_gate.decision {decision!r} contradicts contract status {contract_status!r}"
        )
    for request in requests:
        if not isinstance(request, dict):
            continue
        row = coverage_by_id.get(request.get("id"))
        if not row:
            continue
        if request.get("status") == "done" and row.get("status") != "fait":
            errors.append(
                f"validated_requests {request.get('id')} status done contradicts "
                f"lot_completion_gate coverage status {row.get('status')!r}"
            )
        if request.get("status") == "requires_e2e" and row.get("status") != "requires_e2e":
            errors.append(
                f"validated_requests {request.get('id')} status requires_e2e contradicts "
                f"lot_completion_gate coverage status {row.get('status')!r}"
            )
    if contract_status == "user_testing":
        incomplete_rows = [
            row.get("requirement_id", f"#{index}")
            for index, row in enumerate(coverage_table)
            if isinstance(row, dict) and row.get("status") in {"partiel", "non fait", "bloque"}
        ]
        if incomplete_rows:
            errors.append(
                "status user_testing is incompatible with partial, missing or blocked implementation rows: "
                f"{incomplete_rows}"
            )
        if status not in {"pending", "pass"}:
            errors.append("status user_testing requires lot_completion_gate.status pending or pass")
    if contract_status == "repair" and status != "fail":
        errors.append("status repair requires lot_completion_gate.status fail")

    if data.get("status") == "done":
        if status != "pass":
            errors.append("status done requires lot_completion_gate.status pass")
        blocking_rows = [
            row.get("requirement_id", f"#{index}")
            for index, row in enumerate(coverage_table)
            if isinstance(row, dict) and row.get("status") in BLOCKING_COMPLETION_STATUSES
        ]
        if blocking_rows:
            errors.append(f"status done is incompatible with incomplete lot_completion_gate rows: {blocking_rows}")
        for request in requests:
            if not isinstance(request, dict) or request.get("status") != "done":
                continue
            has_proof = bool(request.get("files")) or bool(request.get("verification")) or bool(request.get("notes"))
            if not has_proof:
                errors.append(f"validated_requests {request.get('id')} marked done requires files, verification or notes proof")
        ui_required = gate.get("ui_ux_required") is True or any(
            isinstance(request, dict) and request_requires_ui_evidence(request) for request in requests
        )
        e2e = data.get("e2e") if isinstance(data.get("e2e"), dict) else {}
        if ui_required and not visual_evidence and not e2e.get("items"):
            errors.append("status done with UI/UX requirements requires lot_completion_gate.visual_evidence or e2e.items")
    return gate


def validate_lot_completion_gate_v31(data: dict, requests: list, errors: list[str]) -> dict:
    gate = require_object(data, "lot_completion_gate", errors)
    if not gate:
        return gate
    if gate.get("derived_from_validated_requests") is not True:
        errors.append("lot_completion_gate.derived_from_validated_requests must be true")
    if not non_empty_string(gate.get("validated_scope_source")):
        errors.append("lot_completion_gate.validated_scope_source must be a non-empty string")
    for key in ("scope_reduction_requested", "scope_reduction_validated_by_user", "ui_ux_required"):
        if not isinstance(gate.get(key), bool):
            errors.append(f"lot_completion_gate.{key} must be boolean")
    if gate.get("scope_reduction_requested") is True and gate.get("scope_reduction_validated_by_user") is not True:
        errors.append("lot_completion_gate scope reduction requires explicit user validation")
    if not isinstance(gate.get("visual_evidence"), list):
        errors.append("lot_completion_gate.visual_evidence must be a list")

    coverage_table = gate.get("coverage_table")
    if not isinstance(coverage_table, list):
        errors.append("lot_completion_gate.coverage_table must be a list")
        coverage_table = []
    request_by_id = {
        item.get("id"): item for item in requests if isinstance(item, dict) and non_empty_string(item.get("id"))
    }
    covered: set[str] = set()
    for index, row in enumerate(coverage_table):
        prefix = f"lot_completion_gate.coverage_table[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        requirement_id = row.get("requirement_id")
        if not non_empty_string(requirement_id):
            errors.append(f"{prefix}.requirement_id must be a non-empty string")
            continue
        if requirement_id in covered:
            errors.append(f"{prefix}.requirement_id is duplicated: {requirement_id}")
        covered.add(requirement_id)
        request = request_by_id.get(requirement_id)
        if request is None:
            errors.append(f"{prefix}.requirement_id references unknown validated_request {requirement_id!r}")
            continue
        expected_row = completion.coverage_row(request)
        for key, expected_value in expected_row.items():
            if row.get(key) != expected_value:
                errors.append(
                    f"{prefix}.{key} {row.get(key)!r} contradicts validated_requests derived value {expected_value!r}"
                )
    missing = sorted(set(request_by_id) - covered)
    if missing:
        errors.append(f"lot_completion_gate.coverage_table must cover all validated_requests: missing {missing}")

    derived_decision = completion.derive_contract_decision(requests)
    derived_status = completion.derive_gate_status(derived_decision)
    if gate.get("decision") != derived_decision:
        errors.append(
            f"lot_completion_gate.decision {gate.get('decision')!r} contradicts derived decision {derived_decision!r}"
        )
    if gate.get("status") != derived_status:
        errors.append(
            f"lot_completion_gate.status {gate.get('status')!r} contradicts derived status {derived_status!r}"
        )
    return gate


def validate_origin_intake_lineage_v31(
    data: dict,
    requests: list,
    errors: list[str],
    warnings: list[str],
    contract_path: Path | None,
) -> None:
    origin = require_object(data, "origin", errors)
    lot_ids: list = []
    if origin:
        if origin.get("pass_id") is not None and not non_empty_string(origin.get("pass_id")):
            errors.append("origin.pass_id must be null or a non-empty string")
        lot_ids = _validate_string_list(origin.get("lot_ids"), "origin.lot_ids", errors)
        if not lot_ids:
            errors.append("origin.lot_ids must not be empty")
        if not non_empty_string(origin.get("validation_source")):
            errors.append("origin.validation_source must be a non-empty string")
        request_lots = {
            item.get("origin", {}).get("lot_id")
            for item in requests
            if isinstance(item, dict) and isinstance(item.get("origin"), dict)
        }
        missing_lots = sorted(set(lot_ids) - request_lots)
        if missing_lots:
            errors.append(
                "validated_requests must include at least one granular requirement for every origin lot: "
                f"missing {missing_lots}"
            )
        unknown_lots = sorted(value for value in request_lots - set(lot_ids) if value)
        if unknown_lots:
            errors.append(f"validated_requests reference lots outside origin.lot_ids: {unknown_lots}")

    request_ids = {item.get("id") for item in requests if isinstance(item, dict)}
    intake = require_object(data, "intake", errors)
    if intake:
        classification = intake.get("classification")
        if classification not in completion.VALID_INTAKE_CLASSIFICATIONS:
            errors.append(f"intake.classification must be one of {sorted(completion.VALID_INTAKE_CLASSIFICATIONS)}")
        matched = _validate_string_list(intake.get("matched_requirement_ids"), "intake.matched_requirement_ids", errors)
        if not isinstance(intake.get("creates_new_lot"), bool):
            errors.append("intake.creates_new_lot must be boolean")
        feedback = intake.get("feedback")
        if feedback is not None and not non_empty_string(feedback):
            errors.append("intake.feedback must be null or a non-empty string")
        existing = {
            "existing_requirement_repair",
            "existing_requirement_clarification",
            "existing_requirement_acceptance",
            "cancelled_requirement",
        }
        if classification in existing and not matched:
            errors.append(f"intake.classification {classification} requires matched_requirement_ids")
        missing_matches = sorted(set(matched) - request_ids)
        if missing_matches:
            errors.append(f"intake.matched_requirement_ids reference unknown requirements: {missing_matches}")
        if classification == "existing_requirement_repair":
            if not non_empty_string(feedback):
                errors.append("existing_requirement_repair requires intake.feedback")
            for request in requests:
                if not isinstance(request, dict) or request.get("id") not in matched:
                    continue
                history = request.get("history") if isinstance(request.get("history"), list) else []
                if not any(
                    isinstance(item, dict) and item.get("type") in {"user_feedback", "repair"}
                    for item in history
                ):
                    errors.append(
                        f"existing_requirement_repair matched requirement {request.get('id')} must record user feedback in history"
                    )
        if classification == "existing_requirement_acceptance":
            for request in requests:
                if isinstance(request, dict) and request.get("id") in matched:
                    if completion.derive_request_decision(request) != "done":
                        errors.append(
                            f"existing_requirement_acceptance matched requirement {request.get('id')} must derive decision done"
                        )
        if classification == "cancelled_requirement":
            for request in requests:
                if not isinstance(request, dict) or request.get("id") not in matched:
                    continue
                disposition = request.get("disposition")
                if not isinstance(disposition, dict) or disposition.get("type") != "cancelled":
                    errors.append(
                        f"cancelled_requirement matched requirement {request.get('id')} requires disposition.type cancelled"
                    )

    lineage = require_object(data, "lineage", errors)
    inherited: list = []
    if lineage:
        parent_contract = lineage.get("parent_contract")
        if parent_contract is not None and not non_empty_string(parent_contract):
            errors.append("lineage.parent_contract must be null or a non-empty string")
        inherited = _validate_string_list(
            lineage.get("inherited_open_requirement_ids"), "lineage.inherited_open_requirement_ids", errors
        )
        reopened = _validate_string_list(lineage.get("reopened_lot_ids"), "lineage.reopened_lot_ids", errors)
        if not non_empty_string(lineage.get("next_coherent_scope")):
            errors.append("lineage.next_coherent_scope must be a non-empty string")
        if intake.get("classification") == "existing_requirement_repair" and not reopened:
            errors.append("existing_requirement_repair requires lineage.reopened_lot_ids")
        if parent_contract:
            if contract_path is None:
                warnings.append("lineage.parent_contract inheritance was not checked because contract_path is unavailable")
            else:
                parent_path = (contract_path.parent / parent_contract).resolve()
                try:
                    parent_data = load_contract(parent_path)
                except ValueError as exc:
                    errors.append(f"lineage.parent_contract cannot be loaded: {exc}")
                else:
                    parent_requests = parent_data.get("validated_requests")
                    if parent_data.get("schema_version") != SCHEMA_VERSION or not isinstance(parent_requests, list):
                        errors.append("lineage.parent_contract must reference a 3.1.0 contract with validated_requests")
                    else:
                        expected_inherited = set(completion.open_requirement_ids(parent_requests))
                        missing_inherited = sorted(expected_inherited - set(inherited))
                        if missing_inherited:
                            errors.append(f"lineage missing inherited open requirements: {missing_inherited}")
                        extra_inherited = sorted(set(inherited) - expected_inherited)
                        if extra_inherited:
                            errors.append(f"lineage inherits requirements not open in parent: {extra_inherited}")
        missing_current = sorted(set(inherited) - request_ids)
        if missing_current:
            errors.append(f"validated_requests missing inherited open requirements: {missing_current}")

    justification = data.get("new_lot_justification")
    creates_new_lot = intake.get("creates_new_lot") is True
    if creates_new_lot:
        if intake.get("classification") not in {"new_requirement", "scope_change"}:
            errors.append("intake.creates_new_lot is allowed only for new_requirement or scope_change")
        if not isinstance(justification, dict):
            errors.append("new_lot_justification is required when intake.creates_new_lot is true")
        else:
            if justification.get("outside_existing_validated_scope") is not True:
                errors.append("new_lot_justification.outside_existing_validated_scope must be true")
            checked = _validate_string_list(justification.get("checked_lots"), "new_lot_justification.checked_lots", errors)
            if not checked:
                errors.append("new_lot_justification.checked_lots must not be empty")
            if not non_empty_string(justification.get("reason")):
                errors.append("new_lot_justification.reason must be a non-empty string")
            if justification.get("user_decision_required") is not True:
                errors.append("new_lot_justification.user_decision_required must be true")
    elif justification is not None:
        errors.append("new_lot_justification must be null when no new lot is created")


def validate_closure_v31(data: dict, requests: list, errors: list[str]) -> None:
    closure = require_object(data, "closure", errors)
    if not closure:
        return
    decision = completion.derive_contract_decision(requests)
    expected_claim = completion.derive_closure_claim(decision)
    if closure.get("overall_claim") != expected_claim:
        errors.append(
            f"closure.overall_claim {closure.get('overall_claim')!r} contradicts derived claim {expected_claim!r}"
        )
    expected_open = completion.open_requirement_ids(requests)
    open_ids = closure.get("open_requirement_ids")
    if open_ids != expected_open:
        errors.append(f"closure.open_requirement_ids must equal derived open requirements {expected_open!r}")
    summary = closure.get("summary")
    if not non_empty_string(summary):
        errors.append("closure.summary must be a non-empty string")
    elif decision != "done" and COMPLETION_WORDS.search(summary) and not QUALIFICATION_WORDS.search(summary):
        errors.append("closure.summary cannot claim the pass is complete, delivered or implemented while requirements remain open")


def validate_ui_validation(data: dict, requests: list, errors: list[str], warnings: list[str]) -> dict:
    ui = data.get("ui_validation")
    gate = data.get("lot_completion_gate") if isinstance(data.get("lot_completion_gate"), dict) else {}
    inferred_ui_required = gate.get("ui_ux_required") is True or any(
        isinstance(request, dict) and request_requires_ui_evidence(request) for request in requests
    )
    e2e = data.get("e2e") if isinstance(data.get("e2e"), dict) else {}

    if ui is None:
        warnings.append("ui_validation missing; accepted as legacy contract")
        return {}
    if not isinstance(ui, dict):
        errors.append("ui_validation must be an object")
        return {}

    required = ui.get("required")
    if not isinstance(required, bool):
        errors.append("ui_validation.required must be boolean")
        required = False
    if "routes" in ui and not isinstance(ui.get("routes"), list):
        errors.append("ui_validation.routes must be a list")

    readiness = ui.get("test_readiness")
    if not isinstance(readiness, dict):
        errors.append("ui_validation.test_readiness must be an object")
        readiness = {}
    else:
        if readiness.get("status") not in VALID_UI_READINESS_STATUSES:
            errors.append(f"ui_validation.test_readiness.status must be one of {sorted(VALID_UI_READINESS_STATUSES)}")
        for key in ("auth_required", "login_redirect_detected"):
            if key in readiness and not isinstance(readiness.get(key), bool):
                errors.append(f"ui_validation.test_readiness.{key} must be boolean")
        if not non_empty_string(readiness.get("auth_mode")):
            errors.append("ui_validation.test_readiness.auth_mode must be a non-empty string")
        for key in ("state_available", "state_valid"):
            if key in readiness and readiness.get(key) is not None and not isinstance(readiness.get(key), bool):
                errors.append(f"ui_validation.test_readiness.{key} must be boolean or null")
        if "blocked_reason" in readiness and readiness.get("blocked_reason") is not None and not isinstance(readiness.get("blocked_reason"), str):
            errors.append("ui_validation.test_readiness.blocked_reason must be string or null")

    visual = ui.get("visual_evidence")
    if not isinstance(visual, dict):
        errors.append("ui_validation.visual_evidence must be an object")
        visual = {}
    else:
        if visual.get("status") not in VALID_UI_VISUAL_STATUSES:
            errors.append(f"ui_validation.visual_evidence.status must be one of {sorted(VALID_UI_VISUAL_STATUSES)}")
        for key in ("routes", "viewports", "screenshots"):
            if not isinstance(visual.get(key), list):
                errors.append(f"ui_validation.visual_evidence.{key} must be a list")
        report_file = visual.get("report_file")
        if report_file is not None and not non_empty_string(report_file):
            errors.append("ui_validation.visual_evidence.report_file must be null or a non-empty string")
        for key in ("console_errors", "page_errors", "request_failed"):
            if key in visual and not isinstance(visual.get(key), int):
                errors.append(f"ui_validation.visual_evidence.{key} must be integer")
        for key in ("horizontal_overflow_detected", "unexpected_login_redirect"):
            if key in visual and not isinstance(visual.get(key), bool):
                errors.append(f"ui_validation.visual_evidence.{key} must be boolean")

    if data.get("status") == "done" and required is True:
        if readiness.get("status") != "pass":
            errors.append("status done with ui_validation.required true requires ui_validation.test_readiness.status pass")
        if visual.get("status") != "pass":
            errors.append("status done with ui_validation.required true requires ui_validation.visual_evidence.status pass")
        if not visual.get("report_file"):
            errors.append("status done with ui_validation.required true requires ui_validation.visual_evidence.report_file")
        if not visual.get("screenshots") and not e2e.get("items"):
            errors.append("status done with ui_validation.required true requires screenshots or e2e.items")
        if readiness.get("login_redirect_detected") is True or visual.get("unexpected_login_redirect") is True:
            errors.append("status done is incompatible with UI login redirect detection")
        if visual.get("page_errors", 0) > 0:
            errors.append("status done is incompatible with UI page_errors")
        if visual.get("horizontal_overflow_detected") is True:
            errors.append("status done is incompatible with unexpected UI horizontal overflow")

    if data.get("status") == "user_testing" and (required is True or inferred_ui_required):
        blocked_or_missing = readiness.get("status") in {"blocked", "fail", "pending"} or visual.get("status") in {"blocked", "repair", "pending"}
        if blocked_or_missing and not e2e.get("items"):
            errors.append("status user_testing with blocked UI automation requires e2e.items describing remaining user tests")

    return ui


def validate_propagation(data: dict, errors: list[str], warnings: list[str]) -> dict:
    propagation = data.get("propagation")
    gates = data.get("gates") if isinstance(data.get("gates"), dict) else {}
    if propagation is None:
        if "propagation" in gates and gates.get("propagation") != "not_applicable":
            errors.append("gates.propagation requires propagation object")
        else:
            warnings.append("propagation missing; accepted as legacy contract")
        return {}
    if not isinstance(propagation, dict):
        errors.append("propagation must be an object")
        return {}

    required = propagation.get("required")
    if not isinstance(required, bool):
        errors.append("propagation.required must be boolean")
        required = False
    status = propagation.get("status")
    if status not in VALID_GATE_STATUSES:
        errors.append(f"propagation.status must be one of {sorted(VALID_GATE_STATUSES)}")
    risk_level = propagation.get("risk_level")
    if risk_level not in VALID_PROPAGATION_RISK_LEVELS:
        errors.append(f"propagation.risk_level must be one of {sorted(VALID_PROPAGATION_RISK_LEVELS)}")
    compatibility = propagation.get("compatibility_strategy")
    if compatibility not in VALID_PROPAGATION_COMPATIBILITY:
        errors.append(f"propagation.compatibility_strategy must be one of {sorted(VALID_PROPAGATION_COMPATIBILITY)}")
    decision = propagation.get("decision")
    if decision not in VALID_PROPAGATION_DECISIONS:
        errors.append(f"propagation.decision must be one of {sorted(VALID_PROPAGATION_DECISIONS)}")

    preflight = propagation.get("preflight")
    if not isinstance(preflight, dict):
        errors.append("propagation.preflight must be an object")
        preflight = {}
    else:
        if not isinstance(preflight.get("done"), bool):
            errors.append("propagation.preflight.done must be boolean")
        if not non_empty_string(preflight.get("summary")):
            errors.append("propagation.preflight.summary must be a non-empty string")
        for key in ("human_validation_required", "human_validation_received"):
            if not isinstance(preflight.get(key), bool):
                errors.append(f"propagation.preflight.{key} must be boolean")

    for key in (
        "changed_symbols",
        "affected_surfaces",
        "consumers_checked",
        "reference_searches",
        "remaining_references",
        "ignored_references",
        "verification",
    ):
        if not isinstance(propagation.get(key), list):
            errors.append(f"propagation.{key} must be a list")

    if required is True and status == "not_applicable":
        errors.append("propagation.status cannot be not_applicable when required is true")
    if required is not True:
        return propagation

    is_done_or_pass = data.get("status") == "done" or status == "pass" or decision == "pass"
    if not is_done_or_pass:
        return propagation

    if status != "pass":
        errors.append("status done requires propagation.status pass when propagation is required")
    if decision != "pass":
        errors.append("status done requires propagation.decision pass when propagation is required")
    if preflight.get("done") is not True:
        errors.append("propagation.preflight.done must be true when propagation is required")
    if preflight.get("human_validation_required") is True and preflight.get("human_validation_received") is not True:
        errors.append("propagation human validation required but not received")
    if not propagation.get("changed_symbols"):
        errors.append("propagation.changed_symbols must not be empty when propagation is required")
    if not propagation.get("reference_searches"):
        errors.append("propagation.reference_searches must not be empty when propagation is required")
    if propagation.get("remaining_references") and not propagation.get("ignored_references"):
        errors.append("propagation.remaining_references require ignored_references justification")
    if risk_level in {"high", "critical"}:
        if not propagation.get("affected_surfaces"):
            errors.append("high/critical propagation requires propagation.affected_surfaces")
        if not propagation.get("consumers_checked"):
            errors.append("high/critical propagation requires propagation.consumers_checked")
        if not propagation.get("verification"):
            errors.append("high/critical propagation requires propagation.verification")
    return propagation


def validate(data: dict, contract_path: Path | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required = (
        "schema_version",
        "task_id",
        "lot_id",
        "task_type",
        "status",
        "objective",
        "validated_requests",
        "lot_completion_gate",
        "scope",
        "product_truth",
        "evidence",
        "skills",
        "plan",
        "findings",
        "decisions",
        "implementation",
        "verification",
        "gates",
        "e2e",
        "context",
        "transition",
    )
    for key in required:
        if key not in data:
            errors.append(f"missing required key: {key}")

    schema_version = data.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(f"schema_version must be one of {sorted(SUPPORTED_SCHEMA_VERSIONS)}")
    if schema_version == SCHEMA_VERSION:
        for key in ("origin", "intake", "lineage", "new_lot_justification", "closure"):
            if key not in data:
                errors.append(f"missing required key: {key}")
    if data.get("task_type") not in VALID_TASK_TYPES:
        errors.append(f"task_type must be one of {sorted(VALID_TASK_TYPES)}")
    status = data.get("status")
    if status not in VALID_STATUSES:
        errors.append(f"status must be one of {sorted(VALID_STATUSES)}")
    for key in ("task_id", "lot_id", "objective"):
        if not non_empty_string(data.get(key)):
            errors.append(f"{key} must be a non-empty string")

    if schema_version == SCHEMA_VERSION:
        requests = validate_requests_v31(data, errors)
        validate_lot_completion_gate_v31(data, requests, errors)
        validate_origin_intake_lineage_v31(data, requests, errors, warnings, contract_path)
        validate_closure_v31(data, requests, errors)
        derived_status = completion.derive_contract_decision(requests)
        if status != derived_status:
            errors.append(f"status {status} contradicts derived status {derived_status}")
    else:
        requests = validate_requests(data, errors)
        validate_lot_completion_gate(data, requests, errors)
        if len(requests) == 1:
            request = requests[0] if isinstance(requests[0], dict) else {}
            combined = " ".join(str(request.get(key, "")) for key in ("id", "source", "coverage")).lower()
            pass_planning = data.get("pass_planning") if isinstance(data.get("pass_planning"), dict) else {}
            lots_included = pass_planning.get("lots_included") if isinstance(pass_planning.get("lots_included"), list) else []
            if len(lots_included) > 1 or any(
                marker in combined for marker in ("tous les lots", "cinq lots", "five lots", "multi-lot")
            ):
                warnings.append(
                    "legacy multi-lot validated_requests registry is too generic; normalize it into stable per-lot and "
                    "per-criterion requirements before resuming or closing the scope"
                )
    ui_validation = validate_ui_validation(data, requests, errors, warnings)
    propagation = validate_propagation(data, errors, warnings)
    if data.get("task_type") != "analysis" and not requests:
        errors.append("validated_requests must not be empty for non-analysis tasks")
    if schema_version == "3.0.0" and status == "done":
        open_statuses = {"todo", "doing", "requires_e2e", "blocked"}
        for request in requests:
            if isinstance(request, dict) and request.get("status") in open_statuses:
                errors.append("status done requires all validated_requests to be done, moved_to_new_lot or cancelled")

    scope = require_object(data, "scope", errors)
    if scope:
        for key in ("in", "out", "allowed_paths", "forbidden_paths"):
            if key in scope and not isinstance(scope[key], list):
                errors.append(f"scope.{key} must be a list")

    product_truth = require_object(data, "product_truth", errors)
    if product_truth:
        required_truth = product_truth.get("required")
        items = product_truth.get("items")
        if not isinstance(required_truth, bool):
            errors.append("product_truth.required must be boolean")
        if not isinstance(items, list):
            errors.append("product_truth.items must be a list")
        if required_truth is True and not items:
            errors.append("product_truth.items must not be empty when product_truth.required is true")

    backlog_mutation = validate_backlog_mutation(data, errors)
    global_impact = validate_global_impact(data, errors)
    if backlog_mutation and global_impact:
        if backlog_mutation.get("structural_change_detected") is True and global_impact.get("required") is not True:
            errors.append("structural backlog changes require global_impact.required true")
    for request in requests:
        if schema_version == "3.0.0" and isinstance(request, dict) and request.get("status") == "moved_to_new_lot":
            notes = request.get("notes") if isinstance(request.get("notes"), list) else []
            notes_text = " ".join(str(item) for item in notes)
            coverage = request.get("coverage") if isinstance(request.get("coverage"), str) else ""
            created_lots = backlog_mutation.get("created_lots") if isinstance(backlog_mutation, dict) else []
            has_target = (
                bool(created_lots)
                or "SR_INBOX" in notes_text
                or "SR_LOTS" in notes_text
                or "SR-" in coverage
                or "lot cible" in coverage.lower()
            )
            if not has_target:
                errors.append("moved_to_new_lot requests require a target lot, SR_INBOX/SR_LOTS note, or backlog_mutation.created_lots")

    evidence = require_object(data, "evidence", errors)
    if evidence:
        for key in ("sources_read", "code_files_read", "tests_or_logs"):
            if key in evidence and not isinstance(evidence[key], list):
                errors.append(f"evidence.{key} must be a list")
        if status == "done" and not evidence.get("sources_read"):
            errors.append("evidence.sources_read must not be empty when status is done")

    skills = require_object(data, "skills", errors)
    if skills:
        for key in ("method", "domain"):
            if key in skills and not isinstance(skills[key], list):
                errors.append(f"skills.{key} must be a list")

    for key in ("plan", "findings", "decisions"):
        value = data.get(key)
        if not isinstance(value, list):
            errors.append(f"{key} must be a list")

    implementation = require_object(data, "implementation", errors)
    if implementation:
        app_code_changed = implementation.get("app_code_changed")
        changed_files = implementation.get("changed_files")
        if not isinstance(app_code_changed, bool):
            errors.append("implementation.app_code_changed must be boolean")
        if not isinstance(changed_files, list):
            errors.append("implementation.changed_files must be a list")
        if app_code_changed is True and not changed_files:
            errors.append("implementation.changed_files must not be empty when app_code_changed is true")

    verification = require_object(data, "verification", errors)
    if verification:
        commands_run = verification.get("commands_run")
        commands_failed = verification.get("commands_failed")
        not_run_reason = verification.get("not_run_reason")
        if not isinstance(commands_run, list):
            errors.append("verification.commands_run must be a list")
            commands_run = []
        if not isinstance(commands_failed, list):
            errors.append("verification.commands_failed must be a list")
            commands_failed = []
        if status == "done" and not commands_run and not non_empty_string(not_run_reason):
            errors.append("status done requires verification.commands_run or verification.not_run_reason")
        if status == "done" and commands_failed and not non_empty_string(not_run_reason):
            errors.append("status done requires failed commands to be justified")

    gates = require_object(data, "gates", errors)
    if gates:
        for key, value in gates.items():
            if value not in VALID_GATE_STATUSES:
                errors.append(f"gates.{key} must be one of {sorted(VALID_GATE_STATUSES)}")
        if status == "done":
            for key, value in gates.items():
                if value == "fail":
                    errors.append(f"status done is incompatible with gates.{key}=fail")
            if gates.get("lot_completion") != "pass":
                errors.append("status done requires gates.lot_completion pass")
            if isinstance(propagation, dict) and propagation.get("required") is True and gates.get("propagation") != "pass":
                errors.append("status done requires gates.propagation pass when propagation is required")
            if isinstance(ui_validation, dict) and ui_validation.get("required") is True:
                if gates.get("ui_test_readiness") != "pass":
                    errors.append("status done requires gates.ui_test_readiness pass when ui_validation is required")
                if gates.get("ui_visual_evidence") != "pass":
                    errors.append("status done requires gates.ui_visual_evidence pass when ui_validation is required")
        if schema_version == SCHEMA_VERSION:
            expected_lot_gate = completion.derive_gate_status(completion.derive_contract_decision(requests))
            if gates.get("lot_completion") != expected_lot_gate:
                errors.append(
                    f"gates.lot_completion {gates.get('lot_completion')!r} contradicts derived status {expected_lot_gate!r}"
                )
            visual = ui_validation.get("visual_evidence") if isinstance(ui_validation, dict) else {}
            if isinstance(visual, dict) and visual.get("status") == "repair" and status != "repair":
                errors.append("ui_validation.visual_evidence.status repair requires contract status repair")

    e2e = require_object(data, "e2e", errors)
    if e2e:
        required_e2e = e2e.get("required")
        items = e2e.get("items")
        if not isinstance(required_e2e, bool):
            errors.append("e2e.required must be boolean")
        if not isinstance(items, list):
            errors.append("e2e.items must be a list")
        if required_e2e is True and not items:
            errors.append("e2e.items must not be empty when e2e.required is true")

    context = require_object(data, "context", errors)
    context_status = None
    if context:
        context_status = context.get("status")
        if context_status not in VALID_CONTEXT_STATUSES:
            errors.append(f"context.status must be one of {sorted(VALID_CONTEXT_STATUSES)}")
        if "report_path" in context and context["report_path"] is not None and not non_empty_string(context["report_path"]):
            errors.append("context.report_path must be null or a non-empty string")

    transition = require_object(data, "transition", errors)
    if transition:
        decision = transition.get("decision")
        if decision not in VALID_TRANSITIONS:
            errors.append(f"transition.decision must be one of {sorted(VALID_TRANSITIONS)}")
        if not non_empty_string(transition.get("reason")):
            errors.append("transition.reason must be a non-empty string")
        next_required = transition.get("next_session_prompt_required")
        if not isinstance(next_required, bool):
            errors.append("transition.next_session_prompt_required must be boolean")
        next_path = transition.get("next_session_prompt_path")
        next_user_prompt = transition.get("next_user_prompt")
        if next_required is True:
            if not non_empty_string(next_path):
                errors.append("transition.next_session_prompt_path is required when next_session_prompt_required is true")
            if not non_empty_string(next_user_prompt):
                errors.append("transition.next_user_prompt is required when next_session_prompt_required is true")
        if context_status in {"red", "stale", "ambiguous"} and decision != "stop_for_new_conversation":
            errors.append("red/stale/ambiguous context requires transition.decision stop_for_new_conversation")
        if context_status == "orange" and decision not in {"recommend_new_conversation", "stop_for_new_conversation"}:
            errors.append("orange context requires transition.decision recommend_new_conversation or stop_for_new_conversation")
        if decision in {"recommend_new_conversation", "stop_for_new_conversation"} and next_required is not True:
            errors.append("new conversation transition requires next_session_prompt_required true")
        if context_status == "yellow" and decision == "continue_current":
            warnings.append("yellow context should usually recommend a new conversation before a long next lot")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a SR 3.0.0 or 3.1.0 sr_contract.json file.")
    parser.add_argument("--file", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--render-user-summary", action="store_true")
    parser.add_argument("--render-resume", action="store_true")
    args = parser.parse_args()

    path = Path(args.file)
    try:
        data = load_contract(path)
        errors, warnings = validate(data, contract_path=path)
    except ValueError as exc:
        errors, warnings = [str(exc)], []

    result = {"ok": not errors, "errors": errors, "warnings": warnings, "file": str(path)}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if errors:
            print("SR contract errors:")
            for error in errors:
                print(f"- {error}")
        if warnings:
            print("SR contract warnings:")
            for warning in warnings:
                print(f"- {warning}")
        if not errors:
            print(f"OK: SR contract valid ({path})")
            if args.render_user_summary and data.get("schema_version") == SCHEMA_VERSION:
                print(completion.render_user_request_table(data.get("validated_requests", [])))
            if args.render_resume and data.get("schema_version") == SCHEMA_VERSION:
                print(completion.render_resume_requirements(data.get("validated_requests", [])))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
