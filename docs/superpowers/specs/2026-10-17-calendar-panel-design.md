# Calendar panel — design spec

**Date:** 2026-10-17
**Status:** approved design, pre-implementation

## Goal
Show the **next 3 upcoming calendar events** (any date, not just today) as a minimal panel in the **bottom-right** of the frame — free-floating text with a shadow, same treatment as the clock (no background box). Source is the user's personal Outlook calendar, kept entirely off the public internet.

## Why not ImmichFrame's `api/Calendar`
It returns **today-only** events, so it cannot show events across the coming weeks. We bypass it and build a dedicated bridge.

## Architecture
```
Outlook ──Graph API (user, read-only)──▶ VM bridge ──"next 3 events" JSON──▶ frame (LAN only)
          one-time device-code login        every 15 min        fetched + rendered natively
```
The **bridge** (on the VM, correct clock + timezone) decides which 3 events are next and pre-formats the display text. The **frame does no date math**, so its unreliable boot-clock never affects the calendar. The frame reaches only the VM (LAN); nothing is published publicly.

## Component 1 — bridge (VM, new)
- Location in repo: `calendar-bridge/` (Python script + Dockerfile + compose snippet).
- Auth: Microsoft Graph via **MSAL device-code flow**. Authority `https://login.microsoftonline.com/consumers`. Token cache persisted to a mounted volume (survives restarts, renews silently). One-time interactive login via `microsoft.com/devicelogin`.
- Query: `GET /me/calendarView` for now → now+`LOOKAHEAD_DAYS`, recurrences expanded by Graph, `$orderby=start/dateTime`, header `Prefer: outlook.timezone="<TZ>"`. Take the first `COUNT` events.
- Serves JSON at `GET http://<vm>:<PORT>/events`:
  ```json
  { "updated":"<iso-utc>",
    "events":[ {"when":"Today 18:30","title":"Dentist","allDay":false}, ... ] }
  ```
  `when` is pre-formatted by the bridge: relative label for today/tomorrow, else `Ddd DD Mon`; time in 24h to match the clock; all-day events show date only (client renders italic).
- Refresh: re-query every `REFRESH_MINUTES` (default 15).
- Config via env: `CLIENT_ID`, `TZ` (default `Australia/Perth`), `LOOKAHEAD_DAYS` (default 90), `COUNT` (default 3), `PORT` (default 8099), `REFRESH_MINUTES` (15).
- Deps kept minimal (python:3-slim + `msal`).

## Component 2 — Android client
- New **optional** preference `calendarUrl` (e.g. `http://192.168.1.51:8099/events`). **Blank ⇒ panel off** (opt-in; a down bridge can never break the frame).
- Retrofit `@GET @Url` fetch of the absolute bridge URL; data class `{ when, title, allDay }`.
- Refresh on a **15-min timer** (mirrors the existing weather timer); lifecycle-managed like the other timers.
- New bottom-right `TextView` (`txtCalendar`) in `main_view.xml`, ~0.9× base font, white, shadow, right-aligned, no background. Renders ≤3 rows: muted `when` + bold `title`; all-day italic.
- **All parsing/rendering wrapped in try/catch; panel hidden (GONE) on empty list or any failure** — a dark corner beats a crash on a wall-mounted frame.
- Bottom-right is free (user does not display photo date/location). If those are ever enabled, stack calendar above them.
- Scope: `MainActivity` only for now (the photo view). `ScreenSaverService` not required (daydream path unused on the frame).

## User setup — Azure app registration (one-time)
At **entra.microsoft.com** (personal Outlook login): App registrations ▸ New registration ▸ "Personal Microsoft accounts only", no redirect URI ▸ copy **Application (client) ID** ▸ Authentication ▸ Allow public client flows = **Yes** ▸ API permissions ▸ Microsoft Graph ▸ Delegated ▸ `Calendars.Read` + `offline_access`. Free; no subscription/credit card.

## Deployment
1. Paste the provided compose service; `docker compose up -d`.
2. `docker logs -f` → enter the device code at `microsoft.com/devicelogin`, consent once.
3. Verify `http://<vm>:8099/events` returns JSON — **gate: paste real JSON before client parsing is written**.
4. Build + install client; verify on frame.

## Work order
Azure reg → write bridge → deploy + login → **verify real `/events` JSON** → build client → install → verify on frame.

## Verification gates / risks
- Real JSON must be confirmed before client parsing (shape, timezone, all-day format).
- Bridge auth is the main setup risk (Azure reg details); device-code + consumers avoids client secrets.
- Failure modes (bridge down, bad JSON, empty) must hide the panel, never crash.

## Out of scope (for now)
Photo de-duplication (separate task); calendar on the daydream/screensaver path; a `showCalendar` on/off toggle beyond "blank URL = off".
