# JCi Global Realty: Phase 4 Workforce Runtime

This is the first working implementation increment for Phase 4. It runs 20 role configurations through a shared execution kernel, maintains a local task and approval queue, and enforces role-specific action permissions outside the prompts.

**Operating mode: offline staging.** The bundled provider is a deterministic test double that echoes an internal brief. It is not an AI model and performs no research, content reasoning, customer communication, or financial activity. No model API, Supabase production project, n8n instance, or website dashboard is connected by this increment.

## Run it

Python 3.10+ is required. Offline execution uses the standard library; the live adapter and its transport tests additionally require Requests. Run these commands from the Project file repository root:

```bash
python3 -m pip install -r workforce/requirements-live.txt
python3 -m unittest discover -s workforce/tests -v
python3 -m workforce profiles
python3 -m workforce --db /tmp/jci-workforce-demo.sqlite demo --country US
python3 -m workforce --db /tmp/jci-workforce-demo.sqlite demo --country AE
python3 -m workforce --db /tmp/jci-workforce-demo.sqlite metrics
```

The demo submits one internal readiness task per role per country. Repeating it with the same database does not create or execute duplicate tasks. Its output is explicitly labeled `OFFLINE TEST DRAFT`.

Use `/tmp` for disposable test data. The default `.local/workforce.sqlite` is for local staging only and is ignored by version control. Never submit a populated queue or real customer records to the Project file repository.

## Architecture and role contracts

- **Role registry**: Loads the 20 roles from `docs/ai_employees.seed.json`, validates the role set and management hierarchy, and builds profiles with job descriptions, responsibilities, inputs/outputs, communications, permissions, metrics, escalation rules, error handling, and human approval requirements.
- **Shared provider interface**: A single `generate(system, data)` interface supplies role-specific system instructions and untrusted task data separately. No provider can directly call a tool through this kernel.
- **Permission engine**: Common internal drafts and role-specific drafts are allowlisted. Sensitive requests are separately allowlisted by role. Every unknown action is rejected regardless of model text, claimed seniority, or permission-tier labels.
- **Durable local queue**: SQLite stores task state, prompt-version fingerprints, validated outputs, approval requests, and audit events. Atomic pending-task claims prevent replay across local workers.
- **Human review**: A trusted local operator supplies configured human principals at process construction. The model and task data cannot add approvers. Decisions are recorded once, with identity and timestamp.
- **No external dispatcher**: A human decision changes an approval record, not the outside world. Production sending, payment, publication, or booking handlers do not exist here.

The permission-tier value in the seed is descriptive. Actual capabilities come from the code-level action allowlists; T3 does not enable messaging and T4 does not enable payments.

## Role-specific work

| Role | Additional internal draft capability |
|---|---|
| AI Chief of Staff | Executive briefing |
| AI Operations Manager | Routing plan |
| AI Finance Manager | Financial report and invoice draft |
| AI Compliance Assistant | Risk flag |
| AI Technology Manager | Incident report |
| AI Property Researcher | Research draft |
| AI Buyer Lead Generation Agent | Qualification draft |
| AI Seller Lead Generation Agent | Seller intake |
| AI Listing Manager | Sale listing draft |
| AI Sales Follow-up Agent | Follow-up draft |
| AI Landlord Acquisition Agent | Onboarding draft |
| AI Tenant Acquisition Agent | Rental-match draft |
| AI Rental Listing Agent | Rental listing draft |
| AI Viewing Coordinator | Viewing plan |
| AI Marketing Strategist | Campaign draft |
| AI SEO Specialist | SEO brief |
| AI Social Media Manager | Social post draft |
| AI Video Content Creator | Video script draft |
| AI Customer Support Agent | Support reply draft |
| AI CRM and Reporting Agent | KPI report draft |

These capabilities describe output types the kernel permits, not quality guarantees from the deterministic provider. Output content still needs professional and human review.

## Input and output contract

Input must contain exactly:

```json
{
  "brief": "Prepare an internal draft from the supplied facts only.",
  "source_ids": ["internal:authorized-brief-001"],
  "country": "US"
}
```

Only `US` and `AE` planning tasks are enabled. This restriction does not activate regulated services or establish a regulatory permission.

Provider output must contain exactly:

```json
{
  "summary": "Draft for human review.",
  "source_ids": ["internal:authorized-brief-001"],
  "actions": [
    {"kind": "draft_note", "payload": {"draft": true}}
  ],
  "escalations": ["Ask a licensed professional where required."]
}
```

Unknown fields, invented evidence identifiers, malformed actions, oversized content, and unauthorized action types fail the task closed. Supplied evidence identifiers are checked for membership only: this is not evidence retrieval or factual verification. No tenant-screening, contract-signing, shell-execution, or arbitrary network action is supported.

## State and failure behavior

`pending → in_progress → completed | awaiting_approval | failed`

After all approval decisions are recorded, the task becomes `reviewed`, not `executed`. Approval rows retain their individual approved/rejected outcomes.

- **Idempotency**: Reusing a key with identical input returns the original task. Changed input with the same key is rejected.
- **Pause**: A trusted human can block queued work for a role and later resume it. This does not interrupt a provider call already in progress.
- **Failures**: Malformed or unauthorized output creates no approval requests. Error class is recorded without raw exception text. Automatic retries are disabled to avoid duplicate effects.
- **Crash recovery**: A crashed `in_progress` task remains locked for operator investigation. Lease-based recovery, provider timeouts, bounded retries, and dead-letter handling remain Phase 5 work.
- **Audit**: Local SQL triggers reject audit updates/deletes through ordinary connections. A database owner can still alter the database; this is not tamper-proof archival storage.

