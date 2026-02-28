"""
Google Calendar connector — View and create calendar events.

Reuses Gmail OAuth credentials. If the user authenticated Gmail with
calendar scopes, this connector works automatically.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.readonly",
]

_TOKEN_DIR = Path.home() / ".clawfounder"

SUPPORTS_MULTI_ACCOUNT = True


def is_connected() -> bool:
    """Check if any Gmail token file exists with calendar scopes."""
    for name in ("gmail_personal.json", "gmail_work.json"):
        token_file = _TOKEN_DIR / name
        if token_file.exists():
            try:
                data = json.loads(token_file.read_text())
                scopes = data.get("scopes", [])
                if any("calendar" in s for s in scopes):
                    return True
            except Exception:
                pass
    return False


TOOLS = [
    {
        "name": "calendar_list_events",
        "description": "List upcoming calendar events. Defaults to today. Use time_range for 'today', 'tomorrow', 'this_week', or provide custom start/end dates.",
        "parameters": {
            "type": "object",
            "properties": {
                "time_range": {
                    "type": "string",
                    "description": "Shortcut: 'today', 'tomorrow', 'this_week', 'next_week' (default: today)",
                },
                "start": {
                    "type": "string",
                    "description": "Custom start datetime (ISO 8601, e.g. 2026-03-01T00:00:00Z). Overrides time_range.",
                },
                "end": {
                    "type": "string",
                    "description": "Custom end datetime (ISO 8601). Overrides time_range.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max events to return (default: 15)",
                },
            },
        },
    },
    {
        "name": "calendar_get_event",
        "description": "Get full details of a specific calendar event by event ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "The event ID (returned by calendar_list_events)",
                },
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "calendar_create_event",
        "description": "Create a new calendar event with title, start/end time, and optional attendees.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Event title",
                },
                "start": {
                    "type": "string",
                    "description": "Start datetime (ISO 8601, e.g. 2026-03-15T14:00:00)",
                },
                "end": {
                    "type": "string",
                    "description": "End datetime (ISO 8601, e.g. 2026-03-15T15:00:00)",
                },
                "description": {
                    "type": "string",
                    "description": "Event description/notes",
                },
                "attendees": {
                    "type": "string",
                    "description": "Comma-separated email addresses of attendees",
                },
                "location": {
                    "type": "string",
                    "description": "Event location",
                },
            },
            "required": ["summary", "start", "end"],
        },
    },
    {
        "name": "calendar_list_calendars",
        "description": "List all calendars the user has access to.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "calendar_quick_add",
        "description": "Create an event from natural language text, e.g. 'Meeting with John tomorrow at 2pm for 1 hour'.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Natural language event description",
                },
            },
            "required": ["text"],
        },
    },
]


# ── Auth ──────────────────────────────────────────────────────────

def _get_token_file(account_id=None):
    """Find a token file with calendar scopes. Tries Gmail personal, then work."""
    if account_id:
        # Look up in accounts registry
        accounts_file = _TOKEN_DIR / "accounts.json"
        if accounts_file.exists():
            try:
                registry = json.loads(accounts_file.read_text())
                for connector in ("gmail", "work_email"):
                    for acct in registry.get("accounts", {}).get(connector, []):
                        if acct["id"] == account_id and "credential_file" in acct:
                            return _TOKEN_DIR / acct["credential_file"]
            except Exception:
                pass

    # Default: try personal Gmail first, then work
    for name in ("gmail_personal.json", "gmail_work.json"):
        token_file = _TOKEN_DIR / name
        if token_file.exists():
            try:
                data = json.loads(token_file.read_text())
                scopes = data.get("scopes", [])
                if any("calendar" in s for s in scopes):
                    return token_file
            except Exception:
                continue
    return None


def _get_calendar_service(account_id=None):
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError("Google API dependencies not installed.")

    token_file = _get_token_file(account_id)
    if not token_file:
        raise ValueError(
            "No Google Calendar credentials found. Re-authenticate Gmail with calendar "
            "scopes: click 'Sign in with Google' on the Gmail card in the dashboard."
        )

    creds = Credentials.from_authorized_user_file(str(token_file), _SCOPES)

    token_data = json.loads(token_file.read_text())
    quota_project = token_data.get("quota_project_id")
    if quota_project:
        creds = creds.with_quota_project(quota_project)

    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())

    return build("calendar", "v3", credentials=creds)


# ── Time range helpers ────────────────────────────────────────────

def _parse_time_range(time_range=None, start=None, end=None):
    """Return (time_min, time_max) as ISO strings."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if start and end:
        return start, end

    tr = (time_range or "today").lower()
    if tr == "today":
        return today_start.isoformat(), (today_start + timedelta(days=1)).isoformat()
    elif tr == "tomorrow":
        tom = today_start + timedelta(days=1)
        return tom.isoformat(), (tom + timedelta(days=1)).isoformat()
    elif tr == "this_week":
        week_start = today_start - timedelta(days=today_start.weekday())
        return week_start.isoformat(), (week_start + timedelta(days=7)).isoformat()
    elif tr == "next_week":
        week_start = today_start - timedelta(days=today_start.weekday()) + timedelta(days=7)
        return week_start.isoformat(), (week_start + timedelta(days=7)).isoformat()
    else:
        # Default: next 24 hours
        return now.isoformat(), (now + timedelta(days=1)).isoformat()


