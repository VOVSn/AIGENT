# backend/tools/executor.py
import logging
import importlib
import inspect
import asyncio # <-- NEW IMPORT

logger = logging.getLogger(__name__)

TOOL_REGISTRY = {
    "web_search": "tools.tool_library.web_search.search_web",
    "manage_calendar": "tools.tool_library.calendar_tool.manage_calendar",
}

def get_tool_function(tool_name: str):
    """
    Dynamically imports and returns the callable function for a given tool.
    Returns None if the tool is not found or fails to import.
    """
    if tool_name not in TOOL_REGISTRY:
        return None
    
    import_path = TOOL_REGISTRY[tool_name]
    try:
        module_path, function_name = import_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        return getattr(module, function_name, None)
    except (ImportError, AttributeError, ValueError):
        logger.error(f"Failed to get function for tool '{tool_name}' from path '{import_path}'.")
        return None

# UPDATED: This function is now SYNCHRONOUS, but can call ASYNC tools.
def execute_tool(tool_name: str, parameters: dict) -> str:
    """
    Dynamically imports and executes a registered tool by name.
    This executor is SYNCHRONOUS, but it can correctly run both
    sync and async tool functions.
    """
    logger.info(f"Executing tool '{tool_name}' with parameters: {parameters}")
    
    tool_function = get_tool_function(tool_name)
    if not tool_function:
        logger.warning(f"Attempted to execute unregistered or invalid tool: {tool_name}")
        return f"Error: Tool '{tool_name}' is not available or configured incorrectly."

    try:
        # Check if the tool function is a coroutine function (async def)
        if inspect.iscoroutinefunction(tool_function):
            # If it's async, run it in its own event loop.
            result = asyncio.run(tool_function(**parameters))
        else:
            # If it's sync, run it directly.
            result = tool_function(**parameters)
            
        logger.info(f"Tool '{tool_name}' executed successfully.")
        return str(result)
    except TypeError as e:
        logger.error(f"Type error executing tool '{tool_name}': {e}. Check parameters.")
        return f"Error: Invalid parameters for tool '{tool_name}'. {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred in tool '{tool_name}': {e}", exc_info=True)
        return f"Error: An unexpected error occurred while running the tool: {e}"