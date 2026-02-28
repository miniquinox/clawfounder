# Google Calendar Connector

View and manage your Google Calendar events. Reuses Gmail OAuth credentials — no extra setup if Gmail is connected with calendar scopes.

## Setup

If Gmail is already connected, just re-authenticate to add calendar scopes. Otherwise:
1. Same OAuth setup as Gmail (console.cloud.google.com)
2. Add scope: `calendar` (full access) or `calendar.readonly`
3. Click "Sign in with Google" on the Gmail card

## Tools

| Tool | Description |
|------|-------------|
| `calendar_list_events` | List upcoming events (today, this week, custom range) |
| `calendar_get_event` | Get full event details by ID |
| `calendar_create_event` | Create a new event with title, time, attendees |
| `calendar_list_calendars` | List all accessible calendars |
| `calendar_quick_add` | Create event from natural language ("Meeting with John tomorrow at 2pm") |

## Workflow Examples

- **"What's on my calendar today?"** → `calendar_list_events` with time_range="today"
- **"Schedule a meeting with Sarah tomorrow at 3pm"** → `calendar_create_event` or `calendar_quick_add`
- **"What do I have this week?"** → `calendar_list_events` with time_range="this_week"
