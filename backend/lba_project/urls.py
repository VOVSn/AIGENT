"""
URL configuration for lba_project project.
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
# Import the new views (adjust path if you put them in a different app's views.py)
from aigents.views import login_page_view, ChatPageView, root_view, PasswordChangePageView


urlpatterns = [
    # Frontend Serving URLs
    path('', root_view, name='root'), # Root redirects to login or chat
    path('login/', login_page_view, name='login_page'),
    path('chat/', ChatPageView.as_view(), name='chat_page'), # Use .as_view() for class-based views
    path('password-change/', PasswordChangePageView.as_view(), name='password_change_page'),

    path('admin/', admin.site.urls),

    # API v1 URLs
    path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/auth/', include('users.urls', namespace='users_api')),
    path('api/v1/', include('aigents.urls', namespace='aigents_api')),
]