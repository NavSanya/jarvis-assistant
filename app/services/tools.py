import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from app.config import Settings

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.types import TextContent
except ImportError:  # pragma: no cover - optional dependency
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None
    TextContent = None


class MCPToolService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.server_script = Path(settings.mcp_server_script)

    @property
    def provider_status(self) -> str:
        if ClientSession is None or stdio_client is None or StdioServerParameters is None:
            return "missing mcp dependency"
        if not self.server_script.exists():
            return "missing mcp server script"
        return "configured"

    def discover_tool_calls(self, message: str) -> list[str]:
        lowered = message.lower()
        tool_names: list[str] = []
        if "time" in lowered or "date" in lowered:
            tool_names.append("get_time")
        if "remember" in lowered or "saved" in lowered or "history" in lowered:
            tool_names.append("conversation_summary")
        return tool_names

    def _server_command(self) -> str:
        if self.settings.mcp_server_command == "python":
            return sys.executable
        return self.settings.mcp_server_command

    async def list_tools(self) -> list[str]:
        if self.provider_status != "configured":
            return []
        server_params = StdioServerParameters(
            command=self._server_command(),
            args=[str(self.server_script)],
        )
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                response = await session.list_tools()
                return [tool.name for tool in response.tools]

    async def run_tool(
        self,
        tool_name: str,
        *,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if self.provider_status != "configured":
            raise RuntimeError("MCP SDK or MCP server is not configured.")

        async def _call_tool() -> dict[str, Any]:
            server_params = StdioServerParameters(
                command=self._server_command(),
                args=[str(self.server_script)],
            )
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    content_blocks = []
                    for item in result.content:
                        if TextContent is not None and isinstance(item, TextContent):
                            try:
                                content_blocks.append(json.loads(item.text))
                            except json.JSONDecodeError:
                                content_blocks.append({"text": item.text})
                    if result.structuredContent is not None:
                        return dict(result.structuredContent)
                    if len(content_blocks) == 1:
                        return dict(content_blocks[0])
                    return {"content": content_blocks}

        return await asyncio.wait_for(
            _call_tool(),
            timeout=self.settings.mcp_timeout_seconds,
        )
