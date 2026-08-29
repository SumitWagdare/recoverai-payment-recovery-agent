"""
RecoverAI — Recovery Agent

Orchestrates the payment recovery workflow with safety controls:
  • Maximum retry limits  (3 per payment)
  • Cooldown periods      (4 h between retries)
  • Stop conditions       (recovered, opted-out, max-retries)
  • Human approval        (high-value, escalations, customer-facing comms)

⚠️ SAFETY: All "executions" are simulations. No real payments
or customer communications are ever triggered.
"""

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import ai_engine, audit_log

IST = timezone(timedelta(hours=5, minutes=30))
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic_payments.json"

# ── Safety Configuration ──────────────────────────────────────────────────────
MAX_RETRIES = 3
COOLDOWN_HOURS = 4
HIGH_VALUE_THRESHOLD = 10_000  # INR
CONTACT_COOLDOWN_HOURS = 24
CUSTOMER_FACING_ACTIONS = {"send_payment_link", "request_alt_method"}


# ── Data helpers ──────────────────────────────────────────────────────────────

def load_payments() -> list[dict]:
    """Load payments from the synthetic dataset."""
    if not DATA_PATH.exists():
        return []
    with open(DATA_PATH, "r") as f:
        return json.load(f)


def save_payments(payments: list[dict]):
    """Save payments back to the dataset."""
    try:
        with open(DATA_PATH, "w") as f:
            json.dump(payments, f, indent=2, ensure_ascii=False)
    except OSError:
        pass  # Vercel read-only filesystem handling


def get_payment(payment_id: str) -> dict | None:
    """Get a specific payment by ID."""
    for p in load_payments():
        if p["payment_id"] == payment_id:
            return p
    return None


# ── Safety checks ─────────────────────────────────────────────────────────────

def _check_stop_conditions(payment: dict) -> tuple[bool, str]:
    """
    Check whether recovery should be halted.

    Returns (should_stop, reason).
    """
    if payment.get("recovery_status") == "recovered":
        return True, "Payment has already been recovered."

    if payment.get("retry_history"):
        last_retry = payment["retry_history"][-1]
        last_ts = datetime.fromisoformat(last_retry["timestamp"])
        now = datetime.now(IST)
        if (now - last_ts) < timedelta(hours=COOLDOWN_HOURS):
            remaining = timedelta(hours=COOLDOWN_HOURS) - (now - last_ts)
            hrs = remaining.seconds // 3600
            mins = (remaining.seconds % 3600) // 60
            return True, f"Cooldown active. Next action allowed in {hrs}h {mins}m."

    return False, ""


def _check_duplicate_contact(payment: dict, action: str) -> tuple[bool, str]:
    """
    Prevent contacting the same customer multiple times within
    CONTACT_COOLDOWN_HOURS. Checks the audit log for recent
    customer-facing actions targeting the same customer_id.

    Returns (is_duplicate, reason).
    """
    if action not in CUSTOMER_FACING_ACTIONS:
        return False, ""

    customer_id = payment.get("customer_id", "")
    if not customer_id:
        return False, ""

    now = datetime.now(IST)
    for entry in audit_log.read_all():
        snap = entry.get("input_snapshot", {})
        if snap.get("customer_id") != customer_id:
            continue
        if entry.get("recommended_action") not in CUSTOMER_FACING_ACTIONS:
            continue
        if entry.get("approval_status") == "rejected":
            continue
        entry_ts = datetime.fromisoformat(entry["timestamp"])
        if (now - entry_ts) < timedelta(hours=CONTACT_COOLDOWN_HOURS):
            return True, (
                f"Duplicate-contact prevention: customer {customer_id} was "
                f"already contacted via '{entry['recommended_action']}' at "
                f"{entry['timestamp']}. Next contact allowed after "
                f"{CONTACT_COOLDOWN_HOURS}h cooldown."
            )

    return False, ""


# ── Core pipeline ─────────────────────────────────────────────────────────────

