"""ImmichFrame calendar bridge.

Authenticates to Microsoft Graph (read-only, device-code flow), fetches the
next few upcoming events, pre-formats them, and serves them as JSON on the LAN
for the ImmichFrame Android client. The frame does no date maths; this service
(with a correct clock + timezone) decides what "next" means.
"""
import atexit
import datetime
import json
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from zoneinfo import ZoneInfo

import msal

CLIENT_ID = os.environ["CLIENT_ID"]
AUTHORITY = "https://login.microsoftonline.com/consumers"
SCOPES = ["Calendars.Read"]
CACHE_PATH = os.environ.get("TOKEN_CACHE", "/data/token.json")

TZ = ZoneInfo(os.environ.get("TZ", "Australia/Perth"))
LOOKAHEAD_DAYS = int(os.environ.get("LOOKAHEAD_DAYS", "90"))
COUNT = int(os.environ.get("COUNT", "3"))
PORT = int(os.environ.get("PORT", "8099"))
REFRESH_MINUTES = int(os.environ.get("REFRESH_MINUTES", "15"))


def _cache():
    c = msal.SerializableTokenCache()
    if os.path.exists(CACHE_PATH):
        c.deserialize(open(CACHE_PATH).read())
    atexit.register(
        lambda: open(CACHE_PATH, "w").write(c.serialize()) if c.has_state_changed else None
    )
    return c


_app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=_cache())


def get_token() -> str:
    accts = _app.get_accounts()
    res = _app.acquire_token_silent(SCOPES, account=accts[0]) if accts else None
    if not res:
        flow = _app.initiate_device_flow(scopes=SCOPES)
        print(flow["message"], flush=True)  # "go to microsoft.com/devicelogin and enter CODE"
        res = _app.acquire_token_by_device_flow(flow)
    if "access_token" not in res:
        raise RuntimeError(res.get("error_description", "auth failed"))
    open(CACHE_PATH, "w").write(_app.token_cache.serialize())
    return res["access_token"]


def format_when(start, now, all_day):
    delta = (start.date() - now.date()).days
    if all_day:
        if delta == 0:
            return "Today"
        if delta == 1:
            return "Tomorrow"
        if 2 <= delta < 7:
            return start.strftime("%a")
        return start.strftime("%a %d %b").lstrip("0")
    tod = start.strftime("%H:%M")
    if delta == 0:
        return f"Today {tod}"
    if delta == 1:
        return f"Tomorrow {tod}"
    if 2 <= delta < 7:
        return f"{start.strftime('%a')} {tod}"
    return f"{start.strftime('%d %b').lstrip('0')} {tod}"


def fetch_events():
    token = get_token()
    now = datetime.datetime.now(TZ)
    end = now + datetime.timedelta(days=LOOKAHEAD_DAYS)
    url = (
        "https://graph.microsoft.com/v1.0/me/calendarView"
        f"?startDateTime={now.isoformat()}&endDateTime={end.isoformat()}"
        "&$orderby=start/dateTime&$top=25&$select=subject,start,isAllDay"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Prefer": f'outlook.timezone="{TZ.key}"',
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        items = json.load(r).get("value", [])
    out = []
    for it in items[:COUNT]:
        s = it["start"]["dateTime"]  # local to TZ via Prefer header
        start = datetime.datetime.fromisoformat(s[:19]).replace(tzinfo=TZ)
        out.append(
            {
                "when": format_when(start, now, it.get("isAllDay", False)),
                "title": it.get("subject", "(no title)"),
                "allDay": bool(it.get("isAllDay", False)),
            }
        )
    return out


_state = {"updated": None, "events": []}


def _refresh_loop():
    while True:
        try:
            _state["events"] = fetch_events()
            _state["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            print(f"refreshed {len(_state['events'])} events", flush=True)
        except Exception as e:  # keep last good state on transient errors
            print("refresh error:", e, flush=True)
        time.sleep(REFRESH_MINUTES * 60)


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/") != "/events":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(_state).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    get_token()  # trigger device-code login on first run
    threading.Thread(target=_refresh_loop, daemon=True).start()
    print(f"serving on :{PORT}/events", flush=True)
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
