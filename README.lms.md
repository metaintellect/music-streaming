# Lyrion / LMS Setup Notes

This document captures the current Lyrion Music Server setup, what is already working, what broke during setup, and what still needs to be finished.

## Current State

- **Windows 11 laptop (`192.168.100.67`)**
  - Runs `Lyrion Music Server`.
  - Reads music from the NAS over SMB at `\\192.168.100.83\xnas\music`.
- **RPi5 NAS / DietPi (`192.168.100.83`)**
  - Still serves the `xnas` Samba share.
  - Now runs `squeezelite` as the LMS player for the Marantz over HDMI.
  - Old `plexamp.service` is disabled so it does not fight for the audio device.
- **RPi3**
  - Runs `piCorePlayer 11.1.0`.
  - Persistent partition was resized from the tiny default image size and is now `3000 MB` on the current card.
  - Runs `squeezelite` as player `RPi3-FiiO`.
  - Audio output is the `FiiO K3` USB DAC.
  - `Jivelite` is installed and enabled.
  - The official Raspberry Pi `7"` touchscreen now works with `Jivelite`.
  - Touch input works on the official `7"` screen.
  - Current `Jivelite` skin choice is `JogglerSkin`, which fits this screen better than the lower-resolution options.
  - `Jivelite` uses `/dev/fb0` on the current working image.
  - USB remote path is a `Flirc` receiver, which shows up as a keyboard device.
- **Mac control**
  - Preferred control UI is the LMS `Material` web interface:
    - `http://192.168.100.67:9000/material/`
  - `SqueezePlay` is not the preferred UI and can be ignored.

## Architecture

```text
Windows LMS Server (192.168.100.67)
  -> SMB reads music from RPi5 NAS share (\\192.168.100.83\xnas\music)
  -> controls LMS players on LAN

RPi5 NAS (192.168.100.83)
  -> squeezelite
  -> HDMI
  -> Marantz

RPi3
  -> piCorePlayer + Jivelite
  -> FiiO K3 USB DAC
  -> local touchscreen + Flirc remote
```

## Windows LMS Server

### Working setup

- LMS web UI: `http://192.168.100.67:9000`
- `Music Folder`: `\\192.168.100.83\xnas\music`
- `Playlists Folder`: local Windows folder, for example `C:\LyrionPlaylists`

### Important Windows / SMB gotcha

The biggest problem was not the path itself. The path worked in File Explorer, but LMS kept dropping it from settings.

Cause:

- LMS on Windows runs as a `service`.
- A Windows service does not automatically run as the logged-in user.
- Because of that, it often cannot see mapped drives and may not have NAS credentials.

What fixed it:

1. Use a `UNC` path, not a mapped drive letter.
2. Run the `Lyrion Music Server` service under the real Windows account that already has access to the NAS share.

Working account setup:

- Windows local user: `x`
- SMB user on NAS: `x`
- Same password on both sides

After changing the service to run as `.\x`, LMS accepted `\\192.168.100.83\xnas\music` and rescanning worked.

### Notes

- Mapped drives are not reliable for LMS on Windows.
- The old folder picker in LMS is misleading and mostly shows local disks.
- If the NAS path ever disappears again, check the service logon account first.

## RPi5 Marantz Player

The `RPi5` is not running Plexamp for this path anymore. It now runs `squeezelite` against the Windows LMS server.

### Installed and active

- Package: `squeezelite`
- Player name: `RPi5-Marantz`
- LMS server: `192.168.100.67`
- Audio output: `plughw:CARD=vc4hdmi1,DEV=0`

### Why this output was needed

Initial setup used raw ALSA output:

```text
hw:CARD=vc4hdmi1,DEV=0
```

That was wrong for this HDMI path. Symptoms:

- playback timer in LMS moved from `00:00` to `00:01` and kept looping
- no sound
- `journalctl` showed:

```text
alsa_open:435 unable to open audio device with any supported format
```

Fix:

- switch output from `hw:` to `plughw:`

Working output:

```text
plughw:CARD=vc4hdmi1,DEV=0
```

### Current config on RPi5

File:

```text
/etc/default/squeezelite
```

Current arguments:

```text
ARGS="-W -C 5 -n RPi5-Marantz -o plughw:CARD=vc4hdmi1,DEV=0 -s 192.168.100.67"
```

### Service state

- `squeezelite.service`: enabled and active
- `plexamp.service`: disabled and inactive

### Useful commands

```bash
ssh root@192.168.100.83 'systemctl status squeezelite --no-pager -l'
ssh root@192.168.100.83 'journalctl -u squeezelite -n 100 --no-pager'
ssh root@192.168.100.83 'cat /etc/default/squeezelite'
ssh root@192.168.100.83 'aplay -L'
```

