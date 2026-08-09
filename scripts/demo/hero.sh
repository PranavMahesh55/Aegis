#!/usr/bin/env bash
set -euo pipefail

base_url="${AEGIS_BASE_URL:-http://localhost:8000}"

post() {
  curl -fsS -X POST "$base_url$1" -H 'Content-Type: application/json' -d "$2"
}

version_of() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])'
}

echo "1/6 Reset to the trusted baseline"
post /api/demo/reset '{"target":"HEALTHY_BASELINE"}' | python3 -m json.tool

echo "2/6 Introduce the unapproved policy"
changed=$(post /api/demo/context-change '{"pipelineId":"refund","scenario":"UNAPPROVED_REFUND_POLICY","expectedIncidentVersion":0}')
echo "$changed" | python3 -m json.tool
version=$(echo "$changed" | version_of)

echo "3/6 Evaluate and block the simulated \$8,500 refund"
blocked=$(post /api/incidents/aegis-4821/evaluate "{\"expectedVersion\":$version,\"toolCall\":{\"tool\":\"issue_refund\",\"amount\":8500,\"currency\":\"USD\",\"caseId\":\"CX-90214\"}}")
echo "$blocked" | python3 -m json.tool
version=$(echo "$blocked" | version_of)

echo "4/6 Restore the approved source"
remediated=$(post /api/incidents/aegis-4821/remediate "{\"expectedVersion\":$version,\"strategy\":\"RESTORE_APPROVED_SOURCE\"}")
echo "$remediated" | python3 -m json.tool
version=$(echo "$remediated" | version_of)

echo "5/6 Run deterministic regression verification"
post /api/incidents/aegis-4821/verify "{\"expectedVersion\":$version,\"suiteId\":\"refund-safety-v1\"}" | python3 -m json.tool

echo "6/6 Confirm the fleet is trusted again"
curl -fsS "$base_url/api/pipelines" | python3 -m json.tool
