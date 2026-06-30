"""Scrapling web extract — uses the MCP Python SDK (streamable_http_client + ClientSession).

Same code path Hermes' own MCP tool infrastructure uses. Handles session init,
Mcp-Session-Id headers, SSE parsing, and tool calls correctly.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)

MCP_URL = "http://localhost:8000/mcp"

# You can override the URL by setting the SCRAPLING_MCP_URL environment variable.
# This is useful if you run Scrapling on a different port or host.
import os as _os
_env_url = _os.environ.get("SCRAPLING_MCP_URL", "").strip()
if _env_url:
    MCP_URL = _env_url.rstrip("/")


def _check_mcp_reachable() -> bool:
    """Cheap availability check — TCP connect to the MCP endpoint.

    Does NOT make a full MCP initialize or fetch example.com, because
    is_available() runs at tool-registration time and on every
    ``hermes tools`` paint (per the ABC contract).
    """
    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse(MCP_URL)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8000
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        return True
    except Exception:
        return False


def _mcp_call_tool(tool_name: str, arguments: dict) -> dict:
    """Open one MCP session, call a tool, return the result dict.

    Uses the MCP Python SDK (same code path as Hermes' own MCP tools).
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async def _run() -> dict:
        async with streamable_http_client(MCP_URL) as (read, write, _get_sid):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return result.model_dump() if hasattr(result, "model_dump") else dict(result)

    return asyncio.run(_run())


def _extract_text_from_result(result: dict) -> str:
    """Extract concatenated text content from an MCP tool result.

    Scrapling's ``get`` tool returns content blocks of type "text".
    The text is a JSON string like ``{"status": 200, "content": [...], "url": "..."}``
    — we parse it and return the joined text content.
    """
    content = ""
    for block in result.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            raw = block.get("text", "")
            # Scrapling wraps the result in a JSON envelope; unwrap it
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and "content" in parsed:
                    texts = parsed["content"]
                    if isinstance(texts, list):
                        content += "\n".join(t for t in texts if isinstance(t, str))
                    elif isinstance(texts, str):
                        content += texts
                else:
                    content += raw
            except (json.JSONDecodeError, TypeError):
                content += raw
    return content


class ScraplingWebExtractProvider(WebSearchProvider):
    """Web extract provider backed by a local Scrapling MCP server.

    Requires a running Scrapling MCP server (Docker or pip) on port 8000.
    Only supports content extraction (no web search).
    """

    name = "scrapling"
    display_name = "Scrapling (local)"

    def is_available(self) -> bool:
        """Return True when the Scrapling MCP server is reachable.

        Uses a cheap TCP connect — no network calls to external sites,
        no full MCP session initialization.
        """
        return _check_mcp_reachable()

    def supports_search(self) -> bool:
        return False

    def supports_extract(self) -> bool:
        return True

    def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        """Extract content from one or more URLs via Scrapling's ``get`` tool.

        Opens a new MCP session for each URL and calls ``get``.
        Accepts ``format`` kwarg (``"markdown"``, ``"html"``, ``"text"``)
        mapped to Scrapling's ``extraction_type`` parameter.
        """
        format = kwargs.get("format", "markdown")
        extraction_type = format if format in ("markdown", "html", "text") else "markdown"

        results: List[Dict[str, Any]] = []
        for url in urls:
            try:
                result = _mcp_call_tool("get", {
                    "url": url,
                    "extraction_type": extraction_type,
                    "main_content_only": True,
                })
                content = _extract_text_from_result(result)
                results.append({
                    "url": url,
                    "title": "",
                    "content": content,
                    "raw_content": content,
                })
            except Exception as e:
                logger.warning("Scrapling extract failed for %s: %s", url, e)
                results.append({
                    "url": url,
                    "title": "",
                    "content": "",
                    "error": str(e),
                })
        return results

    def get_setup_schema(self) -> Dict[str, Any]:
        """Return provider metadata for the ``hermes tools`` picker."""
        return {
            "name": self.display_name,
            "badge": "local",
            "tag": "Requires a running Scrapling MCP server (Docker or pip). Default port 8000, configurable via SCRAPLING_MCP_URL.",
            "env_vars": [],
        }
