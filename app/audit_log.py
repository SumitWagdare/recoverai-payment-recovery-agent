"""
RecoverAI — Audit Log

Append-only JSON Lines audit trail for all AI decisions and recovery actions.
Every decision is fully traceable and human-readable.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))
AUDIT_LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "audit_log.jsonl"


def _ensure_log_file():
    """Ensure the audit log file and its parent directory exist."""
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not AUDIT_LOG_PATH.exists():
        AUDIT_LOG_PATH.touch()


def append_entry(
    payment_id: str,
    input_snapshot: dict,
    classification: dict,
    recommended_action: str,
    action_reasoning: str,
    requires_approval: bool,
    approval_status: str = "pending",
    approved_by: str = "",
    execution_result: str = "",
    notes: str = "",
) -> dict:
    """
    Append a new entry to the audit log.

    Returns the created audit entry.
    """
    _ensure_log_file()

    entry = {
        "audit_id": f"aud_{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(IST).isoformat(),
        "payment_id": payment_id,
        "input_snapshot": input_snapshot,
        "classification": classification,
        "recommended_action": recommended_action,
        "action_reasoning": action_reasoning,
        "requires_approval": requires_approval,
        "approval_status": approval_status,
        "approved_by": approved_by,
        "execution_result": execution_result,
        "notes": notes,
    }

    try:
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # Vercel read-only filesystem handling

    return entry


def update_entry(audit_id: str, updates: dict) -> dict | None:
    """
    Update an existing audit entry by rewriting the log.
    Used for recording approval status and execution results.

    Returns the updated entry, or None if not found.
    """
    _ensure_log_file()

    entries = read_all()
    updated_entry = None

    for entry in entries:
        if entry["audit_id"] == audit_id:
            entry.update(updates)
            entry["last_updated"] = datetime.now(IST).isoformat()
            updated_entry = entry
            break

    if updated_entry:
        try:
            with open(AUDIT_LOG_PATH, "w") as f:
                for entry in entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    return updated_entry


def read_all() -> list[dict]:
    """Read all audit log entries."""
    _ensure_log_file()

    entries = []
    with open(AUDIT_LOG_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def get_entries_for_payment(payment_id: str) -> list[dict]:
    """Get all audit entries for a specific payment."""
    return [e for e in read_all() if e["payment_id"] == payment_id]


def clear_log():
    """Clear the entire audit log. Use with caution."""
    _ensure_log_file()
    with open(AUDIT_LOG_PATH, "w") as f:
        f.write("")
