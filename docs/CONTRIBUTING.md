# Contributing to RecoverAI

Thank you for your interest in contributing! 🎉

## How to Contribute

1. **Fork** the repository.
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Commit** your changes with clear, descriptive messages.
4. **Push** to your fork and open a **Pull Request**.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # linting, formatting, testing
```

## Code Style

- Python code follows **PEP 8** and is formatted with **Black**.
- Type hints are encouraged for all public functions.
- Linting is handled by **Ruff**.

## Testing

```bash
pytest tests/ -v
```

All new features must include tests. Aim for ≥ 80 % coverage on new code.

## Safety Reminder

> ⚠️ **Never** commit real payment credentials, customer PII, or code that
> triggers real payment-gateway calls. All development uses synthetic data
> and Razorpay test-mode concepts only.

## Code of Conduct

Be respectful, inclusive, and constructive. We follow the
[Contributor Covenant](https://www.contributor-covenant.org/) v2.1.
