#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
docker compose up --build -d
echo "Aegis is starting at http://localhost:8000"
echo "Run scripts/demo/verify.sh to inspect readiness."

