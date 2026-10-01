from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from .config import CalendarConfig
from .models import CalendarEvent

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _credentials(config: CalendarConfig, interactive: bool):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials = None
    should_save = False
    if config.token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(config.token_file), SCOPES)
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        should_save = True
    elif not credentials or not credentials.valid:
        if not interactive:
            raise RuntimeError("Google Calendar is not authorized; run 'zmk-widget-sync auth-google'")
        flow = InstalledAppFlow.from_client_secrets_file(str(config.credentials_file), SCOPES)
        credentials = flow.run_local_server(port=0)
        should_save = True

    if should_save:
        config.token_file.parent.mkdir(parents=True, exist_ok=True)
        config.token_file.write_text(credentials.to_json(), encoding="utf-8")
        config.token_file.chmod(0o600)
    return credentials


def authorize(config: CalendarConfig) -> None:
    _credentials(config, interactive=True)


def _parse_event(item: dict, target_timezone: ZoneInfo) -> tuple[datetime, CalendarEvent]:
    start = item.get("start", {})
    title = str(item.get("summary") or "(bez tytulu)")
    if "dateTime" in start:
        moment = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
        local = moment.astimezone(target_timezone)
        return moment.astimezone(timezone.utc), CalendarEvent(local.strftime("%H:%M"), title)

    day = date.fromisoformat(start["date"])
    local = datetime(day.year, day.month, day.day, tzinfo=target_timezone)
    return local.astimezone(timezone.utc), CalendarEvent("CALY", title)


def fetch_events(config: CalendarConfig) -> list[CalendarEvent]:
    from googleapiclient.discovery import build

    credentials = _credentials(config, interactive=False)
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    now = datetime.now(timezone.utc).isoformat()
    target_timezone = ZoneInfo(config.timezone)
    collected: list[tuple[datetime, CalendarEvent]] = []

    for calendar_id in config.calendar_ids:
        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=now,
                maxResults=max(4, config.max_events * 2),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        for item in result.get("items", []):
            if item.get("status") != "cancelled" and item.get("start"):
                collected.append(_parse_event(item, target_timezone))

    collected.sort(key=lambda pair: pair[0])
    return [event for _, event in collected[: config.max_events]]
