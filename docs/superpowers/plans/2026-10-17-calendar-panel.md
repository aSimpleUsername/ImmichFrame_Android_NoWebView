# Calendar Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the next 3 upcoming Outlook events (any date) in the frame's bottom-right, fed by a private VM-side bridge.

**Architecture:** A Python bridge on the VM authenticates to Microsoft Graph (device-code, read-only), computes and pre-formats the next 3 events, and serves them as JSON on the LAN. The Android client fetches that JSON on a timer and renders it as shadowed text — doing no date math, so the frame's unreliable clock is irrelevant.

**Tech Stack:** Python 3 + `msal` (bridge, Docker); Kotlin + Retrofit/Gson (client).

## Global Constraints
- Client: minSdk 23, Java/Kotlin 11, `SimpleDateFormat`/`Calendar` only (no `java.time`); no WebView.
- Keep the `webview_url` preference key name unchanged (upstream merges).
- Frame reaches only the VM; nothing published to the public internet.
- Client: all calendar parsing/rendering in try/catch; hide the panel (GONE) on empty or failure — never crash.
- Bridge auth: authority `https://login.microsoftonline.com/consumers`, scope `Calendars.Read`, device-code flow, token cache persisted to a mounted volume.
- This container compiles Kotlin via `java -cp gradle/wrapper/gradle-wrapper.jar org.gradle.wrapper.GradleWrapperMain assembleDebug --no-daemon`; it cannot run Python or install on the frame. Bridge tests run on the VM; client runtime is verified on the frame by the user.

---

## Task 0 (user precondition): Azure app registration
Not code — the user completes this once and provides the **Application (client) ID**. At **entra.microsoft.com** (personal Outlook login): App registrations ▸ New registration ▸ "Personal Microsoft accounts only", no redirect URI ▸ copy the client ID ▸ Authentication ▸ Allow public client flows = **Yes** ▸ API permissions ▸ Microsoft Graph ▸ Delegated ▸ add `Calendars.Read` and `offline_access`. Free; no subscription/credit card. **Blocks Task 1 login.**

---

## Task 1: Bridge — config + device-code auth

**Files:**
- Create: `calendar-bridge/bridge.py`
- Create: `calendar-bridge/requirements.txt`
- Create: `calendar-bridge/Dockerfile`

**Interfaces:**
- Produces: `get_token() -> str` (a valid Graph access token), reading env `CLIENT_ID`, using cache file `/data/token.json`.

- [ ] **Step 1: requirements.txt**
```
msal==1.31.0
tzdata==2024.2
```

- [ ] **Step 2: bridge.py — config + auth**
```python
import os, atexit, msal

CLIENT_ID = os.environ["CLIENT_ID"]
AUTHORITY = "https://login.microsoftonline.com/consumers"
SCOPES = ["Calendars.Read"]
CACHE_PATH = os.environ.get("TOKEN_CACHE", "/data/token.json")

def _cache():
    c = msal.SerializableTokenCache()
    if os.path.exists(CACHE_PATH):
        c.deserialize(open(CACHE_PATH).read())
    atexit.register(lambda: open(CACHE_PATH, "w").write(c.serialize()) if c.has_state_changed else None)
    return c

_app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=_cache())

def get_token() -> str:
    accts = _app.get_accounts()
    res = _app.acquire_token_silent(SCOPES, account=accts[0]) if accts else None
    if not res:
        flow = _app.initiate_device_flow(scopes=SCOPES)
        print(flow["message"], flush=True)        # "go to microsoft.com/devicelogin and enter CODE"
        res = _app.acquire_token_by_device_flow(flow)
    if "access_token" not in res:
        raise RuntimeError(res.get("error_description", "auth failed"))
    # persist cache immediately after a successful interactive login
    open(CACHE_PATH, "w").write(_app.token_cache.serialize())
    return res["access_token"]

if __name__ == "__main__":
    print("token acquired:", bool(get_token()), flush=True)
```

