#!/usr/bin/env python3
"""
RecoverAI — Synthetic Failed-Payment Data Generator

Generates 120 realistic failed-payment records using Razorpay
test-mode failure concepts. All data is entirely synthetic.

Usage:
    python scripts/generate_data.py
"""

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# --- Configuration ---
NUM_RECORDS = 120
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic_payments.json"
IST = timezone(timedelta(hours=5, minutes=30))

# --- Distributions ---
PAYMENT_METHODS = {
    "upi": 0.35,
    "card": 0.30,
    "netbanking": 0.15,
    "wallet": 0.12,
    "emandate": 0.08,
}

FAILURE_REASONS = {
    "insufficient_funds":      {"weight": 0.20, "methods": ["card", "upi", "netbanking", "wallet", "emandate"]},
    "card_expired":            {"weight": 0.12, "methods": ["card"]},
    "bank_server_down":        {"weight": 0.12, "methods": ["card", "upi", "netbanking", "emandate"]},
    "authentication_failed":   {"weight": 0.12, "methods": ["card", "upi", "netbanking"]},
    "network_timeout":         {"weight": 0.10, "methods": ["card", "upi", "netbanking", "wallet", "emandate"]},
    "invalid_card":            {"weight": 0.08, "methods": ["card"]},
    "payment_cancelled":       {"weight": 0.08, "methods": ["card", "upi", "netbanking", "wallet"]},
    "risk_check_failed":       {"weight": 0.06, "methods": ["card", "upi", "netbanking"]},
    "emandate_debit_failed":   {"weight": 0.06, "methods": ["emandate"]},
    "upi_pin_not_set":         {"weight": 0.06, "methods": ["upi"]},
}

CUSTOMER_SEGMENTS = {
    "new": 0.25,
    "regular": 0.40,
    "premium": 0.20,
    "churning": 0.15,
}

RECOVERY_STATUSES = {
    "pending": 0.45,
    "recovered": 0.25,
    "failed": 0.20,
    "escalated": 0.10,
}

# Amount ranges in INR
AMOUNT_RANGES = [
    (50, 500, 0.20),
    (500, 2000, 0.30),
    (2000, 5000, 0.25),
    (5000, 15000, 0.15),
    (15000, 50000, 0.10),
]


def weighted_choice(options: dict) -> str:
    """Select from a dict of {option: weight}."""
    items = list(options.keys())
    weights = list(options.values())
    return random.choices(items, weights=weights, k=1)[0]


def generate_amount() -> float:
    """Generate a realistic payment amount."""
    ranges_only = [(lo, hi) for lo, hi, _ in AMOUNT_RANGES]
    weights = [w for _, _, w in AMOUNT_RANGES]
    lo, hi = random.choices(ranges_only, weights=weights, k=1)[0]
    return round(random.uniform(lo, hi), 2)


def generate_timestamp(days_back: int = 30) -> str:
    """Generate a random timestamp within the last N days."""
    now = datetime(2026, 8, 29, 12, 0, 0, tzinfo=IST)
    delta = timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    ts = now - delta
    return ts.isoformat()


def get_failure_reason(method: str) -> str:
    """Pick a failure reason compatible with the payment method."""
    compatible = {
        k: v["weight"]
        for k, v in FAILURE_REASONS.items()
        if method in v["methods"]
    }
    return weighted_choice(compatible)


def generate_retry_history(retry_count: int, base_ts: str, failure_reason: str) -> list:
    """Generate retry history entries."""
    history = []
    base_dt = datetime.fromisoformat(base_ts)
    for i in range(retry_count):
        retry_ts = base_dt + timedelta(hours=random.randint(1, 12) * (i + 1))
        outcome = random.choice(["failed", "failed", "failed", "timeout"])
        history.append({
            "attempt": i + 1,
            "timestamp": retry_ts.isoformat(),
            "outcome": outcome,
            "reason": failure_reason if outcome == "failed" else "network_timeout",
        })
    return history


def generate_record(index: int) -> dict:
    """Generate a single synthetic payment record."""
    payment_id = f"pay_{uuid.UUID(int=random.getrandbits(128)).hex[:12]}"
    customer_id = f"cust_{uuid.UUID(int=random.getrandbits(128)).hex[:8]}"
    method = weighted_choice(PAYMENT_METHODS)
    failure_reason = get_failure_reason(method)
    segment = weighted_choice(CUSTOMER_SEGMENTS)
    status = weighted_choice(RECOVERY_STATUSES)
    amount = generate_amount()
    timestamp = generate_timestamp()
    retry_count = random.choices(
        [0, 1, 2, 3, 4], weights=[0.35, 0.30, 0.20, 0.10, 0.05], k=1
    )[0]

    return {
        "payment_id": payment_id,
        "amount": amount,
        "currency": "INR",
        "payment_method": method,
        "failure_reason": failure_reason,
        "retry_count": retry_count,
        "retry_history": generate_retry_history(retry_count, timestamp, failure_reason),
        "customer_segment": segment,
        "customer_id": customer_id,
        "timestamp": timestamp,
        "recovery_status": status,
    }


def main():
    random.seed(42)  # Reproducible output
    records = [generate_record(i) for i in range(NUM_RECORDS)]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    # Print summary
    total_amount = sum(r["amount"] for r in records)
    by_status = {}
    for r in records:
        by_status.setdefault(r["recovery_status"], []).append(r)

    print(f"✅ Generated {len(records)} synthetic failed-payment records")
    print(f"   📁 Saved to: {OUTPUT_PATH}")
    print(f"   💰 Total failed amount: ₹{total_amount:,.2f}")
    print(f"   📊 Status breakdown:")
    for status, items in sorted(by_status.items()):
        print(f"      {status}: {len(items)}")


if __name__ == "__main__":
    main()
