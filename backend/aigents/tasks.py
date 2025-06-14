# backend/aigents/tasks.py
import asyncio
import httpx
import json
import logging
import re
from datetime import datetime, timezone

from celery import shared_task
from .models import Aigent, Prompt, ChatHistory
from tools.models import Tool # Import for type hinting
from tools import executor as tool_executor # Import our new tool executor
from django.contrib.auth import get_user_model
from typing import List

User = get_user_model()
app_logger = logging.getLogger('aigents')
llm_logger = logging.getLogger('llm_logger')

# --- Tool-Related Prompt Generation Helpers ---

TOOL_USE_INSTRUCTIONS = """--- INSTRUCTIONS FOR YOUR RESPONSE ---
You have two choices for how to respond:

1.  **Answer Directly:** If you can fully answer the user's question with your existing knowledge and without using a tool, then respond with the standard JSON format that includes the "answer_to_user", "updated_aigent_state", and "updated_user_state" keys.

2.  **Use a Tool:** If you need to use a tool to find the answer, your *entire response* must be a single JSON object with the following specific format:
    {
      "tool_to_use": "name_of_the_tool_from_the_list",
      "parameters": {
        "parameter_name_1": "value_1"
      }
    }
Do NOT provide any other text or explanation, only this tool-use JSON. The system will then execute the tool and provide you with the results in the next step.
---"""

def _generate_tools_text(tools: List[Tool]) -> str:
    """Formats the list of available tools into a string for the prompt."""
    if not tools:
        return ""
    
    tool_descriptions = []
    for i, tool in enumerate(tools, 1):
        # Format the parameters schema for better readability
        params_str = json.dumps(tool.parameters_schema)
        description = (
            f"{i}. Tool Name: `{tool.name}`\n"
            f"   Description: {tool.description}\n"
            f"   Parameters JSON schema: {params_str}"
        )
        tool_descriptions.append(description)

    return (
        "--- AVAILABLE TOOLS ---\n"
        "You have the following tools at your disposal. You should only use them if you cannot answer the user's question with your existing knowledge.\n\n"
        + "\n\n".join(tool_descriptions) +
        "\n---"
    )

# --- Existing Helper Functions (Mostly unchanged) ---

def extract_json_from_text(text: str) -> str:
    match = re.search(r'\{.*\}|\[.*\]', text, re.DOTALL)
    if match:
        potential_json = match.group(0)
        potential_json = re.sub(r',\s*([}\]])', r'\1', potential_json)
        try:
            json.loads(potential_json)
            app_logger.info("Successfully extracted JSON from LLM response.")
            return potential_json
        except json.JSONDecodeError:
            app_logger.warning("Found a JSON-like block, but it failed to parse. Returning original text.")
    app_logger.warning("Could not find a valid JSON block in the LLM response.")
    return text

async def make_ollama_request(url, payload, timeout):
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()

def get_required_objects_wrapper(user_id: int):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        app_logger.error(f"User with id {user_id} not found.")
        raise
    
    # Use prefetch_related for the ManyToMany 'tools' field for efficiency
    active_aigent = Aigent.objects.filter(is_active=True).select_related('default_prompt_template').prefetch_related('tools').first()
    if not active_aigent:
        app_logger.error("No active Aigent found.")
        raise Aigent.DoesNotExist("No active Aigent found.")
    
    prompt_template_obj = active_aigent.default_prompt_template
    if not prompt_template_obj:
        app_logger.error(f"Aigent '{active_aigent.name}' has no default prompt template assigned.")
        raise Prompt.DoesNotExist(f"Aigent '{active_aigent.name}' has no default prompt template assigned.")
        
    return active_aigent, user, prompt_template_obj

def serialize_user_state_wrapper(user_instance):
    return json.dumps(user_instance.user_state, indent=2) if isinstance(user_instance.user_state, dict) else json.dumps({})

def serialize_aigent_state_wrapper(aigent_instance):
    return json.dumps(aigent_instance.aigent_state, indent=2) if isinstance(aigent_instance.aigent_state, dict) else json.dumps({})

def get_formatted_chat_history_wrapper(user_instance, aigent_instance, limit=10):
    try:
        chat_history_obj = ChatHistory.objects.get(user=user_instance, aigent=aigent_instance)
        history_list = chat_history_obj.history[-limit*2:] if isinstance(chat_history_obj.history, list) else []
        formatted_history = [f"{entry.get('role', 'unknown').capitalize()}: {entry.get('content', '')}" for entry in history_list]
        return "\n".join(formatted_history) if formatted_history else "No previous conversation history."
    except ChatHistory.DoesNotExist:
        return "No previous conversation history."
    except Exception as e:
        app_logger.error(f"Error formatting chat history: {str(e)}")
        return "Error retrieving conversation history."