- [ ] **Step 3: Dockerfile**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bridge.py .
VOLUME /data
EXPOSE 8099
CMD ["python", "bridge.py"]
```

- [ ] **Step 4: Verify auth (user, on VM)** — after Task 0 provides `CLIENT_ID`:
```
cd calendar-bridge
docker build -t immichframe-calendar .
docker run --rm -it -e CLIENT_ID=<id> -v immichframe-cal-data:/data immichframe-calendar
```
Expected: prints a `microsoft.com/devicelogin` code; after you enter + consent, prints `token acquired: True`.

- [ ] **Step 5: Commit**
```bash
git add calendar-bridge/
git commit -m "Add calendar bridge auth skeleton"
```

---

## Task 2: Bridge — fetch events + format "when"

**Files:**
- Modify: `calendar-bridge/bridge.py`
- Create: `calendar-bridge/test_format.py`

**Interfaces:**
- Consumes: `get_token()` from Task 1.
- Produces: `format_when(start: datetime, now: datetime, all_day: bool) -> str`; `fetch_events() -> list[dict]` where each dict is `{"when": str, "title": str, "allDay": bool}`.

- [ ] **Step 1: Failing test for the formatter — test_format.py**
```python
import datetime
from zoneinfo import ZoneInfo
from bridge import format_when

TZ = ZoneInfo("Australia/Perth")
NOW = datetime.datetime(2026, 10, 17, 9, 0, tzinfo=TZ)   # Fri 17 Oct

def at(y, m, d, hh=0, mm=0): return datetime.datetime(y, m, d, hh, mm, tzinfo=TZ)

def test_timed_today():    assert format_when(at(2026,10,17,18,30), NOW, False) == "Today 18:30"
def test_timed_tomorrow(): assert format_when(at(2026,10,18,9,0),  NOW, False) == "Tomorrow 09:00"
def test_timed_thisweek(): assert format_when(at(2026,10,19,9,0),  NOW, False) == "Sun 09:00"
def test_timed_far():      assert format_when(at(2026,10,30,9,0),  NOW, False) == "30 Oct 09:00"
def test_allday_today():   assert format_when(at(2026,10,17),      NOW, True)  == "Today"
def test_allday_far():     assert format_when(at(2026,10,20),      NOW, True)  == "Mon 20 Oct"
```

- [ ] **Step 2: Run test to verify it fails (user, on VM/python env)**
Run: `cd calendar-bridge && pip install tzdata && python -m pytest test_format.py -q`
Expected: FAIL (`ImportError: cannot import name 'format_when'`).

- [ ] **Step 3: Implement formatter + fetch in bridge.py** (append)
```python
import datetime, json, urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.environ.get("TZ", "Australia/Perth"))
LOOKAHEAD_DAYS = int(os.environ.get("LOOKAHEAD_DAYS", "90"))
COUNT = int(os.environ.get("COUNT", "3"))

def format_when(start, now, all_day):
    delta = (start.date() - now.date()).days
    if all_day:
        if delta == 0: return "Today"
        if delta == 1: return "Tomorrow"
        if 2 <= delta < 7: return start.strftime("%a")
        return start.strftime("%a %d %b").lstrip("0")
    tod = start.strftime("%H:%M")
    if delta == 0: return f"Today {tod}"
    if delta == 1: return f"Tomorrow {tod}"
    if 2 <= delta < 7: return f"{start.strftime('%a')} {tod}"
    return f"{start.strftime('%d %b').lstrip('0')} {tod}"

def fetch_events():
    token = get_token()
    now = datetime.datetime.now(TZ)
    end = now + datetime.timedelta(days=LOOKAHEAD_DAYS)
    url = ("https://graph.microsoft.com/v1.0/me/calendarView"
           f"?startDateTime={now.isoformat()}&endDateTime={end.isoformat()}"
           "&$orderby=start/dateTime&$top=25&$select=subject,start,isAllDay")
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Prefer": f'outlook.timezone="{TZ.key}"'})
    with urllib.request.urlopen(req, timeout=20) as r:
        items = json.load(r).get("value", [])
    out = []
    for it in items[:COUNT]:
        s = it["start"]["dateTime"]                       # local to TZ via Prefer header
        start = datetime.datetime.fromisoformat(s[:19]).replace(tzinfo=TZ)
        out.append({"when": format_when(start, now, it.get("isAllDay", False)),
                    "title": it.get("subject", "(no title)"),
                    "allDay": bool(it.get("isAllDay", False))})
    return out
