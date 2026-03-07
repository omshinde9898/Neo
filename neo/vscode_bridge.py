"""VS Code bridge for Neo - JSON-RPC over stdio."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from neo.agent import Agent
from neo.config import Config
from neo.llm.client import OpenAIClient
from neo.tools.registry import ToolRegistry
from neo.tools.file import EditFileTool, GlobTool, ListDirTool, ReadFileTool, WriteFileTool
from neo.tools.git import GitAddTool, GitCommitTool, GitDiffTool, GitStatusTool
from neo.tools.shell import RunShellTool
from neo.tools.code import AnalyzeFileTool, FindSymbolTool
from neo.tools.search import SearchCodeTool, ViewCodeTool
from neo.tools.system import GetSystemInfoTool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("/tmp/neo_bridge.log")],
)
logger = logging.getLogger(__name__)


class VSCodeBridge:
    """Bridge between VS Code and Neo via JSON-RPC over stdio."""

    def __init__(self):
        self.agent: Agent | None = None
        self.message_id = 0
        self.buffer = ""

    async def run(self) -> None:
        """Main loop: read JSON-RPC from stdin, write to stdout."""
        logger.info("Neo VS Code bridge starting...")

        while True:
            try:
                message = await self._read_message()
                if message is None:
                    break

                response = await self._handle_request(message)
                await self._send_response(response)

            except Exception as e:
                logger.exception("Error handling message")
                await self._send_error(0, str(e))

    async def _read_message(self) -> dict[str, Any] | None:
        """Read a JSON-RPC message from stdin."""
        while True:
            line = await asyncio.get_event_loop().run_in_executor(
                None, sys.stdin.readline
            )

            if not line:
                return None

            if line.startswith("Content-Length:"):
                try:
                    length = int(line.split(":")[1].strip())
                    # Read empty line
                    await asyncio.get_event_loop().run_in_executor(
                        None, sys.stdin.readline
                    )
                    # Read message body
                    body = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: sys.stdin.read(length)
                    )
                    return json.loads(body)
                except Exception as e:
                    logger.error(f"Failed to parse message: {e}")
                    continue

    async def _send_response(self, response: dict[str, Any]) -> None:
        """Send JSON-RPC response to stdout."""
        content = json.dumps(response)
        message = f"Content-Length: {len(content)}\r\n\r\n{content}"
        sys.stdout.write(message)
        sys.stdout.flush()

    async def _send_error(self, id: int, message: str) -> None:
        """Send JSON-RPC error response."""
        await self._send_response({
            "jsonrpc": "2.0",
            "id": id,
            "error": {"code": -32603, "message": message},
        })

    async def _handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle JSON-RPC request."""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id", 0)

        logger.info(f"Handling method: {method}")

        try:
            if method == "initialize":
                result = await self._initialize(params)
            elif method == "chat":
                result = await self._chat(params)
            elif method == "cost":
                result = await self._cost()
            elif method == "explain":
                result = await self._explain(params)
            elif method == "tool":
                result = await self._execute_tool(params)
            else:
                raise ValueError(f"Unknown method: {method}")

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result,
            }

        except Exception as e:
            logger.exception(f"Error in {method}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": str(e)},
            }

    async def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Initialize Neo agent for workspace."""
        workspace = Path(params.get("workspace", "."))
        logger.info(f"Initializing Neo for workspace: {workspace}")

        config = Config.load()

        # Create LLM client
        if config.mock_mode or not config.openai_api_key:
            from neo.llm.mock import MockOpenAIClient
            llm = MockOpenAIClient(model="mock")
        else:
            llm = OpenAIClient(
                api_key=config.openai_api_key,
                model=config.model,
                base_url=config.base_url,
            )

        # Create tool registry
        tools = ToolRegistry()
        tools.register(ReadFileTool())
        tools.register(WriteFileTool())
        tools.register(EditFileTool())
        tools.register(ListDirTool())
        tools.register(GlobTool())
        tools.register(GitStatusTool())
        tools.register(GitDiffTool())
        tools.register(GitAddTool())
        tools.register(GitCommitTool())
        tools.register(RunShellTool())
        tools.register(GetSystemInfoTool())
        tools.register(SearchCodeTool())
        tools.register(ViewCodeTool())
        tools.register(AnalyzeFileTool())
        tools.register(FindSymbolTool())

        # Create agent
        self.agent = Agent(
            llm=llm,
            tools=tools,
            project_path=workspace,
            config=config,
        )

        return {
            "status": "ok",
            "version": "0.1.0",
            "model": config.model,
        }

    async def _chat(self, params: dict[str, Any]) -> dict[str, Any]:
        """Process chat message."""
        if not self.agent:
            raise RuntimeError("Neo not initialized. Call initialize first.")

        message = params.get("message", "")
        logger.info(f"Chat message: {message[:50]}...")

        response = await self.agent.run(message)

        return {"response": response}

    async def _cost(self) -> dict[str, Any]:
        """Get cost statistics."""
        if not self.agent:
            raise RuntimeError("Neo not initialized")

        stats = self.agent.llm.get_cost_stats()
        return stats

    async def _explain(self, params: dict[str, Any]) -> dict[str, Any]:
        """Explain code."""
        if not self.agent:
            raise RuntimeError("Neo not initialized")

        code = params.get("code", "")
        prompt = f"Explain this code:\n\n```\n{code}\n```\n\nBe concise."

        response = await self.agent.run(prompt)
        return {"response": response}

    async def _execute_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a specific tool directly."""
        if not self.agent:
            raise RuntimeError("Neo not initialized")

        tool_name = params.get("name", "")
        tool_args = params.get("args", {})

        result = await self.agent.tools.execute(tool_name, tool_args)
        return {"result": result.output if result.success else result.error}


def main():
    """Entry point."""
    bridge = VSCodeBridge()
    try:
        asyncio.run(bridge.run())
    except KeyboardInterrupt:
        logger.info("Bridge stopped")
    except Exception as e:
        logger.exception("Bridge error")
        sys.exit(1)


if __name__ == "__main__":
    main()
