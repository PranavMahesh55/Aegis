import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import { useAgentRun } from "../../api/hooks";
import type { AgentRun } from "../../api/types";
import { ProvenanceLabel } from "../../components/ProvenanceLabel";
import { TrustBadge } from "../../components/TrustBadge";

export function AgentConsole({
  pipelineId,
  runtimeStatus,
  model,
  initialRun,
}: {
  pipelineId: "refund" | "risk";
  runtimeStatus: "READY" | "MODEL_NOT_CONFIGURED" | "FIXTURE_ONLY" | "DATAHUB_UNAVAILABLE";
  model: string | null;
  initialRun: AgentRun | null;
}) {
  const isRefund = pipelineId === "refund";
  const [subjectId, setSubjectId] = useState(isRefund ? "CASE-1042" : "ACC-HIGH-7");
  const [message, setMessage] = useState(
    isRefund
      ? "Resolve this verified refund case using the active policy."
      : "Protect this account if its fraud signals warrant a freeze.",
  );
  const [runId, setRunId] = useState<string | null>(initialRun?.id ?? null);
  const runQuery = useAgentRun(runId);
  const create = useMutation({
    mutationFn: () =>
      api.createRun(pipelineId, {
        message,
        subject: { type: isRefund ? "CASE" : "ACCOUNT", id: subjectId },
      }),
    onSuccess: (accepted) => setRunId(accepted.runId),
  });
  const error = create.error instanceof ApiError ? create.error.problem.detail : create.error?.message;

  return (
    <section className="paper-panel agent-console" aria-labelledby="agent-console-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Live agent console</p>
          <h2 id="agent-console-title">Run the governed pipeline</h2>
        </div>
        <span className={`runtime-pill ${runtimeStatus.toLowerCase()}`}>{runtimeStatus.replaceAll("_", " ")}</span>
      </div>
      <p className="console-explainer">
        This invokes a real OpenAI-backed LangGraph agent. DataHub MCP supplies governance context,
        and Aegis re-reads DataHub before any consequential MCP call.
      </p>
      <div className="console-form">
        <label>
          <span>{isRefund ? "Case" : "Account"}</span>
          {isRefund ? (
            <select value={subjectId} onChange={(event) => setSubjectId(event.target.value)}>
              <option value="CASE-1042">CASE-1042 · $1,500 healthy path</option>
              <option value="CASE-8500">CASE-8500 · $8,500 attack path</option>
            </select>
          ) : (
            <input value={subjectId} onChange={(event) => setSubjectId(event.target.value)} />
          )}
        </label>
        <label className="message-field">
          <span>Agent request</span>
          <textarea rows={3} value={message} onChange={(event) => setMessage(event.target.value)} />
        </label>
      </div>
      <div className="console-actions">
        <button
          className="primary"
          disabled={create.isPending || runtimeStatus !== "READY"}
          onClick={() => create.mutate()}
        >
          {create.isPending ? "Starting…" : "Run live agent"}
        </button>
        <span>{model ?? "No execution model"}</span>
      </div>
      {runtimeStatus === "MODEL_NOT_CONFIGURED" && (
        <p className="console-notice">Set <code>OPENAI_API_KEY</code> to enable live agent runs.</p>
      )}
      {runtimeStatus === "FIXTURE_ONLY" && (
        <p className="console-notice">Switch to <code>AEGIS_DATA_MODE=live</code>; fixture metadata cannot authorize tools.</p>
      )}
      {runtimeStatus === "DATAHUB_UNAVAILABLE" && (
        <p className="console-notice">DataHub GMS is unavailable. Aegis keeps live execution disabled until it recovers.</p>
      )}
      {error && <p className="error-text" role="alert">{error}</p>}
      {runQuery.data && <AgentTrace run={runQuery.data} />}
    </section>
  );
}

export function AgentTrace({ run, compact = false }: { run: AgentRun; compact?: boolean }) {
  const tone = run.status === "COMPLETED" ? "TRUSTED" : run.status === "REVIEW" ? "REVIEW" :
    run.status === "QUEUED" || run.status === "RUNNING" ? "REVIEW" : "BLOCKED";
  return (
    <section className={`agent-trace ${compact ? "compact" : ""}`} aria-label={`Agent run ${run.id}`}>
      <div className="trace-head">
        <div><p className="eyebrow">Execution trace</p><code>{run.id}</code></div>
        <TrustBadge tone={tone} label={run.status} />
      </div>
      <ol className="trace-steps">
        {run.steps.map((step) => (
          <li key={step.id}>
            <span className="trace-index">{step.sequence}</span>
            <div><strong>{step.title}</strong><p>{step.detail}</p><ProvenanceLabel source={step.sourceSystem} /></div>
          </li>
        ))}
      </ol>
      {run.output && <div className="trace-output"><span>Agent output</span><strong>{run.output}</strong></div>}
      {run.proposedToolCall && (
        <details><summary>Model tool proposal</summary><pre>{JSON.stringify(run.proposedToolCall, null, 2)}</pre></details>
      )}
      {run.gateDecision && (
        <details><summary>Enforcement evidence</summary><pre>{JSON.stringify(run.gateDecision, null, 2)}</pre></details>
      )}
      {run.datahubWriteback && (
        <details open>
          <summary>DataHub security record · {run.datahubWriteback.status}</summary>
          <pre>{JSON.stringify(run.datahubWriteback, null, 2)}</pre>
        </details>
      )}
      {run.toolReceipt && (
        <details><summary>Sandbox receipt</summary><pre>{JSON.stringify(run.toolReceipt, null, 2)}</pre></details>
      )}
    </section>
  );
}
