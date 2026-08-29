# RecoverAI

**Explainable AI agent for detecting failed payments and executing safe revenue-recovery workflows.**

🔗 **[Live Demo / Video Pitch](https://recoverai-payment-recovery-agent.vercel.app/)**
### Dashboard
![RecoverAI Dashboard Screenshot](docs/dashboard.png)
### Payments View
![RecoverAI Payments Screenshot](docs/payments.png)
### Audit Log
![RecoverAI Audit Log Screenshot](docs/audit_log.png)

## The Problem
E-commerce and SaaS platforms lose millions of dollars globally to involuntary churn caused by failed payments (expired cards, insufficient funds, network timeouts). Traditional retry systems are binary and rigid, often alienating customers or escalating recovery costs. An intelligent, contextual recovery system is needed to gracefully handle exceptions, reduce churn, and maintain customer trust.

## The Solution
RecoverAI is a Python-based autonomous agent that acts as an intelligent recovery orchestrator. It uses an explainable rule-based AI engine to classify the root cause of a failed payment and recommends a bounded, context-aware recovery action.

### Key Features
- **Explainable Decisions**: Every action recommendation is accompanied by a plain-text reasoning string.
- **Safety First**: Implements strict guardrails (maximum retries, cooldown periods).
- **Human-in-the-Loop**: High-value and customer-facing actions are held for mandatory human operator approval.
- **Duplicate Prevention**: 24-hour cooldown on customer communications.
- **Audit Log**: Immutable JSON Lines trail for all AI decisions and operator actions.
- **Interactive Dashboard**: Premium dark-mode UI for monitoring operations and approving actions.

> [!WARNING]
> **Safety Note:** This project uses synthetic data and Razorpay test-mode concepts only. It is a simulation framework designed for evaluation and **must never trigger real payments or uncontrolled customer communication.**

---

## Architecture
RecoverAI is built entirely in Python (backend) and Vanilla HTML/CSS/JS (frontend) without heavy framework dependencies.

Read the detailed [Architecture Guide](ARCHITECTURE.md) for more information.

---

## Setup & Execution

### Prerequisites
- Python 3.10+
- `pip`

### 1. Installation
Clone the repository and install the minimal dependencies:
```bash
git clone https://github.com/SumitWagdare/recoverai-payment-recovery-agent.git
cd recoverai-payment-recovery-agent
pip install -r requirements.txt
```

### 2. Generate Synthetic Data (Optional)
The repository comes with a pre-generated synthetic dataset and a demo file. You can regenerate a fresh dataset of 120 payments:
```bash
python scripts/generate_data.py
```

### 3. Run the Dashboard API
Start the Flask backend:
```bash
python -m app.server
```
Open **http://127.0.0.1:5000** in your web browser.

### 4. Run the Batch Evaluation
To test the AI engine against the entire dataset and generate a comparative report:
```bash
python scripts/run_batch.py
```
> [!NOTE]
> Running this script is a destructive operation designed for clean benchmarking. It intentionally mutates `data/synthetic_payments.json` by regenerating fresh data and clears `data/audit_log.jsonl` before running the evaluation.

This produces a detailed JSON report in `evaluation/batch_report.json`. Read the [Evaluation Report](EVALUATION.md) for the latest benchmark.

---

## Sample Workflow
1. A simulated payment failure occurs (e.g., `insufficient_funds`).
2. The **AI Engine** (`app/ai_engine.py`) classifies the failure as `customer_action_needed`.
3. The AI recommends the `send_payment_link` action.
4. The **Recovery Agent** (`app/recovery_agent.py`) intercepts the action. Because it is customer-facing, it flags it as `awaiting_approval`.
5. An entry is appended to the **Audit Log** (`data/audit_log.jsonl`).
6. A human operator reviews the decision in the **Dashboard** and clicks "Approve Action".
7. The simulated action executes successfully, and the payment status changes to `recovered`.

---

## Limitations
- **Rule-Based Engine**: The current AI engine uses heuristics rather than a trained ML model to guarantee explainability and 100% deterministic behaviour for this v1 release.
- **Simulated Actions**: Integration with real payment gateways (e.g., Stripe, Razorpay) and communication channels (e.g., Twilio, SendGrid) is mocked.
- **Single Node**: State is managed via local JSON files. It is not currently safe for concurrent, multi-node deployments.

## Future Improvements
- **LLM Integration**: Replace the rule-based engine with an LLM prompt chain (using LangChain or similar) for parsing ambiguous error messages from payment gateways, maintaining the existing approval guardrails.
- **Database Backend**: Migrate from JSON files to PostgreSQL or SQLite.
- **Live Integrations**: Add actual webhook listeners and API clients for payment gateways.
- **A/B Testing**: Support evaluating multiple recovery strategies simultaneously.

## License
MIT License. See [LICENSE](LICENSE) for details.
