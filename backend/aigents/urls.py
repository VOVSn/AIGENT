from django.urls import path
from .views import SendMessageView, TaskStatusView, ChatHistoryView

app_name = 'aigents_api' # Optional namespace

urlpatterns = [
    path('chat/send_message/', SendMessageView.as_view(), name='send_message'),
    path('chat/task_status/<uuid:task_id>/', TaskStatusView.as_view(), name='task_status'), # Use uuid for task_id
    path('chat/history/', ChatHistoryView.as_view(), name='chat_history'),
]