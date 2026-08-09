#!/usr/bin/env bash
set -euo pipefail
curl -fsS http://localhost:8000/api/health/live
echo
curl -fsS http://localhost:8000/api/system/status | python3 -m json.tool

