import { useNavigate, useParams } from "react-router-dom";
import { useGraph, usePipeline } from "../../api/hooks";
import type { Dependency } from "../../api/types";
import { ErrorState, LoadingState } from "../../components/AsyncState";
import { Breadcrumbs } from "../../components/Breadcrumbs";
import { ProvenanceLabel } from "../../components/ProvenanceLabel";
import { TrustBadge } from "../../components/TrustBadge";
import { CausalPath } from "../graph/CausalPath";
import { AgentConsole } from "../agents/AgentConsole";

export function PipelineDetailPage() {
  const { pipelineId = "refund" } = useParams();
  const navigate = useNavigate();
  const detail = usePipeline(pipelineId);
  const graph = useGraph("aegis-4821");
  if (detail.isLoading) return <div className="view"><LoadingState label="Loading pipeline context" /></div>;
  if (detail.error) return <div className="view"><ErrorState error={detail.error} retry={() => void detail.refetch()} /></div>;
  const data = detail.data!;

  return (
    <section className="view detail-view" aria-labelledby="pipeline-heading">
      <Breadcrumbs items={[{ label: "Command Center", to: "/" }, { label: data.pipeline.name }]} />
      <div className="detail-layout">
        <div className="detail-main-stack">
          <article className="paper-panel detail-main">
            <div className="detail-title">
              <div>
                <p className="eyebrow">Selected pipeline</p>
                <h1 id="pipeline-heading" tabIndex={-1}>{data.pipeline.name}</h1>
                <p>{data.pipeline.version} · {data.pipeline.owner} · {data.pipeline.environment}</p>
              </div>
              <TrustBadge tone={data.pipeline.trustState} />
            </div>
            <AttestationCard data={data.attestation} />
          </article>
          {(pipelineId === "refund" || pipelineId === "risk") && (
            <AgentConsole
              pipelineId={pipelineId}
              runtimeStatus={data.runtimeStatus}
              model={data.model}
              initialRun={data.latestRun}
            />
          )}
          {pipelineId === "refund" && graph.data ? (
            <CausalPath graph={graph.data} />
          ) : (
            <DependencyOverview groups={data.dependencies} />
          )}
          <div className="split-blocks">
            <FactList title="DataHub supplied" source="DATAHUB" items={data.factGroups.datahubSupplied} />
            <FactList title="Aegis produced" source="AEGIS" items={data.factGroups.aegisProduced} />
          </div>
        </div>
        <aside className="paper-panel detail-aside">
          <p className="eyebrow">Operational impact</p>
          <h2>Current exposure</h2>
          <dl className="definition-list">
            <div><dt>Highest-impact tool</dt><dd><code>{String(data.highestImpactPermission.tool)}</code></dd></div>
            <div><dt>Risk class</dt><dd>{String(data.highestImpactPermission.riskClass)}</dd></div>
            <div><dt>Current change</dt><dd>{data.pipeline.recentChange}</dd></div>
            <div><dt>Agent URN</dt><dd><code>{data.agent.urn}</code></dd></div>
          </dl>
          <h3>Recent context changes</h3>
          <ul className="quiet-list">{data.recentChanges.map((item) => <li key={item}>{item}</li>)}</ul>
          {data.datahubUrl && <a className="button secondary wide" href={data.datahubUrl} target="_blank" rel="noreferrer">Open context in DataHub</a>}
          {data.openIncident ? (
            <button className="primary wide" onClick={() => navigate(`/incidents/${data.openIncident!.id}`)}>Investigate incident</button>
          ) : (
            <button className="secondary wide" onClick={() => void detail.refetch()}>Refresh attestation</button>
          )}
        </aside>
      </div>
    </section>
  );
}

function AttestationCard({ data }: { data: PipelineDetailPageData["attestation"] }) {
  const stages = ["Trusted", "Invalidated", "Blocked", "Re-evaluated", "Trusted"];
  const active = data.state === "TRUSTED" && data.remediationState === "VERIFIED" ? 4 :
    data.state === "TRUSTED" ? 0 : data.state === "INVALIDATED" ? 1 : data.state === "BLOCKED" ? 2 : 3;
  return (
    <section className={`attestation ${data.decision.toLowerCase()}`}>
      <div>
        <p className="eyebrow">Current Context Attestation</p>
        <strong>{data.state.replaceAll("_", " ")}</strong>
        <span>{data.decision} · evidence {new Date(data.evidenceTimestamp).toLocaleString()}</span>
        <code>{data.id}</code>
      </div>
      <ol className="attestation-strip">
        {stages.map((stage, index) => <li key={`${stage}-${index}`} className={index <= active ? "lit" : ""}>{stage}</li>)}
      </ol>
    </section>
  );
}

type PipelineDetailPageData = NonNullable<ReturnType<typeof usePipeline>["data"]>;

function DependencyOverview({ groups }: { groups: Record<string, Dependency[]> }) {
  return (
    <section className="paper-panel dependency-overview">
      <p className="eyebrow">Relevant dependencies</p>
      <div className="dependency-grid">
        {Object.entries(groups).map(([group, items]) => items.map((item) => (
          <article key={item.urn}>
            <span>{group}</span>
            <strong>{item.name}</strong>
            <code>{item.urn}</code>
            <ProvenanceLabel source={item.provenance.sourceSystem} />
          </article>
        )))}
      </div>
    </section>
  );
}

function FactList({ title, source, items }: { title: string; source: "DATAHUB" | "AEGIS"; items: string[] }) {
  return (
    <section className="fact-list paper-panel">
      <div className="section-head"><h2>{title}</h2><ProvenanceLabel source={source} /></div>
      <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
    </section>
  );
}
