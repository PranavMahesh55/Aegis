import type { SourceSystem } from "../api/types";

export function ProvenanceLabel({ source }: { source: SourceSystem }) {
  const label = {
    DATAHUB: "DataHub",
    DATAHUB_MCP: "DataHub MCP",
    AEGIS: "Aegis",
    OPENAI: "OpenAI model",
    BUSINESS_MCP: "Business MCP",
    SEEDED_DATAHUB: "Seeded DataHub metadata",
    SIMULATED_EXTERNAL: "Simulated external action",
  }[source];
  return <span className={`provenance provenance-${source.toLowerCase()}`}>{label}</span>;
}
