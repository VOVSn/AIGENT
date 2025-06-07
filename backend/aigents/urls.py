from django.urls import path
from .views import (
    SendMessageView, 
    TaskStatusView, 
    ChatHistoryView,
    AigentListView,           # NEW
    SetActiveAigentView       # NEW
)

app_name = 'aigents_api'

urlpatterns = [
    # NEW endpoints for managing aigents
    path('aigents/list/', AigentListView.as_view(), name='aigent_list'),
    path('aigents/set_active/', SetActiveAigentView.as_view(), name='set_active_aigent'),

    # Existing chat endpoints
    path('chat/send_message/', SendMessageView.as_view(), name='send_message'),
    path('chat/task_status/<uuid:task_id>/', TaskStatusView.as_view(), name='task_status'),
    path('chat/history/', ChatHistoryView.as_view(), name='chat_history'),
]