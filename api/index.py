"""Vercel entrypoint for the Aegis seeded showcase.

The production Docker stack can connect to live DataHub and MCP services. Vercel
runs the public showcase in deterministic seeded mode and stores its short-lived
interactive state in the function's writable /tmp directory.
"""

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

os.environ.setdefault("AEGIS_DATABASE_PATH", "/tmp/aegis.db")
os.environ.setdefault("AEGIS_CONTEXT_DATABASE_PATH", "/tmp/aegis-context.db")
os.environ.setdefault("AEGIS_DATA_MODE", "seeded")
os.environ.setdefault("AEGIS_PRIME_BLOCKED", "true")

from aegis.main import app  # noqa: E402,F401