def process_payment(payment_id: str) -> dict:
    """
    Run the full AI decision pipeline on a payment.

    Returns classification, recommendation, and approval requirements.
    """
    payment = get_payment(payment_id)
    if not payment:
        return {"error": f"Payment {payment_id} not found."}

    # Stop-condition gate
    should_stop, stop_reason = _check_stop_conditions(payment)
    if should_stop:
        return {
            "payment_id": payment_id,
            "stopped": True,
            "stop_reason": stop_reason,
            "classification": None,
            "recommendation": None,
        }

    # AI classification
    classification = ai_engine.classify_failure(payment)

    # Action recommendation
    recommendation = ai_engine.recommend_action(payment, classification)

    # Enforce max-retry limit
    if (
        recommendation["action"] == "retry_later"
        and payment.get("retry_count", 0) >= MAX_RETRIES
    ):
        recommendation = {
            "action": "send_payment_link",
            "reasoning": (
                f"Maximum retry limit ({MAX_RETRIES}) reached. "
                f"Switching to payment link instead of further retries."
            ),
            "requires_approval": True,
            "priority": recommendation.get("priority", "high"),
        }

    # Duplicate-contact prevention
    is_duplicate, dup_reason = _check_duplicate_contact(
        payment, recommendation["action"]
    )
    if is_duplicate:
        blocked_entry = audit_log.append_entry(
            payment_id=payment_id,
            input_snapshot=payment,
            classification=classification,
            recommended_action=recommendation["action"],
            action_reasoning=recommendation["reasoning"],
            requires_approval=False,
            approval_status="blocked",
            approved_by="system",
            execution_result="blocked",
            notes=dup_reason,
        )
        return {
            "payment_id": payment_id,
            "stopped": True,
            "stop_reason": dup_reason,
            "classification": classification,
            "recommendation": recommendation,
            "duplicate_blocked": True,
            "audit_id": blocked_entry["audit_id"],
        }

    # High-value payments always need approval
    needs_approval = recommendation["requires_approval"]
    if payment.get("amount", 0) > HIGH_VALUE_THRESHOLD:
        needs_approval = True
        recommendation["requires_approval"] = True

    approval_status = "awaiting_approval" if needs_approval else "auto_approved"

    # Audit trail
    audit_entry = audit_log.append_entry(
        payment_id=payment_id,
        input_snapshot=payment,
        classification=classification,
        recommended_action=recommendation["action"],
        action_reasoning=recommendation["reasoning"],
        requires_approval=needs_approval,
        approval_status=approval_status,
        approved_by="system" if not needs_approval else "",
        execution_result="pending",
    )

    # Auto-execute safe actions
    if not needs_approval:
        result = _simulate_action(payment, recommendation["action"])
        audit_log.update_entry(audit_entry["audit_id"], {
            "execution_result": result["status"],
            "notes": result["message"],
        })
        _update_payment_status(payment_id, recommendation["action"], result["status"])

    return {
        "payment_id": payment_id,
        "stopped": False,
        "classification": classification,
        "recommendation": recommendation,
        "approval_status": approval_status,
        "audit_id": audit_entry["audit_id"],
    }


def approve_action(
    payment_id: str,
    audit_id: str,
    approved_by: str = "human_operator",
) -> dict:
    """Human approves a pending action."""
    audit_log.update_entry(audit_id, {
        "approval_status": "approved",
        "approved_by": approved_by,
    })

    entries = audit_log.get_entries_for_payment(payment_id)
    target = next((e for e in entries if e["audit_id"] == audit_id), None)
    if not target:
        return {"error": "Audit entry not found."}

    payment = get_payment(payment_id)
    if not payment:
        return {"error": "Payment not found."}

    result = _simulate_action(payment, target["recommended_action"])
    audit_log.update_entry(audit_id, {
        "execution_result": result["status"],
        "notes": f"Approved by {approved_by}. {result['message']}",
    })
    _update_payment_status(payment_id, target["recommended_action"], result["status"])

    return {
        "payment_id": payment_id,
        "audit_id": audit_id,
        "action": target["recommended_action"],
        "approval_status": "approved",
        "execution_result": result,
    }


