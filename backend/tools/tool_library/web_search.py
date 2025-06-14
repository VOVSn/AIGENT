# backend/tools/tool_library/web_search.py
import httpx
import logging
import os

logger = logging.getLogger(__name__)

SEARXNG_INTERNAL_URL = os.environ.get("SEARXNG_INTERNAL_URL", "http://searxng:8080")

async def run(params: dict) -> str:
    """
    Executes a web search using the searxng service.
    """
    query = params.get("query")
    if not query:
        return "Error: No search query was provided."

    search_url = f"{SEARXNG_INTERNAL_URL.rstrip('/')}/"
    search_params = {
        "q": query,
        "format": "json",
        "language": "en",
    }

    try:
        # --- THIS LINE IS UPDATED ---
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(search_url, params=search_params)
            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])
        if not results:
            return "No results found for your query."

        snippets = []
        for r in results[:5]:
            title = r.get('title', 'No Title')
            content = r.get('content', 'No Snippet Available')
            url = r.get('url', '#')
            snippets.append(f"Title: {title}\nURL: {url}\nSnippet: {content}")
        
        return "\n\n---\n\n".join(snippets)

    except httpx.RequestError as e:
        logger.error(f"Could not connect to the search service: {e}")
        return f"Error: The web search service is currently unavailable."
    except Exception as e:
        logger.error(f"An unexpected error occurred during web search: {e}")
        return f"An unexpected error occurred while trying to perform a web search."