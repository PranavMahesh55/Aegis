import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useGraph, useIncident, usePipeline, useResetMutation, useWorkflowMutation } from "../../api/hooks";
import type { IncidentState } from "../../api/types";
import { ErrorState, LoadingState } from "../../components/AsyncState";
import { Breadcrumbs } from "../../components/Breadcrumbs";
import { ProvenanceLabel } from "../../components/ProvenanceLabel";
import { TrustBadge } from "../../components/TrustBadge";
import { CausalPath } from "../graph/CausalPath";
import { AgentTrace } from "../agents/AgentConsole";

const stages: Array<{ state: IncidentState; label: string }> = [
  { state: "HEALTHY", label: "Healthy" },
  { state: "CONTEXT_CHANGED", label: "Changed" },
  { state: "BLOCKED", label: "Blocked" },
  { state: "REMEDIATION_APPLIED", label: "Remediated" },
  { state: "RE_EVALUATED", label: "Re-evaluated" },
  { state: "RESOLVED", label: "Trusted" },
];

export function IncidentWorkspacePage() {
  const { incidentId = "aegis-4821" } = useParams();
  if (incidentId !== "aegis-4821") return <ReadOnlyIncidentWorkspacePage incidentId={incidentId} />;
  return <RefundIncidentWorkspacePage incidentId={incidentId} />;
}

function RefundIncidentWorkspacePage({ incidentId }: { incidentId: string }) {
  const navigate = useNavigate();
  const incident = useIncident(incidentId);
  const graph = useGraph(incidentId);
  const pipeline = usePipeline("refund");
  const reset = useResetMutation();
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [rawOpen, setRawOpen] = useState(false);

  const currentVersion = incident.data?.incident.version ?? 0;
  const change = useWorkflowMutation(api.contextChange);
  const evaluate = useWorkflowMutation(api.evaluate);
  const remediate = useWorkflowMutation(api.remediate);
  const verify = useWorkflowMutation(api.verify);
  const activeMutation = [change, evaluate, remediate, verify, reset].find((item) => item.isPending);
  const mutationError = [change, evaluate, remediate, verify, reset].find((item) => item.error)?.error;

  if (incident.isLoading || graph.isLoading) return <div className="view"><LoadingState label="Loading incident workspace" /></div>;
  if (incident.error) return <div className="view"><ErrorState error={incident.error} retry={() => void incident.refetch()} /></div>;
  if (graph.error) return <div className="view"><ErrorState error={graph.error} retry={() => void graph.refetch()} /></div>;

  const data = incident.data!;
  const summary = data.incident;
  const tone = summary.state === "RESOLVED" || summary.state === "HEALTHY" ? "TRUSTED" : summary.decision;
  const title = incidentTitle(summary.state);

  const runPrimary = () => {
    if (summary.state === "HEALTHY") change.mutate(currentVersion);
    else if (summary.state === "CONTEXT_CHANGED") evaluate.mutate(currentVersion);
    else if (summary.state === "BLOCKED" && !evidenceOpen) setEvidenceOpen(true);
    else if (summary.state === "BLOCKED") remediate.mutate(currentVersion);
    else if (summary.state === "REMEDIATION_APPLIED" || summary.state === "RE_EVALUATED") verify.mutate(currentVersion);
    else navigate("/");
  };

  return (
    <section className="view incident-view" aria-labelledby="incident-heading">
      <Breadcrumbs items={[
        { label: "Command Center", to: "/" },
        { label: "Refund Resolution Agent", to: "/pipelines/refund" },
        { label: incidentId },
      ]} />
      <div className="incident-grid">
        <div className="incident-stack">
          <article className={`summary paper-panel ${tone.toLowerCase()}`}>
            <div className="summary-topline">
              <code>{summary.id}</code><span>{summary.environment}</span><span>ApprovedContextSource</span>
              <TrustBadge tone={tone} label={summary.state} />
            </div>
            <h1 id="incident-heading" tabIndex={-1}>{title}</h1>
            <p className="summary-subhead">{incidentBody(summary.state)}</p>
            <div className="decision-grid">
              <Fact label="Decision" value={summary.decision} />
              <Fact label="Causal change" value={summary.causalChange} />
              <Fact label="Prevented action" value={summary.preventedAction} />
              <Fact label="Next step" value={summary.recommendedNextStep} />
            </div>
            <div className="summary-actions">
              <button className="primary" disabled={Boolean(activeMutation)} onClick={runPrimary}>
                {activeMutation ? "Working…" : primaryLabel(summary.state, evidenceOpen)}
              </button>
              {summary.state !== "HEALTHY" && !(summary.state === "BLOCKED" && !evidenceOpen) && (
                <button className="secondary" onClick={() => setEvidenceOpen((open) => !open)}>
                  {evidenceOpen ? "Hide evidence" : "Investigate evidence"}
                </button>
              )}
              <button className="ghost" onClick={() => navigate("/pipelines/refund")}>Open pipeline detail</button>
            </div>
            <div className="mutation-status" aria-live="polite">
              {mutationError && <span className="error-text">{mutationError.message}</span>}
              {summary.state === "RESOLVED" && <strong>Trusted state is now visible across Aegis.</strong>}
            </div>
          </article>

          <CausalPath graph={graph.data!} />

          {pipeline.data?.latestRun && (
            <section className="paper-panel incident-run-trace">
              <p className="eyebrow">Incident-linked live execution</p>
              <h2>Agent and enforcement trace</h2>
              <AgentTrace run={pipeline.data.latestRun} compact />
            </section>
          )}

          <section className="timeline paper-panel" aria-label="Incident progress">
            <ol className="step-list">
              {stages.map((stage, index) => {
                const current = stages.findIndex((item) => item.state === summary.state);
                return (
                  <li key={stage.state} className={`${index === current ? "selected" : ""} ${index < current ? "done" : ""}`}>
                    <span>{index + 1}</span><strong>{stage.label}</strong>
                  </li>
                );
              })}
            </ol>
            <button className="ghost" disabled={reset.isPending} onClick={() => reset.mutate()}>
              {reset.isPending ? "Resetting…" : "Reset simulation"}
            </button>
          </section>
        </div>

        {evidenceOpen ? (
          <EvidencePanel data={data} rawOpen={rawOpen} setRawOpen={setRawOpen} close={() => setEvidenceOpen(false)} />
        ) : (
          <aside className="evidence-closed paper-panel">
            <p className="eyebrow">Evidence</p>
            <strong>Evidence is available on request.</strong>
            <span>Open the investigation to inspect control results, provenance, tool interception, and raw metadata.</span>
            <button className="secondary" onClick={() => setEvidenceOpen(true)}>Open evidence</button>
          </aside>
        )}
      </div>
    </section>
  );
}

