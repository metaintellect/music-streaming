# Plex / Plexamp Setup Notes

This document captures the current Plex migration state from Roon.

## TODO

1. Run deeper security checks on the exposed Plex Remote Access setup from a personal ChatGPT/account/environment, not the company one.

## Architecture

Current roles:

- **Windows 11 laptop (`192.168.100.67`)**
  - Runs Plex Media Server.
  - Reads NAS music over SMB from `\\192.168.100.83\xnas\music`.
  - Owns the Plex music library.
- **RPi5 NAS (`192.168.100.83`)**
  - Still serves the `xnas` Samba share.
  - Runs Plexamp Headless as a playback endpoint named `Pi 5 HDMI`.
  - Outputs to Marantz over HDMI.
- **RPi3 DietPi (`192.168.100.70` Ethernet, `192.168.100.103` WiFi)**
  - Fresh DietPi 64-bit install.
  - WiFi configured and tested.
  - Runs Plexamp Headless as a playback endpoint named `Pi 3 FiiO`.
  - Outputs to FiiO K3 USB DAC.

Playback flow:

```text
Windows Plex Media Server
  -> network
  -> Plexamp Headless on RPi5 / RPi3
  -> HDMI or USB DAC
  -> amplifier / receiver
```

The Plex library remains on Windows PMS. Pi devices are only players.

## Plex Playlists From Roon Excel

Roon does not provide a clean M3U-only export. Its Folder export copies files, which is slow and wasteful.

Roon Excel export works better because it includes a `Path` column with full UNC paths.

Added script:

```text
scripts/roon-excel-to-plex-playlist.py
```

Tests:

```text
tests/test_roon_excel_to_plex_playlist.py
```

Generated preserved M3U backups on NAS:

```text
/Volumes/xnas/playlists/exyu.m3u
/Volumes/xnas/playlists/easy.m3u
```

Imported and verified in Plex:

| Playlist | Expected | Plex verified |
|---|---:|---:|
| `exyu` | 971 | 971 |
| `easy` | 480 | 480 |

Import command pattern:

```bash
PLEX_TOKEN='...' python3 scripts/roon-excel-to-plex-playlist.py \
  --xlsx /Users/x/Documents/exyu.xlsx /Users/x/Documents/easy.xlsx \
  --output-dir /Volumes/xnas/playlists \
  --plex-path-dir "\\\\192.168.100.83\\xnas\\playlists" \
  --plex-url http://192.168.100.67:32400 \
  --library-name Music \
  --import \
  --force
```

Notes:

- Use `X-Plex-Token`; no special PMS token is created.
- Do not commit/store the token.
- If Plex imports too few tracks, wait for Plex library scan to finish and re-import with `--force`.

## RPi5 Plexamp Headless

Installed on RPi5:

- Node.js `20.19.2`
- Plexamp Headless `4.13.1`
- systemd service: `plexamp.service`
- service user: `plexamp`
- install path: `/opt/plexamp`
- state/cache path: `/var/lib/plexamp`

Useful commands:

```bash
ssh root@192.168.100.83 'systemctl status plexamp'
ssh root@192.168.100.83 'journalctl -u plexamp -n 100 --no-pager'
ssh root@192.168.100.83 'curl -s http://127.0.0.1:32500/resources'
```

Verified endpoint:

```text
http://192.168.100.83:32500/resources
```

Expected XML includes:

```text
title="Pi 5 HDMI"
product="Plexamp"
version="4.13.1"
```

Roon services were stopped temporarily to free HDMI:

```bash
ssh root@192.168.100.83 'systemctl stop roonbridge hdmi-bridge'
```

Current working state:

- Plexamp Headless is active.
- `Pi 5 HDMI` appears as a Plexamp target from Mac/mobile.
- HDMI device was freed after stopping `roonbridge` and `hdmi-bridge`.

If reverting to Roon on RPi5:

```bash
ssh root@192.168.100.83 'systemctl stop plexamp; systemctl start roonbridge hdmi-bridge'
```

## RPi3 DietPi State

Hardware:

- Raspberry Pi 3 Model B Rev 1.2
- 1 GB RAM
- 64-bit ARM capable
- FiiO USB DAC planned
- Flirc configured for Marantz remote, to be retested
- Former RoPieee install replaced with DietPi

DietPi image flashed:

```text
DietPi_RPi234-ARMv8-Trixie.img.xz
```

macOS flash command:

```bash
diskutil unmountDisk /dev/disk5
xzcat ~/Downloads/DietPi_RPi234-ARMv8-Trixie.img.xz | sudo dd of=/dev/rdisk5 bs=4m status=progress
sync
diskutil eject /dev/disk5
```

Disk note:

- `/dev/disk5` was the 15.9 GB microSD.
- `/dev/rdisk5` was used for faster raw writes.

Current RPi3 network:

```text
Ethernet: 192.168.100.70
WiFi:     192.168.100.103
```

Configured WiFi SSIDs:

```text
A1_293752491
A1_293752491_Ext
```

The Pi only saw those two. The third local SSID is likely 5 GHz; Raspberry Pi 3 Model B WiFi is 2.4 GHz only.

WiFi-only test passed:

- Ethernet was brought down.
- Default route moved to `wlan0`.
- `ping 1.1.1.1` worked.
- Ethernet was brought back up.

### RPi3 WiFi Persistence Issue

After the first WiFi test, RPi3 was moved to another room and became unreachable. The live WiFi test had passed, but it had not been reboot-verified.

Root cause:

```ini
dtoverlay=disable-wifi
```

was present in:

```text
/boot/firmware/config.txt
```

That disables the onboard WiFi at firmware level, so after reboot Linux did not even create `wlan0`.

Fix:

```bash
ssh root@192.168.100.70
sed -i '/^dtoverlay=disable-wifi$/d' /boot/firmware/config.txt
reboot
```

Post-fix verification:

```bash
ssh root@192.168.100.70 'ip -br addr; ls /sys/class/net'
ssh root@192.168.100.103 'hostname; ping -c 2 1.1.1.1'
```

Expected:

```text
wlan0 UP 192.168.100.103/24
```

Lesson: after changing DietPi WiFi, always reboot once and verify WiFi SSH still works before moving the Pi off Ethernet.

Use after moving rooms:

```bash
ssh root@192.168.100.103
```

## RPi3 Display Notes

The small RPi touchscreen did not show output after DietPi boot.

Likely reason:

- It is a DSI touchscreen, not HDMI.
- RoPieee had display support preconfigured.
- Fresh DietPi can boot headless without showing console on the DSI screen.

This is not blocking for SSH/audio setup.

Possible future display work:

- enable/check Raspberry Pi DSI display overlays
- use the screen as a kiosk/browser for Plexamp Headless web UI
- or leave it disconnected/unused

## Next Steps

RPi3 endpoint work:

1. RPi3 is now in the other room on WiFi.
2. FiiO K3 USB DAC is attached and visible.
3. Plexamp Headless is installed and working.
4. Optional future experiment:
   - piCorePlayer + LMS + Squeeze Plex Hub plugin

Important distinction:

- **Plexamp Headless** is native Plex endpoint control, but requires Plex Pass.
- **piCorePlayer** is excellent for LMS/Squeezelite, but is not a native Plexamp endpoint.
- Plex/LMS bridge plugins are experimental/community plumbing.

## RPi3 Plexamp Headless + FiiO

Installed on RPi3:

- Node.js `20.19.2`
- `alsa-utils`
- `bzip2`
- Plexamp Headless `4.13.1`
- systemd service: `plexamp.service`
- service user: `plexamp`
- install path: `/opt/plexamp`
- state/cache path: `/var/lib/plexamp`

Verified USB devices:

```text
Clay Logic flirc
FiiO Electronics Technology K3
```

Verified ALSA device:

```text
card 0: K3 [K3], device 0: USB Audio [USB Audio]
```

Verified Plexamp endpoint:

```text
http://192.168.100.103:32500/resources
```

Expected XML includes:

```text
title="Pi 3 FiiO"
product="Plexamp"
version="4.13.1"
```

Plexamp log confirmed:

```text
BASS: Device 2: K3: USB Audio
Companion: Registering device 'Pi 3 FiiO' at 192.168.100.103:32500.
Companion: Started HTTP Server on port 32500 and registered.
```

Useful commands:

```bash
ssh root@192.168.100.103 'systemctl status plexamp'
ssh root@192.168.100.103 'journalctl -u plexamp -n 100 --no-pager'
ssh root@192.168.100.103 'tail -n 100 /var/lib/plexamp/.cache/Plexamp/log/Plexamp.log'
ssh root@192.168.100.103 'aplay -l; cat /proc/asound/cards'
ssh root@192.168.100.103 'curl -s http://127.0.0.1:32500/resources'
```

If playback is silent:

1. Open `http://192.168.100.103:32500`.
2. Set audio output to `K3: USB Audio`.
3. Restart Plexamp if needed:

```bash
ssh root@192.168.100.103 'systemctl restart plexamp'
```

## Plexamp Behavior Notes

Confirmed:

- Multiple endpoints work:
  - `Pi 5 HDMI`
  - `Pi 3 FiiO`
  - Mac/mobile Plexamp clients
- Plexamp plays to one selected endpoint at a time.
- It does not provide Roon-style synchronized grouped multi-room playback.
- Plexamp queue mostly shows upcoming tracks, not a full scrollable history above the current track.
- Clicking a track in an album starts playback from that track through the rest of the album.
- For one-track-only behavior, use `Play Next` / queue actions instead of normal click.

Practical queue workarounds:

- use Recently Played
- use previous button for the last few tracks
- return to source album/playlist
- save curated queues as playlists

## Remote Access

Goal:

- expose only Windows Plex Media Server to the internet
- keep NAS SMB private
- stream to mobile Plexamp outside the home network

Router:

```text
Huawei HG8145V5
A1 Croatia fiber
```

WAN status:

```text
Public WAN IP: 188.129.11.174
Plex server:   192.168.100.67
```

The router WAN IP matched Plex's public IP, so this was not CGNAT.

Router port mapping:

```text
WAN:            1_INTERNET_R_VID_60
Internal host:  192.168.100.67
Protocol:       TCP
External port:  21898-21898
Internal port:  32400-32400
External source IP: blank
```

Plex Remote Access:

```text
Manually specify public port: 21898
Upload speed: 10 Mbps
```

Windows firewall:

- allowed Plex Media Server on Private/Public
- allowed Plex DLNA on Private/Public

Local checks from Mac:

```bash
nc -vz 192.168.100.67 32400
curl http://192.168.100.67:32400/identity
```

Public checks from inside the LAN also worked:

```bash
nc -vz 188.129.11.174 21898
curl http://188.129.11.174:21898/identity
```

Plex Remote Access eventually showed:

```text
Fully accessible outside your network
```

Confirmed real-world test:

- iPhone on mobile data could play music from `x430n-plex`.

Important limitation:

- Remote Access exposes the Plex library/server.
- It does not expose local Plexamp Headless endpoints as selectable remote players.
- On mobile data, the phone can play on itself.
- `Pi 3 FiiO` and `Pi 5 HDMI` are LAN control targets and are normally selectable only while the controller is on the home network.
- To control home Pi endpoints from outside, use a VPN such as Tailscale or WireGuard.

If Plex Remote Access flips red again, test the actual port first:

```bash
curl http://188.129.11.174:21898/identity
```

If that returns Plex XML, the router mapping is working and Plex's status page may just be lagging or flaky.
