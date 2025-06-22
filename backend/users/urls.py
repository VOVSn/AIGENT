# users/urls.py
from django.urls import path
from users.views import PasswordChangeView, MeView, CalendarEventListView # UPDATE

app_name = 'users_api'

urlpatterns = [
    path('me/', MeView.as_view(), name='me'),
    path('password/change/', PasswordChangeView.as_view(), name='password_change'),
    # path('calendar/events/', CalendarEventListView.as_view(), name='calendar_events_list'), # ADD
]