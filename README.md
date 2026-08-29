# RecoverAI — Payment Recovery Agent

> **Explainable AI agent for detecting failed payments and executing safe revenue-recovery workflows.**

---

## Problem Statement

Every digital business that accepts online payments suffers from **failed transactions** — card declines, bank timeouts, UPI failures, insufficient-balance errors, and authentication drop-offs. Industry data shows that 10–25 % of recurring and one-time payment attempts fail, and a significant share of that revenue is recoverable with timely, well-crafted follow-ups.

Today, most recovery workflows are either:

| Approach | Weakness |
|---|---|
| **Manual** (support teams chase customers) | Slow, expensive, doesn't scale |
| **Brute-force retries** (blind cron-based re-attempts) | Annoying to customers, low success rate |
| **Static rule engines** (retry after X hours) | Cannot adapt to customer context or failure reason |

There is no open-source, **explainable** agent that combines failure-reason classification, customer-context analysis, and safe automated recovery actions — while keeping a human in the loop for high-risk decisions.

---

## Intended Users

| Persona | How they benefit |
|---|---|
| **Fintech / SaaS engineering teams** | Integrate a pluggable recovery agent into their payment stack |
| **Product managers** | Understand *why* payments fail and which recovery actions work |
| **Data scientists** | Experiment with failure-classification models and policy tuning |
| **Compliance / risk teams** | Audit every recovery action via explainability logs |

---

## Proposed Solution

**RecoverAI** is an AI agent that:

1. **Classifies** each failed payment by root cause (insufficient funds, expired card, bank downtime, authentication failure, network timeout, etc.).
2. **Decides** the best recovery action using a policy model that considers:
   - failure reason and historical success rate for that reason
   - customer payment history and churn risk
   - time-of-day, retry fatigue, and regulatory constraints
3. **Executes** safe, auditable actions:
   - Smart retry (with back-off and jitter)
   - Customer nudge (email / SMS / in-app, drafted by an LLM and human-approved)
   - Payment-link generation
   - Escalation to a human agent
4. **Explains** every decision in plain language so that support, product, and compliance teams can review and override.

### Architecture Overview

```
┌─────────────┐     ┌────────────────┐     ┌──────────────────┐
│  Payment     │────▶│  Failure       │────▶│  Recovery Policy │
│  Event       │     │  Classifier    │     │  Engine          │
│  Ingestion   │     │  (ML / Rules)  │     │  (RL / Heuristic)│
└─────────────┘     └────────────────┘     └──────┬───────────┘
                                                   │
                          ┌────────────────────────┼────────────┐
                          ▼                        ▼            ▼
                   ┌─────────────┐    ┌────────────────┐  ┌──────────┐
                   │ Smart Retry │    │ Customer Nudge │  │ Escalate │
                   │ Engine      │    │ (LLM-drafted)  │  │ to Human │
                   └─────────────┘    └────────────────┘  └──────────┘
                          │                    │                │
                          ▼                    ▼                ▼
                   ┌───────────────────────────────────────────────┐
                   │         Explainability & Audit Log            │
                   └───────────────────────────────────────────────┘
```

---

## What Will Be Measured

| Metric | Description |
|---|---|
| **Recovery Rate** | % of failed payments successfully recovered |
| **Time to Recovery** | Median time from failure to successful payment |
| **False-Positive Rate** | Actions taken on payments that would have self-resolved |
| **Customer Satisfaction (proxy)** | Opt-out / unsubscribe rate after nudges |
| **Explainability Score** | % of decisions with human-readable rationale |
| **Action Audit Coverage** | % of actions logged with full trace |

---

## Project Structure

```
recoverai-payment-recovery-agent/
├── app/                 # Core application code (agent, API, services)
├── data/                # Synthetic datasets and data-generation scripts
├── models/              # ML model definitions, training scripts, checkpoints
├── evaluation/          # Evaluation harnesses, metrics, benchmark results
├── docs/                # Design documents, ADRs, API specs
├── tests/               # Unit, integration, and end-to-end tests
├── scripts/             # Dev-ops and utility scripts
├── .gitignore
├── LICENSE              # MIT License
└── README.md
```

---

## ⚠️ Safety Notice

> **🚨 CAUTION — Synthetic Data & Test-Mode Only**
>
> This project uses **synthetic data** and **[Razorpay test-mode](https://razorpay.com/docs/payments/payments/test-mode/) concepts only**.
>
> - **No real payment gateway credentials** may be configured in any environment.
> - **No real customer PII** is stored, processed, or transmitted.
> - **No real payment retries or charges** are ever triggered.
> - **No uncontrolled customer communication** (email, SMS, push) is sent.
>
> All payment objects, customer profiles, and transaction histories are **entirely synthetic** and generated for development and evaluation purposes.
>
> Before adapting this project for production use, a thorough **security review**, **PCI-DSS compliance assessment**, and **human-in-the-loop approval workflow** must be implemented.

---

## Getting Started

```bash
# Clone the repository
git clone https://github.com/<your-username>/recoverai-payment-recovery-agent.git
cd recoverai-payment-recovery-agent

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # macOS / Linux

# Install dependencies (once added)
pip install -r requirements.txt

# Run tests
pytest tests/
```

---

## Contributing

Contributions are welcome! Please read the [Contributing Guide](docs/CONTRIBUTING.md) before submitting a pull request.

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
