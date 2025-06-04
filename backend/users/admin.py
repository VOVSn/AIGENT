from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

# To display the custom 'user_state' field in the admin.
class UserAdmin(BaseUserAdmin):
    # Add 'user_state' to fieldsets to make it editable
    # You might want to make it readonly or display it in a more user-friendly way
    # For JSONFields, direct editing in admin might be cumbersome for complex JSON.
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('user_state',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Custom Fields', {'fields': ('user_state',)}),
    )
    list_display = BaseUserAdmin.list_display + ('user_state_summary',) # Add a summary display

    def user_state_summary(self, obj):
        # Provide a brief summary or indicator of the user_state
        if obj.user_state:
            return f"{len(obj.user_state)} keys" if isinstance(obj.user_state, dict) else "Populated"
        return "Empty"
    user_state_summary.short_description = 'User State'


admin.site.register(User, UserAdmin)