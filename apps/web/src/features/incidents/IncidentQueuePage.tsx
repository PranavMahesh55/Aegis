import { useState } from "react";
import { Link } from "react-router-dom";
import { useIncidents } from "../../api/hooks";
import { EmptyState, ErrorState, LoadingState } from "../../components/AsyncState";
import { Breadcrumbs } from "../../components/Breadcrumbs";
import { TrustBadge } from "../../components/TrustBadge";

export function IncidentQueuePage() {
  const incidents = useIncidents();
  const [filter, setFilter] = useState<"ALL" | "ACTIVE" | "RESOLVED">("ALL");
  if (incidents.isLoading) return <div className="view"><LoadingState label="Loading incident queue" /></div>;
  if (incidents.error) return <div className="view"><ErrorState error={incidents.error} retry={() => void incidents.refetch()} /></div>;
  const items = incidents.data?.items ?? [];
  const visibleItems = items.filter((item) => (
    filter === "ALL" || (filter === "RESOLVED" ? item.state === "RESOLVED" : item.state !== "RESOLVED")
  ));
  return (
    <section className="view queue-view" aria-labelledby="incidents-heading">
      <Breadcrumbs items={[{ label: "Command Center", to: "/" }, { label: "Incidents" }]} />
      <div className="view-heading compact-heading">
        <p className="eyebrow">Operational queue</p>
        <h1 id="incidents-heading" tabIndex={-1}>Context-safety incidents.</h1>
        <p>Prioritized decisions that require investigation, remediation, or verified closure.</p>
      </div>
      <div className="queue-filters" role="group" aria-label="Filter incidents">
        {(["ALL", "ACTIVE", "RESOLVED"] as const).map((value) => {
          const count = value === "ALL" ? items.length : items.filter((item) => (
            value === "RESOLVED" ? item.state === "RESOLVED" : item.state !== "RESOLVED"
          )).length;
          return (
            <button key={value} className={filter === value ? "active" : ""} aria-pressed={filter === value} onClick={() => setFilter(value)}>
              {value === "ALL" ? "All incidents" : value.toLowerCase()} <span>{count}</span>
            </button>
          );
        })}
      </div>
      {visibleItems.length === 0 ? <EmptyState>No incidents match the current filter.</EmptyState> : (
        <div className="incident-queue">
          {visibleItems.map((incident) => (
            <Link className={`incident-row paper-panel ${incident.decision.toLowerCase()}`} key={incident.id} to={`/incidents/${incident.id}`}>
              <div><code>{incident.id}</code><strong>{incident.pipelineName}</strong></div>
              <div><span>Causal change</span><strong>{incident.causalChange}</strong></div>
              <div><span>Prevented action</span><strong>{incident.preventedAction}</strong></div>
              <TrustBadge tone={incident.state === "RESOLVED" ? "TRUSTED" : incident.decision} label={incident.state} />
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
