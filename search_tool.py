import os
from mcp.server.fastmcp import FastMCP
from tavily import TavilyClient

mcp = FastMCP("search")

client = TavilyClient(
    api_key=os.environ["TAVILY_API_KEY"]
)

@mcp.tool()
def web_search(query: str):
    return client.search(
        query=query,
        max_results=5
    )

if __name__ == "__main__":
    mcp.run()