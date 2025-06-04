from django.urls import path
from users.views import PasswordChangeView

app_name = 'users_api' # Optional: namespace for URLs

urlpatterns = [
    path('password/change/', PasswordChangeView.as_view(), name='password_change'),
]