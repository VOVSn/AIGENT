# backend/users/admin.py

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
import json
from .models import User, get_default_user_state # <-- IMPORT the default state function

# To display the custom 'user_state' field in the admin.
class UserAdmin(BaseUserAdmin):
    
    # --- NEW: Define the custom admin action ---
    actions = ['reset_user_state']

    # --- UPDATED: Show both the editable field and the pretty display ---
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('user_state', 'user_state_display', 'timezone')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Custom Fields', {'fields': ('user_state', 'timezone')}),
    )

    # --- UPDATED: Make the pretty display a readonly field ---
    readonly_fields = BaseUserAdmin.readonly_fields + ('user_state_display',)
    
    list_display = BaseUserAdmin.list_display + ('user_state_summary',)

    def user_state_summary(self, obj):
        # Your existing summary function is great, no changes needed.
        if isinstance(obj.user_state, dict) and obj.user_state:
            default_state = get_default_user_state()
            if obj.user_state == default_state:
                return "Default"
            return f"Custom ({len(obj.user_state['calendar_events'])} events)"
        return "Empty"
    user_state_summary.short_description = 'User State'

    def user_state_display(self, obj):
        """Creates a pretty-printed, read-only view of the JSON state."""
        if obj.user_state:
            formatted_json = json.dumps(obj.user_state, indent=2)
            return format_html("<pre>{}</pre>", formatted_json)
        return "State is empty."
    user_state_display.short_description = 'Formatted User State (Read-Only)'

    # --- NEW: The action method itself ---
    @admin.action(description="Reset selected users' state to default")
    def reset_user_state(self, request, queryset):
        """
        This action resets the user_state JSONField to its default value.
        """
        default_state = get_default_user_state()
        
        # Use update() for efficiency on a large number of objects
        rows_updated = queryset.update(user_state=default_state)
        
        # Send a success message to the admin user
        self.message_user(request, f"{rows_updated} user(s) had their state successfully reset to default.", messages.SUCCESS)


# Unregister the default UserAdmin if it was registered, then register our custom one
# This avoids potential conflicts. It's good practice but often not strictly necessary.
# from django.contrib.auth.models import User as AuthUser
# if admin.site.is_registered(AuthUser):
#     admin.site.unregister(AuthUser)

admin.site.register(User, UserAdmin)