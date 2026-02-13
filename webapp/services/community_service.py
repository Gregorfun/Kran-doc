from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple


def filter_approved_solutions(
    *,
    solutions: List[Dict[str, Any]],
    model: str,
    error_code: str,
    solution_status: Callable[[Dict[str, Any]], str],
    normalize_model: Callable[[str], str],
    normalize_error_code: Callable[[str], str],
) -> List[Dict[str, Any]]:
    approved = [
        s
        for s in solutions
        if solution_status(s) == "approved" and normalize_error_code(s.get("error_code") or "") == error_code
    ]
    if model:
        exact = [s for s in approved if normalize_model(s.get("model") or "") == model]
        if exact:
            return exact
    return approved


def submission_access_error(status: str) -> Optional[str]:
    normalized = (status or "").strip().lower()
    if normalized == "approved":
        return None
    if normalized == "pending":
        return "Dein Account wartet auf Freigabe. Du kannst noch keine Lösungen posten."
    if normalized == "rejected":
        return "Dein Account wurde abgelehnt. Du kannst keine Lösungen posten."
    return "Dein Account ist nicht freigegeben."


def parse_submission_form(
    *,
    form_data: Any,
    normalize_model: Callable[[str], str],
    normalize_error_code: Callable[[str], str],
    split_lines: Callable[[str], List[str]],
) -> Dict[str, Any]:
    return {
        "model": normalize_model(form_data.get("model") or ""),
        "error_code": normalize_error_code(form_data.get("error_code") or ""),
        "title": (form_data.get("title") or "").strip(),
        "symptom": (form_data.get("symptom") or "").strip(),
        "cause": (form_data.get("cause") or "").strip(),
        "fix_steps": split_lines(form_data.get("fix_steps") or ""),
        "parts_tools": split_lines(form_data.get("parts_tools") or ""),
        "safety_note": (form_data.get("safety_note") or "").strip(),
    }


def resolve_review_status_filter(*, form_status: str, args_status: str, default: str = "pending") -> str:
    status = (form_status or args_status or default).strip()
    return status or default


def parse_decision_note(raw_note: str) -> Optional[str]:
    note = (raw_note or "").strip()
    return note or None


def reject_note_error(decision_note: Optional[str]) -> Optional[str]:
    if decision_note:
        return None
    return "Ablehnung benötigt eine Begründung."


def validate_submission(
    *,
    model: str,
    error_code: str,
    title: str,
    symptom: str,
    cause: str,
    fix_steps: List[str],
    submission_count_24h: int,
    max_submissions_24h: int = 3,
) -> Optional[str]:
    if not model:
        return "Modell ist erforderlich."
    if not error_code:
        return "Fehlercode ist erforderlich."
    if not title:
        return "Titel ist erforderlich."
    if not symptom:
        return "Symptom ist erforderlich."
    if not cause:
        return "Ursache ist erforderlich."
    if not fix_steps:
        return "Mindestens ein Schritt ist erforderlich."
    if submission_count_24h >= max_submissions_24h:
        return "Limit erreicht: max. 3 Einsendungen pro 24h."
    return None


def build_submission_payload(
    *,
    model: str,
    error_code: str,
    title: str,
    symptom: str,
    cause: str,
    fix_steps: List[str],
    parts_tools: List[str],
    safety_note: str,
    user: Dict[str, Any],
    timestamp: str,
) -> Dict[str, Any]:
    return {
        "solution_id": uuid.uuid4().hex,
        "model": model,
        "error_code": error_code,
        "title": title,
        "symptom": symptom,
        "cause": cause,
        "fix_steps": fix_steps,
        "parts_tools": parts_tools,
        "safety_note": safety_note,
        "status": "pending",
        "created_by": user.get("user_id"),
        "created_display_name": user.get("display_name"),
        "created_at": timestamp,
        "reviewed_by": None,
        "reviewed_at": None,
        "decision_note": None,
    }


def apply_solution_updates(
    *,
    solution: Dict[str, Any],
    form_data: Any,
    normalize_model: Callable[[str], str],
    normalize_error_code: Callable[[str], str],
    split_lines: Callable[[str], List[str]],
) -> None:
    solution["model"] = normalize_model(form_data.get("model") or solution.get("model") or "")
    solution["error_code"] = normalize_error_code(form_data.get("error_code") or solution.get("error_code") or "")
    solution["title"] = (form_data.get("title") or solution.get("title") or "").strip()
    solution["symptom"] = (form_data.get("symptom") or solution.get("symptom") or "").strip()
    solution["cause"] = (form_data.get("cause") or solution.get("cause") or "").strip()
    solution["fix_steps"] = split_lines(form_data.get("fix_steps") or "\n".join(solution.get("fix_steps") or []))
    solution["parts_tools"] = split_lines(form_data.get("parts_tools") or "\n".join(solution.get("parts_tools") or []))
    solution["safety_note"] = (form_data.get("safety_note") or solution.get("safety_note") or "").strip()


def apply_review_decision(
    *,
    solutions: List[Dict[str, Any]],
    solution_id: str,
    decision: str,
    decision_note: Optional[str],
    reviewer_id: Optional[str],
    reviewed_at: str,
    form_data: Any,
    normalize_model: Callable[[str], str],
    normalize_error_code: Callable[[str], str],
    split_lines: Callable[[str], List[str]],
) -> bool:
    for solution in solutions:
        if solution.get("solution_id") != solution_id:
            continue
        apply_solution_updates(
            solution=solution,
            form_data=form_data,
            normalize_model=normalize_model,
            normalize_error_code=normalize_error_code,
            split_lines=split_lines,
        )
        solution["status"] = decision
        solution["reviewed_by"] = reviewer_id
        solution["reviewed_at"] = reviewed_at
        solution["decision_note"] = decision_note
        return True
    return False


