import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { GraphProjection } from "../../api/types";
import { CausalPath } from "./CausalPath";

const graph: GraphProjection = {
  rootChangeUrn: "urn:policy",
  selectedPathNodeIds: ["source", "rag", "agent", "tool"],
  capturedAt: "2026-08-06T22:00:00Z",
  cached: false,
  nodes: [
    ["source", "POLICY_SOURCE", "refund-policy-q4-draft.md", "urn:policy"],
    ["rag", "RETRIEVAL_INDEX", "Refund RAG index", "urn:rag"],
    ["agent", "AGENT", "Refund Resolution Agent", "urn:agent"],
    ["tool", "TOOL", "issue_refund", "urn:tool"],
  ].map(([id, kind, label, urn]) => ({
    id,
    urn,
    entityType: kind === "AGENT" ? "AI_AGENT" : kind === "TOOL" ? "API" : "DATASET",
    kind,
    label,
    status: "BLOCKED",
    metadata: {},
    sourceSystem: "DATAHUB" as const,
  })),
  edges: ["one", "two", "three"].map((id) => ({
    id,
    source: "source",
    target: "tool",
    relationship: "DOWNSTREAM_OF",
    status: "AFFECTED",
    sourceSystem: "DATAHUB" as const,
    evidence: [],
  })),
};

describe("CausalPath", () => {
  it("renders only the selected four-node path with provenance", () => {
    render(<CausalPath graph={graph} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
    expect(screen.getByText("refund-policy-q4-draft.md")).toBeInTheDocument();
    expect(screen.getByText("issue_refund")).toBeInTheDocument();
    expect(screen.getAllByText("DataHub")).toHaveLength(4);
  });
});

