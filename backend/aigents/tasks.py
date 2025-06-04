import asyncio
import httpx # For asynchronous HTTP requests
import json
import logging
from datetime import datetime

from celery import shared_task
from asgiref.sync import sync_to_async # To call Django ORM from async code

from django.conf import settings
from django.contrib.auth import get_user_model
from .models import Aigent, Prompt, ChatHistory # Assuming models are in the same app

User = get_user_model()

# Get specific loggers
app_logger = logging.getLogger('aigents') # Or your general app logger
llm_logger = logging.getLogger('llm_logger') # For LLM specific logs

# Helper function to convert Django model instances to dict for JSON serialization in prompt
# This is a simplified version; you might want more control over what fields are included.
@sync_to_async
def serialize_user_state(user_instance):
    if user_instance and isinstance(user_instance.user_state, dict):
        return json.dumps(user_instance.user_state, indent=2)
    return json.dumps({})

@sync_to_async
def serialize_aigent_state(aigent_instance):
    if aigent_instance and isinstance(aigent_instance.aigent_state, dict):
        return json.dumps(aigent_instance.aigent_state, indent=2)
    return json.dumps({})

@sync_to_async
def get_formatted_chat_history(user_instance, aigent_instance, limit=10):
    """
    Fetches and formats chat history.
    For Phase 1, this can be simplified or even return a placeholder.
    Actual history formatting will be more crucial in Phase 2.
    """
    try:
        chat_history_obj = ChatHistory.objects.get(user=user_instance, aigent=aigent_instance)
        history_list = chat_history_obj.history[-limit:] # Get last 'limit' messages
        
        formatted_history = []
        for entry in history_list:
            role = entry.get("role", "unknown").capitalize()
            content = entry.get("content", "")
            formatted_history.append(f"{role}: {content}")
        return "\n".join(formatted_history) if formatted_history else "No previous conversation history."
    except ChatHistory.DoesNotExist:
        return "No previous conversation history."
    except Exception as e:
        app_logger.error(f"Error formatting chat history for user {user_instance.id} and aigent {aigent_instance.id}: {e}")
        return "Error retrieving conversation history."


