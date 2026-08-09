import type {
  ControlDefinition,
  AgentRun,
  GraphProjection,
  IncidentDetail,
  IncidentSummary,
  PipelineDetail,
  PipelineSummary,
  ProblemDetail,
  SystemStatus,
} from "./types";

export class ApiError extends Error {
  constructor(public readonly problem: ProblemDetail) {
    super(problem.detail);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const payload = (await response.json()) as T | ProblemDetail;
  if (!response.ok) throw new ApiError(payload as ProblemDetail);
  return payload as T;
}

export const api = {
  status: () => request<SystemStatus>("/api/system/status"),
  pipelines: () =>
    request<{ items: PipelineSummary[]; asOf: string; cached: boolean; dataMode: string }>(
      "/api/pipelines",
    ),
  pipeline: (id: string) => request<PipelineDetail>(`/api/pipelines/${id}`),
  incidents: () => request<{ items: IncidentSummary[]; total: number }>("/api/incidents"),
  incident: (id: string) => request<IncidentDetail>(`/api/incidents/${id}`),
  graph: (id: string) => request<GraphProjection>(`/api/incidents/${id}/graph`),
  controls: () => request<{ items: ControlDefinition[] }>("/api/controls"),
  run: (id: string) => request<AgentRun>(`/api/runs/${id}`),
  createRun: (
    pipelineId: string,
    body: { message: string; subject: { type: "CASE" | "ACCOUNT"; id: string } },
  ) =>
    request<{ runId: string; status: string; streamUrl: string }>(
      `/api/agents/${pipelineId}/runs`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  reset: () =>
    request<Record<string, unknown>>("/api/demo/reset", {
      method: "POST",
      body: JSON.stringify({ target: "HEALTHY_BASELINE" }),
    }),
  prime: () =>
    request<Record<string, unknown>>("/api/demo/prime", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  contextChange: (version: number) =>
    request<Record<string, unknown>>("/api/demo/context-change", {
      method: "POST",
      body: JSON.stringify({
        pipelineId: "refund",
        scenario: "UNAPPROVED_REFUND_POLICY",
        expectedIncidentVersion: version,
      }),
    }),
  evaluate: (version: number) =>
    request<Record<string, unknown>>("/api/incidents/aegis-4821/evaluate", {
      method: "POST",
      body: JSON.stringify({
        expectedVersion: version,
        toolCall: {
          tool: "issue_refund",
          amount: 8500,
          currency: "USD",
          caseId: "CX-90214",
        },
      }),
    }),
  remediate: (version: number) =>
    request<Record<string, unknown>>("/api/incidents/aegis-4821/remediate", {
      method: "POST",
      body: JSON.stringify({ expectedVersion: version, strategy: "RESTORE_APPROVED_SOURCE" }),
    }),
  verify: (version: number) =>
    request<Record<string, unknown>>("/api/incidents/aegis-4821/verify", {
      method: "POST",
      body: JSON.stringify({ expectedVersion: version, suiteId: "refund-safety-v1" }),
    }),
};
