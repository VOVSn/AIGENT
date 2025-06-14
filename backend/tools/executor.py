# backend/tools/executor.py
import importlib
import logging

logger = logging.getLogger(__name__)

async def execute_tool(tool_name: str, parameters: dict) -> str:
    """
    Dynamically imports and runs a tool's 'run' function.

    Args:
        tool_name (str): The name of the tool, corresponding to its module name.
        parameters (dict): The parameters to pass to the tool's run function.

    Returns:
        str: The output from the tool, or an error message.
    """
    try:
        # Construct the full module path
        module_path = f"tools.tool_library.{tool_name}"
        
        # Dynamically import the module
        tool_module = importlib.import_module(module_path)
        
        # Check if the module has an async 'run' function
        if hasattr(tool_module, 'run') and callable(tool_module.run):
            logger.info(f"Executing tool '{tool_name}' with params: {parameters}")
            # Await the async run function
            result = await tool_module.run(parameters)
            return result
        else:
            logger.error(f"Tool '{tool_name}' module does not have a callable 'run' function.")
            return f"Error: Tool '{tool_name}' is not implemented correctly."
            
    except ImportError:
        logger.error(f"Could not find or import tool module for '{tool_name}'.")
        return f"Error: Unknown tool '{tool_name}'."
    except Exception as e:
        logger.error(f"An unexpected error occurred while executing tool '{tool_name}': {e}", exc_info=True)
        return f"An unexpected error occurred while running the tool."