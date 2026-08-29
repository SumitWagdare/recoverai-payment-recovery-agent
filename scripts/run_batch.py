#!/usr/bin/env python3
"""
RecoverAI — Batch Processing & Evaluation

Processes all actionable payments through the AI agent and generates
a comparative report: baseline (no AI) vs AI-assisted recovery.

Usage:
    python scripts/run_batch.py
"""

import copy
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import ai_engine, audit_log, recovery_agent

IST = timezone(timedelta(hours=5, minutes=30))

SEPARATOR = "─" * 70
DOUBLE_SEP = "═" * 70


def main():
    import random
    random.seed(42)
    print(f"\n{DOUBLE_SEP}")
    print("  RecoverAI — Batch Processing & Evaluation Report")
    print(DOUBLE_SEP)

    # ── 1. Regenerate fresh data for a clean evaluation ───────────────
    print("\n📊 Regenerating fresh synthetic dataset...")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_data.py")],
        check=True,
    )
    audit_log.clear_log()

    payments = recovery_agent.load_payments()
    baseline = copy.deepcopy(payments)
    total = len(payments)

    # ── 2. Baseline stats (before AI) ─────────────────────────────────
    b_rec = [p for p in baseline if p["recovery_status"] == "recovered"]
    b_pen = [p for p in baseline if p["recovery_status"] == "pending"]
    b_fail = [p for p in baseline if p["recovery_status"] == "failed"]
    b_esc = [p for p in baseline if p["recovery_status"] == "escalated"]
    b_rate = len(b_rec) / total * 100
    b_amount = sum(p["amount"] for p in b_rec)

    print(f"\n{SEPARATOR}")
    print("BASELINE  (status-quo without AI agent)")
    print(SEPARATOR)
    print(f"  Total payments:     {total}")
    print(f"  Recovered:          {len(b_rec)} ({b_rate:.1f}%)")
    print(f"  Pending:            {len(b_pen)}")
    print(f"  Failed:             {len(b_fail)}")
    print(f"  Escalated:          {len(b_esc)}")
    print(f"  Revenue recovered:  ₹{b_amount:,.2f}")

    # ── 3. Run the AI agent on every actionable payment ───────────────
    print(f"\n{SEPARATOR}")
    print("RUNNING AI AGENT ON ALL ACTIONABLE PAYMENTS")
    print(SEPARATOR)

    actionable = [
        p for p in payments if p["recovery_status"] in ("pending", "failed")
    ]

    stats = {
        "processed": 0,
        "auto_approved": 0,
        "awaiting_approval": 0,
        "stopped": 0,
        "duplicate_blocked": 0,
        "actions": {},
        "categories": {},
        "stop_reasons": [],
        "graceful_failures": [],
    }

    for i, payment in enumerate(actionable):
        pid = payment["payment_id"]
        result = recovery_agent.process_payment(pid)
        stats["processed"] += 1

        if result.get("stopped"):
            stats["stopped"] += 1
            if result.get("duplicate_blocked"):
                stats["duplicate_blocked"] += 1
            stats["stop_reasons"].append({
                "payment_id": pid,
                "reason": result.get("stop_reason", "unknown"),
                "amount": payment["amount"],
                "duplicate": result.get("duplicate_blocked", False),
            })
            continue

        # Record classification
        if result.get("classification"):
            cat = result["classification"]["category"]
            stats["categories"][cat] = stats["categories"].get(cat, 0) + 1

        # Record action
        if result.get("recommendation"):
            act = result["recommendation"]["action"]
            stats["actions"][act] = stats["actions"].get(act, 0) + 1

        # Record approval
        if result.get("approval_status") == "auto_approved":
            stats["auto_approved"] += 1
        elif result.get("approval_status") == "awaiting_approval":
            stats["awaiting_approval"] += 1

            # Capture graceful-failure examples
            conf = result.get("classification", {}).get("confidence", 1.0)
            seg = payment.get("customer_segment", "")
            reason_tag = None
            if conf < 0.85:
                reason_tag = f"Low confidence ({conf:.0%}) — routed to manual review"
            elif seg == "churning":
                reason_tag = "Churning customer — requires human judgement"
            elif payment.get("amount", 0) > recovery_agent.HIGH_VALUE_THRESHOLD:
                reason_tag = f"High-value payment (₹{payment['amount']:,.0f}) — human approval mandatory"
            elif result["recommendation"]["action"] == "escalate_to_support":
                reason_tag = "System-level failure — escalated for investigation"

            if reason_tag:
                stats["graceful_failures"].append({
                    "payment_id": pid,
                    "amount": payment["amount"],
                    "failure_reason": payment["failure_reason"],
                    "customer_segment": seg,
                    "classification": result["classification"],
                    "recommendation": result["recommendation"],
                    "reason": reason_tag,
                })

        if (i + 1) % 20 == 0:
            print(f"  Processed {i + 1}/{len(actionable)}...")

    print(f"  ✅ Processed {stats['processed']}/{len(actionable)} actionable payments")

    # ── 4. Post-processing stats (after AI) ───────────────────────────
    post = recovery_agent.load_payments()
    a_rec = [p for p in post if p["recovery_status"] == "recovered"]
    a_pen = [p for p in post if p["recovery_status"] == "pending"]
    a_fail = [p for p in post if p["recovery_status"] == "failed"]
    a_esc = [p for p in post if p["recovery_status"] == "escalated"]
    a_rate = len(a_rec) / total * 100
    a_amount = sum(p["amount"] for p in a_rec)
    unsafe_blocked = stats["awaiting_approval"]  # actions held for human review

    # ── 5. Comparison table ───────────────────────────────────────────
    print(f"\n{DOUBLE_SEP}")
    print("  RESULTS: BASELINE  vs  AI-ASSISTED")
    print(DOUBLE_SEP)

    hdr = f"  {'Metric':<35} {'Baseline':>12} {'AI-Assisted':>12} {'Delta':>10}"
    rule = f"  {'─' * 69}"
    print(f"\n{hdr}\n{rule}")
    print(f"  {'Recovery Rate':<35} {b_rate:>11.1f}% {a_rate:>11.1f}% {a_rate - b_rate:>+9.1f}%")
    print(f"  {'Revenue Recovered':<35} {'₹'+f'{b_amount:,.0f}':>12} {'₹'+f'{a_amount:,.0f}':>12} {'₹'+f'{a_amount - b_amount:,.0f}':>10}")
    print(f"  {'Recovered Cases':<35} {len(b_rec):>12} {len(a_rec):>12} {len(a_rec) - len(b_rec):>+10}")
    print(f"  {'Pending Cases':<35} {len(b_pen):>12} {len(a_pen):>12} {len(a_pen) - len(b_pen):>+10}")
    print(f"  {'Failed Cases':<35} {len(b_fail):>12} {len(a_fail):>12} {len(a_fail) - len(b_fail):>+10}")
    print(f"  {'Escalated Cases':<35} {len(b_esc):>12} {len(a_esc):>12} {len(a_esc) - len(b_esc):>+10}")

    print(f"\n{rule}")
    print(f"  {'AI Agent Summary':}")
    print(f"  {'Total processed':<35} {stats['processed']:>12}")
    print(f"  {'Auto-approved (safe actions)':<35} {stats['auto_approved']:>12}")
    print(f"  {'Awaiting human approval':<35} {stats['awaiting_approval']:>12}")
    print(f"  {'Stopped by safety controls':<35} {stats['stopped']:>12}")
    print(f"  {'Unsafe-action blocks (held)':<35} {unsafe_blocked:>12}")
    print(f"  {'Duplicate-contact blocks':<35} {stats['duplicate_blocked']:>12}")

    print(f"\n  Action Distribution:")
    for act, cnt in sorted(stats["actions"].items(), key=lambda x: -x[1]):
        print(f"    {act.replace('_', ' ').title():<33} {cnt:>10}")

    print(f"\n  Classification Distribution:")
    for cat, cnt in sorted(stats["categories"].items(), key=lambda x: -x[1]):
        print(f"    {cat.replace('_', ' ').title():<33} {cnt:>10}")

    # ── 6. Action accuracy (expected vs actual) ───────────────────────
    expected_actions = {
        "bank_server_down": "retry_later",
        "network_timeout": "retry_later",
        "insufficient_funds": "send_payment_link",
        "card_expired": "request_alt_method",
        "upi_pin_not_set": "request_alt_method",
        "payment_cancelled": "send_payment_link",
        "invalid_card": "request_alt_method",
        "emandate_debit_failed": "request_alt_method",
        "risk_check_failed": "escalate_to_support",
        "authentication_failed": "escalate_to_support",
    }

    all_entries = audit_log.read_all()
    correct = 0
    total_checked = 0
    for entry in all_entries:
        if entry.get("approval_status") == "blocked":
            continue  # skip duplicate-blocked entries
        snap = entry.get("input_snapshot", {})
        reason = snap.get("failure_reason", "")
        expected = expected_actions.get(reason)
        if expected:
            total_checked += 1
            actual = entry.get("recommended_action", "")
            # Account for max-retry fallback
            if snap.get("retry_count", 0) >= 3 and expected == "retry_later":
                expected = "send_payment_link"
            if snap.get("retry_count", 0) >= 2 and reason in ("invalid_card", "emandate_debit_failed"):
                expected = "escalate_to_support"
            if actual == expected:
                correct += 1

    accuracy = (correct / total_checked * 100) if total_checked else 0
    print(f"\n{rule}")
    print(f"  {'Action Accuracy':<35} {correct}/{total_checked} ({accuracy:.1f}%)")

    # ── 7. Graceful failure examples ──────────────────────────────────
    print(f"\n{SEPARATOR}")
    print("GRACEFUL FAILURE EXAMPLES")
    print("(Ambiguous / high-risk cases routed to manual review)")
    print(SEPARATOR)

    # If we didn't capture enough, pull from awaiting_approval entries
    if len(stats["graceful_failures"]) < 3:
        for entry in all_entries:
            if entry["approval_status"] == "awaiting_approval":
                snap = entry.get("input_snapshot", {})
                stats["graceful_failures"].append({
                    "payment_id": entry["payment_id"],
                    "amount": snap.get("amount", 0),
                    "failure_reason": snap.get("failure_reason", "unknown"),
                    "customer_segment": snap.get("customer_segment", "unknown"),
                    "classification": entry.get("classification", {}),
                    "recommendation": {
                        "action": entry["recommended_action"],
                        "reasoning": entry["action_reasoning"],
                    },
                    "reason": "Requires human approval for customer communication",
                })
                if len(stats["graceful_failures"]) >= 5:
                    break

    for i, gf in enumerate(stats["graceful_failures"][:5], 1):
        cls = gf.get("classification", {})
        rec = gf.get("recommendation", {})
        print(f"\n  Example {i}:")
        print(f"    Payment:    {gf['payment_id']}")
        print(f"    Amount:     ₹{gf['amount']:,.2f}")
        print(f"    Failure:    {gf['failure_reason']}")
        print(f"    Segment:    {gf.get('customer_segment', 'N/A')}")
        print(f"    Category:   {cls.get('category', 'N/A')} ({cls.get('confidence', 0):.0%} confidence)")
        print(f"    Rec. Action:{rec.get('action', 'N/A')}")
        print(f"    → {gf['reason']}")

    # ── 8. Unresolved cases ───────────────────────────────────────────
    unresolved = [p for p in post if p["recovery_status"] in ("pending", "failed")]
    print(f"\n{SEPARATOR}")
    print(f"UNRESOLVED CASES: {len(unresolved)}")
    print(SEPARATOR)
    print(f"  Still pending:  {sum(1 for p in unresolved if p['recovery_status'] == 'pending')}")
    print(f"  Still failed:   {sum(1 for p in unresolved if p['recovery_status'] == 'failed')}")
    print(f"  Total amount:   ₹{sum(p['amount'] for p in unresolved):,.2f}")

    # ── 9. Audit log summary ──────────────────────────────────────────
    print(f"\n{SEPARATOR}")
    print(f"AUDIT LOG: {len(all_entries)} entries")
    print(SEPARATOR)
    by_approval = {}
    for e in all_entries:
        s = e.get("approval_status", "unknown")
        by_approval[s] = by_approval.get(s, 0) + 1
    for status, count in sorted(by_approval.items()):
        print(f"  {status:<25} {count:>5}")

    print(f"\n{DOUBLE_SEP}")
    print("  Evaluation complete.")
    print(DOUBLE_SEP)

    # ── 10. Save structured report ────────────────────────────────────
    report = {
        "baseline": {
            "total": total,
            "recovered": len(b_rec),
            "pending": len(b_pen),
            "failed": len(b_fail),
            "escalated": len(b_esc),
            "recovery_rate": round(b_rate, 1),
            "revenue_recovered": round(b_amount, 2),
        },
        "ai_assisted": {
            "total": total,
            "recovered": len(a_rec),
            "pending": len(a_pen),
            "failed": len(a_fail),
            "escalated": len(a_esc),
            "recovery_rate": round(a_rate, 1),
            "revenue_recovered": round(a_amount, 2),
        },
        "agent_stats": {
            "processed": stats["processed"],
            "auto_approved": stats["auto_approved"],
            "awaiting_approval": stats["awaiting_approval"],
            "stopped": stats["stopped"],
            "unsafe_blocked": unsafe_blocked,
            "duplicate_blocked": stats["duplicate_blocked"],
            "action_accuracy_pct": round(accuracy, 1),
            "actions": stats["actions"],
            "categories": stats["categories"],
        },
        "graceful_failures_count": len(stats["graceful_failures"]),
        "unresolved_count": len(unresolved),
        "unresolved_amount": round(sum(p["amount"] for p in unresolved), 2),
        "audit_entries": len(all_entries),
    }

    report_path = ROOT / "evaluation" / "batch_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n📁 JSON report → {report_path}")


if __name__ == "__main__":
    main()
