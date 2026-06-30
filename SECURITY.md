# Security: Hermes Scrapling Web Extract Plugin

## What this is

Three files, one runtime patch, about 200 lines of code total. Makes `web_extract` talk to a local Scrapling server instead of erroring out.

## Network connections

The plugin itself only talks to your local machine. Here's what connects where:

| Connection | Direction | What for | Risk |
|------------|-----------|----------|------|
| `localhost:8000` | Outbound | Talks to your local Scrapling server | None — stays on your machine |
| Target websites (via Scrapling) | Outbound | Fetches the page content you asked for | Same risk as opening that URL in a browser |
| Any external server | — | — | Doesn't happen. The plugin never sends data anywhere except to your local Scrapling. |

## The monkey-patch explained

### What gets changed

A function inside Hermes called `_is_backend_available()`. This function checks whether a backend name (like "firecrawl" or "searxng") is usable.

### The actual code that runs

```python
orig = wt._is_backend_available
def patched(backend):
    if backend == "scrapling":
        return True
    return orig(backend)
wt._is_backend_available = patched
```

### What this changes

- **Before the patch**: asking `_is_backend_available("scrapling")` returns `False`
- **After the patch**: asking `_is_backend_available("scrapling")` returns `True`
- **Everything else**: unchanged — it calls the original function

### Why it's needed

`_is_backend_available()` has a hardcoded list of 8 backends. Anything not in that list returns `False`, which means your `extract_backend: scrapling` config setting gets ignored before the plugin system is even asked. Without this patch, the plugin can't work.

### What happens if something goes wrong

| Scenario | What happens |
|----------|-------------|
| A Hermes update removes this function | The plugin can't load (import error). `web_extract` falls back to its automatic detection. No crash, no data loss. |
| A Hermes update renames it | Same as above |
| A Hermes update changes how it works | The call fails, plugin doesn't load, same fallback. |
| Another plugin also patches the same function | The last one to load wins. No crash, but behavior depends on which loads first. |

## Where the code comes from

All written from scratch for this purpose. No obfuscation, no minification, no hidden code. The only external library it uses is the `mcp` Python package, which is already part of Hermes' installation.

## How to verify it yourself

1. **Read the files** — there are only three, they're short, open them in any text editor.

2. **Check that `_is_backend_available` is the only function being patched:**
   ```bash
   grep -r "tools\.web_tools\." ~/.hermes/plugins/web/scrapling/
   ```
   This should only show the one patch in `__init__.py`. If you see anything else, something's wrong.

3. **Check that the plugin only talks to localhost:**
   ```bash
   netstat -an | grep 8000
   ```
   On Windows, the equivalent is:
   ```
   netstat -an | findstr 8000
   ```
   This should only show connections to `127.0.0.1` or `localhost` — your own machine.

## A note on how this was made

This plugin was "vibe-coded" — written by an AI agent iterating with a human, not by a traditional developer sitting down and writing it from start to finish. That means there might be edge cases, rough edges, or things a human would have done differently. External audits, pull requests, and issue reports are very welcome. If something looks off, it probably is — and fixing it together is the whole point of open source.
