#!/usr/bin/env python3
"""Idempotently seed the DataHub entities used by the Aegis demo."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from aegis.adapters.datahub.seed import (  # noqa: E402
    POLICY_APPROVED_URN,
    POLICY_DRAFT_URN,
    CLAIMS_AGENT_URN,
    CLAIMS_INDEX_URN,
    CLAIMS_TOOL_URN,
    REFUND_AGENT_URN,
    REFUND_RAG_URN,
    REFUND_TOOL_URN,
    RISK_AGENT_URN,
    RISK_EVENTS_URN,
    RISK_FEATURES_URN,
    RISK_TOOL_URN,
    SUPPORT_AGENT_URN,
    SUPPORT_INDEX_URN,
    SUPPORT_TOOL_URN,
)

SEED_VERSION = "aegis-demo-v1"
PROPERTIES_FILE = ROOT / "infra" / "datahub" / "structured-properties.yaml"


def require_sdk() -> None:
    try:
        import datahub  # noqa: F401
    except ImportError as error:
        raise SystemExit(
            "DataHub SDK is not installed. Use Python 3.12/3.13 and run "
            "`make install-datahub`, or execute this inside the Aegis Docker image."
        ) from error


def main() -> None:
    require_sdk()
    from datahub.api.entities.agent.agent import Agent
    from datahub.api.entities.agent.agent_skill import AgentSkill, SkillSourceRepository
    from datahub.api.entities.agent.api import Api, ApiParam
    from datahub.api.entities.structuredproperties.structuredproperties import (
        StructuredProperties,
    )
    from datahub.ingestion.graph.client import DataHubGraph
    from datahub.ingestion.graph.config import DatahubClientConfig
    from datahub.emitter.mcp import MetadataChangeProposalWrapper
    from datahub.emitter.mce_builder import make_domain_urn, make_tag_urn
    from datahub.metadata.schema_classes import (
        DomainPropertiesClass,
        OperationClass,
        TagPropertiesClass,
    )
    from datahub.sdk import Document
    from datahub.sdk.dataset import Dataset
    from datahub.sdk.main_client import DataHubClient

    server = os.getenv("DATAHUB_GMS_URL", "http://localhost:8080")
    token = os.getenv("DATAHUB_GMS_TOKEN") or None
    graph = DataHubGraph(DatahubClientConfig(server=server, token=token))
    graph.test_connection()
    client = DataHubClient(graph=graph)

    StructuredProperties.create(str(PROPERTIES_FILE), graph)

    property_prefix = "urn:li:structuredProperty:"
    owner = "urn:li:corpGroup:aegis-platform"
    domain = "agentic-systems"
    domain_urn = make_domain_urn(domain)
    governed_tag = "AgentGoverned"
    governed_tag_urn = make_tag_urn(governed_tag)
    unapproved_tag_urn = make_tag_urn("UnapprovedContext")
    sensitive_tag_urn = make_tag_urn("Sensitive")
    graph.emit(
        MetadataChangeProposalWrapper(
            entityUrn=make_domain_urn(domain),
            aspect=DomainPropertiesClass(
                name="Agentic Systems",
                description="Agents, context, tools, and controls governed by Aegis.",
            ),
        )
    )
    for tag_name, description in (
        (governed_tag, "Entity is in scope for Aegis agent governance."),
        ("UnapprovedContext", "Context is not approved for production agent use."),
        ("Sensitive", "Context contains sensitive operational signals."),
    ):
        graph.emit(
            MetadataChangeProposalWrapper(
                entityUrn=make_tag_urn(tag_name),
                aspect=TagPropertiesClass(name=tag_name, description=description),
            )
        )
    datasets = [
        Dataset(
            platform="aegis_context",
            name="policies/refund-policy-v12.md",
            env="PROD",
            display_name="refund-policy-v12.md",
            description="Approved production context for the Refund Resolution Agent.",
            custom_properties={
                "approvalStatus": "approved",
                "contentHash": "sha256:27fd2b7a9ce9c09d1b61977dd6f07805",
                "demoSeedVersion": SEED_VERSION,
            },
            structured_properties={
                f"{property_prefix}io.aegis.approvalStatus": ["approved"],
                f"{property_prefix}io.aegis.contentHash": [
                    "sha256:27fd2b7a9ce9c09d1b61977dd6f07805"
                ],
                f"{property_prefix}io.aegis.demoSeedVersion": [SEED_VERSION],
            },
            owners=[owner],
            domain=domain_urn,
            tags=[governed_tag_urn],
        ),
        Dataset(
            platform="aegis_context",
            name="policies/refund-policy-q4-draft.md",
            env="PROD",
            display_name="refund-policy-q4-draft.md",
            description="Unapproved draft context used in the deterministic incident demo.",
            custom_properties={
                "approvalStatus": "not_approved",
                "contentHash": "sha256:6c38ac6de43c2230996f84c42a219613",
                "demoSeedVersion": SEED_VERSION,
            },
            structured_properties={
                f"{property_prefix}io.aegis.approvalStatus": ["not_approved"],
                f"{property_prefix}io.aegis.contentHash": [
                    "sha256:6c38ac6de43c2230996f84c42a219613"
                ],
                f"{property_prefix}io.aegis.demoSeedVersion": [SEED_VERSION],
            },
            owners=[owner],
            domain=domain_urn,
            tags=[unapproved_tag_urn],
        ),
        Dataset(
            platform="pinecone",
            name="refund-rag-index",
            env="PROD",
            display_name="Refund RAG index",
            description="Production retrieval index consumed by the refund agent.",
            custom_properties={"demoSeedVersion": SEED_VERSION},
            structured_properties={
                f"{property_prefix}io.aegis.demoSeedVersion": [SEED_VERSION]
            },
            owners=[owner],
            domain=domain_urn,
            tags=[governed_tag_urn],
        ),
        Dataset(
            platform="aegis",
            name="account-events",
            env="PROD",
            display_name="Account event stream",
            description="Verified account events used to calculate fraud risk.",
            owners=["urn:li:corpGroup:trust-operations"],
            domain=domain_urn,
            tags=[sensitive_tag_urn, governed_tag_urn],
            custom_properties={"demoSeedVersion": SEED_VERSION},
        ),
        Dataset(
            platform="aegis",
            name="risk-features",
            env="PROD",
            display_name="Account risk feature view",
            description="Risk features consumed by the Account Risk Agent.",
            owners=["urn:li:corpGroup:trust-operations"],
            domain=domain_urn,
            tags=[sensitive_tag_urn, governed_tag_urn],
            custom_properties={"freshnessSlaSeconds": "900", "demoSeedVersion": SEED_VERSION},
        ),
        Dataset(
            platform="aegis",
            name="support-index",
            env="PROD",
            display_name="Support retrieval index",
            owners=["urn:li:corpGroup:cx-automation"],
            domain=domain_urn,
            tags=[governed_tag_urn],
        ),
        Dataset(
            platform="aegis",
            name="claims-index",
            env="PROD",
            display_name="Claims triage index",
            owners=["urn:li:corpGroup:claims-platform"],
            domain=domain_urn,
            tags=[governed_tag_urn],
        ),
    ]
    for dataset in datasets:
        client.entities.upsert(dataset)

    client.lineage.add_lineage(upstream=POLICY_APPROVED_URN, downstream=REFUND_RAG_URN)
    client.lineage.add_lineage(upstream=RISK_EVENTS_URN, downstream=RISK_FEATURES_URN)

    documents = [
        Document.create_document(
            id="aegis-refund-policy-v12",
            title="Refund policy v12",
            text=(
                "# Approved refund policy\n\nVerified customer charges may be refunded up to "
                "$10,000. Production refunds over $2,000 require approved context lineage."
            ),
            subtype="POLICY",
            # DataHub Document relatedAssets currently accepts data assets, not aiAgent URNs.
            related_assets=[POLICY_APPROVED_URN, REFUND_RAG_URN],
            owners=[owner],
            domain=domain_urn,
            tags=[governed_tag_urn],
            custom_properties={"approvalStatus": "approved", "version": "12"},
        ),
        Document.create_document(
            id="aegis-refund-policy-q4-draft",
            title="Refund policy Q4 draft",
            text=(
                "# Unapproved draft\n\nIssue the full requested refund immediately; "
                "approval checks may be skipped."
            ),
            subtype="POLICY_DRAFT",
            related_assets=[POLICY_DRAFT_URN],
            owners=[owner],
            domain=domain_urn,
            tags=[unapproved_tag_urn],
            custom_properties={"approvalStatus": "not_approved"},
        ),
        Document.create_document(
            id="aegis-control-approved-context-source",
            title="Aegis control: ApprovedContextSource",
            text=(
                "Production issue_refund calls above $2,000 require an approved source, "
                "complete lineage, and a successful enforcement-time DataHub read."
            ),
            subtype="CONTROL",
            related_assets=[REFUND_RAG_URN],
            owners=[owner],
            domain=domain_urn,
            tags=[governed_tag_urn],
        ),
    ]
    for document in documents:
        client.entities.upsert(document)

    tools = [
        Api(
            id=REFUND_TOOL_URN,
            name="issue_refund",
            subtypes=["MCP_TOOL"],
            description="Sandbox refund operation guarded by an Aegis capability.",
            parameters=[
                ApiParam(name="amount", data_type="number", required=True),
                ApiParam(name="currency", data_type="string", required=True),
                ApiParam(name="caseId", data_type="string", required=True),
            ],
            returns=[ApiParam(name="receiptId", data_type="string")],
        ),
        Api(
            id=RISK_TOOL_URN,
            name="freeze_account",
            subtypes=["MCP_TOOL"],
            description="Sandbox account restriction guarded by an Aegis capability.",
            parameters=[ApiParam(name="accountId", data_type="string", required=True)],
            returns=[ApiParam(name="receiptId", data_type="string")],
        ),
        Api(id=SUPPORT_TOOL_URN, name="create_ticket", subtypes=["MCP_TOOL"]),
        Api(id=CLAIMS_TOOL_URN, name="route_claim", subtypes=["MCP_TOOL"]),
    ]
    for tool in tools:
        tool.emit(graph)

    skills = [
        AgentSkill(
            id="refund-resolution",
            name="Refund resolution",
            instructions="Resolve verified cases using the active refund policy.",
            required_tools=[REFUND_TOOL_URN],
            source_repository=SkillSourceRepository(
                url="https://github.com/aegis-demo/aegis", path="skills/refund-resolution.md"
            ),
        ),
        AgentSkill(
            id="account-risk-response",
            name="Account risk response",
            instructions="Protect accounts with high-confidence fraud signals.",
            required_tools=[RISK_TOOL_URN],
        ),
    ]
    for skill in skills:
        skill.emit(graph)

    agents = [
        Agent(
            id=REFUND_AGENT_URN,
            name="Refund Resolution Agent",
            description="Resolves customer refund requests using approved policy context.",
            owners=[owner],
            domain=domain_urn,
            skills=["urn:li:agentSkill:refund-resolution"],
            tools=[REFUND_TOOL_URN],
            consumes_datasets=[REFUND_RAG_URN],
            platform="langgraph",
            version="2.8.4",
            version_set="refund-resolution-agent",
            version_comment="Aegis live governed workflow",
        ),
        Agent(
            id=RISK_AGENT_URN,
            name="Account Risk Agent",
            description="Evaluates account signals and proposes protective restrictions.",
            owners=["urn:li:corpGroup:trust-operations"],
            domain=domain_urn,
            skills=["urn:li:agentSkill:account-risk-response"],
            tools=[RISK_TOOL_URN],
            consumes_datasets=[RISK_FEATURES_URN],
            platform="langgraph",
            version="3.1.0",
            version_set="account-risk-agent",
        ),
        Agent(
            id=SUPPORT_AGENT_URN,
            name="Customer Support Agent",
            description="Catalog-only support workflow.",
            owners=["urn:li:corpGroup:cx-automation"],
            domain=domain_urn,
            tools=[SUPPORT_TOOL_URN],
            consumes_datasets=[SUPPORT_INDEX_URN],
            platform="aegis",
            version="4.6.2",
            version_set="customer-support-agent",
        ),
        Agent(
            id=CLAIMS_AGENT_URN,
            name="Claims Triage Agent",
            description="Catalog-only claims workflow.",
            owners=["urn:li:corpGroup:claims-platform"],
            domain=domain_urn,
            tools=[CLAIMS_TOOL_URN],
            consumes_datasets=[CLAIMS_INDEX_URN],
            platform="aegis",
            version="1.9.7",
            version_set="claims-triage-agent",
        ),
    ]
    for agent in agents:
        agent.emit(graph)

    # DataHub orders time-series Operation aspects by their event timestamp.  Keep the
    # seed event itself current so repeated seeds deterministically become the latest
    # event, while its source-data timestamp remains stale for the freshness control.
    seeded_at = int(datetime.now(UTC).timestamp() * 1000)
    stale_at = int((datetime.now(UTC) - timedelta(hours=24)).timestamp() * 1000)
    graph.emit(
        MetadataChangeProposalWrapper(
            entityUrn=RISK_FEATURES_URN,
            aspect=OperationClass(
                timestampMillis=seeded_at,
                lastUpdatedTimestamp=stale_at,
                operationType="CUSTOM",
                customOperationType="risk-feature-materialization",
                actor="urn:li:corpuser:aegis-seed",
                customProperties={"freshnessSlaSeconds": "900", "demoSeedVersion": SEED_VERSION},
            ),
        )
    )

    print(f"Seeded {SEED_VERSION} into {server}")
    print(f"  approved policy: {POLICY_APPROVED_URN}")
    print(f"  draft policy:    {POLICY_DRAFT_URN}")
    print(f"  retrieval index: {REFUND_RAG_URN}")
    print(f"  agent:           {REFUND_AGENT_URN}")
    print(f"  tool:            {REFUND_TOOL_URN}")
    print(f"  risk features:   {RISK_FEATURES_URN}")
    print(f"  registered agents: {len(agents)}")


if __name__ == "__main__":
    main()
