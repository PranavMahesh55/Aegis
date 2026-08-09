import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PipelineSummary } from "../../api/types";
import { CommandCenterPage } from "./CommandCenterPage";

const pipelines: PipelineSummary[] = [
  {
    id: "refund",
    name: "Refund Resolution Agent",
    version: "2.8.4",
    environment: "PRODUCTION",
    trustState: "BLOCKED",
    recentChange: "Unapproved refund-policy source entered context",
    highestImpactAction: "issue_refund",
    actionDetail: "issue_refund · monetary · max $10,000",
    owner: "Commerce AI Platform",
    openIncident: { id: "aegis-4821", state: "BLOCKED" },
    provenance: [{ sourceSystem: "SEEDED_DATAHUB", retrievedAt: "2026-08-06T22:00:00Z", cached: false }],
  },
  {
    id: "support",
    name: "Customer Support Agent",
    version: "4.6.2",
    environment: "PRODUCTION",
    trustState: "TRUSTED",
    recentChange: "Approved support knowledge current",
    highestImpactAction: "create_ticket",
    actionDetail: "create_ticket / escalate_case",
    owner: "CX Automation",
    openIncident: null,
    provenance: [{ sourceSystem: "SEEDED_DATAHUB", retrievedAt: "2026-08-06T22:00:00Z", cached: false }],
  },
];

vi.mock("../../api/hooks", () => ({
  usePrimeMutation: () => ({ isPending: false, mutate: vi.fn() }),
  usePipelines: () => ({
    isLoading: false,
    error: null,
    data: {
      items: pipelines,
      asOf: "2026-08-06T22:00:00Z",
      cached: false,
      dataMode: "SEEDED_DEMO",
    },
    refetch: vi.fn(),
  }),
}));

function Location() {
  return <span data-testid="location">{useLocation().pathname}</span>;
}

describe("CommandCenterPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("makes the blocked refund exposure immediately visible", () => {
    render(<MemoryRouter><CommandCenterPage /></MemoryRouter>);
    expect(screen.getAllByText("Refund Resolution Agent").length).toBeGreaterThan(0);
    expect(screen.getByText("issue_refund")).toBeInTheDocument();
    expect(screen.getAllByText("BLOCKED").length).toBeGreaterThan(0);
    expect(screen.getByText("aegis-4821 · active")).toBeInTheDocument();
    expect(screen.getByText("$8,500")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset showcase" })).toBeInTheDocument();
  });

  it("opens the selected pipeline route", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<><CommandCenterPage /><Location /></>} />
          <Route path="/pipelines/:id" element={<Location />} />
        </Routes>
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: /Customer Support Agent/i }));
    expect(screen.getByTestId("location")).toHaveTextContent("/pipelines/support");
  });
});
