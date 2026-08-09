#!/usr/bin/env bash
set -euo pipefail
curl -fsS -X POST http://localhost:8000/api/demo/reset \
  -H 'Content-Type: application/json' \
  -d '{"target":"HEALTHY_BASELINE"}' | python3 -m json.tool

