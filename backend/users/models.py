from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

def get_default_user_state():
    """Returns the default JSON structure for a new user's state."""
    return {
        "alias": "",
        "preferences": {
            "communication_style": "neutral"
        },
        # "calendar_events": [], # <-- REMOVED. This is now a dedicated model.
        "tasks": [],
    }

class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Adds a user_state JSONField for storing Aigent-modifiable user-specific state.
    """
    user_state = models.JSONField(
        "User Specific State",
        default=get_default_user_state,
        blank=True,
        help_text="Stores user-specific persistent state across sessions, modifiable by Aigents."
    )
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        help_text="The user's IANA timezone name (e.g., 'America/New_York')."
    )

    def __str__(self):
        return self.username

# --- NEW MODEL ---
class CalendarEvent(models.Model):
    """
    Represents a single calendar event for a user.
    All datetimes are stored in UTC.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendar_events')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField(help_text="The start time of the event in UTC.")
    end_time = models.DateTimeField(help_text="The end time of the event in UTC.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"'{self.title}' for {self.user.username} at {self.start_time}"