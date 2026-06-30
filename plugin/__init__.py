"""Scrapling web extract plugin — user plugin, opt-in.

Registers ScraplingWebExtractProvider so web_extract calls route through
the local Scrapling MCP server when web.extract_backend is set to "scrapling".

Also patches two hardcoded gates in tools/web_tools.py:
- _is_backend_available() — the runtime dispatch gate
- check_web_api_key() — the tool-registration gate that decides whether
  web_search/web_extract appear in the tool list at all
"""
from __future__ import annotations

from .provider import ScraplingWebExtractProvider


def register(ctx) -> None:
    """Register the Scrapling extract provider with the plugin context."""
    _patch_web_tools_gates()
    ctx.register_web_search_provider(ScraplingWebExtractProvider())


def _patch_web_tools_gates() -> None:
    """Monkey-patch both hardcoded gates in tools/web_tools.py.

    Hermes has two functions with hardcoded lists of known backends
    (exa, parallel, firecrawl, tavily, searxng, brave-free, ddgs, xai):

    1. _is_backend_available() — called at runtime to check if a configured
       backend name is usable. Returns False for anything not in the list,
       causing _get_extract_backend() to fall through to the legacy searxng
       fallback before the plugin registry is ever consulted.

    2. check_web_api_key() — used as the check_fn when registering the
       web_search and web_extract tools. If this returns False, the tools
       are silently dropped from the available tool list entirely.

    Both are patched to recognize "scrapling" as a valid backend name.
    """
    import tools.web_tools as wt

    # Patch 1: _is_backend_available (runtime dispatch gate)
    orig_is_available = wt._is_backend_available

    def patched_is_available(backend: str) -> bool:
        if backend == "scrapling":
            return True
        return orig_is_available(backend)

    wt._is_backend_available = patched_is_available

    # Patch 2: check_web_api_key (tool registration gate)
    orig_check_key = wt.check_web_api_key

    def patched_check_key() -> bool:
        # If the configured backend is "scrapling", return True directly
        try:
            from agent.web_search_registry import get_provider
            cfg = wt._load_web_config()
            configured = (cfg.get("backend") or cfg.get("extract_backend") or "").lower().strip()
            if configured == "scrapling":
                provider = get_provider("scrapling")
                if provider and provider.is_available():
                    return True
        except Exception:
            pass
        return orig_check_key()

    wt.check_web_api_key = patched_check_key
