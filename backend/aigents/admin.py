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
    # Controls the columns displayed in the main Aigent list
    list_display = ('name', 'is_active', 'presentation_format', 'ollama_model_name')
    
    # Adds a filter sidebar
    list_filter = ('is_active', 'presentation_format', 'created_at')
    
    # Adds a search bar
    search_fields = ('name', 'system_persona_prompt')
    
    # This is the key change: It creates a user-friendly dual-listbox
    # widget for selecting tools, which is much better than the default.
    filter_horizontal = ('tools',)
    
    # Organizes the fields on the Aigent edit/add page into logical groups
    fieldsets = (
        ('Core Configuration', {
            'fields': ('name', 'is_active', 'system_persona_prompt')
        }),
        ('Presentation & Prompting', {
            'fields': ('presentation_format', 'default_prompt_template')
        }),
        # The 'Capabilities' section now neatly contains our tool selector
        ('Capabilities (Tools)', {
            'fields': ('tools',)
        }),
        ('LLM Parameters', {
            'classes': ('collapse',), # This section will be collapsible
            'fields': ('ollama_model_name', 'ollama_endpoints', 'ollama_temperature', 'ollama_context_length', 'request_timeout_seconds')
        }),
        ('Internal State (Advanced)', {
            'classes': ('collapse',),
            'fields': ('aigent_state',)
        }),
    )


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