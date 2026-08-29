"""
Tests for the audit-log module.

Covers:
- Entries are appended correctly
- Each entry contains all required fields
- Entries can be updated (approval status, execution result)
- Per-payment retrieval works
- Log can be cleared
"""

import json
import pytest

from app import audit_log


class TestAuditLogCreation:
    """Every AI decision must produce a complete audit entry."""

    def test_append_creates_entry_with_all_fields(self, clean_env):
        _, audit_path = clean_env

        entry = audit_log.append_entry(
            payment_id="pay_audit_001",
            input_snapshot={"amount": 500, "failure_reason": "bank_server_down"},
            classification={"category": "temporary", "confidence": 0.92, "reasoning": "Test"},
            recommended_action="retry_later",
            action_reasoning="Temporary failure, scheduling retry.",
            requires_approval=False,
            approval_status="auto_approved",
            approved_by="system",
            execution_result="success",
            notes="Simulated retry succeeded.",
        )

        assert entry["audit_id"].startswith("aud_")
        assert entry["payment_id"] == "pay_audit_001"
        assert entry["recommended_action"] == "retry_later"
        assert entry["approval_status"] == "auto_approved"
        assert "timestamp" in entry

    def test_required_fields_are_present(self, clean_env):
        _, audit_path = clean_env

        entry = audit_log.append_entry(
            payment_id="pay_fields_001",
            input_snapshot={"amount": 100},
            classification={"category": "temporary", "confidence": 0.9, "reasoning": "R"},
            recommended_action="retry_later",
            action_reasoning="Reason.",
            requires_approval=False,
        )

        required_fields = [
            "audit_id", "timestamp", "payment_id", "input_snapshot",
            "classification", "recommended_action", "action_reasoning",
            "requires_approval", "approval_status", "approved_by",
            "execution_result", "notes",
        ]
        for field in required_fields:
            assert field in entry, f"Missing field: {field}"

    def test_entries_are_persisted_to_file(self, clean_env):
        _, audit_path = clean_env

        audit_log.append_entry(
            payment_id="pay_persist_001",
            input_snapshot={},
            classification={"category": "temporary", "confidence": 0.9, "reasoning": "R"},
            recommended_action="retry_later",
            action_reasoning="Reason.",
            requires_approval=False,
        )

        # Read raw file
        content = audit_path.read_text().strip()
        assert len(content) > 0
        parsed = json.loads(content)
        assert parsed["payment_id"] == "pay_persist_001"

    def test_multiple_entries_are_separate_lines(self, clean_env):
        _, audit_path = clean_env

        for i in range(3):
            audit_log.append_entry(
                payment_id=f"pay_multi_{i:03d}",
                input_snapshot={},
                classification={"category": "temporary", "confidence": 0.9, "reasoning": "R"},
                recommended_action="retry_later",
                action_reasoning="Reason.",
                requires_approval=False,
            )

        lines = [l for l in audit_path.read_text().strip().split("\n") if l]
        assert len(lines) == 3


class TestAuditLogUpdate:
    """Audit entries must be updatable for approval status and results."""

    def test_update_approval_status(self, clean_env):
        _, _ = clean_env

        entry = audit_log.append_entry(
            payment_id="pay_upd_001",
            input_snapshot={},
            classification={"category": "temporary", "confidence": 0.9, "reasoning": "R"},
            recommended_action="send_payment_link",
            action_reasoning="Reason.",
            requires_approval=True,
            approval_status="awaiting_approval",
        )

        updated = audit_log.update_entry(entry["audit_id"], {
            "approval_status": "approved",
            "approved_by": "human_operator",
        })

        assert updated is not None
        assert updated["approval_status"] == "approved"
        assert updated["approved_by"] == "human_operator"
        assert "last_updated" in updated

    def test_update_nonexistent_returns_none(self, clean_env):
        result = audit_log.update_entry("aud_nonexistent_999", {"notes": "test"})
        assert result is None


