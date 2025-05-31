 # Codex

 ## Project Overview
 - Name: mcp-server-multi-fetch
 - Version: 0.1.0
 - Description: A Model Context Protocol (MCP) server providing tools to fetch and convert web content for usage by LLMs.
 - License: MIT

 ## Repository Structure
 ```
 LICENSE            # MIT License
 pyproject.toml     # PEP 621 project metadata and dependencies
 uv.lock            # Locked dependencies for uv dev environment
 README.md          # User guide and configuration examples
 src/
   mcp_server_multi_fetch/
     __init__.py    # CLI entrypoint (main, serve)
     __main__.py    # Module entry for `python -m mcp_server_fetch`
     server.py      # Core server logic: tool & prompt registration, HTTP fetching, HTML-to-Markdown conversion
 ```

 ## Build & Packaging
 - Build backend: hatchling (`[build-system]` in pyproject.toml)
 - Dev dependencies managed with `uv` and locked in `uv.lock` (e.g., `pyright`, `ruff`)
 - Docker build: multi-stage, uses `ghcr.io/astral-sh/uv`, then Python 3.12-slim
 - Entry point in container: `mcp-server-multi-fetch`

 ## Dependencies & Frameworks
 - Python ≥3.10 (3.12 in Docker)
 - Async HTTP client: `httpx`
 - HTML simplification: `readabilipy` (Readability)
 - Markdown conversion: `markdownify`
 - Robots.txt parsing: `protego`
 - JSON schemas & validation: `pydantic` v2
 - MCP integration: `mcp` library (`mcp.server`, `mcp.types`, `mcp.shared.exceptions`)
 - CLI & concurrency: `argparse`, `asyncio`
 - Linting & type checking (dev): `ruff`, `pyright`

 ## Core Components
 - **CLI** (`src/mcp_server_fetch/__init__.py`):
   - Parses flags: `--user-agent`, `--ignore-robots-txt`, `--proxy-url`
   - Calls `serve()` (async)
 - **Server** (`src/mcp_server_fetch/server.py`):
    - Registers MCP tools & prompts:
    - Tool: `fetch` (Pydantic model `Fetch`)
    - Prompt: `fetch`
    - Tool: `fetch_multi` (Pydantic model `FetchMulti`)
    - Prompt: `fetch_multi`
    - Tool: `search` (Pydantic model `Search`)
    - Prompt: `search`
   - Implements:
     - `check_may_autonomously_fetch_url()`: respects robots.txt or raises `McpError`
     - `fetch_url()`: HTTP GET, error handling, choose raw vs. markdown
     - Tool handler (`call_tool`): enforce schema, fetch content in chunks
     - Prompt handler (`get_prompt`): user-initiated fetch
   - Runs via STDIO server: `mcp.server.stdio.stdio_server`

 ## Usage
 - CLI: `mcp-server-multi-fetch [--user-agent UA] [--ignore-robots-txt] [--proxy-url PROXY_URL]`
 - Python module: `python -m mcp_server_multi_fetch`
 - UVX: `uvx mcp-server-multi-fetch`

 ## Development Workflow
 - Install dependencies: `uv sync` (dev+prod), or `pip install .`
 - Lint: `ruff src/`
 - Type check: `pyright`

 ## Notable Conventions & Tips
 - HTTP timeouts: 30s
 - Default persona User-Agent vs. Autonomous UA
 - Chunked fetching via `max_length` (default 50000) and `start_index`
 - `McpError` used for controlled error signaling over MCP wire
 - No unit tests included (add as needed)

 ## For the AI Assistant
 Refer to this file when:
 - Exploring or modifying the server logic (`server.py`)
 - Updating CLI flags or tooling configuration
 - Adjusting dependency versions or build settings
 - Understanding request-handling flow and error semantics

 Keep this codex up-to-date with any structural or conceptual changes.