function ReadOnlyIncidentWorkspacePage({ incidentId }: { incidentId: string }) {
  const navigate = useNavigate();
  const incident = useIncident(incidentId);
  const [rawOpen, setRawOpen] = useState(false);

  if (incident.isLoading) return <div className="view"><LoadingState label="Loading incident record" /></div>;
  if (incident.error) return <div className="view"><ErrorState error={incident.error} retry={() => void incident.refetch()} /></div>;

  const data = incident.data!;
  const summary = data.incident;
  const tone = summary.state === "RESOLVED" ? "TRUSTED" : summary.decision;
  const openedAt = new Date(summary.openedAt).toLocaleString();
  const resolvedAt = summary.resolvedAt ? new Date(summary.resolvedAt).toLocaleString() : null;

  return (
    <section className="view incident-view" aria-labelledby="incident-heading">
      <Breadcrumbs items={[
        { label: "Command Center", to: "/" },
        { label: "Incidents", to: "/incidents" },
        { label: incidentId },
      ]} />
      <div className="incident-grid">
        <div className="incident-stack">
          <article className={`summary paper-panel ${tone.toLowerCase()}`}>
            <div className="summary-topline">
              <code>{summary.id}</code><span>{summary.environment}</span><span>SHOWCASE FIXTURE · READ ONLY</span>
              <TrustBadge tone={tone} label={summary.state} />
            </div>
            <h1 id="incident-heading" tabIndex={-1}>
              {summary.state === "RESOLVED"
                ? `${summary.pipelineName} incident was resolved.`
                : `${summary.pipelineName} requires review.`}
            </h1>
            <p className="summary-subhead">{summary.recommendedNextStep}</p>
            <div className="decision-grid">
              <Fact label="Decision" value={summary.decision} />
              <Fact label="Causal change" value={summary.causalChange} />
              <Fact label="Prevented action" value={summary.preventedAction} />
              <Fact label="Opened" value={openedAt} />
            </div>
            <div className="summary-actions">
              <button className="secondary" onClick={() => navigate(`/pipelines/${summary.pipelineId}`)}>Open pipeline detail</button>
              <button className="ghost" onClick={() => navigate("/incidents")}>Return to incident queue</button>
            </div>
          </article>

          <section className="timeline paper-panel" aria-label="Incident record status">
            <div className="section-head">
              <div><p className="eyebrow">Recorded outcome</p><h2>Attestation and write-back</h2></div>
              <TrustBadge tone={tone} label={data.writeBackState} />
            </div>
            <div className="decision-grid">
              <Fact label="Attestation" value={data.attestation.state.replaceAll("_", " ")} />
              <Fact label="Owner" value={data.attestation.owner} />
              <Fact label="Opened" value={openedAt} />
              <Fact label="Resolved" value={resolvedAt ?? "Pending"} />
            </div>
          </section>

          <section className="timeline paper-panel" aria-labelledby="audit-heading">
            <div className="section-head"><div><p className="eyebrow">Audit history</p><h2 id="audit-heading">Recorded events</h2></div></div>
            <ol className="static-audit-list">
              {data.auditEvents.map((event) => (
                <li key={event.id}>
                  <div><strong>{event.type.replaceAll("_", " ")}</strong><span>{new Date(event.occurredAt).toLocaleString()}</span></div>
                  <p>{event.detail}</p>
                  <ProvenanceLabel source={event.sourceSystem} />
                </li>
              ))}
            </ol>
          </section>
        </div>

        <EvidencePanel data={data} rawOpen={rawOpen} setRawOpen={setRawOpen} />
      </div>
    </section>
  );
}