class TestAuditLogRetrieval:
    """Retrieval helpers must filter and return correct entries."""

    def test_read_all_returns_all_entries(self, clean_env):
        for i in range(5):
            audit_log.append_entry(
                payment_id=f"pay_read_{i:03d}",
                input_snapshot={},
                classification={"category": "temporary", "confidence": 0.9, "reasoning": "R"},
                recommended_action="retry_later",
                action_reasoning="Reason.",
                requires_approval=False,
            )

        entries = audit_log.read_all()
        assert len(entries) == 5

    def test_get_entries_for_payment(self, clean_env):
        audit_log.append_entry(payment_id="pay_a", input_snapshot={},
            classification={"category": "temporary", "confidence": 0.9, "reasoning": "R"},
            recommended_action="retry_later", action_reasoning="R", requires_approval=False)
        audit_log.append_entry(payment_id="pay_b", input_snapshot={},
            classification={"category": "temporary", "confidence": 0.9, "reasoning": "R"},
            recommended_action="retry_later", action_reasoning="R", requires_approval=False)
        audit_log.append_entry(payment_id="pay_a", input_snapshot={},
            classification={"category": "temporary", "confidence": 0.9, "reasoning": "R"},
            recommended_action="send_payment_link", action_reasoning="R", requires_approval=True)

        entries_a = audit_log.get_entries_for_payment("pay_a")
        entries_b = audit_log.get_entries_for_payment("pay_b")
        assert len(entries_a) == 2
        assert len(entries_b) == 1

    def test_clear_log(self, clean_env):
        _, audit_path = clean_env

        audit_log.append_entry(payment_id="pay_clear", input_snapshot={},
            classification={"category": "temporary", "confidence": 0.9, "reasoning": "R"},
            recommended_action="retry_later", action_reasoning="R", requires_approval=False)

        assert len(audit_log.read_all()) == 1
        audit_log.clear_log()
        assert len(audit_log.read_all()) == 0


class TestAuditLogIntegration:
    """Processing a payment through the agent must create an audit entry."""

    def test_process_payment_creates_audit_entry(self, clean_env, make_payment):
        from app import recovery_agent
        data_path, _ = clean_env

        p = make_payment(failure_reason="bank_server_down", amount=200)
        data_path.write_text(json.dumps([p]))

        result = recovery_agent.process_payment(p["payment_id"])
        assert "audit_id" in result

        entries = audit_log.get_entries_for_payment(p["payment_id"])
        assert len(entries) == 1
        assert entries[0]["recommended_action"] == "retry_later"

    def test_approve_action_updates_audit(self, clean_env, make_payment):
        from app import recovery_agent
        data_path, _ = clean_env

        p = make_payment(failure_reason="insufficient_funds", amount=500)
        data_path.write_text(json.dumps([p]))

        result = recovery_agent.process_payment(p["payment_id"])
        audit_id = result["audit_id"]

        recovery_agent.approve_action(p["payment_id"], audit_id, "test_user")

        entries = audit_log.get_entries_for_payment(p["payment_id"])
        entry = next(e for e in entries if e["audit_id"] == audit_id)
        assert entry["approval_status"] == "approved"
        assert entry["approved_by"] == "test_user"

    def test_reject_action_updates_audit(self, clean_env, make_payment):
        from app import recovery_agent
        data_path, _ = clean_env

        p = make_payment(failure_reason="insufficient_funds", amount=500)
        data_path.write_text(json.dumps([p]))

        result = recovery_agent.process_payment(p["payment_id"])
        audit_id = result["audit_id"]

        recovery_agent.reject_action(p["payment_id"], audit_id, "test_user", "Not appropriate")

        entries = audit_log.get_entries_for_payment(p["payment_id"])
        entry = next(e for e in entries if e["audit_id"] == audit_id)
        assert entry["approval_status"] == "rejected"
        assert entry["execution_result"] == "rejected"
        assert "Not appropriate" in entry["notes"]
