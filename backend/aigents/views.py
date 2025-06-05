from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from celery.result import AsyncResult # To check task status

from .models import Aigent, ChatHistory
from .serializers import (
    ChatMessageSendSerializer, 
    TaskStatusSerializer,
    UserChatHistorySerializer
)
from .tasks import process_user_message_to_aigent # Your Celery task

import logging
logger = logging.getLogger('aigents') # Or your specific app logger

class SendMessageView(generics.GenericAPIView):
    """
    API endpoint to send a message from the user to the active Aigent.
    Triggers a Celery task for processing.
    """
    serializer_class = ChatMessageSendSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        message_content = serializer.validated_data['message']

        logger.info(f"User {user.username} (ID: {user.id}) sending message: '{message_content[:50]}...'")

        # Check for active Aigent (though task does this, good to check early)
        try:
            active_aigent = Aigent.objects.get(is_active=True)
            logger.info(f"Dispatching message to active Aigent: {active_aigent.name}")
        except Aigent.DoesNotExist:
            logger.error(f"SendMessageView: No active Aigent found for user {user.username}.")
            return Response(
                {"error": "No active Aigent configured in the system."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Aigent.MultipleObjectsReturned:
            logger.error(f"SendMessageView: Multiple active Aigents found for user {user.username}. This should not happen.")
            return Response(
                {"error": "System configuration error: Multiple active Aigents."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Dispatch the Celery task
        task = process_user_message_to_aigent.delay(user.id, message_content)
        
        logger.info(f"Celery task {task.id} dispatched for user {user.username}.")

        return Response(
            {"task_id": task.id, "detail": "Message received and processing started."},
            status=status.HTTP_202_ACCEPTED # Indicates asynchronous processing
        )

class TaskStatusView(APIView):
    """
    API endpoint to check the status and result of a Celery task.
    """
    permission_classes = [permissions.IsAuthenticated] # Ensure user is logged in

    def get(self, request, task_id, *args, **kwargs):
        logger.debug(f"User {request.user.username} checking status for task_id: {task_id}")
        try:
            # Validate task_id format if necessary, e.g. using UUID
            # task_uuid = uuid.UUID(task_id) # This would raise ValueError if not a valid UUID
            pass 
        except ValueError:
            return Response({"error": "Invalid task_id format."}, status=status.HTTP_400_BAD_REQUEST)

        async_result = AsyncResult(str(task_id)) # Ensure task_id is a string

        response_data = {
            "task_id": async_result.id,
            "status": async_result.status,
        }

        if async_result.successful():
            # The Celery task returns a dict: {"answer_to_user": ..., "updated_aigent_state_debug": ..., ...}
            # We only need to send 'answer_to_user' to the frontend for the chat UI.
            task_result_data = async_result.result
            if isinstance(task_result_data, dict) and "answer_to_user" in task_result_data:
                response_data["result"] = {"answer_to_user": task_result_data["answer_to_user"]}
            else:
                # Handle case where result might not be the expected dict (e.g. if task failed unexpectedly before returning dict)
                response_data["result"] = task_result_data # Send raw result if not expected dict
                logger.warning(f"Task {task_id} succeeded but result format unexpected: {task_result_data}")
        elif async_result.failed():
            # .info often holds the exception object or its string representation
            error_info = async_result.info 
            response_data["error_message"] = str(error_info) if error_info else "Task failed with an unknown error."
            logger.error(f"Task {task_id} failed. Info: {error_info}. Traceback: {async_result.traceback}")
        elif async_result.status == 'RETRY':
             response_data["error_message"] = f"Task is being retried. Info: {str(async_result.info)}"


        # Serialize the response_data using TaskStatusSerializer for consistency and validation
        serializer = TaskStatusSerializer(data=response_data)
        if serializer.is_valid():
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            # This case should ideally not happen if response_data is constructed correctly
            logger.error(f"TaskStatusView: Failed to serialize response for task {task_id}. Errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatHistoryView(generics.GenericAPIView):
    """
    API endpoint to retrieve the user's chat history with the active Aigent.
    """
    serializer_class = UserChatHistorySerializer # For response
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        logger.info(f"Fetching chat history for user {user.username} (ID: {user.id}).")

        try:
            active_aigent = Aigent.objects.get(is_active=True)
        except Aigent.DoesNotExist:
            logger.warning(f"ChatHistoryView: No active Aigent found for user {user.username}.")
            return Response({"history": [], "detail": "No active Aigent configured."}, status=status.HTTP_200_OK) # Or 404/503
        except Aigent.MultipleObjectsReturned:
            logger.error(f"ChatHistoryView: Multiple active Aigents found. System misconfiguration.")
            return Response({"error": "System configuration error: Multiple active Aigents."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            chat_history_obj = ChatHistory.objects.get(user=user, aigent=active_aigent)
            # The 'history' field in ChatHistory model is already a list of dicts
            # matching ChatHistoryMessageSerializer structure.
            history_data = chat_history_obj.history if isinstance(chat_history_obj.history, list) else []
        except ChatHistory.DoesNotExist:
            logger.info(f"No chat history found for user {user.username} with aigent {active_aigent.name}.")
            history_data = []
        
        serializer = self.get_serializer({"history": history_data})
        return Response(serializer.data, status=status.HTTP_200_OK)
    

def login_page_view(request):
    """Serves the login.html page."""
    # If user is already authenticated, maybe redirect to chat? (Optional)
    # if request.user.is_authenticated:
    #     from django.shortcuts import redirect
    #     return redirect('chat_page') # Assuming 'chat_page' is the name of the chat URL
    return render(request, 'login.html')

class ChatPageView(LoginRequiredMixin, TemplateView):
    """Serves the chat.html page. Requires login."""
    template_name = 'chat.html'
    login_url = '/login/' # Redirect here if not authenticated (matches URL name below)
    # redirect_field_name = 'next' # Default

    # You can pass additional context to the template if needed
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     context['username'] = self.request.user.username
    #     return context

# For simplicity, let's have a root view that redirects to login or chat
from django.shortcuts import redirect
def root_view(request):
    if request.user.is_authenticated:
        return redirect('chat_page') # Name of the chat page URL pattern
    return redirect('login_page')   # Name of the login page URL pattern