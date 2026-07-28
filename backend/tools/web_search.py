"""Web search tool.

Uses the `ddgs` (DuckDuckGo Search) package so the project runs with
zero search-API keys. Swap this out for Tavily/Serper/Brave by keeping
the same function signature and return shape if you want higher quality
results in production.
"""
from ddgs import DDGS

SCHEMA = {
    "name": "web_search",
    "description": (
        "Search the public web for current information. Returns a short list "
        "of results with title, url, and snippet. Use this for facts that "
        "might be recent or that aren't in the uploaded documents."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."},
        },
        "required": ["query"],
    },
}


def run(query: str, max_results: int = 5) -> list[dict]:
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "snippet": r.get("body", ""),
        }
        for r in results
    ]
