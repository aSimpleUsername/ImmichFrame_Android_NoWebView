# ImmichFrame calendar bridge

A small service that reads your Outlook calendar via Microsoft Graph (read-only)
and serves the **next few upcoming events** as JSON on your LAN, for the
ImmichFrame Android client to display. Your calendar is never published to the
public internet; only this service (on your VM) talks to Microsoft, over an
authenticated connection you approve once.

## Run

1. Add the service in `compose.snippet.yml` to your Docker Compose stack
   (plus the `immichframe-cal-data` named volume).
2. `docker compose up -d --build immichframe-calendar`
3. `docker logs -f immichframe-calendar` — it prints a one-time device-login
   code. Visit <https://microsoft.com/devicelogin>, enter it, sign in with your
   Outlook account, and approve read access to your calendars.
4. Verify: open `http://<vm-ip>:8099/events` — you should see the events JSON.
5. Point the Android client's "Calendar feed URL" preference at that URL.

## Authentication / client ID

By default the bridge uses Microsoft's official first-party public client
**"Microsoft Graph Command Line Tools"** (`14d82eec-204b-4c2f-b7e8-296a70dab67e`)
with the device-code flow. This means **no Azure app registration is required**
for a personal Microsoft account.

Trade-off: access shows up (and is revoked) under that shared Microsoft app
name rather than a dedicated one. To use an **isolated identity** instead,
register your own app (Entra ▸ App registrations ▸ "Personal Microsoft
accounts", Allow public client flows = Yes, delegated `Calendars.Read` +
`offline_access`) and set its client ID via the `CLIENT_ID` env var. No code
change or rebuild needed.

Revoke access anytime at <https://account.microsoft.com> ▸ Privacy ▸ app access.

## Config (env)

| Var | Default | Meaning |
|-----|---------|---------|
| `CLIENT_ID` | Graph CLI public client | OAuth client ID |
| `TZ` | `Australia/Perth` | timezone for event times + "today"/"tomorrow" |
| `LOOKAHEAD_DAYS` | `90` | how far ahead to look for events |
| `COUNT` | `3` | number of events to serve |
| `PORT` | `8099` | HTTP port |
| `REFRESH_MINUTES` | `15` | how often to re-query Graph |

## Notes

- The refresh token lives in the mounted volume (`/data/token.json`); protect
  the host/volume accordingly.
- The `/events` endpoint is unauthenticated — intended for a trusted LAN only.
- Tests: `pip install -r requirements.txt && python -m pytest test_format.py -q`.
