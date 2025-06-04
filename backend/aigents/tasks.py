import asyncio
import httpx
import json
import logging
from datetime import datetime

from celery import shared_task
from asgiref.sync import sync_to_async

from django.conf import settings
from django.contrib.auth import get_user_model
from .models import Aigent, Prompt, ChatHistory

User = get_user_model()
app_logger = logging.getLogger('aigents')
llm_logger = logging.getLogger('llm_logger')

# Convert sync functions to async versions
@sync_to_async
def get_required_objects_sync(user_id_sync: int):
    try:
        user = User.objects.get(pk=user_id_sync)
    except User.DoesNotExist as e:
        app_logger.error(f"User with id {user_id_sync} not found in get_required_objects_sync.")
        raise
    active_aigent = Aigent.objects.filter(is_active=True).select_related('default_prompt_template').first()
    if not active_aigent:
        app_logger.error("No active Aigent found in get_required_objects_sync.")
        raise Aigent.DoesNotExist("No active Aigent found.")
    prompt_template_obj = active_aigent.default_prompt_template
    if not prompt_template_obj:
        app_logger.error(f"Aigent '{active_aigent.name}' has no default prompt template assigned.")
        raise Prompt.DoesNotExist(f"Aigent '{active_aigent.name}' has no default prompt template assigned.")
    return active_aigent, user, prompt_template_obj

@sync_to_async
def serialize_user_state_sync(user_instance):
    if user_instance and isinstance(user_instance.user_state, dict):
        return json.dumps(user_instance.user_state, indent=2)
    return json.dumps({})

@sync_to_async
def serialize_aigent_state_sync(aigent_instance):
    if aigent_instance and isinstance(aigent_instance.aigent_state, dict):
        return json.dumps(aigent_instance.aigent_state, indent=2)
    return json.dumps({})

@sync_to_async
def get_formatted_chat_history_sync(user_instance, aigent_instance, limit=10):
    try:
        chat_history_obj = ChatHistory.objects.get(user=user_instance, aigent=aigent_instance)
        history_list = chat_history_obj.history if isinstance(chat_history_obj.history, list) else []
        history_list = history_list[-limit:]
        formatted_history = [f"{entry.get('role', 'unknown').capitalize()}: {entry.get('content', '')}" for entry in history_list]
        return "\n".join(formatted_history) if formatted_history else "No previous conversation history."
    except ChatHistory.DoesNotExist:
        return "No previous conversation history."
    except Exception as e:
        app_logger.error(f"Error formatting chat history for user {user_instance.id} and aigent {aigent_instance.id}: {str(e)}")
        return "Error retrieving conversation history."

@sync_to_async
def update_chat_history_sync(user, active_aigent, user_message_content, answer_to_user):
    history_obj, created = ChatHistory.objects.get_or_create(
        user=user, aigent=active_aigent, defaults={'history': []}
    )
    if not isinstance(history_obj.history, list):
        history_obj.history = []
    timestamp = datetime.utcnow().isoformat() + "Z"
    history_obj.history.append({"role": "user", "content": user_message_content, "timestamp": timestamp})
    history_obj.history.append({"role": "assistant", "content": answer_to_user, "timestamp": timestamp})
    MAX_HISTORY_ENTRIES = 50
    if len(history_obj.history) > MAX_HISTORY_ENTRIES * 2:
        history_obj.history = history_obj.history[-(MAX_HISTORY_ENTRIES*2):]
    history_obj.save()
    app_logger.info(f"Chat history updated for user {user.id} with aigent {active_aigent.id}")

# Async function for HTTP requests
async def make_ollama_request(url, payload, timeout):
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()

