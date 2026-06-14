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
- **RPi3 LibreELEC (`192.168.100.69` WiFi)**
  - Runs LibreELEC `12.2.1` with Kodi on the official DSI touchscreen.
  - Uses `PM4K for Plex` (`script.plexmod`) as the Plex client.
  - Outputs to FiiO K3 USB DAC.
  - Uses FLIRC for remote input; functional but not especially snappy yet.

Playback flow:

```text
Windows Plex Media Server
  -> network
  -> Plexamp Headless on RPi5
  -> HDMI
or
Windows Plex Media Server
  -> network
  -> Kodi + PM4K for Plex on RPi3
  -> FiiO K3 USB DAC
  -> amplifier / receiver
```

The Plex library remains on Windows PMS. Pi devices are only players, but the Pi 3 is now a local Kodi/Plex client rather than a Plexamp Headless endpoint.

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
- legacy Roon services: `roonbridge.service`, `hdmi-bridge.service`
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

### HDMI / ALSA findings

The old Roon setup did not send audio straight to HDMI.

It used:

- ALSA Loopback for `RoonBridge`
- a custom bridge service at `/usr/local/bin/hdmi-bridge.sh`
- fixed stereo PCM to the connected HDMI port `vc4hdmi1`

Bridge behavior:

```bash
arecord -D plughw:Loopback,0,0 -f S32_LE -r 192000 -c 2 -t raw | \
aplay -D plughw:vc4hdmi1,0 -f S32_LE -r 192000 -c 2 -t raw
```

That mattered because it hard-forced:

- HDMI port `vc4hdmi1`
- `2` channels
- one stable PCM path to Marantz

Direct Plexamp playback was more fragile. After stop/close/resume, Marantz could occasionally come back on rear channels instead of front stereo. The likely cause was ALSA/HDMI reopening with ambiguous channel mapping.

Current fix:

- `roonbridge.service` and `hdmi-bridge.service` were disabled
- `/etc/asound.conf` was updated so ALSA default output is an explicit stereo route to `vc4hdmi1`
- `plexamp.service` was restarted after the ALSA change

Current `/etc/asound.conf` shape:

```ini
pcm.loopout {
    type plug
    slave.pcm "hw:Loopback,0,0"
}

pcm.loopin {
    type plug
    slave.pcm "hw:Loopback,1,0"
}

pcm.hdmi_stereo {
    type route
    slave {
        pcm "plughw:vc4hdmi1,0"
        channels 2
    }
    ttable.0.0 1
    ttable.1.1 1
}

pcm.!default {
    type plug
    slave.pcm "hdmi_stereo"
    slave.channels 2
}

ctl.!default {
    type hw
    card vc4hdmi1
}
```

Backup kept on RPi5:

```text
/etc/asound.conf.codex-backup
```

Useful checks:

```bash
ssh root@192.168.100.83 'systemctl status plexamp --no-pager -l'
ssh root@192.168.100.83 'grep -n "Setting audio interface\\|Error initializing device" /var/lib/plexamp/.cache/Plexamp/log/Plexamp.log | tail -n 40'
ssh root@192.168.100.83 'aplay -L | sed -n "1,80p"'
ssh root@192.168.100.83 'cat /etc/asound.conf'
```

Current working state:

- Plexamp Headless is active.
- `Pi 5 HDMI` appears as a Plexamp target from Mac/mobile.
- HDMI device was freed after stopping `roonbridge` and `hdmi-bridge`.
- ALSA default now routes explicitly to stereo HDMI on `vc4hdmi1`.

If reverting to Roon on RPi5:

```bash
ssh root@192.168.100.83 'systemctl stop plexamp; systemctl start roonbridge hdmi-bridge'
```

## RPi3 LibreELEC + Kodi + Plex

The final working Pi 3 setup uses LibreELEC and Kodi, not DietPi and not Plexamp Headless.

Hardware:

- Raspberry Pi 3 Model B Rev 1.2
- official 7" DSI touchscreen
- FiiO K3 USB DAC
- FLIRC USB receiver

