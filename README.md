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

## Phase 4 workforce documentation

Phase 4 has a working local execution kernel, not a completed production workforce. The 20 roles share one runtime and provider interface rather than running as 20 independent services; the CEO retains strategic control, and licensed or otherwise restricted work remains with qualified human professionals.

### Documentation index

- **Runtime and role contracts**: [Architecture and role contracts](workforce/README.md#architecture-and-role-contracts) explains the role registry, permission engine, task queue, and human-review boundary.
- **All 20 roles**: [Role-specific work](workforce/README.md#role-specific-work) maps each role to its permitted internal draft capability; [role seed](docs/ai_employees.seed.json) contains the underlying configuration.
- **Task format**: [Input and output contract](workforce/README.md#input-and-output-contract) defines the brief, supplied evidence identifiers, country, actions, and validation rules.
- **Queue operation**: [State and failure behavior](workforce/README.md#state-and-failure-behavior) covers idempotency, role pause/resume, failures, and operator investigation.
- **Approvals and security**: [Human approval example](workforce/README.md#human-approval-example) and [security boundaries](workforce/README.md#security-and-data-boundaries) explain trusted local identities, synthetic-data requirements, and minimized audit events.
- **OpenAI adapter**: [Setup and controls](docs/OPENAI_CONNECTION.md) documents Requests transport, credential-proxy authentication, structured output, request limits, and the no-retry policy.
- **Production database boundary**: [Supabase integration requirements](workforce/README.md#supabase-integration-boundary) explains the authenticated adapter and schema reconciliation still needed.

### Task lifecycle

```text
Submit internal task
  -> persistent pending queue
  -> claim task and check role permissions
  -> deterministic provider by default
     (optional OpenAI provider only when explicitly authorized)
  -> validate output, evidence identifiers, and action types
  -> completed draft | awaiting human approval | failed
  -> reviewed after all approval decisions, never externally executed
```

The runtime checks evidence identifiers against those supplied with the task; it does not retrieve evidence or independently establish factual accuracy. A human approval changes a local record only and cannot send a message, publish a listing, book an appointment, or move funds.

### Verification and remaining work

- **Implemented**: Role-specific allowlists, persistent local tasks, idempotency, human-review records, audit events, role pause/resume, and optional model-call reservations and usage records.
- **Automated verification**: 55 offline/mocked tests cover runtime permissions and adapter behavior. Run the quick-start test command to verify the current checkout; these tests do not prove live-model quality, regulatory compliance, or production security.
- **Planning markets**: Internal test inputs support `US` and `AE`. This is not authorization to activate regulated services in either country.
- **Still pending**: Successful live-model evaluation across all roles, authenticated production database access, durable worker operation, server-enforced dollar budgets, production integrations, and the Next.js command center.

The SQLite staging database is permission-restricted but unencrypted, and human identity is trusted local configuration rather than production authentication. A crashed in-progress task requires operator investigation; default model-call caps are local to a database, not organization-wide spending controls.

## Operating boundaries

This is local staging software, not a deployed production platform or brokerage service. Human approval records do not execute external actions: sending messages, publishing listings, booking appointments, and moving money remain disabled.

Use synthetic data only. Do not commit credentials, environment secrets, populated databases, customer records, or private account diagnostics; broader business plans and private operational records are not part of this public export.

OpenAI work is paused. Pushing this code does not authorize a new API call or change billing, quota, or account settings.
