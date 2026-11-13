# JCi Global Realty Workforce

JCi Global Realty is a division of JCi Global Corp, not a separate legal entity. This repository contains the Phase 4 workforce staging runtime: 20 role configurations sharing one execution kernel, with role-specific permissions, human review records, audit events, and an optional OpenAI Responses adapter.

## Quick start

Python 3.10 or newer is required. Run these commands from the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r workforce/requirements-live.txt
python3 -m unittest discover -s workforce/tests -v
python3 -m workforce profiles
python3 -m workforce --db /tmp/jci-workforce-demo.sqlite demo --country US
```

The demo uses a deterministic test provider and does not make model API calls. The automated suite has 55 passing tests with mocked model responses; it does not establish live-model quality or production readiness.

## Included

- **Shared runtime**: SQLite staging queue, idempotency, permission validation, human approval records, pause/resume, and minimized audit events.
- **Role seed**: The 20 role definitions in `docs/ai_employees.seed.json`.
- **Optional OpenAI adapter**: Requests-based HTTP transport through an approved, host-scoped credential proxy; structured output, usage records, durable local call caps, and no automatic retries.
- **Operator guidance**: [Workforce runtime guide](workforce/README.md) and [OpenAI adapter guide](docs/OPENAI_CONNECTION.md).

## Operating boundaries

This is local staging software, not a deployed production platform or brokerage service. Human approval records do not execute external actions: sending messages, publishing listings, booking appointments, and moving money remain disabled.

Use synthetic data only. Do not commit credentials, environment secrets, populated databases, customer records, or private account diagnostics; broader business plans and private operational records are not part of this public export.

OpenAI work is paused. Pushing this code does not authorize a new API call or change billing, quota, or account settings.
