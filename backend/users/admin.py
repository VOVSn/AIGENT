from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
import json
from .models import User

# To display the custom 'user_state' field in the admin.
class UserAdmin(BaseUserAdmin):
    # UPDATED: Replaced raw user_state with a pretty display
    
    # NEW: Added our custom method to readonly_fields
    readonly_fields = BaseUserAdmin.readonly_fields + ('user_state_display',)
    
    # UPDATED: Modified fieldsets to use the pretty display method
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('user_state_display',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        # Note: add_fieldsets still uses the raw field, which is fine for creation.
        # The pretty display is most useful on the change form.
        ('Custom Fields', {'fields': ('user_state',)}),
    )
    list_display = BaseUserAdmin.list_display + ('user_state_summary',)

    def user_state_summary(self, obj):
        if obj.user_state:
            return f"{len(obj.user_state)} keys" if isinstance(obj.user_state, dict) else "Populated"
        return "Empty"
    user_state_summary.short_description = 'User State'

    # NEW: Method to render the user_state JSON beautifully
    def user_state_display(self, obj):
        """Creates a pretty-printed, read-only view of the JSON state."""
        if obj.user_state:
            formatted_json = json.dumps(obj.user_state, indent=2)
            # Wrap in <pre> tags to preserve formatting
            return format_html("<pre>{}</pre>", formatted_json)
        return "State is empty."
    user_state_display.short_description = 'Formatted User State'


admin.site.register(User, UserAdmin)