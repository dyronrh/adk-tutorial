import os

from google.adk.agents.llm_agent import Agent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

github_tools = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={"Authorization": f"Bearer {os.getenv('GITHUB_PERSONAL_ACCESS_TOKEN', '')}"},
        timeout=30,
    ),
    tool_filter=[
        "get_me",
        "search_repositories",
        "get_file_contents",
        "list_issues",
        "list_pull_requests",
        "list_commits",
    ],
)

root_agent = Agent(
    model="gemini-flash-latest",
    name="root_agent",
    description="Answers questions about GitHub repositories using the GitHub MCP server.",
    instruction="You are a GitHub assistant. Use your tools to search repositories, read files, and list issues, pull requests and commits. Keep answers short.",
    tools=[github_tools],
)
