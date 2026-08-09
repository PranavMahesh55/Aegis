#!/usr/bin/env python3
"""Verify the exact DataHub evidence Aegis expects from the seed."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from aegis.adapters.datahub.seed import (  # noqa: E402
    POLICY_APPROVED_URN,
    POLICY_DRAFT_URN,
    CLAIMS_AGENT_URN,
    REFUND_AGENT_URN,
    REFUND_RAG_URN,
    REFUND_TOOL_URN,
    RISK_AGENT_URN,
    RISK_FEATURES_URN,
    RISK_TOOL_URN,
    SUPPORT_AGENT_URN,
)


def main() -> None:
    try:
        from datahub.ingestion.graph.client import DataHubGraph
        from datahub.ingestion.graph.config import DatahubClientConfig
        from datahub.metadata.schema_classes import (
            AIAgentDependenciesClass,
            AIAgentInfoClass,
            ApiPropertiesClass,
            DatasetPropertiesClass,
            DocumentInfoClass,
            OperationClass,
            StructuredPropertiesClass,
            UpstreamLineageClass,
        )
    except ImportError as error:
        raise SystemExit(
            "DataHub SDK is not installed. Use Python 3.12/3.13 and run "
            "`make install-datahub`, or execute this inside the Aegis Docker image."
        ) from error

    server = os.getenv("DATAHUB_GMS_URL", "http://localhost:8080")
    token = os.getenv("DATAHUB_GMS_TOKEN") or None
    graph = DataHubGraph(DatahubClientConfig(server=server, token=token))
    graph.test_connection()

    checks: dict[str, bool] = {}
    checks["approvedPolicy"] = graph.get_aspect(
        POLICY_APPROVED_URN, DatasetPropertiesClass
    ) is not None
    checks["draftPolicy"] = graph.get_aspect(
        POLICY_DRAFT_URN, DatasetPropertiesClass
    ) is not None
    checks["retrievalIndex"] = graph.get_aspect(
        REFUND_RAG_URN, DatasetPropertiesClass
    ) is not None
    checks["approvalMetadata"] = graph.get_aspect(
        POLICY_APPROVED_URN, StructuredPropertiesClass
    ) is not None
    checks["agent"] = graph.get_aspect(REFUND_AGENT_URN, AIAgentInfoClass) is not None
    checks["tool"] = graph.get_aspect(REFUND_TOOL_URN, ApiPropertiesClass) is not None
    checks["riskFeatures"] = graph.get_aspect(
        RISK_FEATURES_URN, DatasetPropertiesClass
    ) is not None
    checks["riskAgent"] = graph.get_aspect(RISK_AGENT_URN, AIAgentInfoClass) is not None
    checks["riskTool"] = graph.get_aspect(RISK_TOOL_URN, ApiPropertiesClass) is not None
    checks["catalogOnlyAgents"] = all(
        graph.get_aspect(urn, AIAgentInfoClass) is not None
        for urn in (SUPPORT_AGENT_URN, CLAIMS_AGENT_URN)
    )
    checks["controlDocument"] = graph.get_aspect(
        "urn:li:document:aegis-control-approved-context-source", DocumentInfoClass
    ) is not None
    checks["riskOperation"] = graph.get_latest_timeseries_value(
        RISK_FEATURES_URN, OperationClass, {}
    ) is not None

    rag_lineage = graph.get_aspect(REFUND_RAG_URN, UpstreamLineageClass)
    checks["policyToRetrievalLineage"] = bool(
        rag_lineage
        and any(item.dataset == POLICY_APPROVED_URN for item in rag_lineage.upstreams)
    )
    agent_lineage = graph.get_aspect(REFUND_AGENT_URN, UpstreamLineageClass)
    checks["retrievalToAgentLineage"] = bool(
        agent_lineage
        and any(item.dataset == REFUND_RAG_URN for item in agent_lineage.upstreams)
    )
    dependencies = graph.get_aspect(REFUND_AGENT_URN, AIAgentDependenciesClass)
    checks["agentToToolDependency"] = bool(
        dependencies and REFUND_TOOL_URN in (dependencies.tools or [])
    )

    result = {"server": server, "verified": all(checks.values()), "checks": checks}
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["verified"]:
        raise SystemExit("DataHub seed verification failed")


if __name__ == "__main__":
    main()
