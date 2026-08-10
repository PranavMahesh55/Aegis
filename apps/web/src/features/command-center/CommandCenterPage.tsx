import { useNavigate } from "react-router-dom";
import { usePipelines, usePrimeMutation } from "../../api/hooks";
import type { PipelineSummary } from "../../api/types";
import { ErrorState, LoadingState } from "../../components/AsyncState";
import { ProvenanceLabel } from "../../components/ProvenanceLabel";
import { StatusGlyph } from "../../components/StatusGlyph";
import { TrustBadge } from "../../components/TrustBadge";

export function CommandCenterPage() {
  const pipelines = usePipelines();
  const prime = usePrimeMutation();
  const navigate = useNavigate();
  if (pipelines.isLoading) return <div className="view"><LoadingState /></div>;
  if (pipelines.error) {
    return <div className="view"><ErrorState error={pipelines.error} retry={() => void pipelines.refetch()} /></div>;
  }
  const items = pipelines.data?.items ?? [];
  const refund = items.find((item) => item.id === "refund");
  const needsAttention = refund?.trustState !== "TRUSTED";

  return (
    <section className="view command-view" aria-labelledby="command-heading">
      <div className="hero-row">
        <div className="view-heading">
          <p className="eyebrow">Production Command Center</p>
          <h1 id="command-heading" tabIndex={-1}>Monitor context safety across live agent pipelines.</h1>
          <p>
            DataHub supplies relationships and governance evidence. Aegis evaluates affected paths
            and blocks unsafe consequential actions before execution.
          </p>
        </div>
        <aside className={`operator-note paper-panel ${needsAttention ? "urgent" : "resolved"}`}>
          <div>
            <p className="eyebrow">Operator priority</p>
            <strong>{needsAttention ? "Investigate Refund Resolution Agent first." : "Refund pipeline restored to trusted."}</strong>
            <span>{refund?.recentChange}</span>
          </div>
          <div className="operator-actions">
            <button
              className="primary"
              onClick={() => navigate(needsAttention ? "/incidents/aegis-4821" : "/pipelines/refund")}
            >
              {needsAttention ? "Open incident" : "Review restored pipeline"}
            </button>
            <button className="secondary" disabled={prime.isPending} onClick={() => prime.mutate()}>
              {prime.isPending ? "Resetting…" : "Reset showcase"}
            </button>
          </div>
        </aside>
      </div>
      <div className="impact-strip" aria-label="Aegis impact summary">
        <div><strong>{items.length}</strong><span>agents governed</span></div>
        <div><strong>{items.filter((item) => item.openIncident).length}</strong><span>active incidents</span></div>
        <div><strong>$8,500</strong><span>unsafe exposure prevented</span></div>
        <div><strong>0</strong><span>unsafe executions</span></div>
      </div>
      <div className="fleet-meta">
        <span>{items.length} production pipelines</span>
        <span>As of {new Date(pipelines.data!.asOf).toLocaleTimeString()}</span>
      </div>
      <div className="pipeline-lanes" aria-label="Production agent pipelines">
        {items.map((pipeline) => (
          <PipelineLane key={pipeline.id} pipeline={pipeline} onSelect={() => navigate(`/pipelines/${pipeline.id}`)} />
        ))}
      </div>
    </section>
  );
}

function PipelineLane({ pipeline, onSelect }: { pipeline: PipelineSummary; onSelect: () => void }) {
  return (
    <button className={`pipeline-lane paper-panel ${pipeline.trustState.toLowerCase()}`} onClick={onSelect}>
      <div className="lane-meta">
        <StatusGlyph tone={pipeline.trustState} />
        <div>
          <strong>{pipeline.name}</strong>
          <span>{pipeline.environment} · {pipeline.owner}</span>
        </div>
        <TrustBadge tone={pipeline.trustState} />
      </div>
      <div className="fleet-exposure">
        <span>Highest-impact action</span>
        <code>{pipeline.highestImpactAction}</code>
      </div>
      <p>{pipeline.recentChange}</p>
      <div className="lane-bottom">
        <ProvenanceLabel source={pipeline.provenance[0]?.sourceSystem ?? "SEEDED_DATAHUB"} />
        <em>{pipeline.openIncident ? `${pipeline.openIncident.id} · active` : "No open block"}</em>
      </div>
    </button>
  );
}