# Main async function that handles the entire workflow
async def process_message_async(user_id: int, user_message_content: str, task_id: str):
    """
    Fully async function that handles the entire message processing workflow
    """
    try:
        # 1. Get required objects asynchronously
        active_aigent, user, prompt_template_obj = await get_required_objects_sync(user_id)
        app_logger.info(f"Task {task_id}: Found active Aigent: {active_aigent.name}, User: {user.username}, Prompt: {prompt_template_obj.name}")

        # 2. Prepare data asynchronously
        user_state_str = await serialize_user_state_sync(user)
        aigent_state_str = await serialize_aigent_state_sync(active_aigent)
        formatted_chat_history_str = await get_formatted_chat_history_sync(user, active_aigent)

        # 3. Build prompt synchronously (no DB access)
        prompt_placeholders = {
            "system_persona_prompt": active_aigent.system_persona_prompt,
            "user_state": user_state_str,
            "chat_history": formatted_chat_history_str,
            "current_user_message": user_message_content,
            "aigent_state": aigent_state_str,
        }
        full_prompt = prompt_template_obj.template_str.format(**prompt_placeholders)
        llm_logger.info(f"--- LLM PROMPT (Task: {task_id}, User: {user.id}, Aigent: {active_aigent.id}) ---\n{full_prompt}\n-------------------------")

        # 4. Validate Ollama configuration
        if not active_aigent.ollama_endpoints or not isinstance(active_aigent.ollama_endpoints, list) or not active_aigent.ollama_endpoints[0]:
            err_msg = f"Aigent '{active_aigent.name}' has no valid Ollama endpoints configured."
            app_logger.error(f"Task {task_id}: {err_msg}")
            raise ValueError(err_msg)
        
        ollama_api_url_base = active_aigent.ollama_endpoints[0]
        ollama_api_url_target = f"{ollama_api_url_base.rstrip('/')}/api/generate"

        # 5. Prepare payload
        payload = {"model": active_aigent.ollama_model_name, "prompt": full_prompt, "stream": False, "format": "json", "options": {}}
        if active_aigent.ollama_temperature is not None: 
            payload["options"]["temperature"] = active_aigent.ollama_temperature
        if active_aigent.ollama_context_length is not None: 
            payload["options"]["num_ctx"] = active_aigent.ollama_context_length
        if not payload["options"]: 
            del payload["options"]

        # 6. Make HTTP request asynchronously
        app_logger.info(f"Task {task_id}: Sending request to Ollama: {ollama_api_url_target} with model {payload['model']}")
        ollama_data = await make_ollama_request(ollama_api_url_target, payload, active_aigent.request_timeout_seconds)
        
        # 7. Process response
        llm_json_output_str = ollama_data.get("response")
        if not llm_json_output_str:
            llm_logger.error(f"Task {task_id}: Ollama response missing 'response' field. Raw: {str(ollama_data)[:500]}")
            raise ValueError("Ollama response missing 'response' field.")
        
        llm_logger.info(f"--- LLM RAW JSON RESPONSE (Task: {task_id}) ---\n{llm_json_output_str}\n-------------------------")
        
        structured_llm_output = json.loads(llm_json_output_str)
        required_keys = ["answer_to_user", "updated_aigent_state", "updated_user_state"]
        if not all(key in structured_llm_output for key in required_keys):
            missing = [key for key in required_keys if key not in structured_llm_output]
            raise ValueError(f"Ollama JSON output missing keys: {missing}. Got: {list(structured_llm_output.keys())}")
        
        # 8. Update chat history asynchronously
        answer_to_user = structured_llm_output["answer_to_user"]
        await update_chat_history_sync(user, active_aigent, user_message_content, answer_to_user)
        
        app_logger.info(f"Task {task_id} successful. Answer: '{str(answer_to_user)[:100]}...'")
        return {
            "answer_to_user": answer_to_user, 
            "updated_aigent_state_debug": structured_llm_output["updated_aigent_state"], 
            "updated_user_state_debug": structured_llm_output["updated_user_state"]
        }
        
    except Exception as e:
        # Re-raise with task context
        raise type(e)(f"Task {task_id}: {str(e)}") from e

# SYNCHRONOUS WRAPPER FUNCTIONS (for Celery tasks)
def get_required_objects_wrapper(user_id: int):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist as e:
        app_logger.error(f"User with id {user_id} not found.")
        raise
    active_aigent = Aigent.objects.filter(is_active=True).select_related('default_prompt_template').first()
    if not active_aigent:
        app_logger.error("No active Aigent found.")
        raise Aigent.DoesNotExist("No active Aigent found.")
    prompt_template_obj = active_aigent.default_prompt_template
    if not prompt_template_obj:
        app_logger.error(f"Aigent '{active_aigent.name}' has no default prompt template assigned.")
        raise Prompt.DoesNotExist(f"Aigent '{active_aigent.name}' has no default prompt template assigned.")
    return active_aigent, user, prompt_template_obj

def serialize_user_state_wrapper(user_instance):
    if user_instance and isinstance(user_instance.user_state, dict):
        return json.dumps(user_instance.user_state, indent=2)
    return json.dumps({})

def serialize_aigent_state_wrapper(aigent_instance):
    if aigent_instance and isinstance(aigent_instance.aigent_state, dict):
        return json.dumps(aigent_instance.aigent_state, indent=2)
    return json.dumps({})

