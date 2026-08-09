from typing import Any, Literal

from pydantic import BaseModel, Field

from aegis.domain.enums import (
    AttestationState,
    DataMode,
    Decision,
    GraphStatus,
    IncidentState,
    Relationship,
    RunStatus,
    RunStepType,
    SourceSystem,
    TrustState,
)


class Provenance(BaseModel):
    sourceSystem: SourceSystem
    retrievedAt: str
    cached: bool = False
    evidenceId: str | None = None


class IncidentLink(BaseModel):
    id: str
    state: IncidentState


class PipelineSummary(BaseModel):
    id: str
    name: str
    version: str
    environment: str
    trustState: TrustState
    recentChange: str
    highestImpactAction: str
    actionDetail: str
    owner: str
    openIncident: IncidentLink | None = None
    provenance: list[Provenance] = Field(default_factory=list)


class Dependency(BaseModel):
    urn: str
    name: str
    kind: str
    status: str
    version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance


class ConditionResult(BaseModel):
    field: str
    operator: str
    expected: Any
    actual: Any
    passed: bool
    evidenceId: str | None = None


class ControlEvaluation(BaseModel):
    id: str
    controlId: str
    decision: Decision
    reasonCode: str
    conditionResults: list[ConditionResult]
    evidenceIds: list[str]
    evaluatedAt: str


class RegressionScenario(BaseModel):
    id: str
    label: str
    status: Literal["PASSED", "FAILED"]
    expected: str
    actual: str


class RegressionRun(BaseModel):
    id: str
    suiteId: str
    status: Literal["PASSED", "FAILED"]
    scenarios: list[RegressionScenario]
    completedAt: str


class Attestation(BaseModel):
    id: str
    agentUrn: str
    agentVersion: str
    environment: str
    owner: str
    state: AttestationState
    decision: Decision
    graphFingerprint: str
    evidenceTimestamp: str
    incidentId: str | None = None
    controlResults: list[ControlEvaluation] = Field(default_factory=list)
    regressionResults: list[RegressionRun] = Field(default_factory=list)
    remediationState: str = "NONE"
    supersedesId: str | None = None


class GraphNode(BaseModel):
    id: str
    urn: str
    entityType: Literal["DATASET", "AI_AGENT", "API", "DOCUMENT"]
    kind: Literal["POLICY_SOURCE", "RETRIEVAL_INDEX", "AGENT", "TOOL"]
    label: str
    status: GraphStatus
    metadata: dict[str, Any]
    sourceSystem: SourceSystem


class EdgeEvidence(BaseModel):
    id: str
    label: str


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship: Relationship
    status: Literal["NORMAL", "AFFECTED", "RESTORED"]
    sourceSystem: SourceSystem
    evidence: list[EdgeEvidence]


class GraphProjection(BaseModel):
    rootChangeUrn: str
    selectedPathNodeIds: list[str]
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    capturedAt: str
    cached: bool


class PipelineDetail(BaseModel):
    pipeline: PipelineSummary
    agent: Dependency
    attestation: Attestation
    dependencies: dict[str, list[Dependency]]
    highestImpactPermission: dict[str, Any]
    recentChanges: list[str]
    openIncident: IncidentLink | None
    factGroups: dict[str, list[str]]
    executionCapability: Literal["EXECUTABLE", "CATALOG_ONLY"] = "CATALOG_ONLY"
    runtimeStatus: Literal[
        "READY", "MODEL_NOT_CONFIGURED", "FIXTURE_ONLY", "DATAHUB_UNAVAILABLE"
    ] = "FIXTURE_ONLY"
    model: str | None = None
    skills: list[str] = Field(default_factory=list)
    datahubUrl: str | None = None
    latestRun: "AgentRun | None" = None


class IncidentSummary(BaseModel):
    id: str
    pipelineId: str
    pipelineName: str
    environment: str
    state: IncidentState
    decision: Decision
    causalChange: str
    preventedAction: str
    recommendedNextStep: str
    openedAt: str
    resolvedAt: str | None = None
    version: int


class EvidenceItem(BaseModel):
    id: str
    label: str
    value: str
    detail: str
    sourceSystem: SourceSystem
    raw: dict[str, Any] | None = None


class AuditEvent(BaseModel):
    id: str
    type: str
    actor: str
    occurredAt: str
    detail: str
    sourceSystem: SourceSystem


