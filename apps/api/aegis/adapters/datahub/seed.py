from typing import Any

POLICY_APPROVED_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:aegis_context,"
    "policies/refund-policy-v12.md,PROD)"
)
POLICY_DRAFT_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:aegis_context,"
    "policies/refund-policy-q4-draft.md,PROD)"
)
REFUND_RAG_URN = "urn:li:dataset:(urn:li:dataPlatform:pinecone,refund-rag-index,PROD)"
REFUND_AGENT_URN = "urn:li:aiAgent:refund-resolution-agent-v2_8_4"
REFUND_TOOL_URN = "urn:li:api:refund-service.issue_refund"
RISK_EVENTS_URN = "urn:li:dataset:(urn:li:dataPlatform:aegis,account-events,PROD)"
RISK_FEATURES_URN = "urn:li:dataset:(urn:li:dataPlatform:aegis,risk-features,PROD)"
RISK_AGENT_URN = "urn:li:aiAgent:account-risk-agent-v3_1_0"
RISK_TOOL_URN = "urn:li:api:account-service.freeze_account"
SUPPORT_INDEX_URN = "urn:li:dataset:(urn:li:dataPlatform:aegis,support-index,PROD)"
SUPPORT_AGENT_URN = "urn:li:aiAgent:customer-support-agent-v4_6_2"
SUPPORT_TOOL_URN = "urn:li:api:support-service.create_ticket"
CLAIMS_INDEX_URN = "urn:li:dataset:(urn:li:dataPlatform:aegis,claims-index,PROD)"
CLAIMS_AGENT_URN = "urn:li:aiAgent:claims-triage-agent-v1_9_7"
CLAIMS_TOOL_URN = "urn:li:api:claims-service.route_claim"


PIPELINES: list[dict[str, Any]] = [
    {
        "id": "refund",
        "name": "Refund Resolution Agent",
        "version": "2.8.4",
        "owner": "Commerce AI Platform",
        "environment": "PRODUCTION",
        "source": "refund-policy-q4-draft.md",
        "context": "Refund RAG index",
        "agentUrn": REFUND_AGENT_URN,
        "tool": "issue_refund",
        "toolUrn": REFUND_TOOL_URN,
        "actionDetail": "issue_refund · monetary · max $10,000",
        "recent": [
            "docs-sync MCP replaced refund-policy-v12.md",
            "Approval state changed to not approved",
            "Affected agent path confirmed",
        ],
        "datahub": [
            "Dataset identity and environment",
            "Approval and ownership metadata",
            "Policy-to-index lineage",
            "Agent tool dependency",
            "Metadata change history",
        ],
        "aegis": [
            "Smallest affected path selected",
            "ApprovedContextSource evaluated",
            "$8,500 tool call intercepted",
            "Approved policy restoration recommended",
        ],
    },
    {
        "id": "risk",
        "name": "Account Risk Agent",
        "version": "3.1.0",
        "owner": "Trust Operations",
        "environment": "PRODUCTION",
        "source": "risk_features_daily",
        "context": "Account risk feature view",
        "agentUrn": "urn:li:aiAgent:account-risk-agent-v3_1_0",
        "tool": "freeze_account",
        "toolUrn": "urn:li:api:account-service.freeze_account",
        "actionDetail": "freeze_account · account restriction",
        "recent": [
            "Feature job missed 04:00 UTC SLA",
            "Owner notified",
            "Restriction tool held for review",
        ],
        "datahub": ["Feature view", "Freshness assertion", "Owner", "Tool dependency"],
        "aegis": ["Review decision", "Freshness warning", "Human approval required"],
    },
    {
        "id": "support",
        "name": "Customer Support Agent",
        "version": "4.6.2",
        "owner": "CX Automation",
        "environment": "PRODUCTION",
        "source": "kb-shipping-v19.md",
        "context": "Support retrieval index",
        "agentUrn": "urn:li:aiAgent:customer-support-agent-v4_6_2",
        "tool": "create_ticket",
        "toolUrn": "urn:li:api:support-service.create_ticket",
        "actionDetail": "create_ticket / escalate_case",
        "recent": [
            "Shipping policy approved",
            "Escalation skill unchanged",
            "Regression scenarios passed",
        ],
        "datahub": ["Knowledge source", "Index lineage", "Ownership"],
        "aegis": ["Allow decision", "Regression suite passed", "Attestation current"],
    },
    {
        "id": "claims",
        "name": "Claims Triage Agent",
        "version": "1.9.7",
        "owner": "Claims Platform",
        "environment": "PRODUCTION",
        "source": "claims-procedure-v8.md",
        "context": "Claims triage index",
        "agentUrn": "urn:li:aiAgent:claims-triage-agent-v1_9_7",
        "tool": "route_claim",
        "toolUrn": "urn:li:api:claims-service.route_claim",
        "actionDetail": "route_claim · workflow assignment",
        "recent": [
            "Procedure v8 approved",
            "Routing skill unchanged",
            "Nightly regression passed",
        ],
        "datahub": ["Procedure Dataset", "Index lineage", "Skill dependency"],
        "aegis": ["Allow decision", "Context source verified", "No monetary exposure"],
    },
]
