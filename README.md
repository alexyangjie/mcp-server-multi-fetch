# Multi Fetch MCP Server

This project is based on the [Fetch MCP Server](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch) by Anthropic.
This fork replaces direct HTTP fetching with the Firecrawl Python SDK. Set up your Firecrawl API key to enable web scraping via Firecrawl.

A Model Context Protocol server that provides web content fetching capabilities. This server enables LLMs to retrieve and process content from web pages, converting HTML to markdown for easier consumption.

The fetch tool will truncate the response, but by using the `start_index` argument, you can specify where to start the content extraction. This lets models read a webpage in chunks, until they find the information they need.

### Available Tools

 - `fetch` - Fetches a URL from the internet and extracts its contents as markdown.
    - `url` (string, required): URL to fetch
    - `max_length` (integer, optional): Maximum number of characters to return (default: 50000)
    - `start_index` (integer, optional): Start content from this character index (default: 0)
    - `raw` (boolean, optional): Get raw content without markdown conversion (default: false)
 - `fetch_multi` - Fetches multiple URLs concurrently and returns an array of results. Input is an array of objects, each with:
    - `url` (string, required): URL to fetch
    - `max_length` (integer, optional): Maximum number of characters to return (default: 50000)
    - `start_index` (integer, optional): Start content from this character index (default: 0)
    - `raw` (boolean, optional): Get raw content without markdown conversion (default: false)

- `search` - Searches the web using the Firecrawl search API and scrapes results in markdown and link formats by default.
    - `query` (string, required): Search query string
    - `limit` (integer, optional): Maximum number of results to return (default: 10)
### Prompts

- **fetch**
  - Fetch a URL and extract its contents as markdown
  - Arguments:
    - `url` (string, required): URL to fetch

- **search**
  - Search the web using the Firecrawl search API
  - Arguments:
    - `query` (string, required): Search query string
    - `limit` (integer, optional): Maximum number of results to return (default: 10)
## Installation

Install the Firecrawl SDK and configure your API key before running the server:

```bash
# Install the MCP server and Firecrawl SDK
pip install mcp-server-multi-fetch firecrawl-py

# Set your Firecrawl API key (required)
export FIRECRAWL_API_KEY="fc-YOUR_API_KEY"

# Optionally, override the Firecrawl API endpoint
export FIRECRAWL_API_URL="https://api.firecrawl.dev"
```

Optionally: Install node.js, this will cause the fetch server to use a different HTML simplifier that is more robust.

### Using uv (recommended)

When using [`uv`](https://docs.astral.sh/uv/) no specific installation is needed. We will
use [`uvx`](https://docs.astral.sh/uv/guides/tools/) to directly run *mcp-server-multi-fetch*.


## Configuration

### Configure for Claude.app

Add to your Claude settings:

<details>
<summary>Using uvx</summary>

```json
"mcpServers": {
  "fetch": {
    "command": "uvx",
    "args": ["mcp-server-multi-fetch"]
  }
}
```
</details>

### Customization - robots.txt

By default, the server will obey a websites robots.txt file if the request came from the model (via a tool), but not if
the request was user initiated (via a prompt). This can be disabled by adding the argument `--ignore-robots-txt` to the
`args` list in the configuration.

### Customization - User-agent

By default, depending on if the request came from the model (via a tool), or was user initiated (via a prompt), the
server will use either the user-agent
```
ModelContextProtocol/1.0 (Autonomous; +https://github.com/modelcontextprotocol/servers)
```
or
```
ModelContextProtocol/1.0 (User-Specified; +https://github.com/modelcontextprotocol/servers)
```

This can be customized by adding the argument `--user-agent=YourUserAgent` to the `args` list in the configuration.

### Customization - Proxy

The server supports HTTP(S) and SOCKS5 proxies via the `--proxy-url` argument. For example:

```bash
# HTTP proxy
mcp-server-multi-fetch --proxy-url http://192.168.1.1:8080

# SOCKS5 proxy
mcp-server-multi-fetch --proxy-url socks5://192.168.1.1:8080
```

Proxy handling is provided by the Firecrawl Python SDK, which supports HTTP(S) and SOCKS5 proxies configured via the `--proxy-url` flag.

## Debugging

You can use the MCP inspector to debug the server. For uvx installations:

```
npx @modelcontextprotocol/inspector uvx mcp-server-multi-fetch
```

Or if you've installed the package in a specific directory or are developing on it:

```
cd path/to/servers/src/fetch
npx @modelcontextprotocol/inspector uv run mcp-server-multi-fetch
```

## License

mcp-server-multi-fetch is licensed under the MIT License. This means you are free to use, modify, and distribute the software, subject to the terms and conditions of the MIT License. For more details, please see the LICENSE file in the project repository.
