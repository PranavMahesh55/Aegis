import os
from pathlib import Path
from typing import Any

from aegis.context_store import BusinessContextStore
from aegis.security.capabilities import verify_capability


def create_server() -> Any:
    # Kept out of module import so the base API/test environment has no MCP dependency.
    from fastmcp import FastMCP

    server = FastMCP("Aegis Business Context")
    store = BusinessContextStore(
        Path(os.getenv("AEGIS_CONTEXT_DATABASE_PATH", "var/aegis-context.db"))
    )
    secret = os.getenv("AEGIS_CAPABILITY_SIGNING_SECRET", "dev-only-change-me")

    @server.tool()
    def lookup_case(case_id: str) -> dict[str, Any]:
        """Return verified business facts for a refund case."""
        return store.get_case(case_id) or {"error": "CASE_NOT_FOUND", "caseId": case_id}

    @server.tool()
    def search_refund_policy(query: str) -> dict[str, Any]:
        """Retrieve the currently active refund instructions for an agent."""
        return {"query": query, **store.refund_policy()}

    @server.tool()
    def lookup_account(account_id: str) -> dict[str, Any]:
        """Return account state and latest calculated risk features."""
        return store.get_account(account_id) or {
            "error": "ACCOUNT_NOT_FOUND",
            "accountId": account_id,
        }

    @server.tool()
    def issue_refund(
        case_id: str, amount: float, currency: str, capability_token: str
    ) -> dict[str, Any]:
        """Record a sandbox refund; requires a short-lived Aegis ALLOW capability."""
        arguments = {"caseId": case_id, "amount": amount, "currency": currency}
        capability = verify_capability(
            secret, capability_token, tool="issue_refund", arguments=arguments
        )
        return store.record_consequence(
            tool="issue_refund",
            subject_id=case_id,
            arguments=arguments,
            run_id=capability["runId"],
            capability_id=capability["jti"],
        )

    @server.tool()
    def freeze_account(account_id: str, capability_token: str) -> dict[str, Any]:
        """Record a sandbox account freeze; requires a short-lived Aegis ALLOW capability."""
        arguments = {"accountId": account_id}
        capability = verify_capability(
            secret, capability_token, tool="freeze_account", arguments=arguments
        )
        return store.record_consequence(
            tool="freeze_account",
            subject_id=account_id,
            arguments=arguments,
            run_id=capability["runId"],
            capability_id=capability["jti"],
        )

    return server


def main() -> None:
    create_server().run(transport="http")


if __name__ == "__main__":
    main()
