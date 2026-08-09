export type TrustState = "TRUSTED" | "REVIEW" | "BLOCKED";
export type IncidentState =
  | "HEALTHY"
  | "CONTEXT_CHANGED"
  | "BLOCKED"
  | "REMEDIATION_APPLIED"
  | "RE_EVALUATED"
  | "RESOLVED";
export type Decision = "ALLOW" | "REVIEW" | "BLOCK";
export type SourceSystem =
  | "DATAHUB"
  | "DATAHUB_MCP"
  | "AEGIS"
  | "OPENAI"
  | "BUSINESS_MCP"
  | "SEEDED_DATAHUB"
  | "SIMULATED_EXTERNAL";
export type RunStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "BLOCKED" | "REVIEW";

export interface Provenance {
  sourceSystem: SourceSystem;
  retrievedAt: string;
  cached: boolean;
  evidenceId?: string | null;
}

export interface PipelineSummary {
  id: string;
  name: string;
  version: string;
  environment: string;
  trustState: TrustState;
  recentChange: string;
  highestImpactAction: string;
  actionDetail: string;
  owner: string;
  openIncident: { id: string; state: IncidentState } | null;
  provenance: Provenance[];
}

export interface Dependency {
  urn: string;
  name: string;
  kind: string;
  status: string;
  version?: string | null;
  metadata: Record<string, unknown>;
  provenance: Provenance;
}

export interface Evaluation {
  id: string;
  controlId: string;
  decision: Decision;
  reasonCode: string;
  conditionResults: Array<{
    field: string;
    operator: string;
    expected: unknown;
    actual: unknown;
    passed: boolean;
    evidenceId?: string;
  }>;
  evidenceIds: string[];
  evaluatedAt: string;
}

export interface RegressionRun {
  id: string;
  suiteId: string;
  status: "PASSED" | "FAILED";
  scenarios: Array<{
    id: string;
    label: string;
    status: "PASSED" | "FAILED";
    expected: string;
    actual: string;
  }>;
  completedAt: string;
}

export interface Attestation {
  id: string;
  agentUrn: string;
  agentVersion: string;
  environment: string;
  owner: string;
  state: string;
  decision: Decision;
  graphFingerprint: string;
  evidenceTimestamp: string;
  incidentId: string | null;
  controlResults: Evaluation[];
  regressionResults: RegressionRun[];
  remediationState: string;
}

export interface PipelineDetail {
  pipeline: PipelineSummary;
  agent: Dependency;
  attestation: Attestation;
  dependencies: Record<string, Dependency[]>;
  highestImpactPermission: Record<string, unknown>;
  recentChanges: string[];
  openIncident: { id: string; state: IncidentState } | null;
  factGroups: { datahubSupplied: string[]; aegisProduced: string[] };
  executionCapability: "EXECUTABLE" | "CATALOG_ONLY";
  runtimeStatus: "READY" | "MODEL_NOT_CONFIGURED" | "FIXTURE_ONLY" | "DATAHUB_UNAVAILABLE";
  model: string | null;
  skills: string[];
  datahubUrl: string | null;
  latestRun: AgentRun | null;
}

export interface CatalogEvidenceSnapshot {
  capturedAt: string;
  datahubAvailable: boolean;
  approvalStatus: string | null;
  lineageComplete: boolean;
  observedAt: string | null;
  ageSeconds: number | null;
  evidenceIds: string[];
  raw: Record<string, unknown>;
}

export interface GateDecision {
  decision: Decision;
  reasonCode: string;
  controlId: string;
  evidenceSnapshot: CatalogEvidenceSnapshot;
  evaluationId: string | null;
}

export interface RunStep {
  id: string;
  runId: string;
  sequence: number;
  type: string;
  title: string;
  detail: string;
  sourceSystem: SourceSystem;
  occurredAt: string;
  payload: Record<string, unknown>;
}

export interface DataHubRunWriteback {
  recordType: "INCIDENT" | "ATTESTATION";
  status: "WRITTEN" | "FAILED";
  urn: string | null;
  attemptedAt: string;
  detail: string;
}

export interface AgentRun {
  id: string;
  pipelineId: string;
  status: RunStatus;
  message: string;
  subject: { type: "CASE" | "ACCOUNT"; id: string };
  model: string;
  startedAt: string;
  updatedAt: string;
  completedAt: string | null;
  output: string | null;
  proposedToolCall: Record<string, unknown> | null;
  gateDecision: GateDecision | null;
  toolReceipt: Record<string, unknown> | null;
  datahubWriteback: DataHubRunWriteback | null;
  errorCode: string | null;
  errorDetail: string | null;
  steps: RunStep[];
}

export interface GraphNode {
  id: string;
  urn: string;
  entityType: string;
  kind: string;
  label: string;
  status: string;
  metadata: Record<string, unknown>;
  sourceSystem: SourceSystem;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship: string;
  status: string;
  sourceSystem: SourceSystem;
  evidence: Array<{ id: string; label: string }>;
}

export interface GraphProjection {
  rootChangeUrn: string;
  selectedPathNodeIds: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  capturedAt: string;
  cached: boolean;
}

export interface IncidentSummary {
  id: string;
  pipelineId: string;
  pipelineName: string;
  environment: string;
  state: IncidentState;
  decision: Decision;
  causalChange: string;
  preventedAction: string;
  recommendedNextStep: string;
  openedAt: string;
  resolvedAt: string | null;
  version: number;
}

export interface EvidenceItem {
  id: string;
  label: string;
  value: string;
  detail: string;
  sourceSystem: SourceSystem;
  raw: Record<string, unknown> | null;
}

export interface IncidentDetail {
  incident: IncidentSummary;
  attestation: Attestation;
  availableActions: string[];
  evidenceSummary: EvidenceItem[];
  auditEvents: Array<{
    id: string;
    type: string;
    actor: string;
    occurredAt: string;
    detail: string;
    sourceSystem: SourceSystem;
  }>;
  datahubIncidentUrn: string | null;
  writeBackState: string;
}

export interface SystemStatus {
  api: "HEALTHY" | "DEGRADED";
  frontend: "AVAILABLE";
  datahub: {
    state: string;
    instance: string;
    serverVersion: string | null;
    lastSuccessfulQueryAt: string | null;
    detail: string;
  };
  dataMode: string;
  seedVersion: string;
  projection: { cached: boolean; capturedAt: string };
}

export interface ControlDefinition {
  id: string;
  name: string;
  version: string;
  enabled: boolean;
  scope: Record<string, unknown>;
  conditions: Array<Record<string, unknown>>;
  missingEvidencePolicy: "BLOCK";
  lastEvaluation: Evaluation | null;
  coveredAgents: string[];
  linkedIncidentId: string;
}

export interface ProblemDetail {
  title: string;
  status: number;
  detail: string;
  code: string;
  traceId: string;
}
