#test_script.py
# Django Shell Script for Testing Fixed Celery Tasks
# Run this in Django shell: python manage.py shell

import time
import json
from aigents.tasks import process_user_message_to_aigent, ollama_ping_task
from aigents.models import Aigent, ChatHistory
from django.contrib.auth import get_user_model
from celery.result import AsyncResult

User = get_user_model()

# --- Configuration ---
TEST_USER_ID = 1  # !!! IMPORTANT: Change this to an existing user ID !!!
CONVERSATION_MESSAGES = [
    "Hello LBA-Prime, what's the weather like today?",
    "Interesting. Can you also tell me a fun fact about Large Language Models?",
    "Thanks! That's all for now.",
    "Can you help me with a Python coding question?",
    "What's the difference between async and sync programming?"
]
MESSAGE_DELAY_SECONDS = 3  # Delay between sending messages
WAIT_FOR_RESULT_TIMEOUT = 180  # Seconds to wait for each task result

# --- Helper Functions ---
def print_separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_task_status(async_result, start_time=None):
    state = async_result.state
    print(f"  Task ID: {async_result.id}")
    print(f"  State: {state}")
    if start_time:
        duration = time.time() - start_time
        print(f"  Duration: {duration:.2f} seconds")
    
    if state == 'SUCCESS':
        result = async_result.result
        print(f"  SUCCESS - Answer: {result.get('answer_to_user', 'N/A')[:100]}...")
        if result.get('updated_aigent_state_debug'):
            print(f"  Aigent State Update: {result['updated_aigent_state_debug']}")
        if result.get('updated_user_state_debug'):
            print(f"  User State Update: {result['updated_user_state_debug']}")
    elif state == 'FAILURE':
        print(f"  FAILURE - Error: {async_result.info}")
        traceback_info = async_result.traceback
        if isinstance(traceback_info, str) and traceback_info.strip():
            print(f"  Traceback (last 500 chars): ...{traceback_info[-500:]}")
    elif state == 'RETRY':
        print(f"  RETRY - Info: {async_result.info}")
    elif state == 'PENDING':
        print(f"  PENDING - Task is queued or running...")
    else:
        print(f"  UNKNOWN STATE: {state}")

def wait_for_task_completion(async_result, timeout=180):
    """Wait for task completion with periodic status updates"""
    start_time = time.time()
    last_state = None
    
    while time.time() - start_time < timeout:
        current_state = async_result.state
        
        # Print status update if state changed or every 10 seconds
        if current_state != last_state or (time.time() - start_time) % 10 < 1:
            elapsed = time.time() - start_time
            print(f"    [{elapsed:.1f}s] State: {current_state}")
            last_state = current_state
        
        if current_state in ['SUCCESS', 'FAILURE']:
            break
            
        time.sleep(1)
    
    return async_result.state

def display_chat_history(user_instance, aigent_instance, limit=20):
    """Display recent chat history"""
    try:
        chat_history_obj = ChatHistory.objects.get(user=user_instance, aigent=aigent_instance)
        if chat_history_obj.history and isinstance(chat_history_obj.history, list):
            recent_history = chat_history_obj.history[-limit:]
            print(f"  Recent Chat History ({len(recent_history)} messages):")
            for i, entry in enumerate(recent_history, 1):
                role = entry.get("role", "System").capitalize()
                content = entry.get("content", "")[:100]
                timestamp = entry.get("timestamp", "")
                print(f"    {i:2d}. [{timestamp}] {role}: {content}...")
        else:
            print("  No chat history found or history is empty.")
    except ChatHistory.DoesNotExist:
        print("  No ChatHistory object found for this user and aigent.")
    except Exception as e:
        print(f"  Error fetching chat history: {type(e).__name__} - {e}")