def reject_action(
    payment_id: str,
    audit_id: str,
    rejected_by: str = "human_operator",
    reason: str = "",
) -> dict:
    """Human rejects a pending action."""
    note = f"Rejected by {rejected_by}."
    if reason:
        note += f" Reason: {reason}"

    audit_log.update_entry(audit_id, {
        "approval_status": "rejected",
        "approved_by": rejected_by,
        "execution_result": "rejected",
        "notes": note,
    })

    return {
        "payment_id": payment_id,
        "audit_id": audit_id,
        "approval_status": "rejected",
        "reason": reason,
    }


# ── Action simulation ─────────────────────────────────────────────────────────

def _simulate_action(payment: dict, action: str) -> dict:
    """
    Simulate executing a recovery action.

    ⚠️ SAFETY: This is a simulation only. No real payments or
    customer communications are triggered.
    """
    rng = random.Random(hash(payment.get("payment_id", "")) + hash(action))

    sims = {
        "retry_later": (0.45, "Simulated retry succeeded. Payment recovered.",
                              "Simulated retry failed. Same error persists."),
        "send_payment_link": (0.60, "Simulated payment link sent. Customer completed payment.",
                                    "Simulated payment link sent. Awaiting customer action."),
        "request_alt_method": (0.35, "Simulated request sent. Customer provided alternative method.",
                                     "Simulated request sent. No response from customer yet."),
        "escalate_to_support": (0.70, "Escalated to support team. Ticket created.",
                                      "Escalated to support team. Ticket created, awaiting assignment."),
    }

    rate, ok_msg, fail_msg = sims.get(action, sims["escalate_to_support"])
    success = rng.random() < rate

    return {
        "status": "success" if success else "pending",
        "message": ok_msg if success else fail_msg,
        "simulated": True,
    }


def _update_payment_status(payment_id: str, action: str, result_status: str):
    """Update the payment's recovery status based on the action result."""
    payments = load_payments()
    for p in payments:
        if p["payment_id"] == payment_id:
            if result_status == "success":
                p["recovery_status"] = "recovered"
            elif action == "escalate_to_support":
                p["recovery_status"] = "escalated"
            elif result_status == "rejected":
                pass  # No change on rejection
            else:
                p["recovery_status"] = "pending"
            break
    save_payments(payments)


# ── Dashboard stats ───────────────────────────────────────────────────────────

def get_dashboard_stats() -> dict:
    """Calculate aggregated dashboard statistics."""
    payments = load_payments()

    if not payments:
        return {
            "total_failed_amount": 0, "recoverable_amount": 0,
            "recovery_rate": 0, "pending_cases": 0,
            "total_cases": 0, "recovered_cases": 0,
            "escalated_cases": 0, "failed_cases": 0,
            "by_failure_reason": {}, "by_payment_method": {},
            "by_customer_segment": {},
        }

    total_amount = sum(p["amount"] for p in payments)
    recovered = [p for p in payments if p["recovery_status"] == "recovered"]
    pending   = [p for p in payments if p["recovery_status"] == "pending"]
    escalated = [p for p in payments if p["recovery_status"] == "escalated"]
    failed    = [p for p in payments if p["recovery_status"] == "failed"]

    recovered_amount = sum(p["amount"] for p in recovered)
    pending_amount   = sum(p["amount"] for p in pending)
    recoverable_amount = recovered_amount + pending_amount

    recovery_rate = (len(recovered) / len(payments) * 100) if payments else 0

    def _breakdown(key):
        out = {}
        for p in payments:
            v = p.get(key, "unknown")
            out.setdefault(v, {"count": 0, "amount": 0})
            out[v]["count"] += 1
            out[v]["amount"] = round(out[v]["amount"] + p["amount"], 2)
        return out

    return {
        "total_failed_amount": round(total_amount, 2),
        "recoverable_amount": round(recoverable_amount, 2),
        "recovery_rate": round(recovery_rate, 1),
        "pending_cases": len(pending),
        "total_cases": len(payments),
        "recovered_cases": len(recovered),
        "escalated_cases": len(escalated),
        "failed_cases": len(failed),
        "by_failure_reason": _breakdown("failure_reason"),
        "by_payment_method": _breakdown("payment_method"),
        "by_customer_segment": _breakdown("customer_segment"),
    }
