from django.contrib.auth.models import AbstractUser
from django.db import models

def get_default_user_state():
    """Returns the default JSON structure for a new user's state."""
    return {
        "alias": "",  # The Aigent can ask for and set this preferred name.
        "preferences": {
            "communication_style": "neutral" # e.g., 'formal', 'casual'
        },
        "calendar_events": [
            # Example:
            # {
            #   "event_id": "uuid-here",
            #   "title": "Project Alpha Deadline",
            #   "start_time_utc": "2024-10-26T14:00:00Z",
            #   "end_time_utc": "2024-10-26T15:00:00Z",
            #   "description": "Final report submission for Project Alpha."
            # }
        ],
        "tasks": [], # User-specific tasks assigned by the Aigent
    }

class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Adds a user_state JSONField for storing Aigent-modifiable user-specific state.
    """
    user_state = models.JSONField(
        "User Specific State",
        default=get_default_user_state, # Use the function to generate the default
        blank=True,
        help_text="Stores user-specific persistent state across sessions, modifiable by Aigents."
    )
    # --- NEW FIELD ---
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        help_text="The user's IANA timezone name (e.g., 'America/New_York')."
    )

    def __str__(self):
        return self.username