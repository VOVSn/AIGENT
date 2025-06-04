from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Adds a user_state JSONField for storing Aigent-modifiable user-specific state.
    """
    user_state = models.JSONField(
        "User Specific State",
        default=dict,
        blank=True,
        help_text="Stores user-specific persistent state across sessions, modifiable by Aigents."
    )

    # Add any other custom fields for your User model here if needed in the future.
    # For example:
    # profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    # department = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.username