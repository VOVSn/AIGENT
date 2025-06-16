# backend/tools/tool_library/calendar_tool.py
from datetime import datetime
import pytz
from django.contrib.auth import get_user_model
from users.models import CalendarEvent

User = get_user_model()

# Helper to parse datetime strings with timezone awareness
def _parse_datetime(time_str: str, user_timezone_str: str) -> datetime:
    user_tz = pytz.timezone(user_timezone_str)
    # Assume "YYYY-MM-DD HH:MM:SS" format for simplicity
    dt_naive = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    dt_aware = user_tz.localize(dt_naive)
    return dt_aware.astimezone(pytz.utc)

def _add_event(user, title, description, start_time_utc, end_time_utc):
    event = CalendarEvent.objects.create(
        user=user,
        title=title,
        description=description,
        start_time=start_time_utc,
        end_time=end_time_utc,
    )
    return f"Successfully added event '{event.title}' with ID {event.id}."

def _list_events(user):
    now_utc = datetime.now(pytz.utc)
    events = CalendarEvent.objects.filter(user=user, end_time__gte=now_utc).order_by('start_time')[:10]
    if not events.exists():
        return "No upcoming events found in the calendar."
    
    event_list = [
        f"ID: {e.id}, Title: '{e.title}', Start: {e.start_time.isoformat()}"
        for e in events
    ]
    return "Upcoming events:\n" + "\n".join(event_list)

def _update_event(user, event_id, updates):
    try:
        event = CalendarEvent.objects.get(pk=event_id, user=user)
        updated_fields = []
        if 'title' in updates:
            event.title = updates['title']
            updated_fields.append('title')
        if 'description' in updates:
            event.description = updates['description']
            updated_fields.append('description')
        
        user_tz_str = user.timezone
        if 'start_time' in updates:
            event.start_time = _parse_datetime(updates['start_time'], user_tz_str)
            updated_fields.append('start_time')
        if 'end_time' in updates:
            event.end_time = _parse_datetime(updates['end_time'], user_tz_str)
            updated_fields.append('end_time')
            
        if updated_fields:
            event.save()
            return f"Successfully updated fields {updated_fields} for event ID {event_id}."
        return "No valid fields provided to update."

    except CalendarEvent.DoesNotExist:
        return f"Error: Event with ID {event_id} not found."
    except Exception as e:
        return f"Error updating event: {str(e)}"

def _delete_event(user, event_id):
    try:
        event = CalendarEvent.objects.get(pk=event_id, user=user)
        title = event.title
        event.delete()
        return f"Successfully deleted event '{title}' (ID: {event_id})."
    except CalendarEvent.DoesNotExist:
        return f"Error: Event with ID {event_id} not found."


def manage_calendar(action: str, user_id: int, **kwargs):
    """
    Manages the user's calendar. This is a SYNCHRONOUS function.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return "Error: User not found."

    if action == 'add':
        start_time_str = kwargs.get('start_time')
        end_time_str = kwargs.get('end_time')
        if not all([start_time_str, end_time_str]):
            return "Error: 'start_time' and 'end_time' are required for adding an event."
        
        try:
            start_time_utc = _parse_datetime(start_time_str, user.timezone)
            end_time_utc = _parse_datetime(end_time_str, user.timezone)
            return _add_event(user, kwargs.get('title', 'Untitled Event'), kwargs.get('description', ''), start_time_utc, end_time_utc)
        except Exception as e:
            return f"Error parsing date/time: {e}. Expected format 'YYYY-MM-DD HH:MM:SS'."
            
    elif action == 'list':
        return _list_events(user)
        
    elif action == 'update':
        event_id = kwargs.get('event_id')
        updates = kwargs.get('updates')
        if not event_id or not isinstance(updates, dict):
            return "Error: 'event_id' and an 'updates' dictionary are required for updating an event."
        return _update_event(user, event_id, updates)

    elif action == 'delete':
        event_id = kwargs.get('event_id')
        if not event_id:
            return "Error: 'event_id' is required for deleting an event."
        return _delete_event(user, event_id)
        
    else:
        return "Error: Invalid action. Must be one of 'add', 'list', 'update', 'delete'."