def get_formatted_chat_history_wrapper(user_instance, aigent_instance, limit=10):
    try:
        chat_history_obj = ChatHistory.objects.get(user=user_instance, aigent=aigent_instance)
        history_list = chat_history_obj.history if isinstance(chat_history_obj.history, list) else []
        history_list = history_list[-limit:]
        formatted_history = [f"{entry.get('role', 'unknown').capitalize()}: {entry.get('content', '')}" for entry in history_list]
        return "\n".join(formatted_history) if formatted_history else "No previous conversation history."
    except ChatHistory.DoesNotExist:
        return "No previous conversation history."
    except Exception as e:
        app_logger.error(f"Error formatting chat history for user {user_instance.id} and aigent {aigent_instance.id}: {str(e)}")
        return "Error retrieving conversation history."

def update_chat_history_wrapper(user, active_aigent, user_message_content, answer_to_user):
    history_obj, created = ChatHistory.objects.get_or_create(
        user=user, aigent=active_aigent, defaults={'history': []}
    )
    if not isinstance(history_obj.history, list):
        history_obj.history = []
    timestamp = datetime.utcnow().isoformat() + "Z"
    history_obj.history.append({"role": "user", "content": user_message_content, "timestamp": timestamp})
    history_obj.history.append({"role": "assistant", "content": answer_to_user, "timestamp": timestamp})
    MAX_HISTORY_ENTRIES = 50
    if len(history_obj.history) > MAX_HISTORY_ENTRIES * 2:
        history_obj.history = history_obj.history[-(MAX_HISTORY_ENTRIES*2):]
    history_obj.save()
    app_logger.info(f"Chat history updated for user {user.id} with aigent {active_aigent.id}")

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_user_message_to_aigent(self, user_id: int, user_message_content: str):
    """
    Celery task for processing user messages - mixed sync/async approach
    """
    task_id = self.request.id
    app_logger.info(f"Task {task_id} [process_user_message_to_aigent] started for user_id: {user_id}, message: '{user_message_content[:50]}...' (Attempt: {self.request.retries + 1})")
    
    try:
        # 1. Get required objects synchronously
        active_aigent, user, prompt_template_obj = get_required_objects_wrapper(user_id)
        app_logger.info(f"Task {task_id}: Found active Aigent: {active_aigent.name}, User: {user.username}, Prompt: {prompt_template_obj.name}")

        # 2. Prepare data synchronously
        user_state_str = serialize_user_state_wrapper(user)
        aigent_state_str = serialize_aigent_state_wrapper(active_aigent)
        formatted_chat_history_str = get_formatted_chat_history_wrapper(user, active_aigent)

        # 3. Build prompt synchronously (no DB access)
        prompt_placeholders = {
            "system_persona_prompt": active_aigent.system_persona_prompt,
            "user_state": user_state_str,
            "chat_history": formatted_chat_history_str,
            "current_user_message": user_message_content,
            "aigent_state": aigent_state_str,
        }
        full_prompt = prompt_template_obj.template_str.format(**prompt_placeholders)
        llm_logger.info(f"--- LLM PROMPT (Task: {task_id}, User: {user.id}, Aigent: {active_aigent.id}) ---\n{full_prompt}\n-------------------------")

        # 4. Validate Ollama configuration
        if not active_aigent.ollama_endpoints or not isinstance(active_aigent.ollama_endpoints, list) or not active_aigent.ollama_endpoints[0]:
            err_msg = f"Aigent '{active_aigent.name}' has no valid Ollama endpoints configured."
            app_logger.error(f"Task {task_id}: {err_msg}")
            raise ValueError(err_msg)
        
        ollama_api_url_base = active_aigent.ollama_endpoints[0]
        ollama_api_url_target = f"{ollama_api_url_base.rstrip('/')}/api/generate"

        # 5. Prepare payload
        payload = {"model": active_aigent.ollama_model_name, "prompt": full_prompt, "stream": False, "format": "json", "options": {}}
        if active_aigent.ollama_temperature is not None: 
            payload["options"]["temperature"] = active_aigent.ollama_temperature
        if active_aigent.ollama_context_length is not None: 
            payload["options"]["num_ctx"] = active_aigent.ollama_context_length
        if not payload["options"]: 
            del payload["options"]

        # 6. Make HTTP request asynchronously (this is the only async part)
        async def make_request_and_process():
            app_logger.info(f"Task {task_id}: Sending request to Ollama: {ollama_api_url_target} with model {payload['model']}")
            ollama_data = await make_ollama_request(ollama_api_url_target, payload, active_aigent.request_timeout_seconds)
            
            # Process response
            llm_json_output_str = ollama_data.get("response")
            if not llm_json_output_str:
                llm_logger.error(f"Task {task_id}: Ollama response missing 'response' field. Raw: {str(ollama_data)[:500]}")
                raise ValueError("Ollama response missing 'response' field.")
            
            llm_logger.info(f"--- LLM RAW JSON RESPONSE (Task: {task_id}) ---\n{llm_json_output_str}\n-------------------------")
            
            structured_llm_output = json.loads(llm_json_output_str)
            required_keys = ["answer_to_user", "updated_aigent_state", "updated_user_state"]
            if not all(key in structured_llm_output for key in required_keys):
                missing = [key for key in required_keys if key not in structured_llm_output]
                raise ValueError(f"Ollama JSON output missing keys: {missing}. Got: {list(structured_llm_output.keys())}")
            
            return structured_llm_output

        # Run the async part
        structured_llm_output = asyncio.run(make_request_and_process())
        
        # 7. Update chat history synchronously
        answer_to_user = structured_llm_output["answer_to_user"]
        update_chat_history_wrapper(user, active_aigent, user_message_content, answer_to_user)
        
        app_logger.info(f"Task {task_id} successful. Answer: '{str(answer_to_user)[:100]}...'")
        return {
            "answer_to_user": answer_to_user, 
            "updated_aigent_state_debug": structured_llm_output["updated_aigent_state"], 
            "updated_user_state_debug": structured_llm_output["updated_user_state"]
        }

    except (Aigent.DoesNotExist, User.DoesNotExist, Prompt.DoesNotExist) as e:
        err_msg = f"Task {task_id} ({type(e).__name__}): {str(e)}"
        app_logger.error(err_msg)
        raise Exception(err_msg)  # Fail, don't retry config errors
    
    except httpx.HTTPStatusError as e:
        err_msg = f"Ollama API request failed: {e.response.status_code} - {e.response.text[:200]}"
        app_logger.error(f"Task {task_id}: {err_msg}")
        if 500 <= e.response.status_code < 600:
            app_logger.info(f"Task {task_id}: Retrying (HTTPStatusError)...")
            raise self.retry(countdown=int(self.default_retry_delay * (self.request.retries + 1)), exc=e)
        raise Exception(err_msg)  # For non-retryable HTTP errors
    
    except httpx.RequestError as e:
        err_msg = f"Ollama request network error: {str(e)}"
        app_logger.error(f"Task {task_id}: {err_msg}")
        app_logger.info(f"Task {task_id}: Retrying (RequestError)...")
        raise self.retry(countdown=int(self.default_retry_delay * (self.request.retries + 1)), exc=e)
    
    except ValueError as e:  # JSON errors, config errors like missing endpoints
        err_msg = f"Task {task_id} (ValueError): {str(e)}"
        app_logger.error(err_msg)
        raise Exception(err_msg)  # Fail, don't retry
    
    except Exception as e:
        err_msg = f"Task {task_id} (Unexpected {type(e).__name__}): {str(e)}"
        app_logger.error(err_msg, exc_info=True)
        raise Exception(err_msg)

