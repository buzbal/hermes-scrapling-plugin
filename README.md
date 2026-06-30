# Hermes Scrapling Web Extract Plugin

A Hermes plugin that makes `web_extract` use a local Scrapling server instead of falling through to SearXNG and erroring out. No API keys, runs locally, works with Docker or pip.

## Why this exists

Hermes' `web_extract` tool (the thing that fetches web page content when you ask the AI to read a URL) only knows about a fixed set of backends — services like Firecrawl, Tavily, Exa, SearXNG, etc. If your backend isn't on that list, it doesn't matter that you configured it. The code rejects it before it even checks the plugin system. This plugin works around that.

Without the plugin, you can still use Scrapling's tools directly — they show up as soon as you connect the Scrapling server. But the AI model has no memory of which tool to use between sessions, so you'd have to remind it every time you start a new conversation. The plugin makes `web_extract` route through Scrapling automatically, so it just works without the model needing to know Scrapling exists.

## How it works

When you call `web_extract(url)`, Hermes does this:

```
1. Read config → sees "use scrapling"
2. Check if "scrapling" is a valid backend name  ← plugin patches this check
3. Look up "scrapling" in the plugin registry    ← plugin registered it
4. Call the scrapling provider to fetch the URL
5. Provider opens a connection to Scrapling's server → gets page content → returns it
```

