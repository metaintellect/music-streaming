# JRiver Setup Notes

This document captures the current JRiver trial setup and the intended Windows-headless architecture.

## Architecture

Current intended roles:

- **Windows 11 laptop (`192.168.100.67`)**
  - Runs JRiver Media Center.
  - Reads NAS music over SMB from `\\192.168.100.83\xnas\music`.
  - Outputs audio to Marantz over HDMI.
  - Stays awake with lid closed for headless use.
- **RPi5 NAS (`192.168.100.83`)**
  - Serves the `xnas` Samba share.
  - No longer needed for JRiver playback in the main-room path.
- **RPi3 LibreELEC (`192.168.100.69` WiFi)**
  - Official 7" DSI touchscreen.
  - FiiO K3 USB DAC.
  - FLIRC USB receiver.
  - Candidate JRiver network playback target via DLNA/UPnP renderer-style flow.
- **Mac / iPhone**
  - Control clients for the Windows JRiver server.

Playback flow:

```text
NAS SMB share
  -> Windows JRiver library
  -> HDMI
  -> Marantz
```

Optional secondary-room flow:

```text
Windows JRiver
  -> network
  -> RPi3 player/renderer
  -> FiiO K3 USB DAC
  -> amplifier / receiver
```

## Server Setup

Install normal JRiver Media Center on Windows. There is no separate server package.

Minimum Windows-side setup:

1. Install JRiver Media Center.
2. Set `Tools > Options > Audio > Audio Device` to the Marantz HDMI endpoint using `WASAPI`.
3. Import the NAS music folder from `\\192.168.100.83\xnas\music`.
4. Enable `Tools > Options > Media Network > Use Media Network to share this library and enable DLNA`.
5. Allow the Windows firewall prompt if shown.

Notes:

- Prefer the explicit Marantz/NVIDIA HDMI `WASAPI` device over generic `Direct Audio Device`.
- `Show only 1` for the desktop is fine as long as Windows still sees the Marantz HDMI audio device.
- Avoid using Windows RDP for normal playback sessions because it can interfere with audio devices.
- If HDMI audio disappears after power/input changes on the AVR/TV side, an EDID emulator may be needed.

## Access Key

JRiver Media Network generates a six-character access key for remote control clients.

Do not commit the live key to git.

Use a local-only note like:

```text
Current access key: <fill locally and rotate if shared>
```

## Mac / iPhone Control

Preferred remote-control path:

- **Mac**
  - Use `Panel` in a browser first.
  - URL: <https://jriver.com/panel.html>
  - Enter the Windows server access key.
- **iPhone**
  - Use `JRemote`, or use `Panel` in the browser for initial testing.

Full JRiver on Mac is optional.

If using the full Mac app, connect via:

```text
File > Library > Search for Media Servers
```

That requires Media Network to already be enabled on Windows.

Remote playback notes from the Mac app:

- Open the Windows library from:

```text
File > Library > LAPTOP-J6LN68ST (Library Server)
```

- In the Mac client, `Here` means local playback on the Mac.
- `There` means playback on the remote Windows JRiver side.
- For the preferred main-room path, use:

```text
Send To > Play (There)
```

- `Play (There: Marantz SR5015)` is a different route using the Marantz as a network renderer, not the preferred Windows HDMI path.

## Trial

JRiver's current trial is `30 days` with the full feature set.

That is enough to test:

- Windows HDMI -> Marantz playback
- NAS import
- Media Network
- Mac/iPhone remote control
- RPi3 renderer experiments

## RPi3 Renderer Format

For the RPi3 target, `Original Format` is the correct first choice if the player on the Pi can handle the source format directly.

Practical meaning:

- If the library file is `FLAC`, JRiver will send `FLAC`.
- This avoids unnecessary transcoding on the Windows server.
- It is the best starting point for a Pi 3 + USB DAC music target.

Use `Original Format` first when:

- the Pi client/player supports `FLAC`
- you want bit-preserving delivery
- you do not need JRiver to downsample or convert for compatibility

If the Pi target has compatibility problems with some formats, sample rates, or gapless behavior, the next thing to try is:

```text
Specified output format only when necessary
```

That keeps direct delivery where possible and only converts when the target cannot handle the original file cleanly.

## Current Status

- JRiver imported the NAS library on Windows.
- Windows HDMI output is set to the Marantz/NVIDIA `WASAPI` endpoint.
- The desktop is set to `Show only 1`, with HDMI still connected.
- Mac control of the Windows library works.
- `Send To > Play (There)` from the Mac app plays on the Windows/Marantz side.
- The next checks are reboot/startup behavior and Pi 3 playback behavior.

## Startup / Reboot

Recommended JRiver startup setting on Windows:

```text
Tools > Options > Startup > Run on Windows startup: Media Center and Media Server
```

Practical test order:

1. Reboot Windows.
2. Log in normally.
3. Do not open JRiver manually.
4. Confirm the Mac/iPhone can still see and control the server.
5. Test playback to the Windows/Marantz zone.

For this setup, do not treat `no login at all` as the target state.

Reason:

- JRiver can auto-start in a user session.
- Windows HDMI audio is more reliable in a normal logged-in session.
- A true Windows-service-style setup is not the preferred path for local HDMI playback.