## Human approval example

Only a trusted application process or local operator should construct this configuration:

```python
from workforce.runtime import Workforce

worker = Workforce(
    "/tmp/jci-local-review.sqlite",
    human_approvers=("human:ceo",),
)
# After a task proposes a sensitive action:
# worker.decide(approval_id, True, actor="human:ceo")
worker.close()
```

This is a local trust boundary, not production authentication. Do not expose caller-supplied actor strings or this CLI as a public endpoint. A production API must derive identity from a verified session, check server-owned roles, and scope every read and write.

## Security and data boundaries

- **Offline by default**: The deterministic provider makes no network calls. The opt-in OpenAI adapter uses Requests through an approved credential proxy; no external action tools are enabled.
- **No credential handling**: No secrets are requested, stored, or embedded in this implementation.
- **Local data**: The SQLite file is set to owner-read/write (`0600`), but it is not encrypted. Do not use real PII for staging. Parent-directory and host security remain operator responsibilities.
- **Minimized audit events**: Events record identifiers, state changes, error classes, and output hashes, not raw prompts, provider exception messages, or customer content.
- **Untrusted output**: Actions cannot escape the role allowlist. Prompt-injection tests verify these deterministic boundaries; they do not establish resistance of an unconnected live model to every attack.
- **Financial controls**: Starting Phase 4 or publishing this source does not authorize paid services, contracts, financial actions, or spending.

## Supabase integration boundary

The current Supabase schema is the planned production destination; the local queue is not automatically synchronized to it. Before adding an adapter:

1. Inspect the deployed schema and create additive migrations only.
2. Map `role → assigned_ai_employee`, local task input/output to structured task records, and approval requests to the production approval table.
3. Add explicit support for the local `reviewed` outcome before attempting to persist it: the current Supabase task status check does not include that state.
4. Authenticate humans from verified sessions; never accept arbitrary approver IDs.
5. Add scoped data queries, protected endpoints, atomic claims, idempotency constraints, and enforced publication/financial gates.
6. Confirm production audit, encryption, retention, backup/restore, and recovery controls.

Do not point this SQLite implementation at production or claim the local tests validate Supabase integration.

## Remaining Phase 4 milestone

The next milestone requires an authorized model connection, live-model evaluations for all 20 roles, enforced usage limits and measured usage/costs, authenticated database integration, and CEO review of the workforce behavior. The Next.js command-center UI, CRM integrations, and deployed worker services are not delivered by this kernel.

No purchases, customer messages, property publication, country activation, or money movement were performed during this implementation.

## OpenAI adapter increment

`workforce/openai_provider.py` now implements an opt-in Responses API adapter, with structured output conversion back to the runtime's existing contract. Its transport shape follows the [OpenAI Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).

The configured default is `gpt-5.4-mini-2026-03-17`; OpenAI documents Responses API, structured outputs, and reasoning effort `none` support for this model. See the [GPT-5.4 mini model page](https://developers.openai.com/api/docs/models/gpt-5.4-mini).

**Public implementation status:** The adapter uses Requests through the approved credential proxy. All 55 automated tests pass with offline/mocked responses; they are not proof of successful live generation. Private account diagnostics are intentionally excluded from this public repository. See `docs/OPENAI_CONNECTION.md` for setup and operating boundaries.

The adapter uses the approved, host-scoped HTTPS credential proxy rather than accepting a raw key. Do not paste a key into source, chat, a command, or a committed environment file. The proxy grant is temporary and is not a durable deployed-worker credential configuration.

After a synthetic test is explicitly authorized, an operator may use this template, substituting only the exact approved handle returned by a fresh credential listing and reviewing the ledger cap before another attempt. Live work is currently paused; publishing this code does not resume it.

```text
pplx credentials run <exact-approved-handle> -- python3 -m workforce \
  --db /tmp/jci-openai-authorized-test.sqlite live-test \
  --credential-proxy --case-id synthetic-support-001
```

The default test is synthetic, uses one support role, sends no customer PII, and asks for an internal draft only. Default limits are three total live-call reservations per local database, 900 maximum output tokens per request, a 10-second connection timeout, and a 45-second read timeout. The read timeout is not a total wall-clock deadline. Failed/uncertain requests consume a slot; they are never automatically retried. The call cap is not a monthly dollar budget, a global account spending limit, or protection against an operator intentionally creating a new database.

Requests retains environment proxy settings and TLS certificate verification. A no-op auth handler prevents implicit `.netrc` credentials; authentication remains supplied only by the approved proxy. Redirect following is disabled, HTTP errors are handled before reading a response body, and successful response bodies are streamed with a 256 KiB cap.

The request uses `store:false`, no tools, a fixed OpenAI endpoint, and no redirect following. `store:false` is a request setting, not a promise of zero provider retention. Response token usage, when supplied, is stored separately even if runtime validation rejects the output; no dollar cost is fabricated or inferred from token counts.

Live output still passes through the runtime's evidence-ID and role-action validation. All communications, payments, publication, and appointment execution remain disabled, including after human approval. See `docs/OPENAI_CONNECTION.md` for the current milestone status.