class IncidentDetail(BaseModel):
    incident: IncidentSummary
    attestation: Attestation
    availableActions: list[str]
    evidenceSummary: list[EvidenceItem]
    auditEvents: list[AuditEvent]
    datahubIncidentUrn: str | None = None
    writeBackState: str


class ToolCall(BaseModel):
    tool: Literal["issue_refund"] = "issue_refund"
    amount: float = Field(gt=0, le=10000)
    currency: Literal["USD"] = "USD"
    caseId: str = Field(min_length=3, max_length=64)


class FreezeAccountCall(BaseModel):
    tool: Literal["freeze_account"] = "freeze_account"
    accountId: str = Field(min_length=3, max_length=64)


class RunSubject(BaseModel):
    type: Literal["CASE", "ACCOUNT"]
    id: str = Field(min_length=2, max_length=128)


class AgentRunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    subject: RunSubject


class CatalogEvidenceSnapshot(BaseModel):
    capturedAt: str
    datahubAvailable: bool
    approvalStatus: str | None = None
    lineageComplete: bool
    observedAt: str | None = None
    ageSeconds: int | None = None
    evidenceIds: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class GateDecision(BaseModel):
    decision: Decision
    reasonCode: str
    controlId: str
    evidenceSnapshot: CatalogEvidenceSnapshot
    evaluationId: str | None = None


class RunStep(BaseModel):
    id: str
    runId: str
    sequence: int
    type: RunStepType
    title: str
    detail: str
    sourceSystem: SourceSystem
    occurredAt: str
    payload: dict[str, Any] = Field(default_factory=dict)


class DataHubRunWriteback(BaseModel):
    recordType: Literal["INCIDENT", "ATTESTATION"]
    status: Literal["WRITTEN", "FAILED"]
    urn: str | None = None
    attemptedAt: str
    detail: str


class AgentRun(BaseModel):
    id: str
    pipelineId: str
    status: RunStatus
    message: str
    subject: RunSubject
    model: str
    startedAt: str
    updatedAt: str
    completedAt: str | None = None
    output: str | None = None
    proposedToolCall: dict[str, Any] | None = None
    gateDecision: GateDecision | None = None
    toolReceipt: dict[str, Any] | None = None
    datahubWriteback: DataHubRunWriteback | None = None
    errorCode: str | None = None
    errorDetail: str | None = None
    steps: list[RunStep] = Field(default_factory=list)


class AgentRunAccepted(BaseModel):
    runId: str
    status: RunStatus
    streamUrl: str


class ContextChangeRequest(BaseModel):
    pipelineId: Literal["refund"] = "refund"
    scenario: Literal["UNAPPROVED_REFUND_POLICY"] = "UNAPPROVED_REFUND_POLICY"
    expectedIncidentVersion: int


class EvaluateRequest(BaseModel):
    expectedVersion: int
    toolCall: ToolCall


class RemediateRequest(BaseModel):
    expectedVersion: int
    strategy: Literal["RESTORE_APPROVED_SOURCE"] = "RESTORE_APPROVED_SOURCE"


class VerifyRequest(BaseModel):
    expectedVersion: int
    suiteId: Literal["refund-safety-v1"] = "refund-safety-v1"


class ResetRequest(BaseModel):
    target: Literal["HEALTHY_BASELINE"] = "HEALTHY_BASELINE"


class RuntimeToolRequest(BaseModel):
    pipelineId: Literal["refund"] = "refund"
    agentVersion: str = "2.8.4"
    toolCall: ToolCall


class ControlDefinition(BaseModel):
    id: str
    name: str
    version: str
    enabled: bool
    scope: dict[str, Any]
    conditions: list[dict[str, Any]]
    missingEvidencePolicy: Literal["BLOCK"]
    lastEvaluation: ControlEvaluation | None
    coveredAgents: list[str]
    linkedIncidentId: str


class ProblemDetail(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    code: str
    traceId: str
    errors: list[Any] = Field(default_factory=list)


class SystemStatus(BaseModel):
    api: Literal["HEALTHY", "DEGRADED"]
    frontend: Literal["AVAILABLE"]
    datahub: dict[str, Any]
    dataMode: DataMode
    seedVersion: str
    projection: dict[str, Any]
