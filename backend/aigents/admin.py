from django.contrib import admin
from django.utils.html import format_html
import json
from .models import Prompt, Aigent, ChatHistory

@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name', 'template_str')

@admin.register(Aigent)
class AigentAdmin(admin.ModelAdmin):
    # UPDATED: Reorganized the admin view for better clarity
    list_display = ('name', 'is_active', 'presentation_format', 'ollama_model_name', 'default_prompt_template', 'created_at')
    list_filter = ('is_active', 'presentation_format', 'ollama_model_name')
    search_fields = ('name', 'system_persona_prompt')
    
    # NEW: Added readonly_fields for our pretty JSON display
    readonly_fields = ('aigent_state_display',)

    # NEW: Organized the fields into logical sections using fieldsets
    fieldsets = (
        ('Core Information', {
            'fields': ('name', 'is_active', 'presentation_format')
        }),
        ('Persona & Prompting', {
            'fields': ('system_persona_prompt', 'default_prompt_template')
        }),
        ('Ollama Configuration', {
            'fields': (
                'ollama_model_name', 
                'ollama_endpoints', 
                'ollama_temperature', 
                'ollama_context_length', 
                'request_timeout_seconds'
            )
        }),
        ('Aigent State', {
            'classes': ('collapse',), # Make this section collapsible
            'fields': ('aigent_state_display',), # Use our new pretty display field
        }),
    )

    # NEW: Method to render the aigent_state JSON beautifully
    def aigent_state_display(self, obj):
        """Creates a pretty-printed, read-only view of the JSON state."""
        if obj.aigent_state:
            formatted_json = json.dumps(obj.aigent_state, indent=2)
            # Wrap in <pre> tags to preserve formatting
            return format_html("<pre>{}</pre>", formatted_json)
        return "State is empty."
    aigent_state_display.short_description = 'Formatted Aigent State'


@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'aigent', 'message_count', 'updated_at')
    list_filter = ('aigent', 'user') 
    search_fields = ('user__username', 'aigent__name')
    readonly_fields = ('history_display',) 

    def message_count(self, obj):
        if isinstance(obj.history, list):
            return len(obj.history)
        return 0
    message_count.short_description = 'Messages'

    def history_display(self, obj):
        if obj.history:
            formatted_json = json.dumps(obj.history, indent=2)
            return format_html("<pre>{}</pre>", formatted_json)
        return "No history."
    history_display.short_description = 'Formatted Chat History'