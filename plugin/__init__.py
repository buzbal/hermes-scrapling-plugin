"""Scrapling web extract plugin — user plugin, opt-in.

Registers ScraplingWebExtractProvider so web_extract calls route through
the local Scrapling MCP server when web.extract_backend is set to "scrapling".

Also patches _is_backend_available() in web_tools.py so the dispatcher
recognizes "scrapling" as a valid backend name. This is necessary because
_is_backend_available() has a hardcoded list of known backends and returns
False for anything not in that list, causing _get_extract_backend() to fall
through to the legacy searxng fallback before the registry is ever consulted.
"""
from __future__ import annotations

from .provider import ScraplingWebExtractProvider


def register(ctx) -> None:
    """Register the Scrapling extract provider with the plugin context."""
    _patch_is_backend_available()
    ctx.register_web_search_provider(ScraplingWebExtractProvider())


def _patch_is_backend_available() -> None:
    """Monkey-patch tools.web_tools._is_backend_available to know about scrapling.

    Hermes' _is_backend_available() has a hardcoded list of known backends
    (exa, parallel, firecrawl, tavily, searxng, brave-free, ddgs, xai).
    Any name not in that list returns False, which causes _get_extract_backend()
    to fall through to the legacy searxng fallback before the plugin registry
    is ever consulted. This patch adds "scrapling" to the recognized backends.
    """
    import tools.web_tools as wt

    orig = wt._is_backend_available

    def patched(backend: str) -> bool:
        if backend == "scrapling":
            return True
        return orig(backend)

    wt._is_backend_available = patched
