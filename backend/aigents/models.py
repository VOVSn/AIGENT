from django.db import models
from django.conf import settings
import uuid

User = settings.AUTH_USER_MODEL

def get_default_aigent_state():
    """Returns the default JSON structure for a new aigent's state."""
    return {
        "internal_name": "AigentCore_v1",
        "current_goal": "Establish a helpful and productive relationship with the user.",
        "session_topics": [], # List of topics discussed in the current session
        "long_term_topics": [], # Topics discussed across all sessions
        "internal_thoughts": "A new session has started. I should be welcoming and ready to assist.",
        "emotional_state": {
            "curiosity": 0.6,
            "confidence": 0.7,
            "empathy": 0.5,
            "neutral_helpful": 0.8
        },
        "knowledge_gaps": [], # Things the aigent realizes it doesn't know
        "last_interaction_summary": None
    }


class Prompt(models.Model):
    # ... (no changes to Prompt model)
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
    # ADDED: Choices for the new field
    PRESENTATION_FORMAT_CHOICES = [
        ('markdown', 'Markdown'),
        ('html', 'HTML'),
        ('raw', 'Raw Text'),
    ]

    # ... (other fields are unchanged)
    name = models.CharField(max_length=255, unique=True, help_text="A unique name for this Aigent (e.g., 'LBA Support Aigent').")
    is_active = models.BooleanField(default=False, help_text="Designates whether this Aigent is the currently active one for general user interaction. Only one should be active at a time.")
    
    # ADDED: The new presentation_format field
    presentation_format = models.CharField(
        max_length=10,
        choices=PRESENTATION_FORMAT_CHOICES,
        default='markdown',
        help_text="The format for presenting the Aigent's responses in the UI (e.g., Markdown, HTML)."
    )
    
    system_persona_prompt = models.TextField(help_text="Brief description of the Aigent's role, personality, goals. This is a *part* of the full prompt.", blank=True)
    ollama_model_name = models.CharField(max_length=100, help_text="The Ollama model name to use (e.g., 'llama3:latest').")
    ollama_endpoints = models.JSONField(default=list, help_text="A list of Ollama API base URLs for this Aigent (e.g., ['http://10.0.0.2:11434']).")
    ollama_temperature = models.FloatField(null=True, blank=True, help_text="LLM temperature setting (optional). Controls randomness. Lower is more deterministic.")
    ollama_context_length = models.IntegerField(null=True, blank=True, help_text="Context window size if configurable for the LLM (optional).")
    
    aigent_state = models.JSONField(
        "Aigent Specific State",
        default=get_default_aigent_state, # Use the function to generate the default
        blank=True,
        help_text="Stores the Aigent's own persistent state, modifiable by itself."
    )

    default_prompt_template = models.ForeignKey(Prompt, on_delete=models.SET_NULL, null=True, blank=True, related_name='aigents', help_text="The primary prompt template this Aigent uses.")
    request_timeout_seconds = models.IntegerField(default=60, help_text="Timeout in seconds for requests to the Ollama server.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_active:
            Aigent.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class ChatHistory(models.Model):
    # ... (no changes to ChatHistory model)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_histories')
    aigent = models.ForeignKey(Aigent, on_delete=models.CASCADE, related_name='chat_histories')
    history = models.JSONField(default=list, help_text="Stores chat messages: [{'role': 'user/assistant', 'content': '...', 'timestamp': '...'}, ...]")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name_plural = "Chat Histories"
        unique_together = ('user', 'aigent')
    def __str__(self):
        return f"Chat history for {self.user.username} with {self.aigent.name}"
    def add_message(self, role: str, content: str, timestamp: str):
        if not isinstance(self.history, list): self.history = []
        self.history.append({"role": role, "content": content, "timestamp": timestamp})
        self.save()