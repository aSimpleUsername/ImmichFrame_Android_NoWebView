<div align="center">
  <a href="https://github.com/immichFrame/ImmichFrame_Android">
    <img src="https://github.com/immichFrame/ImmichFrame_Desktop/blob/main/src-tauri/icons/icon.png" alt="Logo" width="160" height="160">
  </a>

  <h3 align="center">ImmichFrame Android — WebView-free fork</h3>

  <p align="center">
    A native-rendering Android client for <a href="https://github.com/immichFrame/ImmichFrame">ImmichFrame</a>,
    built for old / low-power digital photo frames.
  </p>
</div>

## What this fork is

This is a fork of the official [ImmichFrame Android](https://github.com/immichFrame/ImmichFrame_Android)
client with the **WebView removed**. The stock client renders the slideshow in a
WebView; on older, low-power frames (e.g. a Frameo frame running Android 6 /
API 23) the WebView is slow, janky, and prone to crashing. This fork draws
everything natively instead, so it runs smoothly on that hardware.

It talks to the same ImmichFrame server as the upstream client — only the
client-side rendering differs.

## What's different from upstream

- **No WebView.** The slideshow, clock, weather, and overlays are rendered
  natively. This is the main reason the fork exists.
- **Real-time clock.** The clock ticks every minute instead of only updating
  when the photo changes (~every slideshow interval).
- **Native calendar panel.** A minimal, free-floating list of your next few
  upcoming events in the bottom-right corner — no background box, styled like
  the clock. Fed by a small LAN-only bridge service (see below); your calendar
  is never published to the public internet.
- **Tunable calendar text size.** A `calendarFontScale` preference (multiple of
  the server's base font size) so you can resize the calendar text on the device
  without rebuilding.

## Target / requirements

- Designed and tested against **Android 6 (API 23)**; `minSdk 23`.
- A running [ImmichFrame server](https://github.com/immichFrame/ImmichFrame) on
  your network.
- Build toolchain: JDK 17, Android Gradle Plugin 8.13.x, `compileSdk 36`.

## Build

With Android Studio: open the project and run the `app` configuration.

From the command line:

```bash
./gradlew assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

## Install & configure on a frame

Install over adb (the frame must have USB or network adb enabled):

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Then set the server URL (and any other preferences) in the app's Settings, or
push them via adb for a headless frame. The relevant preference keys are:

| Key | Meaning |
|-----|---------|
| `webview_url` | ImmichFrame server URL (name is kept from upstream) |
| `authSecret` | ImmichFrame authorization secret (optional) |
| `calendarUrl` | Calendar bridge feed URL, e.g. `http://<vm-ip>:8099/events` (optional) |
| `calendarFontScale` | Calendar text size as a multiple of the base font (default `1.1`) |

## Calendar panel

The calendar panel is optional and driven by a small companion service, the
**calendar bridge**, which reads your Outlook calendar via Microsoft Graph
(read-only) and serves the next few events as JSON on your LAN. Setup,
authentication, and configuration are documented in
[`calendar-bridge/README.md`](calendar-bridge/README.md).

The frame does no date maths — the bridge decides what "next" means and
pre-formats the labels, so the client just displays strings.

## Credits

- [ImmichFrame](https://github.com/immichFrame/ImmichFrame) and the official
  [ImmichFrame Android](https://github.com/immichFrame/ImmichFrame_Android)
  client, which this is a fork of.
- [Immich](https://github.com/immich-app/immich), the self-hosted photo server
  that ImmichFrame is built around.
- The WebView-free approach was informed by developersorli's reference fork,
  [ImmichFrame_nowebview_Android](https://github.com/developersorli/ImmichFrame_nowebview_Android).

## License

See [LICENSE](LICENSE). This fork retains the upstream project's license.
