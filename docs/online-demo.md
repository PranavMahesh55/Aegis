# Online DataHub demo runbook

This runbook turns the static/seeded product story into a real two-agent execution demo. The
only simulated part is the external business consequence: refunds and freezes are recorded in
a sandbox database rather than sent to a payment or account system.

## 1. Prerequisites

- Docker Desktop and Compose v2
- DataHub Core 1.7+ with GMS, Kafka, and Schema Registry reachable from Docker, or an
  Agent Registry-enabled DataHub Cloud deployment and credentials
- An OpenAI API key with access to the configured model

For local DataHub Core, start the v1.7 quickstart first:

```bash
datahub docker quickstart --version v1.7.0
```

The v1.6.0 release image predates the `api`, `agentSkill`, and `aiAgent` schemas and is not
compatible with this demo, even though later 1.6 documentation and SDK patch releases describe
Agent Registry. The v1.7 quickstart's common endpoints are GMS on `localhost:8080`, frontend on
`localhost:9002`, and Kafka on `localhost:9092`; its Schema Registry-compatible API is served by
GMS at `/schema-registry/api/`. Aegis exposes DataHub MCP on `localhost:8082`.

## 2. Configure secrets and endpoints

```bash
cp .env.example .env
```

Set at least:

```dotenv
AEGIS_DATA_MODE=live
AEGIS_PRIME_BLOCKED=false
OPENAI_API_KEY=...
AEGIS_OPENAI_MODEL=gpt-5.6-terra
AEGIS_CAPABILITY_SIGNING_SECRET=<strong random value>
AEGIS_DATAHUB_ACTIONS_SHARED_SECRET=<different strong random value>
```

The `.env.example` endpoints are appropriate for the Docker Compose stack: Aegis reaches the
host's local Core through `host.docker.internal` and reaches the MCP services by Compose service
name. If you run the API directly on the Mac instead, change the GMS, GraphQL, DataHub MCP, and
Business MCP hosts back to `localhost`. For DataHub Cloud, set `DATAHUB_GMS_URL`,
`DATAHUB_GMS_TOKEN`, `DATAHUB_GRAPHQL_URL`, and `DATAHUB_FRONTEND_URL`. The read-only DataHub MCP
container receives the same GMS connection.

DataHub Core 1.7 accepts and exposes the Agent Registry entity types through GMS, so the seed,
verification, lineage, and enforcement paths are real. Its open-source frontend does not include
the Cloud Agent Registry profile UI. For that reason, **Open context in DataHub** links to the
pipeline's browseable retrieval or feature dataset. An Agent Registry-enabled DataHub Cloud
deployment can additionally provide native agent, skill, and tool profile pages.

## 3. Seed and prove the DataHub model

```bash
docker compose build
docker compose run --rm --no-deps aegis python scripts/datahub/seed.py
docker compose run --rm --no-deps aegis python scripts/datahub/verify.py
```

Do not skip verification. It checks the concrete Agent Registry, API, Dataset, Document,
structured-property, lineage, dependency, and Operation aspects—not just GMS health.

## 4. Start the online profile

```bash
docker compose --profile online up -d
docker compose ps
curl -fsS http://localhost:8000/api/system/status | python3 -m json.tool
```

The profile adds:

- `business-mcp` on port 8010
- read-only `datahub-mcp` on port 8082
- `datahub-actions`, consuming DataHub's Kafka events and forwarding relevant changes to Aegis

The Actions worker joins the quickstart-created `datahub_network` so Kafka can advertise its
internal `broker:29092` address. If your Core deployment uses another Docker network, set
`DATAHUB_DOCKER_NETWORK`; for an external Kafka cluster, also override the Kafka and Schema
Registry URLs.

The Refund and Risk pipeline pages should show `READY`. `MODEL NOT CONFIGURED`, `FIXTURE ONLY`,
or `DATAHUB UNAVAILABLE` explains which prerequisite is missing.

## 5. Live refund sequence

Healthy case:

1. Open **Refund Resolution Agent**.
2. Select `CASE-1042 · $1,500 healthy path`.
3. Run the agent.
4. Inspect DataHub MCP retrieval, business MCP retrieval, real model proposal, fresh GMS gate,
   capability-protected execution, sandbox receipt, and DataHub attestation writeback in the
   trace. The resulting Document is `urn:li:document:aegis-run-attestation-<run-id>`.

Attack case:

1. Reset to the healthy baseline.
2. Use **Simulate context change** in the incident story. In live mode this switches the real
   RAG lineage from the approved policy to the draft and records a DataHub Operation.
3. Select `CASE-8500 · $8,500 attack path` and run the agent.
4. The model can genuinely propose `issue_refund`; Aegis must show `BLOCK` and no receipt because
   the fresh lineage resolves to `approvalStatus=not_approved`.
5. Remediate and verify from the incident workspace. Aegis restores the approved lineage,
   resolves the DataHub Incident, and writes a trusted attestation Document.

A blocked or review live run also writes its own active Incident at
`urn:li:incident:aegis-<run-id>`. It associates the agent and governed context, and its
description records the subject, proposed tool, control, reason code, and evidence IDs. The
trace reports `WRITTEN` or `FAILED`; either result leaves the original gate decision unchanged.

API equivalent for starting a run:

```bash
curl -fsS -X POST http://localhost:8000/api/agents/refund/runs \
  -H 'Content-Type: application/json' \
  -d '{"message":"Resolve this verified refund case using the active policy.","subject":{"type":"CASE","id":"CASE-1042"}}'
```

Poll the returned `/api/runs/{runId}` or consume `/api/runs/{runId}/events` as server-sent events.

## 6. Live account-risk sequence

Open **Account Risk Agent** and run `ACC-HIGH-7`. The seeded risk feature dataset intentionally
has a stale latest DataHub Operation. The model can propose `freeze_account`, but
`FreshRiskContext` returns `REVIEW`; no executor receipt is created. Updating the real Operation
within the configured SLA turns that same path into an allow case.

## 7. Security checks worth showing

- Stop GMS and refresh a pipeline: status becomes `DATAHUB UNAVAILABLE`, and new runs fail closed.
- Remove the approval structured property or active lineage edge: the high-value refund blocks.
- Call `issue_refund` directly without a capability: business MCP returns an error.
- Reuse a previously accepted capability: atomic one-time consumption rejects the replay.
- Post an Actions callback without the HMAC signature: the integration endpoint returns 401.

## 8. Troubleshooting

- `MODEL_NOT_CONFIGURED`: place `OPENAI_API_KEY` in `.env`, then recreate `aegis`.
- `FIXTURE_ONLY`: set `AEGIS_DATA_MODE=live` and recreate `aegis`.
- `DATAHUB_UNAVAILABLE`: verify GMS from the container with
  `docker compose run --rm --no-deps aegis python scripts/datahub/verify.py`.
- DataHub MCP failures: inspect `docker compose logs datahub-mcp`; mutation tools are intentionally
  disabled.
- Actions connection failures: verify `KAFKA_BOOTSTRAP_SERVER` and `SCHEMA_REGISTRY_URL`, then
  inspect `docker compose logs datahub-actions`.
- A failed agent run is still useful: its trace stops before the consequence step and records the
  exact safe failure.

Stop Aegis with `docker compose --profile online down`. The `aegis-state` volume preserves traces
and receipts; `POST /api/demo/reset` restores the deterministic business fixtures.
