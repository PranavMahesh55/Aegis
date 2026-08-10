import { useEffect } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { usePipelines, useStatus } from "../api/hooks";
import { StatusGlyph } from "../components/StatusGlyph";
import { TrustBadge } from "../components/TrustBadge";

const nav = [
  ["/", "Command Center"],
  ["/pipelines/refund", "Pipelines"],
  ["/incidents", "Incidents"],
  ["/controls", "Controls"],
] as const;

const incidentPipelines: Record<string, string> = {
  "aegis-4821": "refund",
  "aegis-7392": "risk",
  "aegis-6158": "support",
  "aegis-4770": "claims",
};

const controlPipelines: Record<string, string> = {
  "approved-context-source": "refund",
  "fresh-risk-context": "risk",
};

export function AppShell() {
  const location = useLocation();
  const status = useStatus();
  const pipelines = usePipelines();
  const incidentId = location.pathname.match(/incidents\/([^/]+)/)?.[1];
  const controlId = location.pathname.match(/controls\/([^/]+)/)?.[1];
  const pipelineId = location.pathname.match(/pipelines\/([^/]+)/)?.[1] ??
    (incidentId ? incidentPipelines[incidentId] : undefined) ??
    (controlId ? controlPipelines[controlId] : undefined) ??
    "refund";
  const selected = pipelines.data?.items.find((item) => item.id === pipelineId) ??
    pipelines.data?.items.find((item) => item.id === "refund");

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    window.requestAnimationFrame(() => {
      const heading = document.querySelector<HTMLElement>("main h1");
      heading?.focus({ preventScroll: true });
    });
  }, [location.pathname]);

  const connection = status.data?.datahub.state ?? "CHECKING";
  const connected = connection === "CONNECTED";
  const connectionTone = connected ? "trusted" : connection === "DEGRADED" ? "blocked" : "review";

  return (
    <div className="aegis-app">
      <header className="topbar paper-panel">
        <NavLink className="brand" to="/" aria-label="Open Command Center">
          <span className="brand-mark">AG</span>
          <span>
            <strong>Aegis</strong>
            <em>Runtime context safety</em>
          </span>
        </NavLink>
        <nav aria-label="Primary navigation">
          {nav.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"}>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="connection" aria-live="polite">
          <StatusGlyph tone={connectionTone} />
          <span>
            {connected
              ? "DataHub connected"
              : connection === "SEEDED_OFFLINE"
                ? "Showcase ready"
                : connection.replaceAll("_", " ").toLowerCase()}
          </span>
        </div>
        <div className="context-line">
          <span>{selected?.name ?? "Production agent fleet"}</span>
          <span>{selected?.environment ?? "Production"}</span>
          {selected?.openIncident && <span>{selected.openIncident.id}</span>}
          {selected && <TrustBadge tone={selected.trustState} />}
        </div>
      </header>
      <main id="main-content">
        <Outlet />
      </main>
    </div>
  );
}