function EvidencePanel({
  data,
  rawOpen,
  setRawOpen,
  close,
}: {
  data: NonNullable<ReturnType<typeof useIncident>["data"]>;
  rawOpen: boolean;
  setRawOpen: (open: boolean) => void;
  close?: () => void;
}) {
  return (
    <aside className="evidence-panel paper-panel" aria-label="Investigation evidence">
      <div className="evidence-head">
        <div><p className="eyebrow">Investigation evidence</p><h2>Why Aegis made this decision</h2></div>
        {close && <button className="ghost" onClick={close}>Close</button>}
      </div>
      {data.evidenceSummary.map((item) => (
        <article className="evidence-row" key={item.id}>
          <div className="evidence-label"><span>{item.label}</span><ProvenanceLabel source={item.sourceSystem} /></div>
          <strong>{item.value}</strong>
          <p>{item.detail}</p>
        </article>
      ))}
      {data.attestation.regressionResults.map((run) => (
        <section className="regression-block" key={run.id}>
          <div className="section-head"><h3>Regression verification</h3><TrustBadge tone={run.status === "PASSED" ? "TRUSTED" : "BLOCKED"} label={run.status} /></div>
          <ul>{run.scenarios.map((scenario) => <li key={scenario.id}><strong>{scenario.id}</strong><span>{scenario.status} · expected {scenario.expected}</span></li>)}</ul>
        </section>
      ))}
      <details open={rawOpen} onToggle={(event) => setRawOpen(event.currentTarget.open)}>
        <summary>Raw metadata and audit payload</summary>
        <pre>{JSON.stringify({
          incident: data.incident,
          evidence: data.evidenceSummary.map((item) => ({ id: item.id, sourceSystem: item.sourceSystem, raw: item.raw })),
          writeBack: { state: data.writeBackState, urn: data.datahubIncidentUrn },
          attestation: data.attestation,
          auditEvents: data.auditEvents,
        }, null, 2)}</pre>
      </details>
    </aside>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return <div className="fact"><span>{label}</span><strong>{value}</strong></div>;
}

function incidentTitle(state: IncidentState) {
  return {
    HEALTHY: "Refund pipeline is healthy.",
    CONTEXT_CHANGED: "Policy source changed; safety gate pending.",
    BLOCKED: "Refund Resolution Agent blocked before issuing $8,500 refund.",
    REMEDIATION_APPLIED: "Approved policy restored; verification is required.",
    RE_EVALUATED: "Context was re-evaluated; write-back is pending.",
    RESOLVED: "Refund Resolution Agent is trusted again.",
  }[state];
}

function incidentBody(state: IncidentState) {
  return {
    HEALTHY: "Start the controlled scenario to see how a context change propagates through the agent supply chain.",
    CONTEXT_CHANGED: "A simulated change introduced refund-policy-q4-draft.md into the active DataHub context path.",
    BLOCKED: "Aegis selected the affected path, evaluated an inspectable control, and intercepted issue_refund before execution.",
    REMEDIATION_APPLIED: "The approved v12 policy is pinned again, but trust remains blocked until deterministic regressions pass.",
    RE_EVALUATED: "The restored path has been evaluated. Aegis is completing the resolution evidence.",
    RESOLVED: "The control and regression suite passed, and the incident resolution is recorded with its attestation.",
  }[state];
}

function primaryLabel(state: IncidentState, evidenceOpen: boolean) {
  return {
    HEALTHY: "Simulate context change",
    CONTEXT_CHANGED: "Run safety gate",
    BLOCKED: evidenceOpen ? "Apply remediation" : "Investigate evidence",
    REMEDIATION_APPLIED: "Verify recovery",
    RE_EVALUATED: "Complete verification",
    RESOLVED: "Return to Command Center",
  }[state];
}