def update_chat_history_wrapper(user, aigent, user_message_content, answer_to_user):
    history_obj, _ = ChatHistory.objects.get_or_create(user=user, aigent=aigent, defaults={'history': []})
    if not isinstance(history_obj.history, list): history_obj.history = []
    timestamp = datetime.utcnow().isoformat() + "Z"
    history_obj.history.extend([
        {"role": "user", "content": user_message_content, "timestamp": timestamp},
        {"role": "assistant", "content": answer_to_user, "timestamp": timestamp}
    ])
    MAX_HISTORY_ENTRIES = 50
    if len(history_obj.history) > MAX_HISTORY_ENTRIES * 2:
        history_obj.history = history_obj.history[-(MAX_HISTORY_ENTRIES*2):]
    history_obj.save()
    app_logger.info(f"Chat history updated for user {user.id} with aigent {aigent.id}")

def update_states_wrapper(user, aigent, new_user_state, new_aigent_state):
    try:
        if isinstance(new_user_state, dict):
            user.user_state = new_user_state
            user.save(update_fields=['user_state'])
        if isinstance(new_aigent_state, dict):
            aigent.aigent_state = new_aigent_state
            aigent.save(update_fields=['aigent_state'])
        app_logger.info(f"Updated states for user {user.id} and aigent {aigent.id}")
    except Exception as e:
        app_logger.error(f"Failed to update states in wrapper: {str(e)}", exc_info=True)
        raise

