from rest_framework import serializers
from .models import ChatHistory # We might use this later, or for history directly

class ChatMessageSendSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=4000, help_text="User's message content.")
    # No user_id here, as we'll get the user from request.user

class TaskStatusSerializer(serializers.Serializer):
    task_id = serializers.UUIDField(help_text="The ID of the Celery task.")
    status = serializers.CharField(help_text="Current status of the task (e.g., PENDING, STARTED, SUCCESS, FAILURE, RETRY).")
    result = serializers.JSONField(required=False, help_text="Result of the task if completed successfully (contains 'answer_to_user').")
    error_message = serializers.CharField(required=False, help_text="Error message if the task failed.")

class ChatHistoryMessageSerializer(serializers.Serializer):
    """Serializer for individual messages within the chat history."""
    role = serializers.CharField()
    content = serializers.CharField()
    timestamp = serializers.DateTimeField()

class UserChatHistorySerializer(serializers.Serializer):
    """Serializer for the entire chat history of a user with the active aigent."""
    history = ChatHistoryMessageSerializer(many=True, help_text="List of chat messages.")
    # You could add aigent_name or other context if needed
    # aigent_name = serializers.CharField(read_only=True)