"""
URL configuration for lba_project project.
"""
from django.contrib import admin
from django.urls import path, include # Add include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView, # Optional: if you want an endpoint to verify token validity
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # API v1 URLs
    path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Optional: Endpoint to verify a token.
    # path('api/v1/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # We will add other app-specific API URLs here later, e.g., for chat
    # path('api/v1/chat/', include('aigents.urls')), # Example for later
    # path('api/v1/users/', include('users.urls')), # Example for later (password change)
]