@shared_task(bind=True, max_retries=3, default_retry_delay=60) # bind=True gives access to self
async def process_user_message_to_aigent(self, user_id: int, user_message_content: str):
    """
    Celery task to process a user's message with an Aigent via Ollama.
    Phase 1: Basic interaction, focus on structured JSON output from LLM.
    """
    app_logger.info(f"Task process_user_message_to_aigent started for user_id: {user_id}, message: '{user_message_content[:50]}...'")

    try:
        # 1. Fetch active Aigent, User, and Prompt Template (using sync_to_async for ORM calls)
        # @sync_to_async
        def get_required_objects():
            active_aigent = Aigent.objects.filter(is_active=True).first()
            if not active_aigent:
                raise Aigent.DoesNotExist("No active Aigent found.")
            
            user = User.objects.get(pk=user_id)
            
            prompt_template_obj = active_aigent.default_prompt_template
            if not prompt_template_obj:
                raise Prompt.DoesNotExist(f"Aigent '{active_aigent.name}' has no default prompt template assigned.")
            
            return active_aigent, user, prompt_template_obj

        active_aigent, user, prompt_template_obj = await get_required_objects()
        app_logger.info(f"Found active Aigent: {active_aigent.name}, User: {user.username}, Prompt: {prompt_template_obj.name}")

        # 2. Fetch states and history (simplified for Phase 1)
        user_state_str = await serialize_user_state(user)
        aigent_state_str = await serialize_aigent_state(active_aigent)
        
        # For Phase 1, formatted_chat_history can be very simple or even hardcoded for testing structure
        # In Phase 2, this will be properly built from ChatHistory.history
        formatted_chat_history_str = await get_formatted_chat_history(user, active_aigent)

        # 3. Construct the Full Prompt
        prompt_placeholders = {
            "system_persona_prompt": active_aigent.system_persona_prompt,
            "user_state": user_state_str,
            "chat_history": formatted_chat_history_str, # Placeholder/Simplified for Phase 1
            "current_user_message": user_message_content,
            "aigent_state": aigent_state_str,
        }
        
        full_prompt = prompt_template_obj.template_str.format(**prompt_placeholders)
        
        llm_logger.info(f"--- LLM PROMPT (User: {user.id}, Aigent: {active_aigent.id}) ---\n{full_prompt}\n-------------------------")

        # 4. Ollama Call (Simplified: single endpoint, basic error handling)
        if not active_aigent.ollama_endpoints:
            app_logger.error(f"Aigent '{active_aigent.name}' has no Ollama endpoints configured.")
            raise ValueError(f"Aigent '{active_aigent.name}' has no Ollama endpoints configured.")
        
        # For Phase 1, just use the first endpoint. Round-robin/failover in Phase 2.
        ollama_api_url_base = active_aigent.ollama_endpoints[0]
        ollama_api_url_generate = f"{ollama_api_url_base.rstrip('/')}/api/generate" # Or /api/chat if using chat completions

        # Prepare payload for Ollama
        # Note: Ollama's /api/generate expects a raw prompt string.
        # If using /api/chat, the payload structure is different (list of messages).
        # Our current prompt template expects a single, large prompt string.
        payload = {
            "model": active_aigent.ollama_model_name,
            "prompt": full_prompt,
            "stream": False, # We want the full response, not streamed chunks
            "format": "json", # CRITICAL: Request structured JSON output
            "options": {
                # Only include temperature/context_length if they have values
            }
        }
        if active_aigent.ollama_temperature is not None:
            payload["options"]["temperature"] = active_aigent.ollama_temperature
        if active_aigent.ollama_context_length is not None:
            # Note: 'num_ctx' is a common parameter for context length in Ollama's 'options'
            payload["options"]["num_ctx"] = active_aigent.ollama_context_length
        
        # If options is empty, remove it, as some Ollama versions might not like an empty options object
        if not payload["options"]:
            del payload["options"]

        app_logger.info(f"Sending request to Ollama: {ollama_api_url_generate} with model {payload['model']}")

        async with httpx.AsyncClient(timeout=active_aigent.request_timeout_seconds) as client:
            response = await client.post(ollama_api_url_generate, json=payload)
            response.raise_for_status() # Will raise an httpx.HTTPStatusError for 4xx/5xx responses

        ollama_response_raw_text = response.text # Get raw text for logging
        
        # Ollama with "format": "json" and "stream": False for /api/generate
        # returns a JSON where the 'response' field contains the LLM's JSON string.
        # Example: {"model":"...", "created_at":"...", "response":"{\n  \"answer_to_user\": ...}\n", ...}
        ollama_data = response.json()
        llm_json_output_str = ollama_data.get("response")

        if not llm_json_output_str:
            llm_logger.error(f"Ollama response missing 'response' field or it's empty. Raw: {ollama_response_raw_text[:500]}")
            raise ValueError("Ollama response missing 'response' field containing the JSON output.")

        llm_logger.info(f"--- LLM RAW JSON RESPONSE (User: {user.id}, Aigent: {active_aigent.id}) ---\n{llm_json_output_str}\n-------------------------")
        
        # 5. Parse Ollama's JSON Response
        try:
            # The 'response' field itself should be a string that is valid JSON
            structured_llm_output = json.loads(llm_json_output_str)
        except json.JSONDecodeError as e:
            llm_logger.error(f"Failed to decode JSON from Ollama's 'response' field: {e}. String was: {llm_json_output_str[:500]}")
            raise ValueError(f"Ollama's output was not valid JSON: {e}")

        # Validate the expected keys
        required_keys = ["answer_to_user", "updated_aigent_state", "updated_user_state"]
        if not all(key in structured_llm_output for key in required_keys):
            llm_logger.error(f"Ollama JSON output missing one or more required keys ({required_keys}). Got: {list(structured_llm_output.keys())}")
            raise ValueError(f"Ollama JSON output missing required keys. Expected: {required_keys}")
        
        answer_to_user = structured_llm_output["answer_to_user"]
        # For Phase 1, we primarily care about answer_to_user.
        # updated_aigent_state = structured_llm_output["updated_aigent_state"]
        # updated_user_state = structured_llm_output["updated_user_state"]
        
        # 6. Update State in DB (Placeholder for Phase 1 - full logic in Phase 2)
        # await sync_to_async(active_aigent.save_state)(updated_aigent_state) # Example for later
        # await sync_to_async(user.save_state)(updated_user_state) # Example for later
        
        # Add user message and LLM answer to ChatHistory (Simplified for Phase 1)
        # @sync_to_async
        def update_chat_history():
            history_obj, created = ChatHistory.objects.get_or_create(
                user=user, aigent=active_aigent
            )
            # Ensure history is a list
            if not isinstance(history_obj.history, list):
                history_obj.history = []

            timestamp = datetime.utcnow().isoformat() + "Z"
            history_obj.history.append({"role": "user", "content": user_message_content, "timestamp": timestamp})
            history_obj.history.append({"role": "assistant", "content": answer_to_user, "timestamp": timestamp})
            
            # Optional: Trim history if it gets too long
            MAX_HISTORY_LENGTH = 50 # Store last 50 exchanges (100 messages)
            if len(history_obj.history) > MAX_HISTORY_LENGTH * 2:
                history_obj.history = history_obj.history[-(MAX_HISTORY_LENGTH*2):]

            history_obj.save()
            app_logger.info(f"Chat history updated for user {user.id} with aigent {active_aigent.id}")

        await update_chat_history()

        app_logger.info(f"Task successful for user {user.id}. LLM Answer: '{str(answer_to_user)[:100]}...'")
        return {
            "answer_to_user": answer_to_user,
            # In Phase 1, we don't strictly need to return the states to the API endpoint,
            # but the task itself should be aware of them.
            "updated_aigent_state_debug": structured_llm_output["updated_aigent_state"],
            "updated_user_state_debug": structured_llm_output["updated_user_state"]
        }

    except Aigent.DoesNotExist as e:
        app_logger.error(f"Task failed for user_id {user_id}: {e}")
        # self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        raise # Re-raise to mark task as failed
    except User.DoesNotExist as e:
        app_logger.error(f"Task failed for user_id {user_id}: User not found.")
        raise
    except Prompt.DoesNotExist as e:
        app_logger.error(f"Task failed for user_id {user_id}: {e}")
        raise
    except httpx.HTTPStatusError as e:
        app_logger.error(f"Ollama API request failed: {e.response.status_code} - {e.response.text[:200]}")
        # Retry for server-side errors (5xx) or specific client errors like timeouts
        if 500 <= e.response.status_code < 600 or isinstance(e, httpx.TimeoutException):
            raise self.retry(exc=e, countdown=int(self.default_retry_delay * (self.request.retries + 1)))
        raise # Don't retry for other client errors like 400, 404 immediately
    except httpx.RequestError as e: # Network errors, timeouts not caught by HTTPStatusError
        app_logger.error(f"Ollama request network error: {e}")
        raise self.retry(exc=e, countdown=int(self.default_retry_delay * (self.request.retries + 1)))
    except ValueError as e: # For JSON parsing or validation errors
        app_logger.error(f"Data processing error in task: {e}")
        raise # Usually not something to retry without code change
    except Exception as e:
        app_logger.error(f"Unexpected error in task process_user_message_to_aigent for user_id {user_id}: {e}", exc_info=True)
        # You might want to retry for some unexpected errors, or not.
        # For now, let it fail to investigate.
        # raise self.retry(exc=e)
        raise