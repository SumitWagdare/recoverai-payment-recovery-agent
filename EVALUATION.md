# Evaluation Report

RecoverAI includes a batch processing script (`scripts/run_batch.py`) to systematically test the AI agent's performance against the entire dataset and compare it against a passive baseline.

## Latest Batch Run Results

**Date**: 2026-08-29

### Baseline (No Agent) vs AI-Assisted Recovery

| Metric | Baseline | AI-Assisted | Delta |
|--------|----------|-------------|-------|
| **Recovery Rate** | 28.3% | 35.8% | **+7.5%** |
| **Revenue Recovered** | ₹289,262 | ₹296,421 | **+₹7,159** |
| **Recovered Cases** | 34 | 43 | +9 |
| **Pending Cases** | 49 | 43 | -6 |
| **Failed Cases** | 25 | 22 | -3 |
| **Escalated Cases**| 12 | 12 | 0 |

> [!TIP]
> The AI agent successfully recovered an additional **₹7,159** through automated, safe retries without requiring human intervention.

### Agent Action Distribution

Of the 74 actionable payments processed by the agent:

- **Send Payment Link**: 35
- **Retry Later**: 24
- **Escalate To Support**: 9
- **Request Alt Method**: 5

### Safety & Automation Metrics

- **Total Processed**: 74
- **Action Accuracy**: 100.0% (AI decisions strictly adhered to the policy matrix)
- **Auto-approved**: 17 actions executed automatically (safe retries).
- **Awaiting Approval**: 56 actions held safely for human review (customer communication or high-value).
- **Duplicate Blocks**: 0 (in this clean dataset; see unit tests for duplicate prevention coverage).
- **Safety Blocks**: 1 (stopped due to cooldown / max-retry rules).

### Graceful Failures
The system correctly identified ambiguous or sensitive scenarios and routed them to human review rather than acting autonomously. Examples:
- **Low Confidence**: `authentication_failed` (82% confidence) -> Escalated for manual review.
- **High-Value**: `bank_server_down` (₹33,519) -> Although a safe action (`retry_later`), it exceeded the ₹10,000 threshold and was held for approval.
- **Churning Customer**: `insufficient_funds` on a churning account -> Held for human judgement before sending a payment link.

## Reproducing the Evaluation
You can reproduce these results at any time by running:
```bash
python scripts/run_batch.py
```