# --- Main Test Script ---
def run_celery_test():
    print_separator("Starting Enhanced Celery Task Test")
    
    # Step 1: Validate setup
    print("\n[STEP 1] Validating Setup...")
    
    try:
        test_user = User.objects.get(id=TEST_USER_ID)
        print(f"✓ Test User Found: {test_user.username} (ID: {test_user.id})")
    except User.DoesNotExist:
        print(f"✗ ERROR: User with ID {TEST_USER_ID} not found!")
        print("Please update TEST_USER_ID with a valid user ID.")
        return False
    
    try:
        active_aigent = Aigent.objects.get(is_active=True)
        print(f"✓ Active Aigent Found: {active_aigent.name} (ID: {active_aigent.id})")
        
        # Check if aigent has required configurations
        if not active_aigent.ollama_endpoints:
            print("⚠ WARNING: Aigent has no Ollama endpoints configured!")
        if not active_aigent.default_prompt_template:
            print("⚠ WARNING: Aigent has no default prompt template!")
            
    except Aigent.DoesNotExist:
        print("✗ ERROR: No active Aigent found!")
        return False
    except Aigent.MultipleObjectsReturned:
        print("✗ ERROR: Multiple active Aigents found!")
        return False
    
    # Step 2: Test Ollama connectivity
    print_separator("Testing Ollama Connectivity")
    
    print("Sending ping to Ollama...")
    ping_result = ollama_ping_task.delay()
    print(f"Ping task submitted: {ping_result.id}")
    
    ping_state = wait_for_task_completion(ping_result, timeout=30)
    print_task_status(ping_result)
    
    if ping_state != 'SUCCESS':
        print("⚠ WARNING: Ollama ping failed. Tasks may fail.")
    else:
        print("✓ Ollama connectivity confirmed!")
    
    # Step 3: Process conversation messages
    print_separator("Processing Conversation Messages")
    
    task_results = []
    successful_tasks = 0
    
    for i, message in enumerate(CONVERSATION_MESSAGES, 1):
        print(f"\n[Message {i}/{len(CONVERSATION_MESSAGES)}]")
        print(f"Sending: '{message}'")
        
        # Submit task
        start_time = time.time()
        async_result = process_user_message_to_aigent.delay(
            user_id=test_user.id,
            user_message_content=message
        )
        task_results.append(async_result)
        
        print(f"Task submitted: {async_result.id}")
        
        # Wait for completion
        final_state = wait_for_task_completion(async_result, WAIT_FOR_RESULT_TIMEOUT)
        print_task_status(async_result, start_time)
        
        if final_state == 'SUCCESS':
            successful_tasks += 1
            print("✓ Task completed successfully!")
        else:
            print("✗ Task failed!")
        
        # Delay before next message (except for last message)
        if i < len(CONVERSATION_MESSAGES) and MESSAGE_DELAY_SECONDS > 0:
            print(f"Waiting {MESSAGE_DELAY_SECONDS} seconds before next message...")
            time.sleep(MESSAGE_DELAY_SECONDS)
    
    # Step 4: Summary and results
    print_separator("Test Results Summary")
    
    print(f"Total Messages Sent: {len(CONVERSATION_MESSAGES)}")
    print(f"Successful Tasks: {successful_tasks}")
    print(f"Failed Tasks: {len(CONVERSATION_MESSAGES) - successful_tasks}")
    print(f"Success Rate: {(successful_tasks/len(CONVERSATION_MESSAGES)*100):.1f}%")
    
    if successful_tasks == len(CONVERSATION_MESSAGES):
        print("🎉 ALL TASKS COMPLETED SUCCESSFULLY!")
    else:
        print("⚠ Some tasks failed. Check the logs above for details.")
    
    # Step 5: Display chat history
    print_separator("Final Chat History")
    display_chat_history(test_user, active_aigent)
    
    # Step 6: Task details for debugging
    print_separator("Detailed Task Information")
    
    for i, result in enumerate(task_results, 1):
        print(f"\n[Task {i} Details]")
        print_task_status(result)
    
    print_separator("Test Completed")
    return successful_tasks == len(CONVERSATION_MESSAGES)

# --- Quick Test Function ---
def quick_test():
    """Quick single message test"""
    print("=== QUICK TEST ===")
    
    try:
        user = User.objects.get(id=TEST_USER_ID)
        print(f"Testing with user: {user.username}")
        
        test_message = "Hello, this is a quick test message!"
        print(f"Sending: {test_message}")
        
        result = process_user_message_to_aigent.delay(user.id, test_message)
        print(f"Task ID: {result.id}")
        
        # Wait up to 60 seconds
        try:
            response = result.get(timeout=60)
            print("✓ SUCCESS!")
            print(f"Response: {response.get('answer_to_user', 'N/A')}")
            return True
        except Exception as e:
            print(f"✗ FAILED: {e}")
            return False
            
    except User.DoesNotExist:
        print(f"✗ User {TEST_USER_ID} not found!")
        return False

# --- Usage Instructions ---
def show_usage():
    print("""
=== USAGE INSTRUCTIONS ===

1. Run full test suite:
   >>> run_celery_test()

2. Run quick single message test:
   >>> quick_test()

3. Check specific task result:
   >>> from celery.result import AsyncResult
   >>> result = AsyncResult('your-task-id-here')
   >>> print(result.state)
   >>> print(result.result)

4. Monitor Celery worker logs:
   - Check your Docker logs or worker terminal

5. Update configuration:
   - Change TEST_USER_ID to match your setup
   - Adjust CONVERSATION_MESSAGES as needed
   - Modify timeouts if needed

=== READY TO TEST ===
Run: run_celery_test()
""")

# Show usage when script is loaded
show_usage()