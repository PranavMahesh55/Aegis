from fastapi.testclient import TestClient


def test_complete_healthy_to_resolved_journey(client: TestClient) -> None:
    reset = client.post("/api/demo/reset", json={"target": "HEALTHY_BASELINE"})
    assert reset.status_code == 200
    assert reset.json()["state"] == "HEALTHY"

    changed = client.post(
        "/api/demo/context-change",
        json={
            "pipelineId": "refund",
            "scenario": "UNAPPROVED_REFUND_POLICY",
            "expectedIncidentVersion": 0,
        },
    )
    assert changed.status_code == 200
    assert changed.json()["attestationState"] == "INVALIDATED"

    evaluated = client.post(
        "/api/incidents/aegis-4821/evaluate",
        json={
            "expectedVersion": 1,
            "toolCall": {
                "tool": "issue_refund",
                "amount": 8500,
                "currency": "USD",
                "caseId": "CX-90214",
            },
        },
    )
    assert evaluated.status_code == 200
    assert evaluated.json()["decision"] == "BLOCK"
    assert evaluated.json()["executed"] is False

    graph = client.get("/api/incidents/aegis-4821/graph")
    assert graph.status_code == 200
    assert [node["kind"] for node in graph.json()["nodes"]] == [
        "POLICY_SOURCE",
        "RETRIEVAL_INDEX",
        "AGENT",
        "TOOL",
    ]

    remediated = client.post(
        "/api/incidents/aegis-4821/remediate",
        json={"expectedVersion": 2, "strategy": "RESTORE_APPROVED_SOURCE"},
    )
    assert remediated.status_code == 200
    assert remediated.json()["state"] == "REMEDIATION_APPLIED"

    verified = client.post(
        "/api/incidents/aegis-4821/verify",
        json={"expectedVersion": 3, "suiteId": "refund-safety-v1"},
    )
    assert verified.status_code == 200
    assert verified.json()["state"] == "RESOLVED"
    assert verified.json()["regressionRun"]["status"] == "PASSED"
    assert verified.json()["writeBack"]["verified"] is True

    fleet = client.get("/api/pipelines").json()["items"]
    refund = next(item for item in fleet if item["id"] == "refund")
    risk = next(item for item in fleet if item["id"] == "risk")
    assert refund["trustState"] == "TRUSTED"
    assert refund["openIncident"] is None
    assert risk["openIncident"] == {"id": "aegis-7392", "state": "RE_EVALUATED"}


def test_invalid_transition_is_problem_detail(client: TestClient) -> None:
    client.post("/api/demo/reset", json={"target": "HEALTHY_BASELINE"})
    response = client.post(
        "/api/incidents/aegis-4821/remediate",
        json={"expectedVersion": 0, "strategy": "RESTORE_APPROVED_SOURCE"},
    )
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "INVALID_INCIDENT_TRANSITION"


def test_blocked_runtime_call_never_executes(client: TestClient) -> None:
    response = client.post(
        "/api/demo/tools/issue_refund",
        json={
            "pipelineId": "refund",
            "agentVersion": "2.8.4",
            "toolCall": {
                "tool": "issue_refund",
                "amount": 8500,
                "currency": "USD",
                "caseId": "CX-90214",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "BLOCK"
    assert response.json()["executed"] is False
    assert response.json()["simulatedReceipt"] is None


def test_every_top_level_query_has_working_data(client: TestClient) -> None:
    assert client.get("/api/system/status").status_code == 200
    assert len(client.get("/api/pipelines").json()["items"]) == 4
    assert client.get("/api/pipelines/support").status_code == 200
    refund = client.get("/api/pipelines/refund").json()
    assert refund["datahubUrl"] == (
        "http://localhost:9002/dataset/"
        "urn:li:dataset:(urn:li:dataPlatform:pinecone,refund-rag-index,PROD)"
    )
    assert "/entity/" not in refund["datahubUrl"]
    incidents = client.get("/api/incidents").json()
    assert incidents["total"] == 4
    assert {item["id"] for item in incidents["items"]} == {
        "aegis-4821",
        "aegis-7392",
        "aegis-6158",
        "aegis-4770",
    }
    historical = client.get("/api/incidents/aegis-6158")
    assert historical.status_code == 200
    assert historical.json()["incident"]["state"] == "RESOLVED"
    assert len(historical.json()["evidenceSummary"]) == 3
    controls = client.get("/api/controls").json()["items"]
    assert {control["id"] for control in controls} == {
        "approved-context-source",
        "fresh-risk-context",
    }
    fresh_risk = next(control for control in controls if control["id"] == "fresh-risk-context")
    assert fresh_risk["lastEvaluation"]["decision"] == "REVIEW"
    assert fresh_risk["linkedIncidentId"] == "aegis-7392"