# --- Main Celery Task (Fully Refactored with Reasoning Loop) ---
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_user_message_to_aigent(self, user_id: int, user_message_content: str):
    task_id = self.request.id
    app_logger.info(f"Task {task_id} [process_user_message_to_aigent] started for user_id: {user_id}")
    
    try:
        # 1. SETUP: Get all required objects and initial data
        active_aigent, user, prompt_template_obj = get_required_objects_wrapper(user_id)
        available_tools = list(active_aigent.tools.all())
        
        user_state_str = serialize_user_state_wrapper(user)
        aigent_state_str = serialize_aigent_state_wrapper(active_aigent)
        formatted_chat_history_str = get_formatted_chat_history_wrapper(user, active_aigent)

        # 2. DECIDER PROMPT: Prepare and make the first LLM call
        tools_text_block = _generate_tools_text(available_tools)
        instructions_text_block = TOOL_USE_INSTRUCTIONS if available_tools else ""

        prompt_placeholders = {
            "current_utc_datetime": datetime.now(timezone.utc).isoformat(),
            "system_persona_prompt": active_aigent.system_persona_prompt,
            "user_state": user_state_str,
            "chat_history": formatted_chat_history_str,
            "current_user_message": user_message_content,
            "aigent_state": aigent_state_str,
            "available_tools": tools_text_block,
            "tool_use_instructions": instructions_text_block,
        }
        
        # This will now correctly format the prompt without a KeyError
        decider_prompt = prompt_template_obj.template_str.format(**prompt_placeholders)
        llm_logger.info(f"--- LLM DECIDER PROMPT (Task: {task_id}) ---\n{decider_prompt}\n---")

        ollama_api_url = f"{active_aigent.ollama_endpoints[0].rstrip('/')}/api/generate"
        payload = {"model": active_aigent.ollama_model_name, "prompt": decider_prompt, "stream": False, "format": "json"}
        if active_aigent.ollama_temperature is not None: payload.setdefault("options", {})["temperature"] = active_aigent.ollama_temperature
        if active_aigent.ollama_context_length is not None: payload.setdefault("options", {})["num_ctx"] = active_aigent.ollama_context_length
        
        app_logger.info(f"Task {task_id}: Sending DECIDER request to Ollama...")
        decider_response_data = asyncio.run(make_ollama_request(ollama_api_url, payload, active_aigent.request_timeout_seconds))
        decider_raw_output = decider_response_data.get("response", "")
        llm_logger.info(f"--- LLM DECIDER RAW RESPONSE (Task: {task_id}) ---\n{decider_raw_output}\n---")
        
        cleaned_json_str = extract_json_from_text(decider_raw_output)
        structured_decider_output = json.loads(cleaned_json_str)

        # 3. REASONING LOOP: Check if a tool was chosen
        if "tool_to_use" in structured_decider_output:
            # --- TOOL PATH ---
            tool_name = structured_decider_output["tool_to_use"]
            tool_params = structured_decider_output.get("parameters", {})
            app_logger.info(f"Task {task_id}: Aigent chose to use tool '{tool_name}' with params: {tool_params}")

            # Execute the tool and get the results
            tool_observation_results = asyncio.run(tool_executor.execute_tool(tool_name, tool_params))
            llm_logger.info(f"--- TOOL RESULTS (Task: {task_id}) ---\n{tool_observation_results}\n---")

            # SYNTHESIS PROMPT: Prepare and make the second LLM call
            synthesis_prompt_template = Prompt.objects.get(name="ToolSynthesisPrompt_v1")
            
            synthesis_prompt_placeholders = {
                "system_persona_prompt": active_aigent.system_persona_prompt,
                "chat_history": formatted_chat_history_str,
                "original_user_message": user_message_content,
                "tool_name": tool_name,
                "tool_parameters": json.dumps(tool_params),
                "tool_observation_results": tool_observation_results,
            }
            synthesis_prompt = synthesis_prompt_template.template_str.format(**synthesis_prompt_placeholders)
            llm_logger.info(f"--- LLM SYNTHESIS PROMPT (Task: {task_id}) ---\n{synthesis_prompt}\n---")
            
            payload["prompt"] = synthesis_prompt # Reuse the payload, just change the prompt
            app_logger.info(f"Task {task_id}: Sending SYNTHESIS request to Ollama...")
            synthesis_response_data = asyncio.run(make_ollama_request(ollama_api_url, payload, active_aigent.request_timeout_seconds))
            synthesis_raw_output = synthesis_response_data.get("response", "")
            llm_logger.info(f"--- LLM SYNTHESIS RAW RESPONSE (Task: {task_id}) ---\n{synthesis_raw_output}\n---")
            
            cleaned_synthesis_json = extract_json_from_text(synthesis_raw_output)
            final_structured_output = json.loads(cleaned_synthesis_json)
        else:
            # --- DIRECT ANSWER PATH ---
            app_logger.info(f"Task {task_id}: Aigent chose to answer directly.")
            final_structured_output = structured_decider_output

        # 4. FINALIZATION: Process the final result
        required_keys = ["answer_to_user", "updated_aigent_state", "updated_user_state"]
        if not all(key in final_structured_output for key in required_keys):
            missing = [key for key in required_keys if key not in final_structured_output]
            raise ValueError(f"Final LLM JSON output missing required keys: {missing}")

        updated_user_state = final_structured_output["updated_user_state"]
        updated_aigent_state = final_structured_output["updated_aigent_state"]
        update_states_wrapper(user, active_aigent, updated_user_state, updated_aigent_state)

        answer_to_user = final_structured_output["answer_to_user"]
        update_chat_history_wrapper(user, active_aigent, user_message_content, answer_to_user)
        
        app_logger.info(f"Task {task_id} successful. Answer: '{str(answer_to_user)[:100]}...'")
        
        return {
            "answer_to_user": answer_to_user, 
            "updated_aigent_state_debug": updated_aigent_state, 
            "updated_user_state_debug": updated_user_state
        }

    # --- Exception Handling ---
    except (Aigent.DoesNotExist, User.DoesNotExist, Prompt.DoesNotExist) as e:
        err_msg = f"Task {task_id} configuration error: {str(e)}"
        app_logger.error(err_msg, exc_info=True)
        # Non-retryable error
        raise Exception(err_msg)
    
    except httpx.HTTPStatusError as e:
        err_msg = f"Ollama API request failed: {e.response.status_code} - {e.response.text[:200]}"
        app_logger.error(f"Task {task_id}: {err_msg}")
        if 500 <= e.response.status_code < 600:
            app_logger.info(f"Task {task_id}: Retrying (HTTPStatusError)...")
            raise self.retry(exc=e)
        raise Exception(err_msg)
    
    except httpx.RequestError as e:
        err_msg = f"Ollama request network error: {str(e)}"
        app_logger.error(f"Task {task_id}: {err_msg}")
        app_logger.info(f"Task {task_id}: Retrying (RequestError)...")
        raise self.retry(exc=e)
    
    except (ValueError, json.JSONDecodeError, KeyError) as e:
        err_msg = f"Task {task_id} data processing error ({type(e).__name__}): {e}"
        app_logger.error(err_msg, exc_info=True)
        # Usually non-retryable
        raise Exception(err_msg)
    
    except Exception as e:
        err_msg = f"Task {task_id} unexpected error ({type(e).__name__}): {str(e)}"
        app_logger.error(err_msg, exc_info=True)
        # Depending on the error, could be retryable, but we'll fail for now
        raise Exception(err_msg)