Three files in the plugin folder (`%USERPROFILE%\.hermes\plugins\web\scrapling\` — more on that path below):

| File | What it does |
|------|-------------|
| `plugin.yaml` | Tells Hermes "I'm a backend plugin called scrapling" |
| `__init__.py` | Registers the provider + applies a small runtime fix at load time |
| `provider.py` | The actual extraction logic — uses Python's MCP library to talk to Scrapling |

## Prerequisites

- **Hermes Agent** installed and working (any recent version)
- **Scrapling server** running somewhere your machine can reach (see installation)
- **Python `mcp` package** — this comes with Hermes, you don't need to install it separately

## Installation

> **Already have Scrapling running?** Skip to [step 2](#2-install-the-plugin).
> **Already installed the plugin?** Skip to [step 3](#3-configure-hermes).

### 1. Start the Scrapling server

Scrapling is a tool that can fetch web pages. It runs as a server that Hermes talks to. You can run it either in Docker (a container) or directly on your machine.

#### Option A: Docker

Docker runs programs in isolated containers. On Windows, Docker Desktop uses WSL2 (Windows Subsystem for Linux) under the hood — Docker Desktop's installer usually handles this setup automatically. If you don't have Docker yet, download it from [docker.com](https://www.docker.com/products/docker-desktop/).

```bash
# Replace {CONTAINER_NAME} with whatever name you like (e.g. "scrapling", "hermes-scrapling")
# Port 8000 is Scrapling's default. If something else already uses port 8000,
# change the left number: -p 8001:8000 would make it available on port 8001 instead.
docker run -d \
  --name {CONTAINER_NAME} \
  -p 8000:8000 \
  pyd4vinci/scrapling:latest \
  mcp --http
```

Or if you use Docker Compose (a way to define containers in a text file):

```yaml
services:
  scrapling:
    image: pyd4vinci/scrapling:latest
    ports:
      - "8000:8000"
    command: mcp --http
```

#### Option B: Direct install (pip)

If you don't use Docker, you can install Scrapling directly with pip (Python's package installer). Python comes with Hermes' own bundled environment, but for a system-wide install you'll need Python installed separately — get it from [python.org](https://python.org) if you don't have it.

```bash
pip install "scrapling[ai]"
scrapling mcp --http
```

This starts the server on port 8000. To use a different port:

```bash
scrapling mcp --http --port {PORT}
```

#### Verify it's running

`curl` is a command-line tool that makes HTTP requests (like a browser without a window). Use it to check if Scrapling is responding:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/mcp
```

This should return `406`. That's expected — the server only accepts POST requests (the kind Hermes sends), not GET requests (the kind curl sends by default). A 406 means "I hear you, but you're asking wrong" — which means the server is alive.

In PowerShell (Windows' default terminal), the equivalent is:

```powershell
Invoke-WebRequest -Uri http://localhost:8000/mcp -Method GET | Select-Object StatusCode
```

This will also show a 406 error, which is the expected result.

> **Port note:** The plugin connects to `http://localhost:8000/mcp` by default. If you run Scrapling on a different port, you can either:
> - Set the environment variable `SCRAPLING_MCP_URL` to the correct URL (e.g. `http://localhost:8001/mcp`)
> - Or edit the `MCP_URL` line in `provider.py` directly

### 2. Install the plugin

The `~` in Linux paths means your home folder. On Windows, that's `C:\Users\<YourUsername>`. Hermes stores its data in `%USERPROFILE%\.hermes\` — that's the same as `C:\Users\<You>\.hermes\`.

Create the plugin folder and copy the three files there:

```bash
mkdir -p ~/.hermes/plugins/web/scrapling/
cp plugin.yaml ~/.hermes/plugins/web/scrapling/
cp __init__.py ~/.hermes/plugins/web/scrapling/
cp provider.py ~/.hermes/plugins/web/scrapling/
```

If you're on Windows and using Command Prompt instead of bash, the paths look like:

```
mkdir "%USERPROFILE%\.hermes\plugins\web\scrapling"
copy plugin.yaml "%USERPROFILE%\.hermes\plugins\web\scrapling\"
copy __init__.py "%USERPROFILE%\.hermes\plugins\web\scrapling\"
copy provider.py "%USERPROFILE%\.hermes\plugins\web\scrapling\"
```

### 3. Configure Hermes

Tell Hermes to load the plugin and use Scrapling for web extraction:

```bash
hermes plugins enable web-scrapling
hermes config set web.extract_backend scrapling
```

Or add these lines to your `%USERPROFILE%\.hermes\config.yaml` (open it in any text editor):

```yaml
plugins:
  enabled:
    - web-scrapling
web:
  extract_backend: scrapling
```

### 4. Restart Hermes

In the Hermes chat, type:

```
/reset
```

This restarts the current session with the new configuration loaded. Alternatively:

```
/exit
```

Then start Hermes again.

### 5. Test it

In the Hermes chat, type:

```
web_extract(urls=["https://example.com"])
```

You should get the page content back instead of an error message saying SearXNG can't do extraction.

## What the monkey-patch does (and why it's safe)

This plugin applies one small runtime patch — a "monkey-patch" in programmer slang, meaning it temporarily replaces a function while the program is running. Here's exactly what, why, and why you don't need to worry.

### The problem

Inside Hermes, there's a function called `_is_backend_available()` that checks whether a backend name is usable. It has a hardcoded list:

```python
def _is_backend_available(backend):
    if backend == "exa":       ...
    if backend == "parallel":  ...
    if backend == "firecrawl": ...
    if backend == "tavily":    ...
    if backend == "searxng":   ...
    if backend == "brave-free":...
    if backend == "ddgs":      ...
    if backend == "xai":       ...
    return False  # ← anything else is rejected
```

When you set `extract_backend: scrapling` in config, this function returns `False` because `"scrapling"` isn't in the list. The config value gets thrown away, `web_extract` falls back to SearXNG, SearXNG can't extract pages (it's a search engine, not a page fetcher), and you get an error. The plugin system is never even asked.

### The patch

```python
import tools.web_tools as wt
orig = wt._is_backend_available

def patched(backend):
    if backend == "scrapling":
        return True          # ← only adds this one name
    return orig(backend)     # ← everything else unchanged

wt._is_backend_available = patched
```

This saves the original function, then replaces it with a new one that first checks for `"scrapling"` and passes everything else through to the original. It's like adding one item to a checklist without touching the rest.

### Safety

| Concern | Answer |
|---------|--------|
| Changes behavior for built-in backends? | No. For all 8, it calls the original — identical behavior. |
| Affects other plugins? | No. Only adds `"scrapling"`. No other plugin uses that name. |
| Modifies files on disk? | No. It changes a function in memory while Hermes is running. Nothing is written to disk. |
| Survives across sessions? | No. Each time you start Hermes, it's a fresh process with the original code. The patch runs again when the plugin loads. |
| What if Hermes updates and removes this function? | The import fails, the plugin doesn't load, `web_extract` falls back to auto-detect. No crash, no data loss. |
| What if Hermes changes how the function works? | Same — fails gracefully, plugin doesn't load, no harm. |
| Does it phone home or send data anywhere? | No. The plugin only connects to `localhost:8000` (your local Scrapling). Nothing goes to the internet. |
| Can I check what it does? | Yes. Three files, about 200 lines total. Open them in any text editor. |

### Why not fix Hermes itself?

The proper fix is a one-line change to Hermes' source code: make `_is_backend_available()` check the plugin registry as a fallback before returning `False`. That would make every registered provider work automatically. Until that change is made in an official Hermes release, this monkey-patch is the only way to add custom backends.

## Files in this repository

```
hermes-scrapling-plugin/
├── README.md              # This file
├── plugin/
│   ├── plugin.yaml        # Plugin manifest (tells Hermes what this is)
│   ├── __init__.py        # Registration + monkey-patch
│   └── provider.py        # The actual extraction code
└── SECURITY.md            # Security notes
```

## License

MIT — do whatever you want with it.

## Credits

- **[Scrapling](https://github.com/D4Vinci/Scrapling)** by [D4Vinci](https://github.com/D4Vinci) — the web scraping engine this plugin talks to. All the actual page-fetching work is done by Scrapling's MCP server.
- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** by [Nous Research](https://nousresearch.com) — the AI agent framework this plugin extends.
- The plugin code was written by an AI agent (primarily DeepSeek V4 Flash, with testing by Qwen and Ornith) at the request of [buzbal](https://github.com/buzbal), who provided the requirements, testing, and pushback to make sure it actually worked.