```
Note: `%d`/date strings keep a leading zero on some platforms; `.lstrip("0")` only trims a leading pad — acceptable for `dd MMM`. If a cleaner day number is wanted later, use `str(start.day)`.

- [ ] **Step 4: Run test to verify it passes (user, on VM)**
Run: `python -m pytest test_format.py -q`
Expected: PASS (6 passed). *(If `test_timed_far`/`allday_far` disagree on leading-zero, adjust `lstrip` — the assertion strings are the source of truth.)*

- [ ] **Step 5: Commit**
```bash
git add calendar-bridge/bridge.py calendar-bridge/test_format.py
git commit -m "Add calendar event fetch and when-formatting to bridge"
```

---

## Task 3: Bridge — serve JSON + refresh loop + compose

**Files:**
- Modify: `calendar-bridge/bridge.py`
- Create: `calendar-bridge/compose.snippet.yml`

**Interfaces:**
- Consumes: `fetch_events()` from Task 2.
- Produces: HTTP `GET /events` → `{"updated": iso, "events": [...]}` on `PORT` (default 8099).

- [ ] **Step 1: Append server + loop to bridge.py** (replace the `if __name__` block)
```python
import threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", "8099"))
REFRESH_MINUTES = int(os.environ.get("REFRESH_MINUTES", "15"))
_state = {"updated": None, "events": []}

