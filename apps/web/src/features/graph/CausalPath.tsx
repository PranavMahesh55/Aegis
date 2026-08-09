import type { GraphProjection } from "../../api/types";
import { ProvenanceLabel } from "../../components/ProvenanceLabel";

export function CausalPath({ graph, compact = false }: { graph: GraphProjection; compact?: boolean }) {
  return (
    <section className={`lineage-wrap paper-panel ${compact ? "compact" : ""}`} aria-labelledby="path-heading">
      <div className="section-head">
        <div>
          <p className="eyebrow">Selected affected path</p>
          <h2 id="path-heading">DataHub context lineage</h2>
        </div>
        <span className="path-caption">source → retrieval → agent → tool</span>
      </div>
      <ol className="lineage" aria-label="Causal path">
        {graph.nodes.map((node, index) => (
          <li className="lineage-step" key={node.id}>
            <article className={`lineage-node ${node.status.toLowerCase()}`}>
              <span>{node.kind.replaceAll("_", " ")}</span>
              <strong>{node.label}</strong>
              <code>{node.urn}</code>
              <ProvenanceLabel source={node.sourceSystem} />
            </article>
            {index < graph.nodes.length - 1 && (
              <span className={`edge ${graph.edges[index]?.status.toLowerCase()}`} aria-hidden="true" />
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

