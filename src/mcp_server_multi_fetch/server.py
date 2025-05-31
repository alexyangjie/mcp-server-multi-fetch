from typing import Annotated, Tuple
from urllib.parse import urlparse, urlunparse

import markdownify
import readabilipy.simple_json
from mcp.shared.exceptions import McpError
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    ErrorData,
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
    Tool,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)
from protego import Protego
from pydantic import BaseModel, Field, AnyUrl
import asyncio
import json
from firecrawl import AsyncFirecrawlApp

# Firecrawl client for scraping URLs
firecrawl_app = AsyncFirecrawlApp()

DEFAULT_USER_AGENT_AUTONOMOUS = "ModelContextProtocol/1.0 (Autonomous; +https://github.com/modelcontextprotocol/servers)"
DEFAULT_USER_AGENT_MANUAL = "ModelContextProtocol/1.0 (User-Specified; +https://github.com/modelcontextprotocol/servers)"


def extract_content_from_html(html: str) -> str:
    """Extract and convert HTML content to Markdown format.

    Args:
        html: Raw HTML content to process

    Returns:
        Simplified markdown version of the content
    """
    ret = readabilipy.simple_json.simple_json_from_html_string(
        html, use_readability=True
    )
    if not ret["content"]:
        return "<error>Page failed to be simplified from HTML</error>"
    content = markdownify.markdownify(
        ret["content"],
        heading_style=markdownify.ATX,
    )
    return content


def get_robots_txt_url(url: str) -> str:
    """Get the robots.txt URL for a given website URL.

    Args:
        url: Website URL to get robots.txt for

    Returns:
        URL of the robots.txt file
    """
    # Parse the URL into components
    parsed = urlparse(url)

    # Reconstruct the base URL with just scheme, netloc, and /robots.txt path
    robots_url = urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))

    return robots_url


async def check_may_autonomously_fetch_url(url: str, user_agent: str, proxy_url: str | None = None) -> None:
    """
    Check if the URL can be fetched by the user agent according to the robots.txt file.
    Raises a McpError if not.
    """
    from httpx import AsyncClient, HTTPError

    robot_txt_url = get_robots_txt_url(url)

    async with AsyncClient(proxies=proxy_url) as client:
        try:
            response = await client.get(
                robot_txt_url,
                follow_redirects=True,
                headers={"User-Agent": user_agent},
            )
        except HTTPError:
            raise McpError(ErrorData(
                code=INTERNAL_ERROR,
                message=f"Failed to fetch robots.txt {robot_txt_url} due to a connection issue",
            ))
        if response.status_code in (401, 403):
            raise McpError(ErrorData(
                code=INTERNAL_ERROR,
                message=f"When fetching robots.txt ({robot_txt_url}), received status {response.status_code} so assuming that autonomous fetching is not allowed, the user can try manually fetching by using the fetch prompt",
            ))
        elif 400 <= response.status_code < 500:
            return
        robot_txt = response.text
    processed_robot_txt = "\n".join(
        line for line in robot_txt.splitlines() if not line.strip().startswith("#")
    )
    robot_parser = Protego.parse(processed_robot_txt)
    if not robot_parser.can_fetch(str(url), user_agent):
        raise McpError(ErrorData(
            code=INTERNAL_ERROR,
            message=f"The sites robots.txt ({robot_txt_url}), specifies that autonomous fetching of this page is not allowed, "
            f"<useragent>{user_agent}</useragent>\n"
            f"<url>{url}</url>"
            f"<robots>\n{robot_txt}\n</robots>\n"
            f"The assistant must let the user know that it failed to view the page. The assistant may provide further guidance based on the above information.\n"
            f"The assistant can tell the user that they can try manually fetching the page by using the fetch prompt within their UI.",
        ))


