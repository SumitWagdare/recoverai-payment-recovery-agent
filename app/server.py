"""
RecoverAI — Flask API Server

Serves the REST API and the dashboard SPA.

⚠️ SAFETY: This server operates on synthetic data only.
"""

from flask import Flask, jsonify, request, send_from_directory
from pathlib import Path

from . import recovery_agent, audit_log

app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static",
)


# ── Dashboard SPA ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.route("/api/dashboard")
def dashboard_stats():
    return jsonify(recovery_agent.get_dashboard_stats())


@app.route("/api/payments")
def list_payments():
    payments = recovery_agent.load_payments()

    # Optional query-string filters
    status  = request.args.get("status")
    method  = request.args.get("method")
    segment = request.args.get("segment")

    if status:
        payments = [p for p in payments if p["recovery_status"] == status]
    if method:
        payments = [p for p in payments if p["payment_method"] == method]
    if segment:
        payments = [p for p in payments if p["customer_segment"] == segment]

    payments.sort(key=lambda p: p.get("timestamp", ""), reverse=True)
    return jsonify({"payments": payments, "total": len(payments)})


@app.route("/api/payments/<payment_id>")
def get_payment(payment_id):
    payment = recovery_agent.get_payment(payment_id)
    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    audit_history = audit_log.get_entries_for_payment(payment_id)
    return jsonify({"payment": payment, "audit_history": audit_history})


@app.route("/api/payments/<payment_id>/process", methods=["POST"])
def process_payment(payment_id):
    result = recovery_agent.process_payment(payment_id)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


@app.route("/api/payments/<payment_id>/approve", methods=["POST"])
def approve_payment(payment_id):
    data = request.get_json() or {}
    audit_id    = data.get("audit_id", "")
    approved_by = data.get("approved_by", "human_operator")

    if not audit_id:
        return jsonify({"error": "audit_id is required"}), 400

    result = recovery_agent.approve_action(payment_id, audit_id, approved_by)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


@app.route("/api/payments/<payment_id>/reject", methods=["POST"])
def reject_payment(payment_id):
    data = request.get_json() or {}
    audit_id    = data.get("audit_id", "")
    rejected_by = data.get("rejected_by", "human_operator")
    reason      = data.get("reason", "")

    if not audit_id:
        return jsonify({"error": "audit_id is required"}), 400

    result = recovery_agent.reject_action(payment_id, audit_id, rejected_by, reason)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


@app.route("/api/audit-log")
def get_audit_log():
    entries = audit_log.read_all()
    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return jsonify({"entries": entries, "total": len(entries)})

@app.route("/api/evaluation")
def get_evaluation():
    report_path = Path(__file__).resolve().parent.parent / "evaluation" / "batch_report.json"
    if not report_path.exists():
        return jsonify({"error": "Evaluation report not found"}), 404
    import json
    with open(report_path, "r") as f:
        data = json.load(f)
    return jsonify(data)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