def partition_review_lists(
    *,
    solutions: List[Dict[str, Any]],
    solution_status: Callable[[Dict[str, Any]], str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    pending = [s for s in solutions if solution_status(s) == "pending"]
    approved = [s for s in solutions if solution_status(s) == "approved"]
    rejected = [s for s in solutions if solution_status(s) == "rejected"]
    return pending, approved, rejected


def normalize_status_filter(
    *,
    status_filter: str,
    default: str = "pending",
    allowed: Tuple[str, ...] = ("pending", "approved", "rejected", "all"),
) -> str:
    normalized = (status_filter or default).strip().lower()
    if normalized not in allowed:
        return default
    return normalized


def filter_by_status(
    *,
    items: List[Dict[str, Any]],
    status_filter: str,
    status_resolver: Callable[[Dict[str, Any]], str],
) -> List[Dict[str, Any]]:
    if status_filter == "all":
        return list(items)
    return [item for item in items if status_resolver(item) == status_filter]


def sort_by_created_at_desc(
    *,
    items: List[Dict[str, Any]],
    parse_ts: Callable[[Optional[str]], Optional[datetime]],
) -> List[Dict[str, Any]]:
    items.sort(key=lambda item: parse_ts(item.get("created_at")) or datetime.min, reverse=True)
    return items


def apply_simple_review_decision(
    *,
    items: List[Dict[str, Any]],
    id_field: str,
    id_value: str,
    decision: str,
    decision_note: Optional[str],
    reviewer_id: Optional[str],
    reviewed_at: str,
) -> bool:
    for item in items:
        if item.get(id_field) != id_value:
            continue
        item["status"] = decision
        item["reviewed_by"] = reviewer_id
        item["reviewed_at"] = reviewed_at
        item["decision_note"] = decision_note
        return True
    return False


def build_admin_dashboard_context(
    *,
    users: List[Dict[str, Any]],
    solutions: List[Dict[str, Any]],
    user_status: Callable[[Dict[str, Any]], str],
    solution_status: Callable[[Dict[str, Any]], str],
) -> Dict[str, Any]:
    pending_users = [u for u in users if user_status(u) == "pending"]
    pending_solutions = [s for s in solutions if solution_status(s) == "pending"]
    return {
        "pending_users_count": len(pending_users),
        "pending_solutions_count": len(pending_solutions),
    }


def build_admin_list_context(
    *,
    items: List[Dict[str, Any]],
    requested_status: str,
    status_resolver: Callable[[Dict[str, Any]], str],
    parse_ts: Callable[[Optional[str]], Optional[datetime]],
    normalize_status_filter: Callable[..., str],
) -> Dict[str, Any]:
    status_filter = normalize_status_filter(status_filter=requested_status or "pending")
    filtered = filter_by_status(
        items=items,
        status_filter=status_filter,
        status_resolver=status_resolver,
    )
    sorted_items = sort_by_created_at_desc(items=filtered, parse_ts=parse_ts)
    return {
        "items": sorted_items,
        "status_filter": status_filter,
    }


def execute_simple_review_action(
    *,
    items: List[Dict[str, Any]],
    id_field: str,
    id_value: str,
    decision: str,
    raw_decision_note: str,
    reviewer_id: Optional[str],
    reviewed_at: str,
    form_status: str,
    args_status: str,
    success_message: str,
    not_found_message: str,
    require_note_for_reject: bool = False,
) -> Dict[str, Any]:
    decision_note = parse_decision_note(raw_decision_note)
    if require_note_for_reject:
        decision_error = reject_note_error(decision_note)
        if decision_error:
            return {
                "ok": False,
                "validation_error": decision_error,
                "status_filter": resolve_review_status_filter(form_status=form_status, args_status=args_status),
            }

    updated = apply_simple_review_decision(
        items=items,
        id_field=id_field,
        id_value=id_value,
        decision=decision,
        decision_note=decision_note,
        reviewer_id=reviewer_id,
        reviewed_at=reviewed_at,
    )

    return {
        "ok": updated,
        "validation_error": None,
        "flash_message": success_message if updated else not_found_message,
        "flash_category": "success" if updated else "error",
        "status_filter": resolve_review_status_filter(form_status=form_status, args_status=args_status),
    }


def execute_solution_review_action(
    *,
    solutions: List[Dict[str, Any]],
    solution_id: str,
    decision: str,
    raw_decision_note: str,
    reviewer_id: Optional[str],
    reviewed_at: str,
    form_data: Any,
    normalize_model: Callable[[str], str],
    normalize_error_code: Callable[[str], str],
    split_lines: Callable[[str], List[str]],
    success_message: str,
    not_found_message: str,
    require_note_for_reject: bool = False,
) -> Dict[str, Any]:
    decision_note = parse_decision_note(raw_decision_note)
    if require_note_for_reject:
        decision_error = reject_note_error(decision_note)
        if decision_error:
            return {
                "ok": False,
                "validation_error": decision_error,
            }

    updated = apply_review_decision(
        solutions=solutions,
        solution_id=solution_id,
        decision=decision,
        decision_note=decision_note,
        reviewer_id=reviewer_id,
        reviewed_at=reviewed_at,
        form_data=form_data,
        normalize_model=normalize_model,
        normalize_error_code=normalize_error_code,
        split_lines=split_lines,
    )

    return {
        "ok": updated,
        "validation_error": None,
        "flash_message": success_message if updated else not_found_message,
        "flash_category": "success" if updated else "error",
    }
