import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ControlsPage } from "./ControlsPage";

vi.mock("../../api/hooks", () => ({
  useControls: () => ({
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    data: {
      items: [
        {
          id: "approved-context-source",
          name: "ApprovedContextSource",
          version: "1",
          enabled: true,
          scope: { environment: "PRODUCTION", tool: "issue_refund" },
          conditions: [],
          missingEvidencePolicy: "BLOCK",
          lastEvaluation: null,
          coveredAgents: ["refund"],
          linkedIncidentId: "aegis-4821",
        },
        {
          id: "fresh-risk-context",
          name: "FreshRiskContext",
          version: "1",
          enabled: true,
          scope: { environment: "PRODUCTION", tool: "freeze_account" },
          conditions: [],
          missingEvidencePolicy: "BLOCK",
          lastEvaluation: null,
          coveredAgents: ["risk"],
          linkedIncidentId: "aegis-7392",
        },
      ],
    },
  }),
}));

describe("ControlsPage", () => {
  it("shows the fail-closed rule and links to its incident", () => {
    render(
      <MemoryRouter initialEntries={["/controls"]}>
        <Routes><Route path="/controls" element={<ControlsPage />} /></Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("ON MISSING EVIDENCE")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open linked incident" }))
      .toHaveAttribute("href", "/incidents/aegis-4821");
  });

  it("exposes the freshness control for the account risk agent", () => {
    render(
      <MemoryRouter initialEntries={["/controls/fresh-risk-context"]}>
        <Routes><Route path="/controls/:controlId" element={<ControlsPage />} /></Routes>
      </MemoryRouter>,
    );
    expect(screen.getAllByText("FreshRiskContext").length).toBeGreaterThan(0);
    expect(screen.getByText("risk.ageSeconds <= 900")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open linked incident" }))
      .toHaveAttribute("href", "/incidents/aegis-7392");
  });
});
