from django.contrib import admin
from .models import Prompt, Aigent, ChatHistory

@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name', 'template_str')

@admin.register(Aigent)
class AigentAdmin(admin.ModelAdmin):
    # UPDATED list_display and list_filter
    list_display = ('name', 'is_active', 'presentation_format', 'ollama_model_name', 'default_prompt_template', 'created_at')
    list_filter = ('is_active', 'presentation_format', 'ollama_model_name')
    search_fields = ('name', 'system_persona_prompt')
    # For JSONFields like ollama_endpoints and aigent_state,
    # direct editing in admin can be clunky. Consider custom widgets or readonly display
    # if they become very complex.
    # Example:
    # readonly_fields = ('aigent_state',) # If you want to prevent direct admin edit


@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'aigent', 'message_count', 'updated_at')
    list_filter = ('aigent', 'user') # Make sure user filter is usable if many users
    search_fields = ('user__username', 'aigent__name')
    readonly_fields = ('history_display',) # Display history nicely

    def message_count(self, obj):
        if isinstance(obj.history, list):
            return len(obj.history)
        return 0
    message_count.short_description = 'Messages'

    def history_display(self, obj):
        # A more readable display for the JSON history in admin
        from django.utils.html import format_html
        import json
        if obj.history:
            # Pretty print the JSON
            formatted_json = json.dumps(obj.history, indent=2)
            return format_html("<pre>{}</pre>", formatted_json)
        return "No history."
    history_display.short_description = 'Formatted Chat History'

    # To make 'history' field non-editable directly if it's complex or managed by code
    # You could exclude 'history' from fields or add it to readonly_fields
    # fields = ('user', 'aigent', 'history_display', 'created_at', 'updated_at') # if hiding direct history edit