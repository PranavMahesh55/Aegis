# Security posture

## Consequential tool boundary

Only the live agent path can call the business MCP consequence tools. The executor accepts a
short-lived HMAC capability only when it matches the exact tool and canonical argument hash,
has not expired, and has not been consumed. Consumption and receipt creation share one SQLite
transaction, preventing concurrent replay.

The endpoint under `/api/demo/tools/issue_refund` belongs solely to the deterministic seeded UI
story. It writes an explicitly `SIMULATED_EXTERNAL` local receipt and is not part of live agent
execution. It must not be wired to an external business system.

## Evidence boundary

DataHub MCP results give the model useful catalog context but cannot authorize execution.
DataHub Actions callbacks are authenticated, idempotent invalidation hints. Enforcement uses a
fresh direct GMS aspect read immediately before the capability can be minted and fails closed on
unavailable, missing, or incomplete evidence.

## Dependency advisory note

The client-only SPA pins React Router 7.18.2. The remaining npm advisory concerns React Server
Components action handling. Aegis does not use React Router framework mode, SSR, RSC, loaders,
actions, server actions, or server-controlled redirects; the affected code is not exposed by
this Vite SPA. Reassess this exception before adding any server-rendered React surface.