async def fetch_url(
    url: str, user_agent: str, force_raw: bool = False, proxy_url: str | None = None
) -> Tuple[str, str]:
    """
    Fetch the URL and return the content in a form ready for the LLM, as well as a prefix string with status information.
    """
    # Use Firecrawl SDK to scrape the URL for markdown or raw HTML
    try:
        data = await firecrawl_app.scrape_url(
            url=url,
            formats=["html"] if force_raw else ["markdown"],
        )
    except Exception as e:
        raise McpError(ErrorData(
            code=INTERNAL_ERROR,
            message=f"Failed to fetch {url} via Firecrawl SDK: {e!r}"
        ))

    if force_raw:
        content = data.html or ""
        if not content:
            raise McpError(ErrorData(
                code=INTERNAL_ERROR,
                message=f"No HTML content returned for {url}"
            ))
        return content, ""
    else:
        content = data.markdown or ""
        if not content:
            raise McpError(ErrorData(
                code=INTERNAL_ERROR,
                message=f"No Markdown content returned for {url}"
            ))
        return content, ""


class Fetch(BaseModel):
    """Parameters for fetching a URL."""

    url: Annotated[AnyUrl, Field(description="URL to fetch")]
    max_length: Annotated[
        int,
        Field(
            default=50000,
            description="Maximum number of characters to return.",
            gt=0,
            lt=1000000,
        ),
    ]
    start_index: Annotated[
        int,
        Field(
            default=0,
            description="On return output starting at this character index, useful if a previous fetch was truncated and more context is required.",
            ge=0,
        ),
    ]
    raw: Annotated[
        bool,
        Field(
            default=False,
            description="Get the actual HTML content of the requested page, without simplification.",
        ),
    ]

class FetchMulti(BaseModel):
    """Parameters for fetching multiple URLs in parallel."""
    requests: list[Fetch] = Field(
        ..., description="List of fetch requests to process in parallel"
    )

class Search(BaseModel):
    """Parameters for searching using Firecrawl search API."""
    query: Annotated[str, Field(description="Search query string")]
    limit: Annotated[int, Field(default=10, description="Maximum number of results to return.", ge=1)]

