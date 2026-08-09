import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { IncidentWorkspacePage } from "./IncidentWorkspacePage";

const mutation = { isPending: false, error: null, mutate: vi.fn() };

vi.mock("../../api/hooks", () => ({
  usePipeline: () => ({ data: null }),
  useIncident: () => ({
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    data: {
      incident: {
        id: "aegis-4821",
        pipelineId: "refund",
        pipelineName: "Refund Resolution Agent",
        environment: "PRODUCTION",
        state: "BLOCKED",
        decision: "BLOCK",
        causalChange: "refund-policy-q4-draft.md entered context",
        preventedAction: "$8,500 refund blocked before execution",
        recommendedNextStep: "Investigate evidence",
        openedAt: "2026-08-06T18:50:46Z",
        resolvedAt: null,
        version: 2,
      },
      attestation: {
        id: "att-refund-2",
        agentUrn: "urn:agent",
        agentVersion: "2.8.4",
        environment: "PRODUCTION",
        owner: "Commerce AI Platform",
        state: "BLOCKED",
        decision: "BLOCK",
        graphFingerprint: "sha256:test",
        evidenceTimestamp: "2026-08-06T18:50:46Z",
        incidentId: "aegis-4821",
        controlResults: [],
        regressionResults: [],
        remediationState: "NONE",
      },
      availableActions: ["OPEN_EVIDENCE", "REMEDIATE"],
      evidenceSummary: [{
        id: "evidence-tool-call",
        label: "Intercepted tool call",
        value: "issue_refund({ amount: 8500 })",
        detail: "The simulated executor was not called.",
        sourceSystem: "SIMULATED_EXTERNAL",
        raw: { amount: 8500, executed: false },
      }],
      auditEvents: [],
      datahubIncidentUrn: "urn:li:incident:aegis-4821",
      writeBackState: "ACTIVE",
    },
  }),
  useGraph: () => ({
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    data: {
      rootChangeUrn: "urn:policy",
      selectedPathNodeIds: ["source", "rag", "agent", "tool"],
      nodes: [
        ["source", "POLICY_SOURCE", "refund-policy-q4-draft.md"],
        ["rag", "RETRIEVAL_INDEX", "Refund RAG index"],
        ["agent", "AGENT", "Refund Resolution Agent"],
        ["tool", "TOOL", "issue_refund"],
      ].map(([id, kind, label]) => ({
        id, kind, label, urn: `urn:${id}`, entityType: "DATASET", status: "BLOCKED",
        metadata: {}, sourceSystem: "SEEDED_DATAHUB",
      })),
      edges: [],
      capturedAt: "2026-08-06T18:50:46Z",
      cached: false,
    },
  }),
  useWorkflowMutation: () => mutation,
  useResetMutation: () => mutation,
}));

describe("IncidentWorkspacePage", () => {
  it("keeps evidence and raw metadata behind separate disclosures", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/incidents/aegis-4821"]}>
        <Routes>
          <Route path="/incidents/:incidentId" element={<IncidentWorkspacePage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getAllByRole("button", { name: "Investigate evidence" })).toHaveLength(1);
    expect(screen.queryByText("Intercepted tool call")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open evidence" }));
    expect(screen.getByText("Intercepted tool call")).toBeInTheDocument();
    expect(screen.getByText("Raw metadata and audit payload")).toBeInTheDocument();
    expect(screen.getByText(/"executed": false/)).not.toBeVisible();
    await user.click(screen.getByText("Raw metadata and audit payload"));
    expect(screen.getByText(/"executed": false/)).toBeVisible();
  });
});