def _refresh_loop():
    while True:
        try:
            _state["events"] = fetch_events()
            _state["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            print(f"refreshed {len(_state['events'])} events", flush=True)
        except Exception as e:
            print("refresh error:", e, flush=True)   # keep last good state
        time.sleep(REFRESH_MINUTES * 60)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/") != "/events":
            self.send_response(404); self.end_headers(); return
        body = json.dumps(_state).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

if __name__ == "__main__":
    get_token()                                  # trigger device-code login on first run
    threading.Thread(target=_refresh_loop, daemon=True).start()
    print(f"serving on :{PORT}/events", flush=True)
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
```

- [ ] **Step 2: compose.snippet.yml** (user pastes into their stack)
```yaml
  immichframe-calendar:
    build: ./calendar-bridge
    container_name: immichframe-calendar
    restart: unless-stopped
    environment:
      CLIENT_ID: "<your-app-client-id>"
      TZ: "Australia/Perth"
    volumes:
      - immichframe-cal-data:/data
    ports:
      - "8099:8099"
# add to top-level volumes:
#   immichframe-cal-data:
```

- [ ] **Step 3: Deploy + first login (user, on VM)**
```
docker compose up -d --build immichframe-calendar
docker logs -f immichframe-calendar     # enter the devicelogin code once
```
Expected: logs show `serving on :8099/events` and `refreshed N events`.

- [ ] **Step 4: VERIFICATION GATE — real JSON**
Open `http://192.168.1.51:8099/events` in a browser. Confirm it returns `{"updated":..., "events":[{"when","title","allDay"}, ...]}`. **Paste this to the implementer before starting Task 6 parsing.** Include at least one timed and (if possible) one all-day event.

- [ ] **Step 5: Commit**
```bash
git add calendar-bridge/bridge.py calendar-bridge/compose.snippet.yml
git commit -m "Serve next-events JSON from the calendar bridge"
```

---

## Task 4: Client — preference + data model + fetch

**Files:**
- Modify: `app/src/main/res/xml/settings_view.xml` (Connection Settings category)
- Modify: `app/src/main/java/com/immichframe/immichframe/Helpers.kt` (add data classes + ApiService method)

**Interfaces:**
- Produces: pref key `calendarUrl` (String, blank = off); `Helpers.CalendarResponse`, `Helpers.CalendarEvent`; `ApiService.getCalendar(@Url url: String): Call<CalendarResponse>`.

- [ ] **Step 1: Add the preference** — in `settings_view.xml`, inside the `Connection Settings` category after `authSecret`:
```xml
        <EditTextPreference
            android:defaultValue=""
            android:inputType="textUri"
            android:key="calendarUrl"
            android:title="Calendar feed URL (optional)" />
```

- [ ] **Step 2: Add data classes to Helpers.kt** (near `ServerSettings`)
```kotlin
    data class CalendarResponse(
        val updated: String?,
        val events: List<CalendarEvent>?
    )

    data class CalendarEvent(
        @SerializedName("when") val whenLabel: String?,
        val title: String?,
        val allDay: Boolean?
    )
```
Add import if missing: `import com.google.gson.annotations.SerializedName`.

- [ ] **Step 3: Add the ApiService call** — in `interface ApiService` in Helpers.kt:
```kotlin
        @GET
        fun getCalendar(@retrofit2.http.Url url: String): Call<CalendarResponse>
```
(`@Url` lets this one call target the absolute bridge URL instead of the ImmichFrame base.)

- [ ] **Step 4: Compile (implementer, this container)**
Run: `java -cp gradle/wrapper/gradle-wrapper.jar org.gradle.wrapper.GradleWrapperMain assembleDebug --no-daemon`
Expected: BUILD SUCCESSFUL.

- [ ] **Step 5: Commit**
```bash
git add app/src/main/res/xml/settings_view.xml app/src/main/java/com/immichframe/immichframe/Helpers.kt
git commit -m "Add calendar feed preference, data model and API call"
```

---

## Task 5: Client — bottom-right calendar TextView

**Files:**
- Modify: `app/src/main/res/layout/main_view.xml`

**Interfaces:**
- Produces: view id `R.id.txtCalendar`.

- [ ] **Step 1: Add the TextView** after `txtDateTime` in `main_view.xml` (mirrors its styling, anchored bottom|end, right-aligned, hidden until data arrives):
```xml
        <TextView
            android:id="@+id/txtCalendar"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:layout_gravity="bottom|end"
            android:background="@android:color/transparent"
            android:gravity="end"
            android:padding="8dp"
            android:shadowColor="#99000000"
            android:shadowDx="2"
            android:shadowDy="2"
            android:shadowRadius="4"
            android:text=""
            android:textColor="@android:color/white"
            android:textSize="16sp"
            android:visibility="gone" />
```

- [ ] **Step 2: Compile (implementer, this container)**
Run: `java -cp gradle/wrapper/gradle-wrapper.jar org.gradle.wrapper.GradleWrapperMain assembleDebug --no-daemon`
Expected: BUILD SUCCESSFUL.

- [ ] **Step 3: Commit**
```bash
git add app/src/main/res/layout/main_view.xml
git commit -m "Add bottom-right calendar TextView to the main layout"
```

---

## Task 6: Client — wire up fetch, timer, render (hide on failure)

**Files:**
- Modify: `app/src/main/java/com/immichframe/immichframe/MainActivity.kt`

**Interfaces:**
- Consumes: `R.id.txtCalendar`, `Helpers.CalendarResponse/CalendarEvent`, `ApiService.getCalendar`, pref `calendarUrl`.

- [ ] **Step 1: Field + view binding** — add a field near the other views and bind it in `onCreate` next to `txtDateTime`:
```kotlin
    private lateinit var txtCalendar: TextView
    private var calendarUrl: String = ""
    private var isCalendarTimerRunning = false
    private val calendarRunnable = object : Runnable {
        override fun run() {
            if (isCalendarTimerRunning) {
                handler.postDelayed(this, 900000)   // 15 min
                getCalendar()
            }
        }
    }
```
In `onCreate` (after `txtDateTime = findViewById(...)`):
```kotlin
        txtCalendar = findViewById(R.id.txtCalendar)
```

- [ ] **Step 2: Read the pref in `loadSettings()`** — after `showCurrentDate = ...`:
```kotlin
        calendarUrl = prefs.getString("calendarUrl", "")?.trim() ?: ""
```

- [ ] **Step 3: Start the timer in `onSettingsLoaded()`** — after the weather timer block:
```kotlin
        if (calendarUrl.isNotEmpty()) {
            if (!isCalendarTimerRunning) {
                isCalendarTimerRunning = true
                handler.post(calendarRunnable)
            }
        } else {
            txtCalendar.visibility = View.GONE
        }
```

- [ ] **Step 4: Fetch + render** — add methods (fetch uses the existing `apiService`; `@Url` overrides the base):
```kotlin
    private fun getCalendar() {
        if (calendarUrl.isEmpty()) return
        apiService.getCalendar(calendarUrl).enqueue(object : Callback<Helpers.CalendarResponse> {
            override fun onResponse(
                call: Call<Helpers.CalendarResponse>,
                response: Response<Helpers.CalendarResponse>
            ) {
                try {
                    val events = response.body()?.events.orEmpty()
                        .filter { !it.title.isNullOrBlank() }
                        .take(3)
                    renderCalendar(events)
                } catch (_: Exception) {
                    txtCalendar.visibility = View.GONE
                }
            }
            override fun onFailure(call: Call<Helpers.CalendarResponse>, t: Throwable) {
                txtCalendar.visibility = View.GONE
            }
        })
    }

    private fun renderCalendar(events: List<Helpers.CalendarEvent>) {
        if (events.isEmpty()) {
            txtCalendar.visibility = View.GONE
            return
        }
        val sb = android.text.SpannableStringBuilder()
        events.forEachIndexed { i, e ->
            if (i > 0) sb.append("\n")
            val whenStart = sb.length
            sb.append(e.whenLabel.orEmpty())
            sb.setSpan(android.text.style.RelativeSizeSpan(0.8f), whenStart, sb.length,
                android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            sb.setSpan(android.text.style.ForegroundColorSpan(0xB3FFFFFF.toInt()), whenStart, sb.length,
                android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            sb.append("  ")
            val titleStart = sb.length
            sb.append(e.title.orEmpty())
            sb.setSpan(android.text.style.StyleSpan(android.graphics.Typeface.BOLD), titleStart, sb.length,
                android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }
        txtCalendar.text = sb
        txtCalendar.textSize = Helpers.cssFontSizeToSp(serverSettings.baseFontSize, this) * 0.9f
        txtCalendar.visibility = View.VISIBLE
    }
```

- [ ] **Step 5: Stop the timer** — in `onDestroy()` before `handler.removeCallbacksAndMessages(null)` (already clears it) add the flag reset, and in `setFrameActive(false)` after `stopWeatherTimer()`:
```kotlin
        isCalendarTimerRunning = false
```

- [ ] **Step 6: Compile (implementer, this container)**
Run: `java -cp gradle/wrapper/gradle-wrapper.jar org.gradle.wrapper.GradleWrapperMain assembleDebug --no-daemon`
Expected: BUILD SUCCESSFUL.

- [ ] **Step 7: Install + verify on frame (user)**
```
adb -s 192.168.1.103:5555 install -r "C:\claude-box\workspace\ImmichFrame_Android_NoWebView\app\build\outputs\apk\debug\app-debug.apk"
```
Then set the calendar URL pref (via the adb prefs-push method) to `http://192.168.1.51:8099/events`, relaunch, and confirm the bottom-right shows up to 3 events. Kill the bridge and confirm the panel disappears (no crash).

- [ ] **Step 8: Commit**
```bash
git add app/src/main/java/com/immichframe/immichframe/MainActivity.kt
git commit -m "Fetch and render the calendar panel, hiding it on failure"
```

---

## Self-review notes
- Spec coverage: bridge auth (T1), fetch+format (T2), serve+deploy (T3), client pref/model (T4), layout (T5), wiring+hide-on-fail (T6), Azure precondition (T0), real-JSON gate (T3.4). All covered.
- The `@Url` call reuses the existing `apiService`; confirm Retrofit's base URL (the ImmichFrame server) is set before `getCalendar` runs — it is, because `loadSettings` builds `apiService` before `onSettingsLoaded` starts the calendar timer.
- Client has little pure logic to unit-test (rendering is Android-coupled; the bridge pre-formats), so client verification is compile + on-frame, consistent with this project.
