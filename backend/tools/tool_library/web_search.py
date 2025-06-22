# backend/tools/tool_library/web_search.py
import httpx
import logging
import os
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# The internal URL for the searxng service from within the Docker network
SEARXNG_INTERNAL_URL = os.environ.get("SEARXNG_URL", "http://searxng:8080")

async def search_web(query: str, **kwargs) -> str: # Renamed from run(params) to match registry
    """
    Executes a web search using the searxng service and returns a
    formatted string of results for an LLM to process.
    
    Args:
        query (str): The specific search query string.

    Returns:
        str: A formatted string of search results or an error message.
    """
    if not query:
        return "Error: No search query was provided to the web_search tool."

    search_url = f"{SEARXNG_INTERNAL_URL.rstrip('/')}/search"
    search_params = {
        "q": query,
        "format": "json",
        "categories": "general",
        "language": "en",
    }
    
    logger.info(f"Executing web_search tool with query: '{query}'")

    try:
        # Use an async client to make the request non-blocking
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(search_url, params=search_params)
            
            # Check for HTTP errors
            response.raise_for_status()
            
            data = response.json()

        results = data.get("results", [])
        if not results:
            logger.warning(f"web_search for '{query}' returned no results.")
            return "No results found for the query."

        # Format the top 5 results into a clean string for the LLM
        snippets = []
        for r in results[:5]:
            title = r.get('title', 'No Title')
            content = r.get('content', 'No Snippet Available').strip()
            url = r.get('url', '#')
            # Create a compact, readable block for each result
            snippets.append(f"Title: {title}\nURL: {url}\nSnippet: {content}")
        
        # Join the blocks with a clear separator
        return "\n\n---\n\n".join(snippets)

    except httpx.HTTPStatusError as e:
        logger.error(f"web_search failed with HTTP status {e.response.status_code} for query '{query}'. Response: {e.response.text[:200]}")
        return f"Error: The web search service returned an HTTP error ({e.response.status_code})."
    except httpx.RequestError as e:
        logger.error(f"Could not connect to the search service for query '{query}': {e}")
        return "Error: The web search service is currently unavailable or timed out."
    except Exception as e:
        logger.error(f"An unexpected error occurred during web search for query '{query}': {e}", exc_info=True)
        return "An unexpected error occurred while trying to perform a web search."