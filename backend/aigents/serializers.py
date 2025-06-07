from rest_framework import serializers
from .models import Aigent, ChatHistory

# UPDATED: Serializer for listing available Aigents in the UI
class AigentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aigent
        fields = ['id', 'name', 'is_active', 'presentation_format']

# NEW: Serializer for the request to set the active Aigent
class SetActiveAigentSerializer(serializers.Serializer):
    aigent_id = serializers.IntegerField(required=True)

    def validate_aigent_id(self, value):
        if not Aigent.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Aigent with this ID does not exist.")
        return value

class ChatMessageSendSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=4000, help_text="User's message content.")

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