async def serve(
    custom_user_agent: str | None = None,
    ignore_robots_txt: bool = False,
    proxy_url: str | None = None,
) -> None:
    """Run the fetch MCP server.

    Args:
        custom_user_agent: Optional custom User-Agent string to use for requests
        ignore_robots_txt: Whether to ignore robots.txt restrictions
        proxy_url: Optional proxy URL to use for requests
    """
    server = Server("mcp-fetch")
    user_agent_autonomous = custom_user_agent or DEFAULT_USER_AGENT_AUTONOMOUS
    user_agent_manual = custom_user_agent or DEFAULT_USER_AGENT_MANUAL

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="fetch",
                description="""Fetches a single URL from the internet and optionally extracts its contents as markdown.
This tool now grants you internet access. Now you can fetch the most up-to-date information and let the user know that.""",
                inputSchema=Fetch.model_json_schema(),
            ),
        Tool(
            name="fetch_multi",
            description="""Fetches multiple URLs in parallel and returns an array of results. Each element corresponds to an input fetch request and includes either the fetched content or an error message.""",
            inputSchema=FetchMulti.model_json_schema(),
        ),
        Tool(
            name="search",
            description="""Searches the web using the Firecrawl search API and scrapes results in markdown and link formats by default.""",
            inputSchema=Search.model_json_schema(),
        ),
        ]

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name="fetch",
                description="Fetch a single URL and extract its contents as markdown",
                arguments=[
                    PromptArgument(
                        name="url", description="URL to fetch", required=True
                    )
                ],
            ),
        Prompt(
            name="fetch_multi",
            description="Fetch multiple URLs in parallel and return their contents as an array of results",
            arguments=[
                PromptArgument(
                    name="requests",
                    description="JSON array of fetch requests, each with url, max_length, start_index, and raw",
                    required=True,
                ),
            ],
        ),
        Prompt(
            name="search",
            description="Search the web using the Firecrawl search API",
            arguments=[
                PromptArgument(name="query", description="Search query string", required=True),
                PromptArgument(name="limit", description="Maximum number of results to return", required=False),
            ],
        ),
        ]

    @server.call_tool()
    async def call_tool(name, arguments: dict) -> list[TextContent]:
        if name == "fetch":
            try:
                args = Fetch(**arguments)
            except ValueError as e:
                raise McpError(ErrorData(code=INVALID_PARAMS, message=str(e)))

            url = str(args.url)
            if not url:
                raise McpError(ErrorData(code=INVALID_PARAMS, message="URL is required"))

            if not ignore_robots_txt:
                await check_may_autonomously_fetch_url(url, user_agent_autonomous, proxy_url)

            content, prefix = await fetch_url(
                url, user_agent_autonomous, force_raw=args.raw, proxy_url=proxy_url
            )
            original_length = len(content)
            if args.start_index >= original_length:
                content = "<error>No more content available.</error>"
            else:
                truncated_content = content[args.start_index : args.start_index + args.max_length]
                if not truncated_content:
                    content = "<error>No more content available.</error>"
                else:
                    content = truncated_content
                    actual_content_length = len(truncated_content)
                    remaining_content = original_length - (args.start_index + actual_content_length)
                    if actual_content_length == args.max_length and remaining_content > 0:
                        next_start = args.start_index + actual_content_length
                        content += f"\n\n<error>Content truncated. Call the fetch tool with a start_index of {next_start} to get more content.</error>"
            return [TextContent(type="text", text=f"{prefix}Contents of {url}:\n{content}")]

        if name == "fetch_multi":
            try:
                multi = FetchMulti.model_validate(arguments)
            except Exception as e:
                raise McpError(ErrorData(code=INVALID_PARAMS, message=str(e)))

            async def fetch_single(req: Fetch) -> dict:
                url = str(req.url)
                try:
                    if not ignore_robots_txt:
                        await check_may_autonomously_fetch_url(url, user_agent_autonomous, proxy_url)
                    content, prefix = await fetch_url(
                        url, user_agent_autonomous, force_raw=req.raw, proxy_url=proxy_url
                    )
                    original_length = len(content)
                    if req.start_index >= original_length:
                        content_text = "<error>No more content available.</error>"
                    else:
                        truncated = content[req.start_index : req.start_index + req.max_length]
                        if not truncated:
                            content_text = "<error>No more content available.</error>"
                        else:
                            content_text = truncated
                            actual_content_length = len(truncated)
                            remaining_content = original_length - (req.start_index + actual_content_length)
                            if actual_content_length == req.max_length and remaining_content > 0:
                                next_start = req.start_index + actual_content_length
                                content_text += f"\n\n<error>Content truncated. Call the fetch tool with a start_index of {next_start} to get more content.</error>"
                    return {"url": url, "prefix": prefix, "content": content_text}
                except McpError as e:
                    return {"url": url, "error": str(e)}

            tasks = [fetch_single(req) for req in multi.requests]
            results = await asyncio.gather(*tasks)
            return [TextContent(type="text", text=json.dumps(results))]

        if name == "search":
            try:
                args = Search(**arguments)
            except ValueError as e:
                raise McpError(ErrorData(code=INVALID_PARAMS, message=str(e)))
            try:
                result = await firecrawl_app.search(
                    query=args.query,
                    limit=args.limit,
                    scrapeOptions={"formats": ["markdown", "links"]},
                )
            except Exception as e:
                raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to search via Firecrawl SDK: {e!r}"))
            try:
                json_text = result.model_dump_json()
            except AttributeError:
                json_text = json.dumps(result)
            return [TextContent(type="text", text=json_text)]

        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Unknown tool: {name}"))

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None) -> GetPromptResult:
        if not arguments or "url" not in arguments:
            raise McpError(ErrorData(code=INVALID_PARAMS, message="URL is required"))

        url = arguments["url"]

        try:
            content, prefix = await fetch_url(url, user_agent_manual, proxy_url=proxy_url)
            # TODO: after SDK bug is addressed, don't catch the exception
        except McpError as e:
            return GetPromptResult(
                description=f"Failed to fetch {url}",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(type="text", text=str(e)),
                    )
                ],
            )
        return GetPromptResult(
            description=f"Contents of {url}",
            messages=[
                PromptMessage(
                    role="user", content=TextContent(type="text", text=prefix + content)
                )
            ],
        )

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)
