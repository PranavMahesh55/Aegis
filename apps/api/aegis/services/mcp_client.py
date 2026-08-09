import json
from typing import Any


class MCPCallError(RuntimeError):
    pass


async def call_mcp_tool(url: str, tool: str, arguments: dict[str, Any]) -> Any:
    """Call a streamable-HTTP MCP tool while keeping MCP an optional API dependency."""
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
    except ImportError as error:
        raise MCPCallError("MCP runtime dependencies are not installed") from error

    try:
        async with streamable_http_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool, arguments)
    except Exception as error:
        raise MCPCallError(f"{tool} failed: {type(error).__name__}") from error
    if getattr(result, "isError", False):
        raise MCPCallError(f"{tool} returned an MCP error")
    content = getattr(result, "content", [])
    values: list[Any] = []
    for item in content:
        text = getattr(item, "text", None)
        if text is None:
            continue
        try:
            values.append(json.loads(text))
        except (json.JSONDecodeError, TypeError):
            values.append(text)
    if len(values) == 1:
        return values[0]
    return values