Current network:

```text
WiFi: 192.168.100.69
```

Software:

- LibreELEC `12.2.1` (`RPi2.arm`)
- Kodi with default Estuary home restored
- `PM4K for Plex` (`script.plexmod`) installed and enabled
- Plex server remains Windows PMS at `192.168.100.67`

What was done to make Kodi/Plex work on RPi3:

1. Installed LibreELEC and confirmed the official DSI touchscreen worked.
2. Enabled SSH and added the local `~/.ssh/id_ed25519.pub` key to `/storage/.ssh/authorized_keys`.
3. Confirmed the FiiO DAC was visible to ALSA.
4. Forced Kodi audio output to the FiiO K3 device.
5. Installed `PM4K for Plex` and its Python dependencies manually from Kodi mirror package URLs over SSH.
6. No custom PM4K/Plex add-on repository URL was configured inside Kodi itself.
7. Linked `PM4K` to the existing Plex server using the normal `plex.tv/link` auth flow from the PM4K UI.
8. Restored the normal Kodi home screen and added Plex to Kodi `Favorites`.

Installed Kodi/Plex add-ons:

- `script.plexmod`
- `script.module.requests`
- `script.module.six`
- `script.module.kodi-six`
- `script.module.certifi`
- `script.module.chardet`
- `script.module.idna`
- `script.module.urllib3`

Verified USB / ALSA devices:

```text
Clay Logic flirc
FiiO Electronics Technology K3
card 1: K3 [K3], device 0: USB Audio [USB Audio]
```

Kodi audio settings now point to:

```text
audiooutput.audiodevice=ALSA:@:CARD=K3,DEV=0|K3
audiooutput.passthrough=false
audiooutput.passthroughdevice=ALSA:iec958:CARD=K3,DEV=0|K3
```

Current user flow after reboot:

- Kodi boots to the normal Estuary home screen.
- Open Plex from `Favorites`.
- Fallback path: `Add-ons -> Video add-ons -> PM4K for Plex`.
- PM4K is linked and album browsing/playback works.

Notes about install/login:

- PM4K was not added through a custom repo URL inside Kodi.
- The add-on files were fetched directly from `mirrors.kodi.tv` during SSH setup.
- Plex account/server linking happened through the normal `plex.tv/link` flow shown by PM4K on screen.

Useful checks:

```bash
ssh root@192.168.100.69 'systemctl is-active kodi'
ssh root@192.168.100.69 'aplay -l; cat /proc/asound/cards'
ssh root@192.168.100.69 'grep -n "audiooutput\\." /storage/.kodi/userdata/guisettings.xml | sed -n "1,40p"'
ssh root@192.168.100.69 'cat /storage/.kodi/userdata/favourites.xml'
ssh root@192.168.100.69 'sed -n "1,120p" /storage/.kodi/userdata/addon_data/script.plexmod/settings.xml'
```

Important distinction:

- **RPi5** remains a true Plexamp Headless endpoint named `Pi 5 HDMI`.
- **RPi3** is now a local Kodi/Plex client.
- PM4K is a separate Plex UI inside Kodi; it is not Kodi's native Music library.
- This Pi 3 path avoids the Plex Pass requirement that came with Plexamp Headless on RPi3.

Current caveats:

- PM4K works, but it is not especially snappy on Pi 3 hardware.
- FLIRC works, but navigation still needs tuning/testing.
- Keep the normal Kodi home; trying to force a special music-only home made the box harder to recover.

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
- `Pi 5 HDMI` is still a LAN Plexamp control target and is normally selectable only while the controller is on the home network.
- `RPi3` now behaves as its own local Kodi/Plex client, not as a remote Plexamp target.
- To control home Pi endpoints from outside, use a VPN such as Tailscale or WireGuard.

If Plex Remote Access flips red again, test the actual port first:

```bash
curl http://188.129.11.174:21898/identity
```

If that returns Plex XML, the router mapping is working and Plex's status page may just be lagging or flaky.
