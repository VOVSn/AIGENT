from django.db import models
from django.conf import settings # To get AUTH_USER_MODEL
import uuid # For task_id, though not directly in these models, good to keep in mind for related logic

# It's good practice to get the User model using settings.AUTH_USER_MODEL
# especially in reusable apps, though here it's for our project's User model.
User = settings.AUTH_USER_MODEL

class Prompt(models.Model):
    """
    Stores prompt templates that Aigents can use.
    """
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="A unique name for this prompt template (e.g., 'StandardChatInteraction')."
    )
    template_str = models.TextField(
        help_text="The full prompt string with placeholders like {system_persona_prompt}, {user_state}, etc."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Aigent(models.Model):
    """
    Represents an AI agent configuration.
    """
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="A unique name for this Aigent (e.g., 'LBA Support Aigent')."
    )
    is_active = models.BooleanField(
        default=False,
        help_text="Designates whether this Aigent is the currently active one for general user interaction. Only one should be active at a time."
    )
    system_persona_prompt = models.TextField(
        help_text="Brief description of the Aigent's role, personality, goals. This is a *part* of the full prompt.",
        blank=True # Can be empty if the full persona is in the main template
    )
    ollama_model_name = models.CharField(
        max_length=100,
        help_text="The Ollama model name to use (e.g., 'llama3:latest')."
    )
    ollama_endpoints = models.JSONField(
        default=list,
        help_text="A list of Ollama API base URLs for this Aigent (e.g., ['http://10.0.0.2:11434'])."
    )
    ollama_temperature = models.FloatField(
        null=True,
        blank=True,
        help_text="LLM temperature setting (optional). Controls randomness. Lower is more deterministic."
    )
    ollama_context_length = models.IntegerField(
        null=True,
        blank=True,
        help_text="Context window size if configurable for the LLM (optional)."
    )
    aigent_state = models.JSONField(
        "Aigent Specific State",
        default=dict,
        blank=True,
        help_text="Stores the Aigent's own persistent state, modifiable by itself."
    )
    default_prompt_template = models.ForeignKey(
        Prompt,
        on_delete=models.SET_NULL, # Or models.PROTECT if a prompt should not be deleted if in use
        null=True,
        blank=True, # An Aigent might not have one initially, or it could be hardcoded/dynamic
        related_name='aigents',
        help_text="The primary prompt template this Aigent uses."
    )
    request_timeout_seconds = models.IntegerField(
        default=60,
        help_text="Timeout in seconds for requests to the Ollama server."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    # Optional: Add a clean method to ensure only one Aigent is active
    def save(self, *args, **kwargs):
        if self.is_active:
            # Set all other Aigents to inactive
            Aigent.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

class ChatHistory(models.Model):
    """
    Stores the chat history for a user with a specific Aigent.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE, # If user is deleted, their chat history is also deleted
        related_name='chat_histories'
    )
    aigent = models.ForeignKey(
        Aigent,
        on_delete=models.CASCADE, # If Aigent is deleted, associated history is also deleted
        related_name='chat_histories'
    )
    history = models.JSONField(
        default=list,
        help_text="Stores chat messages: [{'role': 'user/assistant', 'content': '...', 'timestamp': '...'}, ...]"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Chat Histories" # For Django Admin display
        unique_together = ('user', 'aigent')   # A user should have one history record per aigent

    def __str__(self):
        return f"Chat history for {self.user.username} with {self.aigent.name}"

    def add_message(self, role: str, content: str, timestamp: str):
        """Helper method to add a message to the history."""
        if not isinstance(self.history, list):
            self.history = [] # Ensure history is a list
        self.history.append({"role": role, "content": content, "timestamp": timestamp})
        self.save()