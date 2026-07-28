"""Retrieval tool over the user's uploaded documents."""
from backend.rag.store import store

SCHEMA = {
    "name": "search_knowledge_base",
    "description": (
        "Search the user's uploaded documents for relevant passages. Use this "
        "before web_search when the question might be answered by material "
        "the user has already provided."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to look for."},
        },
        "required": ["query"],
    },
}


def run(query: str) -> list[dict]:
    results = store.search(query, k=4)
    if not results:
        return [{"note": "No documents have been uploaded yet, or nothing matched."}]
    return results
