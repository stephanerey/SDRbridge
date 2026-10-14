#!/usr/bin/env python3
"""Deterministic requirement and Completion Gate rules for SR contracts."""
from __future__ import annotations

from typing import Iterable


VALID_IMPLEMENTATION_STATUSES = {"not_started", "partial", "complete", "defective"}
VALID_EVIDENCE_STATUSES = {
    "not_required",
    "missing",
    "partial",
    "failed",
    "sufficient",
    "awaiting_user_acceptance",
    "user_accepted",
}
VALID_EVIDENCE_KINDS = {
    "unit",
    "build",
    "runtime",
    "visual",
    "e2e",
    "human_acceptance",
    "documentation",
    "other",
}
VALID_OBTAINED_EVIDENCE_STATUSES = {"pass", "fail", "blocked", "not_run", "accepted"}
VALID_REQUEST_DECISIONS = {
    "done",
    "user_testing",
    "repair",
    "blocked",
    "deferred",
    "cancelled",
    "moved_to_new_lot",
}
OPEN_REQUEST_DECISIONS = {"user_testing", "repair", "blocked"}
VALID_INTAKE_CLASSIFICATIONS = {
    "existing_requirement_repair",
    "existing_requirement_clarification",
    "existing_requirement_acceptance",
    "new_requirement",
    "scope_change",
    "cancelled_requirement",
}
VALID_DISPOSITIONS = {"deferred", "cancelled", "moved_to_new_lot"}


def _required_expected(request: dict) -> list[dict]:
    items = request.get("expected_evidence")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict) and item.get("required") is True]


def _obtained(request: dict) -> list[dict]:
    items = request.get("obtained_evidence")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def missing_required_evidence_kinds(request: dict) -> set[str]:
    required = {str(item.get("kind")) for item in _required_expected(request)}
    satisfied = {
        str(item.get("kind"))
        for item in _obtained(request)
        if item.get("status") in {"pass", "accepted"}
    }
    return required - satisfied


def derive_evidence_status(request: dict) -> str:
    """Derive the aggregate evidence state from typed expected/obtained proofs."""
    expected = _required_expected(request)
    obtained = _obtained(request)
    if not expected:
        return "not_required"

    required_kinds = [str(item.get("kind")) for item in expected]
    relevant = [item for item in obtained if str(item.get("kind")) in required_kinds]
    if any(item.get("status") == "fail" for item in relevant):
        return "failed"

    satisfied = {
        str(item.get("kind"))
        for item in relevant
        if item.get("status") in {"pass", "accepted"}
    }
    missing = [kind for kind in required_kinds if kind not in satisfied]
    if not missing:
        return "user_accepted" if "human_acceptance" in required_kinds else "sufficient"

    non_human_missing = [kind for kind in missing if kind != "human_acceptance"]
    if not non_human_missing and "human_acceptance" in missing:
        return "awaiting_user_acceptance"
    if not satisfied:
        return "missing"
    return "partial"


def derive_request_decision(request: dict) -> str:
    """Map one requirement to its product-facing completion decision."""
    disposition = request.get("disposition")
    if isinstance(disposition, dict) and disposition.get("type") in VALID_DISPOSITIONS:
        return str(disposition["type"])

    implementation = request.get("implementation_status")
    evidence_status = derive_evidence_status(request)
    blocked_reason = request.get("blocked_reason")

    if implementation in {"partial", "defective"}:
        return "repair"
    if implementation == "not_started":
        return "blocked" if isinstance(blocked_reason, str) and blocked_reason.strip() else "repair"
    if implementation != "complete":
        return "repair"
    if evidence_status == "failed":
        return "repair"
    if isinstance(blocked_reason, str) and blocked_reason.strip():
        return "blocked"
    if evidence_status in {"missing", "partial", "awaiting_user_acceptance"}:
        missing_kinds = missing_required_evidence_kinds(request)
        if missing_kinds and missing_kinds <= {"visual", "e2e", "human_acceptance"}:
            return "user_testing"
        return "repair"
    return "done"


def derive_contract_decision(requests: Iterable[dict]) -> str:
    decisions = [derive_request_decision(item) for item in requests if isinstance(item, dict)]
    if any(value == "repair" for value in decisions):
        return "repair"
    if any(value == "blocked" for value in decisions):
        return "blocked"
    if any(value == "user_testing" for value in decisions):
        return "user_testing"
    return "done"


def derive_gate_status(decision: str) -> str:
    if decision == "done":
        return "pass"
    if decision == "user_testing":
        return "pending"
    return "fail"


def derive_closure_claim(decision: str) -> str:
    if decision == "done":
        return "complete"
    if decision == "user_testing":
        return "technically_complete_awaiting_evidence"
    return "not_complete"


def open_requirement_ids(requests: Iterable[dict]) -> list[str]:
    return [
        str(item.get("id"))
        for item in requests
        if isinstance(item, dict)
        and item.get("id")
        and derive_request_decision(item) in OPEN_REQUEST_DECISIONS
    ]


def coverage_row(request: dict) -> dict:
    proof = [
        str(item.get("reference"))
        for item in _obtained(request)
        if isinstance(item.get("reference"), str) and item.get("reference").strip()
    ]
    return {
        "requirement_id": request.get("id"),
        "requirement": request.get("requirement"),
        "implementation_status": request.get("implementation_status"),
        "evidence_status": derive_evidence_status(request),
        "decision": derive_request_decision(request),
        "proof": proof,
        "remaining_work": list(request.get("remaining_work") or []),
        "remaining_tests": list(request.get("remaining_tests") or []),
    }


def render_user_request_table(requests: Iterable[dict]) -> str:
    lines = [
        "| Demande utilisateur | Etat | Preuve | Reste a faire |",
        "|---|---|---|---|",
    ]
    for item in requests:
        if not isinstance(item, dict):
            continue
        evidence_refs = [
            str(proof.get("reference"))
            for proof in _obtained(item)
            if proof.get("reference")
        ]
        remaining = list(item.get("remaining_work") or []) + list(item.get("remaining_tests") or [])
        lines.append(
            "| {requirement} | {decision} | {proof} | {remaining} |".format(
                requirement=str(item.get("requirement") or item.get("id") or "-").replace("|", "\\|"),
                decision=derive_request_decision(item),
                proof="; ".join(evidence_refs).replace("|", "\\|") or "Aucune",
                remaining="; ".join(str(value) for value in remaining).replace("|", "\\|") or "Aucun",
            )
        )
    return "\n".join(lines)


def render_resume_requirements(requests: Iterable[dict]) -> str:
    groups: dict[str, list[str]] = {"done": [], "user_testing": [], "repair": [], "blocked": []}
    for item in requests:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        decision = derive_request_decision(item)
        if decision in groups:
            groups[decision].append(str(item["id"]))
    lines = ["## Exigences persistantes"]
    labels = {
        "done": "Faites",
        "user_testing": "Implementation complete, preuves ou acceptation restantes",
        "repair": "Partielles, absentes ou defectueuses",
        "blocked": "Bloquees",
    }
    for key in ("done", "repair", "user_testing", "blocked"):
        lines.append(f"- {labels[key]}: {', '.join(groups[key]) if groups[key] else 'aucune'}")
    return "\n".join(lines)
