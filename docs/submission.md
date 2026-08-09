# Aegis hackathon submission guide

## One-line pitch

Aegis is a DataHub-native safety control plane that checks fresh governance evidence at the
last responsible moment and blocks unsafe AI-agent tool calls before they execute.

## The problem

Agent inventories and lineage graphs explain what an agent *can* reach, but they do not stop a
consequential action when upstream context changes after deployment. A policy document can lose
approval, a feature view can go stale, or lineage can become incomplete while the agent still
appears healthy.

## The solution

Aegis turns DataHub metadata into runtime enforcement evidence. Before a consequential MCP call,
it re-reads the relevant DataHub aspects, evaluates a deterministic control, and issues a
short-lived single-use capability only for an `ALLOW` decision. `REVIEW`, `BLOCK`, outages,
missing evidence, tampering, and replay never reach the executor.

## What to show judges in 90 seconds

1. **0–15 seconds — fleet:** Open the Command Center. Point out four governed agents, the
   blocked Refund Resolution Agent, the Account Risk review, and zero unsafe executions.
2. **15–40 seconds — proof:** Open `aegis-4821`, investigate evidence, and show the four-node
   DataHub causal path, failed approval check, exact `$8,500` tool proposal, and absent receipt.
3. **40–58 seconds — policy:** Open `ApprovedContextSource` and show that the rule is inspectable,
   deterministic, and fail-closed. Mention `FreshRiskContext` as the second reusable control.
4. **58–78 seconds — recovery:** Apply remediation and verify recovery. Return to the Command
   Center and show the pipeline becoming trusted without erasing the incident history.
5. **78–90 seconds — architecture:** Explain that the model proposes, DataHub supplies evidence,
   Aegis decides, and only a scoped one-time capability can reach the sandbox executor.

Use **Reset showcase** on the Command Center before every rehearsal or judge session.

## What is real and what is simulated

| Capability | Submission behavior |
| --- | --- |
| OpenAI reasoning and strict tool proposal | Real in online mode |
| DataHub MCP discovery and context reads | Real in online mode |
| Fresh direct DataHub enforcement read | Real in online mode |
| LangGraph orchestration | Real in online mode |
| Deterministic `ALLOW`, `REVIEW`, `BLOCK` controls | Real |
| HMAC capability binding, expiry, and replay protection | Real |
| DataHub incident and attestation write-back | Real in online mode |
| Refund and account restriction consequence | Sandboxed SQLite receipt |
| Additional Support and Claims incident history | Clearly labeled showcase fixtures |

## Judge checkpoints

- No model output is treated as authorization.
- Cached metadata and Actions events never authorize execution.
- Missing or unavailable governance evidence fails closed.
- A blocked tool proposal has no executor receipt.
- An allowed capability is bound to exact arguments and can be consumed once.
- Enforcement remains authoritative even if downstream write-back fails.

## Preflight

```bash
docker compose up --build -d
scripts/demo/verify.sh
make test
make lint
make build
```

For the full connected demo, also run the DataHub verifier described in
[online-demo.md](online-demo.md).
