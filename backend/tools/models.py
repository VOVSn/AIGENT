# backend/tools/models.py
from django.db import models

class Tool(models.Model):
    """
    Represents a capability or action that an Aigent can choose to use.
    The 'name' must correspond to a module in the 'tools.tool_library' package.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="The unique identifier for the tool (e.g., 'web_search'). Must match the tool's implementation filename in the tool_library."
    )
    description = models.TextField(
        help_text="A detailed description for the LLM to understand what the tool does, its purpose, and when to use it."
    )
    parameters_schema = models.JSONField(
        default=dict,
        blank=True,
        help_text="A JSON schema describing the parameters the tool's run() function expects. E.g., {'query': 'string'}"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']