# ── Tool implementations ──────────────────────────────────────────

def _list_events(time_range=None, start=None, end=None, max_results=15, account_id=None):
    service = _get_calendar_service(account_id)
    time_min, time_max = _parse_time_range(time_range, start, end)

    result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = result.get("items", [])
    if not events:
        return f"No events found for {time_range or 'today'}."

    output = []
    for event in events:
        start_dt = event["start"].get("dateTime", event["start"].get("date", ""))
        end_dt = event["end"].get("dateTime", event["end"].get("date", ""))
        attendees = [a.get("email", "") for a in event.get("attendees", [])]
        output.append({
            "id": event["id"],
            "summary": event.get("summary", "(no title)"),
            "start": start_dt,
            "end": end_dt,
            "location": event.get("location", ""),
            "attendees": attendees[:10],
            "status": event.get("status", ""),
            "htmlLink": event.get("htmlLink", ""),
        })
    return json.dumps(output, indent=2)


def _get_event(event_id, account_id=None):
    service = _get_calendar_service(account_id)
    event = service.events().get(calendarId="primary", eventId=event_id).execute()
    return json.dumps({
        "id": event["id"],
        "summary": event.get("summary", "(no title)"),
        "description": event.get("description", ""),
        "start": event["start"].get("dateTime", event["start"].get("date", "")),
        "end": event["end"].get("dateTime", event["end"].get("date", "")),
        "location": event.get("location", ""),
        "attendees": [
            {"email": a.get("email"), "status": a.get("responseStatus", "")}
            for a in event.get("attendees", [])
        ],
        "organizer": event.get("organizer", {}).get("email", ""),
        "htmlLink": event.get("htmlLink", ""),
    }, indent=2)


def _create_event(summary, start, end, description=None, attendees=None, location=None, account_id=None):
    service = _get_calendar_service(account_id)
    body = {
        "summary": summary,
        "start": {"dateTime": start, "timeZone": "UTC"},
        "end": {"dateTime": end, "timeZone": "UTC"},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        emails = [e.strip() for e in attendees.split(",")]
        body["attendees"] = [{"email": e} for e in emails if e]

    event = service.events().insert(calendarId="primary", body=body).execute()
    return f"Event created: {summary} ({start} to {end}). Link: {event.get('htmlLink', '')}"


def _list_calendars(account_id=None):
    service = _get_calendar_service(account_id)
    result = service.calendarList().list().execute()
    calendars = []
    for cal in result.get("items", []):
        calendars.append({
            "id": cal["id"],
            "summary": cal.get("summary", ""),
            "primary": cal.get("primary", False),
            "accessRole": cal.get("accessRole", ""),
        })
    return json.dumps(calendars, indent=2)


def _quick_add(text, account_id=None):
    service = _get_calendar_service(account_id)
    event = service.events().quickAdd(calendarId="primary", text=text).execute()
    start = event["start"].get("dateTime", event["start"].get("date", ""))
    return f"Event created: {event.get('summary', text)} at {start}. Link: {event.get('htmlLink', '')}"


# ── Handler ───────────────────────────────────────────────────────

def handle(tool_name: str, args: dict, account_id: str = None) -> str:
    try:
        if tool_name == "calendar_list_events":
            return _list_events(
                args.get("time_range"), args.get("start"), args.get("end"),
                args.get("max_results", 15), account_id=account_id,
            )
        elif tool_name == "calendar_get_event":
            return _get_event(args["event_id"], account_id=account_id)
        elif tool_name == "calendar_create_event":
            return _create_event(
                args["summary"], args["start"], args["end"],
                args.get("description"), args.get("attendees"), args.get("location"),
                account_id=account_id,
            )
        elif tool_name == "calendar_list_calendars":
            return _list_calendars(account_id=account_id)
        elif tool_name == "calendar_quick_add":
            return _quick_add(args["text"], account_id=account_id)
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        err = str(e)
        if "accessNotConfigured" in err or "has not been used" in err or "PERMISSION_DENIED" in err:
            return (
                "Calendar API not enabled. Go to console.cloud.google.com/apis/library/calendar-json.googleapis.com "
                "and click Enable for your project."
            )
        if "invalid_grant" in err or "Token has been expired" in err:
            return "Calendar token expired. Re-authenticate Gmail to refresh."
        return f"Calendar error: {e}"
