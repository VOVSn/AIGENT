"""
URL configuration for lba_project project.
"""
from django.contrib import admin
from django.urls import path, include # Ensure include is imported
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    # TokenVerifyView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # API v1 Auth specific URLs from simplejwt
    path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # path('api/v1/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # Include URLs from the 'users' app under an 'auth' prefix or similar
    path('api/v1/auth/', include('users.urls', namespace='users_api')), # Added this line

    # We will add other app-specific API URLs here later, e.g., for chat
    # path('api/v1/chat/', include('aigents.urls')),
]