If reverting to Plexamp later:

```bash
ssh root@192.168.100.83 'systemctl disable --now squeezelite'
ssh root@192.168.100.83 'systemctl enable --now plexamp'
```

## Mac Control

Preferred control method on macOS:

```text
http://192.168.100.67:9000/material/
```

Reason:

- `SqueezePlay` is an old appliance-style UI.
- It works more like an old Squeezebox than a normal Mac app.
- Browser control through `Material` is the sane option.

## Syncing RPi5 and RPi3

If you want the same music on both rooms at the same time, sync the two LMS players instead of starting playback separately on each one.

Players involved:

- `RPi5-Marantz`
- `RPi3-FiiO`

Preferred UI:

```text
http://192.168.100.67:9000/material/
```

### Material UI steps

1. Open `Material`.
2. Start by selecting the player that should be the main playback target, usually `RPi5-Marantz` or `RPi3-FiiO`.
3. Open the player selector in the top bar.
4. Use the `Synchronize` / `Sync` action for the currently selected player.
5. Add the other player to that sync group.
6. Start playback on the synced group.

Expected result:

- both players play the same queue
- play/pause/skip acts on the group while they stay synced

Important behavior:

- If you later switch to one individual player and queue music directly to only that player, it can break away from the sync group.
- For casual ad hoc listening, standard LMS sync is enough.
- If `RPi5-Marantz + RPi3-FiiO` becomes a frequent permanent pair, consider the LMS `Group Players` plugin later so the pair behaves like one reusable virtual player.

## RPi3 piCorePlayer

### Current status

- `piCorePlayer` image was flashed for the `RPi3`.
- Use the `32-bit` image for `Pi0-3`.
- First boot and SSH setup are complete.
- Persistent partition was resized successfully.
- `Jivelite` is installed and enabled.
- `squeezelite` is configured and connected to LMS.
- The official Raspberry Pi `7"` touchscreen is now showing `Jivelite`.
- Touch input is working on the current setup.
- `pcp bu` has been run after the current `Jivelite` setup, so language/skin settings should now persist across reboot.

### Current config

- Player name: `RPi3-FiiO`
- LMS server: `192.168.100.67`
- Output: `hw:CARD=K3`
- Audio mode: `USB`
- `JIVELITE="yes"`
- `JL_FRAME_BUFFER="/dev/fb0"`

Current relevant `pcp.cfg` values:

```text
NAME="RPi3-FiiO"
OUTPUT="hw:CARD=K3"
AUDIO="USB"
SERVER_IP="192.168.100.67"
JIVELITE="yes"
JL_FRAME_BUFFER="/dev/fb0"
```

Current relevant `PCP_BOOT/config.txt` display lines:

```text
# display_auto_detect=1
dtoverlay=vc4-kms-v3d
dtoverlay=vc4-kms-dsi-7inch
```

Active process after reboot:

```text
/usr/local/bin/squeezelite -n RPi3-FiiO -o hw:CARD=K3 -a 80 0 -s 192.168.100.67
/opt/jivelite/bin/jivelite.sh
/opt/jivelite/bin/jivelite
```

### Why resize was needed

Earlier guidance was "usually no resize needed", but for this actual card/image the persistent partition was still tiny.

Before resize:

- `/dev/mmcblk0p2` was about `84 MB`
- only about `7 MB` free
- not enough for `pcp-jivelite`

After resize on the current card:

- partition 2 is `3000 MB`
- filesystem now has plenty of space for `Jivelite` and related packages

### What happened on first boot

- `piCorePlayer` is basically headless first.
- No `Jivelite` GUI on first boot is expected.
- SSH is not enabled by default on current `piCorePlayer`.
- On the fresh image used here, the effective state was still close to default:
  - `JIVELITE="no"`
  - `OUTPUT="hw:CARD=Headphones"`
  - no `pcp-jivelite` package in the running setup yet

### What was done

1. Boot `RPi3` on wired Ethernet.
2. Open `http://pcp.local` or the Pi IP.
3. Set the system password.
4. Enable `SSH`.
5. Resize partition 2 so there is enough persistent space for `Jivelite`.
6. Download `pcp-jivelite.tcz` and dependencies.
7. Set player config to `RPi3-FiiO`, `hw:CARD=K3`, LMS server `192.168.100.67`.
8. Enable `Jivelite` in `pcp.cfg`.
9. Add `pcp-jivelite.tcz` to `onboot.lst`.
10. Add `opt/jivelite` to `.xfiletool.lst`.
11. Backup and reboot.
12. If the screen is still blank, mount the boot partition and fix `config.txt`:

```text
# display_auto_detect=1
dtoverlay=vc4-kms-v3d
dtoverlay=vc4-kms-dsi-7inch
```

13. Keep `JL_FRAME_BUFFER="/dev/fb0"` on the current working image.
14. Backup and reboot again.

### Why wired first

- The `RPi3` currently needs first setup over the web UI.
- Doing first boot on Wi-Fi only is more annoying than it is worth.
- Wired first is the clean path, then move to Wi-Fi later if desired.

### Display and input findings

- The official Raspberry Pi `7"` touchscreen is detected.
- Kernel framebuffer log on the working system shows:

```text
Registered framebuffer for display 0, size 800x480
Registered framebuffer for display 1, size 720x480
```

- Input devices currently detected:

```text
flirc.tv flirc Keyboard -> event0
raspberrypi-ts -> event1
```

- Backlight device exists as `rpi_backlight`.
- Working backlight values were:

```text
brightness=255
actual_brightness=255
bl_power=0
```

- The key failure turned out **not** to be LMS or the DAC.
- The real blocker was the display boot path:
  - `Jivelite` was running
  - `raspberrypi-ts` existed
  - backlight was on
  - but the DSI nodes were effectively not coming up correctly for the panel
- For the current working image:
  - `fb0` had pixel data
  - `fb1` was blank
  - `Jivelite` had to use `/dev/fb0`

### Important correction to earlier notes

Earlier troubleshooting pointed at `/dev/fb1` plus extra `fbcon` arguments in `cmdline.txt`.

That was **not** the final fix on the current `piCorePlayer 11.1.0` image.

The final working fix was:

- install `pcp-jivelite`
- set `JIVELITE="yes"`
- set `JL_FRAME_BUFFER="/dev/fb0"`
- force the official display overlays in `PCP_BOOT/config.txt`

```text
# display_auto_detect=1
dtoverlay=vc4-kms-v3d
dtoverlay=vc4-kms-dsi-7inch
```

### Remote / LIRC note

This setup is **not** using classic `LIRC` right now.

Reason:

- The attached USB IR device is a `Flirc`.
- `Flirc` exposes itself as a USB keyboard.
- For `Jivelite`, that is usually better than using raw `LIRC`.

So the current expectation is:

- `Flirc` remote works by sending keyboard-style navigation keys to `Jivelite`
- `IR_LIRC` stays off unless a different raw IR receiver is used later

Current saved Flirc config files in this repo:

- [kodi_rpi_flirc_config.fcfg](/Users/x/src/music-streaming/kodi_rpi_flirc_config.fcfg) is the older Kodi-era snapshot.
- [jivelite_flirc_config.fcfg](/Users/x/src/music-streaming/jivelite_flirc_config.fcfg) is the current Jivelite-era snapshot/work-in-progress.

Important note:

- Flirc changes are written directly to the receiver when recorded in the GUI or CLI.
- The `.fcfg` files are only saved snapshots.
- If the live Flirc receiver is changed, save a new `.fcfg` afterward if you want the repo copy to match the hardware.

Current Jivelite remote direction:

- D-pad arrows are for UI navigation.
- Dedicated `<<` / `>>` transport buttons are being moved toward `z` / `b` style Jivelite transport control instead of left/right UI navigation.
- `Play/Pause` was additionally recorded as `space` to improve Jivelite behavior.
- `Stop` is lower priority and may be left alone if `prev/next/play-pause` are working reliably.

Persistence note:

- If language, theme, or other Jivelite settings reset after reboot, run `pcp bu`.
- The live preferences are stored in `/home/tc/.jivelite/userpath/settings/`.
- The issue earlier was simply that those files had not yet been included in the last `mydata.tgz` backup.

Current `pcp.cfg` IR state:

```text
IR_LIRC="no"
IR_KEYTABLES="no"
```

## Problems Hit So Far

### 1. LMS on Windows rejected NAS path

Cause:

- service account problem

Fix:

- run the LMS Windows service as `.\x`

### 2. LMS folder picker only showed `C:`

Cause:

- old UI and service-context limitations

Fix:

- type UNC paths manually
- do not rely on mapped drives

### 3. RPi5 player connected but produced no sound

Cause:

- wrong ALSA output mode (`hw:` instead of `plughw:`)

Fix:

- use:

```text
plughw:CARD=vc4hdmi1,DEV=0
```

### 4. SqueezePlay on macOS was misleading

Cause:

- `.dmg` did not make it obvious that the app had to be copied manually to `/Applications`
- after launch, the UI itself is old and not a good daily-control choice

Fix:

- copy app manually if needed
- prefer browser `Material` UI instead