@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def ollama_ping_task(self):
    """
    Celery task for pinging Ollama - simple async HTTP request
    """
    task_id = self.request.id
    ping_url = "http://host.docker.internal:11434/"  # Adjust if your Ollama URL differs
    
    app_logger.info(f"Task {task_id} [ollama_ping_task] started (Attempt: {self.request.retries + 1}). Pinging {ping_url}")
    
    try:
        async def _ping():
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(ping_url)
                response.raise_for_status()
                return response
        
        response = asyncio.run(_ping())
        app_logger.info(f"Task {task_id}: Ollama ping successful! Status: {response.status_code}, Response: {response.text[:100]}")
        return {"status": "success", "ollama_response": response.text[:100]}
        
    except httpx.HTTPStatusError as e:
        err_msg = f"Ollama ping HTTP error: {e.response.status_code} - {e.response.text[:200]}"
        app_logger.error(f"Task {task_id}: {err_msg}")
        app_logger.info(f"Task {task_id}: Retrying ping (HTTPStatusError)...")
        raise self.retry(countdown=int(self.default_retry_delay * (self.request.retries + 1)), exc=e)
    except httpx.RequestError as e:
        err_msg = f"Ollama ping network error: {str(e)}"
        app_logger.error(f"Task {task_id}: {err_msg}")
        app_logger.info(f"Task {task_id}: Retrying ping (RequestError)...")
        raise self.retry(countdown=int(self.default_retry_delay * (self.request.retries + 1)), exc=e)
    except Exception as e:
        err_msg = f"Task {task_id} (Unexpected {type(e).__name__} during ping): {str(e)}"
        app_logger.error(err_msg, exc_info=True)
        raise Exception(err_msg)