import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { IncidentSummary } from "../../api/types";
import { IncidentQueuePage } from "./IncidentQueuePage";

const incidents: IncidentSummary[] = [
  {
    id: "aegis-4821",
    pipelineId: "refund",
    pipelineName: "Refund Resolution Agent",
    environment: "PRODUCTION",
    state: "BLOCKED",
    decision: "BLOCK",
    causalChange: "Unapproved refund policy entered context",
    preventedAction: "$8,500 refund blocked before execution",
    recommendedNextStep: "Investigate evidence",
    openedAt: "2026-08-06T18:50:46Z",
    resolvedAt: null,
    version: 2,
  },
  {
    id: "aegis-7392",
    pipelineId: "risk",
    pipelineName: "Account Risk Agent",
    environment: "PRODUCTION",
    state: "RE_EVALUATED",
    decision: "REVIEW",
    causalChange: "Risk features missed their freshness SLA",
    preventedAction: "freeze_account held for analyst approval",
    recommendedNextStep: "Re-attest refreshed features",
    openedAt: "2026-08-08T13:42:18Z",
    resolvedAt: null,
    version: 3,
  },
  {
    id: "aegis-6158",
    pipelineId: "support",
    pipelineName: "Customer Support Agent",
    environment: "PRODUCTION",
    state: "RESOLVED",
    decision: "ALLOW",
    causalChange: "Shipping knowledge owner metadata was removed",
    preventedAction: "escalate_case paused until ownership was restored",
    recommendedNextStep: "No action",
    openedAt: "2026-08-07T16:18:09Z",
    resolvedAt: "2026-08-07T16:46:31Z",
    version: 5,
  },
];

vi.mock("../../api/hooks", () => ({
  useIncidents: () => ({
    isLoading: false,
    error: null,
    data: { items: incidents, total: incidents.length },
    refetch: vi.fn(),
  }),
}));

describe("IncidentQueuePage", () => {
  it("shows active and historical incidents with working detail links", () => {
    render(<MemoryRouter><IncidentQueuePage /></MemoryRouter>);

    expect(screen.getByText("Refund Resolution Agent")).toBeInTheDocument();
    expect(screen.getByText("Account Risk Agent")).toBeInTheDocument();
    expect(screen.getByText("Customer Support Agent")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Account Risk Agent/i }))
      .toHaveAttribute("href", "/incidents/aegis-7392");
    expect(screen.getByRole("link", { name: /Customer Support Agent/i }))
      .toHaveAttribute("href", "/incidents/aegis-6158");
  });

  it("filters the queue without hiding incident history by default", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><IncidentQueuePage /></MemoryRouter>);

    await user.click(screen.getByRole("button", { name: /resolved 1/i }));
    expect(screen.getByText("Customer Support Agent")).toBeInTheDocument();
    expect(screen.queryByText("Refund Resolution Agent")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /active 2/i }));
    expect(screen.getByText("Refund Resolution Agent")).toBeInTheDocument();
    expect(screen.getByText("Account Risk Agent")).toBeInTheDocument();
  });
});