### 5. RPi3 had too little persistent storage for Jivelite

Cause:

- the `piCorePlayer` image had not expanded partition 2 yet
- `pcp-jivelite` would not fit into the default tiny partition

Fix:

- resize partition 2 so `pcp-jivelite` and its dependencies fit comfortably

### 6. RPi3 remote is not actually a LIRC receiver

Cause:

- the USB receiver is `Flirc`, not a raw `lirc` USB receiver

Fix:

- keep `LIRC` disabled for now
- use `Flirc` as a keyboard input path for `Jivelite`

### 7. RPi3 screen stayed blank even though Jivelite was running

Cause:

- Fresh `piCorePlayer` image was still close to default:
  - `JIVELITE="no"`
  - output still on `Headphones`
  - `pcp-jivelite` not yet installed
- After `Jivelite` was installed, the screen was still blank because the boot display path was wrong for the official `7"` panel.
- `display_auto_detect=1` alone was not enough on this image.
- Live checks showed:
  - `raspberrypi-ts` existed
  - `rpi_backlight` existed and was on
  - `Jivelite` was running
  - `fb0` had pixel data
  - `fb1` was blank

Fix:

- install `pcp-jivelite`
- set audio/player config back to the intended values:

```text
NAME="RPi3-FiiO"
OUTPUT="hw:CARD=K3"
AUDIO="USB"
SERVER_IP="192.168.100.67"
```

- set this in `pcp.cfg`:

```text
JIVELITE="yes"
JL_FRAME_BUFFER="/dev/fb0"
```

- change `PCP_BOOT/config.txt` to:

```text
# display_auto_detect=1
dtoverlay=vc4-kms-v3d
dtoverlay=vc4-kms-dsi-7inch
```

- backup and reboot

Result:

- touchscreen UI came alive
- `Jivelite` displayed correctly
- touch input worked
- `squeezelite` came back as `RPi3-FiiO` on `hw:CARD=K3`
- `JogglerSkin` proved to be the best current fit for the official `7"` touchscreen

## Metadata Genre Normalization

If some albums lost or got wrong `GENRE` tags during `WAV -> FLAC` conversion, use:

```text
scripts/normalize-audio-library-tags.py
```

Default bucket mappings already include:

- `misc -> Pop Rock`
- `exyu -> ExYU`

Dry-run `misc`:

```bash
python3 scripts/normalize-audio-library-tags.py \
  --music-root /Volumes/xnas/music \
  --include-bucket misc \
  --set-genre
```

Apply `misc`:

```bash
python3 scripts/normalize-audio-library-tags.py \
  --music-root /Volumes/xnas/music \
  --include-bucket misc \
  --set-genre \
  --apply
```

Dry-run `exyu`:

```bash
python3 scripts/normalize-audio-library-tags.py \
  --music-root /Volumes/xnas/music \
  --include-bucket exyu \
  --set-genre
```

Apply `exyu`:

```bash
python3 scripts/normalize-audio-library-tags.py \
  --music-root /Volumes/xnas/music \
  --include-bucket exyu \
  --set-genre \
  --apply
```

If only compilation folders are wrong, narrow it first:

```bash
python3 scripts/normalize-audio-library-tags.py \
  --music-root /Volumes/xnas/music \
  --include-bucket misc \
  --artist-folder "Various Artists" \
  --set-genre
```

After applying changes, run LMS:

- `Settings -> Basic Settings -> Rescan Music Library`
- use `Look for new and changed media files`

### CUE sidecar warning

If a single-image `FLAC+CUE` rip is split into individual track files, do not keep the `.cue` file in the final library folder.

Why:

- LMS reads `REM GENRE` from `.cue` files
- old cue metadata can create extra genre buckets even when the split FLAC tracks are tagged correctly

The current `scripts/promote-cd-rip-album.sh` now skips copying `.cue` files into the destination album folder when it had to split an image via CUE.

## Jivelite Screen Sleep

For the `RPi3` official `7"` touchscreen in `Jivelite`:

- `Settings -> Screen -> Screensavers -> Delay -> 15 minutes`
- `Settings -> Screen -> Screensavers -> When stopped -> Display Off`

Important:

- `When stopped` is the normal idle/paused path to test first
- `When off -> Display Off` only applies after you actually turn the player off from LMS/Jivelite, it is not the same as pause/idle

## What Still Needs To Be Done

1. Decide whether the current `jivelite_flirc_config.fcfg` is final enough to treat as the canonical Jivelite remote snapshot.
2. Decide whether to change the pCP hostname from default `pCP` as a cosmetic cleanup.
3. Optionally document `Material` player-switch workflow once both Pi players are in daily use.
