# OpenAI Adapter Guide

The optional OpenAI Responses adapter uses Requests through an approved host-scoped credential proxy. Offline mode remains the default, and this public guide contains no private account diagnostics, credential handles, or billing records.

## Setup

Install the live dependency with `python3 -m pip install -r workforce/requirements-live.txt`. The adapter deliberately does not accept raw API keys; the credential proxy must be available in the operator's environment.

After explicit authorization for a synthetic test, list the available approved credentials and use only the exact returned handle. The following is a template, not a runnable credential:

```text
pplx credentials run <exact-approved-handle> -- python3 -m workforce \
  --db /tmp/jci-openai-authorized-test.sqlite live-test \
  --credential-proxy --case-id synthetic-support-001
```

Do not invoke this command while live work is paused. Inspect the existing ledger and obtain authorization before raising its call cap or creating another test.

## Controls

- **Transport**: Fixed HTTPS endpoint, verified TLS, environment proxy/CA settings retained, implicit `.netrc` authentication disabled, no redirect following, and no automatic retries.
- **Limits**: Default three call reservations per database, 900 output tokens per request, 10-second connection timeout, 45-second read timeout, and 256 KiB streamed response cap. Connection/read timeouts are not a total wall-clock deadline.
- **Usage**: Provider-reported token usage is persisted when available, including if later runtime validation rejects the output. Missing usage is unknown, not zero; local call caps are not organization-wide dollar budgets.
- **Output**: Structured output is decoded and revalidated against the role's action permissions and supplied evidence IDs. Refusals, incomplete responses, and invalid outputs fail closed.
- **Privacy**: Synthetic facts only for staging. Requests use `store:false`, which does not establish zero provider retention.

The request format follows the [OpenAI Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs). The configured default model is documented on the [GPT-5.4 mini model page](https://developers.openai.com/api/docs/models/gpt-5.4-mini).

## Remaining production work

Successful live generation and evaluation of the 20 roles are not established by mocked tests. Durable deployed-worker credentials, authenticated database integration, dollar-budget enforcement, and production service operation require separate implementation and approval.

The adapter enables generation of internal drafts only. No external dispatcher exists, even after a human approval record is created.
