from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from celery.result import AsyncResult

from .models import Aigent, ChatHistory
from .serializers import (
    ChatMessageSendSerializer, 
    TaskStatusSerializer,
    UserChatHistorySerializer,
    AigentListSerializer,
    SetActiveAigentSerializer
)
from .tasks import process_user_message_to_aigent

import logging
logger = logging.getLogger('aigents')

class AigentListView(generics.ListAPIView):
    """
    API endpoint to list all available Aigents.
    Includes an 'is_active' flag for the current user's session.
    """
    queryset = Aigent.objects.all().order_by('name')
    serializer_class = AigentListSerializer
    permission_classes = [permissions.IsAuthenticated]

class SetActiveAigentView(generics.GenericAPIView):
    """
    API endpoint to set the active Aigent for the user.
    This effectively changes the user's conversation context.
    """
    serializer_class = SetActiveAigentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        aigent_id = serializer.validated_data['aigent_id']

        try:
            # The Aigent model's .save() method automatically handles
            # deactivating any other active Aigents.
            aigent_to_activate = Aigent.objects.get(pk=aigent_id)
            aigent_to_activate.is_active = True
            aigent_to_activate.save()
            
            logger.info(f"User {request.user.username} switched active aigent to: {aigent_to_activate.name}")
            return Response(
                {"detail": f"Active aigent switched to {aigent_to_activate.name}."},
                status=status.HTTP_200_OK
            )
        except Aigent.DoesNotExist:
            return Response({"error": "Aigent not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error switching active aigent for user {request.user.username}: {e}")
            return Response({"error": "An error occurred while switching aigents."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            logger.error(f"SendMessageView: Multiple active Aigents found. This should not happen.")
            return Response(
                {"error": "System configuration error: Multiple active Aigents."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        task = process_user_message_to_aigent.delay(user.id, message_content)
        logger.info(f"Celery task {task.id} dispatched for user {user.username}.")

        return Response(
            {"task_id": task.id, "detail": "Message received and processing started."},
            status=status.HTTP_202_ACCEPTED
        )

class TaskStatusView(APIView):
    """
    API endpoint to check the status and result of a Celery task.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, task_id, *args, **kwargs):
        logger.debug(f"User {request.user.username} checking status for task_id: {task_id}")
        async_result = AsyncResult(str(task_id))
        response_data = {
            "task_id": async_result.id,
            "status": async_result.status,
        }

        if async_result.successful():
            task_result_data = async_result.result
            if isinstance(task_result_data, dict) and "answer_to_user" in task_result_data:
                response_data["result"] = {"answer_to_user": task_result_data["answer_to_user"]}
            else:
                response_data["result"] = task_result_data
                logger.warning(f"Task {task_id} succeeded but result format unexpected: {task_result_data}")
        elif async_result.failed():
            error_info = async_result.info 
            response_data["error_message"] = str(error_info) if error_info else "Task failed with an unknown error."
            logger.error(f"Task {task_id} failed. Info: {error_info}. Traceback: {async_result.traceback}")
        elif async_result.status == 'RETRY':
             response_data["error_message"] = f"Task is being retried. Info: {str(async_result.info)}"

        serializer = TaskStatusSerializer(data=response_data)
        if serializer.is_valid():
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            logger.error(f"TaskStatusView: Failed to serialize response for task {task_id}. Errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatHistoryView(generics.GenericAPIView):
    """
    API endpoint to retrieve (GET) or delete (DELETE) the user's chat history 
    with the active Aigent.
    """
    serializer_class = UserChatHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        logger.info(f"Fetching chat history for user {user.username} (ID: {user.id}).")

        try:
            active_aigent = Aigent.objects.get(is_active=True)
        except (Aigent.DoesNotExist, Aigent.MultipleObjectsReturned):
            logger.warning(f"ChatHistoryView: No active Aigent found for user {user.username}.")
            return Response({"history": [], "detail": "No active Aigent configured."}, status=status.HTTP_200_OK)

        try:
            chat_history_obj = ChatHistory.objects.get(user=user, aigent=active_aigent)
            history_data = chat_history_obj.history if isinstance(chat_history_obj.history, list) else []
        except ChatHistory.DoesNotExist:
            logger.info(f"No chat history found for user {user.username} with aigent {active_aigent.name}.")
            history_data = []
        
        serializer = self.get_serializer({"history": history_data})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        """
        Deletes the chat history for the authenticated user with the active aigent.
        """
        user = request.user
        logger.info(f"Attempting to delete chat history for user {user.username} (ID: {user.id}).")

        try:
            active_aigent = Aigent.objects.get(is_active=True)
        except (Aigent.DoesNotExist, Aigent.MultipleObjectsReturned):
            logger.error(f"Cannot delete history: Active Aigent configuration is invalid for user {user.username}.")
            return Response(
                {"error": "System configuration error preventing history deletion."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        deleted_count, _ = ChatHistory.objects.filter(user=user, aigent=active_aigent).delete()
        
        if deleted_count > 0:
            logger.info(f"Successfully deleted chat history for user {user.username} with aigent {active_aigent.name}.")
        else:
            logger.info(f"No chat history found to delete for user {user.username} with aigent {active_aigent.name}.")

        return Response(status=status.HTTP_204_NO_CONTENT)

# --- Template Views ---

def login_page_view(request):
    """Serves the login.html page."""
    return render(request, 'login.html')

class ChatPageView(LoginRequiredMixin, TemplateView):
    """Serves the chat.html page. Requires login."""
    template_name = 'chat.html'
    login_url = '/login/'

def root_view(request):
    """Redirects to the chat page if logged in, otherwise to the login page."""
    if request.user.is_authenticated:
        return redirect('chat_page')
    return redirect('login_page')

class PasswordChangePageView(LoginRequiredMixin, TemplateView):
    """Serves the password_change.html page. Requires login."""
    template_name = 'password_change.html'
    login_url = '/login/'