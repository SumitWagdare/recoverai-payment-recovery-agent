#!/bin/bash
set -e

# Remove the workflow so we don't commit it
rm -rf .github

# Get the initial commit hash from our script (which is e7f5f82)
INIT_COMMIT=e7f5f82

# Soft reset to the initial commit, keeping all changes in the working directory
git reset --soft $INIT_COMMIT
git reset HEAD .

# Commit 1
git add SAFETY.md docs/CONTRIBUTING.md || true
git commit --amend -m "chore(repo): establish project structure and safety policy

- Setup initial folders, README, LICENSE, .gitignore
- Document strict safety guardrails in SAFETY.md
- Add contributing guidelines"

# Commit 2
git add scripts/generate_data.py data/synthetic_payments.json data/demo_payments.json || true
git commit -m "feat(data): add synthetic failed-payment generator

- Create reproducible python generator for synthetic payments
- Include 120 generated records across different failure scenarios
- Include 5-record demo dataset"

# Commit 3
git add app/ai_engine.py app/__init__.py || true
git commit -m "feat(engine): classify failures and recommend recovery actions

- Add heuristic rule-engine to classify 10 failure types into 4 categories
- Add action recommender mapped to failure categories
- Output human-readable reasoning strings for explainability"

# Commit 4
git add app/recovery_agent.py || true
git commit -m "feat(safety): enforce retry limits and recovery guardrails

- Create recovery orchestrator with strict safety controls
- Implement 3-retry maximum and 4-hour cooldown periods
- Add duplicate-contact prevention for customer communications
- Hold high-value payments (>\u20b910k) for human approval"

# Commit 5
git add app/audit_log.py data/audit_log.jsonl || true
git commit -m "feat(audit): record explainable recovery decisions

- Implement append-only JSON Lines audit log
- Record input snapshot, classification, recommendation, and approval status
- Add retrieval and update helper methods"

# Commit 6
git add scripts/run_batch.py evaluation/batch_report.json || true
git commit -m "feat(evaluation): compare baseline and agent-assisted recovery

- Add batch processing script to evaluate agent performance
- Generate comparative metrics (recovery rate, revenue recovered)
- Output automated structured JSON report"

# Commit 7
git add tests/test_classification.py tests/test_stopping_rules.py tests/__init__.py tests/conftest.py || true
git commit -m "test(engine): cover classification and policy behavior

- Add pytest coverage for all AI classification edge cases
- Test stopping rules, cooldown enforcement, and max retries
- Provide shared testing fixtures"

# Commit 8
git add tests/test_audit_log.py tests/test_duplicate_prevention.py || true
git commit -m "test(audit): verify audit logging and duplicate prevention

- Test append and update behaviors of the audit log
- Verify duplicate contact prevention triggers correctly"

# Commit 9
git add app/server.py app/static/ requirements.txt || true
git commit -m "feat(ui): add recovery operations dashboard

- Create Flask REST API for dashboard integration
- Build vanilla JS/CSS glassmorphism dashboard SPA
- Include animated stat cards and interactive approval modals"

# Commit 10
git add ARCHITECTURE.md EVALUATION.md || true
git commit -m "docs(demo): document architecture evaluation and walkthrough

- Document modular architecture and execution flow
- Include Mermaid diagram for visual component mapping
- Document the latest batch evaluation results"

# Commit 11
git add README.md restructure.sh restructure2.sh
git add .
git commit -m "docs(readme): add setup results and limitations

- Update main README with comprehensive instructions
- Document problem statement, solution, and sample workflow
- State explicit system limitations and future improvements"

