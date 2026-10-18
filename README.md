<div align="center">
  <a href="https://github.com/immichFrame/ImmichFrame_Android">
    <img src="https://github.com/immichFrame/ImmichFrame_Desktop/blob/main/src-tauri/icons/icon.png" alt="Logo" width="160" height="160">
  </a>

  <h3 align="center">ImmichFrame Android — WebView-free fork</h3>

  <p align="center">
    A native Android client for <a href="https://github.com/immichFrame/ImmichFrame">ImmichFrame</a>, built for old and low-power digital photo frames.
  </p>
</div>

## Is this for you?

If you run ImmichFrame on an old or low-powered Android frame and the stock app
is slow or crashes, yes.

The official [ImmichFrame Android](https://github.com/immichFrame/ImmichFrame_Android)
client renders the slideshow in a WebView. On weak hardware (for example a
Frameo frame on Android 6 / API 23) that WebView is sluggish and crashes. This
fork drops the WebView and draws everything natively, so the slideshow, clock,
weather, and overlays run smoothly on that kind of device.

It connects to the same ImmichFrame server as the official client, so you keep
your existing server setup. Only the on-device rendering changes.

## Extras

- A clock that updates every minute, not just when the photo changes.
- An optional calendar panel: your next few events, listed in the bottom-right
  corner with no background box. It's fed by a small bridge service that runs on
  your LAN, so your calendar is never exposed to the internet. See
  [Calendar panel](#calendar-panel) below.
- A `calendarFontScale` preference to resize the calendar text on the device
  without rebuilding.

## Requirements

- A running [ImmichFrame server](https://github.com/immichFrame/ImmichFrame) on
  your network.
- Tested on Android 6 (API 23); `minSdk 23`.
- To build: JDK 17, Android Gradle Plugin 8.13.x, `compileSdk 36`.

## Build

In Android Studio, open the project and run the `app` configuration.

From the command line:

```bash
./gradlew assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

## Install and configure

Install over adb (the frame needs USB or network adb enabled):

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Set the server URL and other preferences in the app's Settings, or push them
over adb for a headless frame:

| Key | Meaning |
|-----|---------|
| `webview_url` | ImmichFrame server URL (name kept from upstream) |
| `authSecret` | ImmichFrame authorization secret (optional) |
| `calendarUrl` | Calendar bridge feed URL, e.g. `http://<vm-ip>:8099/events` (optional) |
| `calendarFontScale` | Calendar text size as a multiple of the base font (default `1.1`) |

## Calendar panel

The calendar panel is optional. It's driven by a companion service, the
**calendar bridge**, which reads your Outlook calendar via Microsoft Graph
(read-only) and serves the next few events as JSON on your LAN. The bridge
decides which events count as "next" and formats the labels, so the client just
displays what it's given.

Setup, authentication, and configuration are in
[`calendar-bridge/README.md`](calendar-bridge/README.md).

## Credits

- [ImmichFrame](https://github.com/immichFrame/ImmichFrame) and the official
  [ImmichFrame Android](https://github.com/immichFrame/ImmichFrame_Android)
  client this is forked from.
- [Immich](https://github.com/immich-app/immich), the self-hosted photo server
  ImmichFrame is built around.
- developersorli's [ImmichFrame_nowebview_Android](https://github.com/developersorli/ImmichFrame_nowebview_Android),
  which informed the WebView-free approach.

## License

See [LICENSE](LICENSE). This fork retains the upstream project's license.
