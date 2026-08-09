import { Link, useParams } from "react-router-dom";
import { useControls } from "../../api/hooks";
import { ErrorState, LoadingState } from "../../components/AsyncState";
import { Breadcrumbs } from "../../components/Breadcrumbs";
import { TrustBadge } from "../../components/TrustBadge";

export function ControlsPage() {
  const { controlId } = useParams();
  const controls = useControls();
  if (controls.isLoading) return <div className="view"><LoadingState label="Loading controls" /></div>;
  if (controls.error) return <div className="view"><ErrorState error={controls.error} retry={() => void controls.refetch()} /></div>;
  const control = controls.data!.items.find((item) => item.id === (controlId ?? "approved-context-source"));
  if (!control) return <div className="view"><ErrorState error={new Error("Control not found")} /></div>;
  const isRisk = control.id === "fresh-risk-context";
  const description = isRisk
    ? "Holds consequential account restrictions for review when risk evidence exceeds its freshness SLA."
    : "Blocks consequential production tool calls when context approval or causal evidence is untrusted.";
  const rules = isRisk ? [
    ["IF", "environment == PRODUCTION"],
    ["AND", "tool == freeze_account"],
    ["REQUIRE", "risk.ageSeconds <= 900"],
    ["REQUIRE", "lineage.complete == true"],
    ["ON MISSING EVIDENCE", "BLOCK"],
  ] : [
    ["IF", "environment == PRODUCTION"],
    ["AND", "tool == issue_refund"],
    ["AND", "amount > 2000"],
    ["REQUIRE", "context.approvalStatus == approved"],
    ["ON MISSING EVIDENCE", "BLOCK"],
  ];
  const coveredAgents = isRisk ? "Account Risk Agent" : "Refund Resolution Agent";
  return (
    <section className="view controls-view" aria-labelledby="controls-heading">
      <Breadcrumbs items={[{ label: "Command Center", to: "/" }, { label: "Controls" }, { label: control.name }]} />
      <nav className="control-tabs" aria-label="Safety controls">
        {controls.data!.items.map((item) => (
          <Link key={item.id} className={item.id === control.id ? "active" : ""} to={`/controls/${item.id}`}>
            <span>{item.name}</span>
            <TrustBadge tone={item.lastEvaluation?.decision ?? "TRUSTED"} label={item.lastEvaluation?.decision ?? "READY"} />
          </Link>
        ))}
      </nav>
      <article className="paper-panel control-card">
        <div className="detail-title">
          <div>
            <p className="eyebrow">Deterministic safety control</p>
            <h1 id="controls-heading" tabIndex={-1}>{control.name}</h1>
            <p>{description}</p>
          </div>
          <TrustBadge tone="TRUSTED" label={control.enabled ? "Enabled" : "Disabled"} />
        </div>
        <div className="rule-box">
          {rules.map(([keyword, expression]) => (
            <div className="rule-row" key={`${keyword}-${expression}`}><strong>{keyword}</strong><code>{expression}</code></div>
          ))}
        </div>
        <div className="control-grid">
          <Fact label="Scope" value={`Production · ${String(control.scope.tool)}`} />
          <Fact label="Missing evidence" value={control.missingEvidencePolicy} />
          <Fact label="Covered agents" value={coveredAgents} />
          <Fact label="Last result" value={control.lastEvaluation ? `${control.lastEvaluation.decision} · ${control.lastEvaluation.reasonCode}` : "No evaluation recorded"} />
        </div>
        {control.lastEvaluation && (
          <section className="evaluation-table">
            <div className="section-head"><h2>Latest evaluation</h2><TrustBadge tone={control.lastEvaluation.decision} /></div>
            <div role="table" aria-label="Control conditions">
              {control.lastEvaluation.conditionResults.map((condition) => (
                <div role="row" key={condition.field}>
                  <code role="cell">{condition.field}</code>
                  <span role="cell">{condition.operator}</span>
                  <strong role="cell">{String(condition.actual)}</strong>
                  <span role="cell" className={condition.passed ? "pass" : "fail"}>{condition.passed ? "Pass" : "Fail"}</span>
                </div>
              ))}
            </div>
          </section>
        )}
        <Link className="button primary" to={`/incidents/${control.linkedIncidentId}`}>Open linked incident</Link>
      </article>
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return <div className="fact"><span>{label}</span><strong>{value}</strong></div>;
}
