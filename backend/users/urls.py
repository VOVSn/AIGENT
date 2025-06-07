# users/urls.py
from django.urls import path
from users.views import PasswordChangeView, MeView # UPDATE THIS

app_name = 'users_api'

urlpatterns = [
    path('me/', MeView.as_view(), name='me'), # ADD THIS
    path('password/change/', PasswordChangeView.as_view(), name='password_change'),
]