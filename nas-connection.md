# NAS Connection Details

## Server
- **IP:** 192.168.100.83
- **Hostname:** DietPi
- **SSH:** `ssh root@192.168.100.83`

## Samba Share
- **URL:** `smb://192.168.100.83/xnas`
- **Share name:** xnas
- **User:** x
- **Pass:** aeon
- **Mount point:** `/mnt/nas`
- **Guest access:** disabled

## Access Policy
- SMB guest access is disabled on the live server.
- Authenticated access is limited to Samba user `x` for the `xnas` share.
- SMB exposure is network-local unless ports are explicitly forwarded or the NAS is bridged into another reachable network/VPN.
- If guest were enabled, it would only help devices that can already reach `192.168.100.83` over the local network.

## Network Hardware
- **Switch:** TP-Link TL-SG108E (8-port Gigabit managed)

## Setup Summary (2026-01-15)

| Component | Status |
|-----------|--------|
| RAID 1 | 2x WD Red Pro 14TB mirrored |
| Storage | ~12TB usable at `/mnt/nas` |
| Filesystem | ext4 (label: xnas) |
| Samba | Share `xnas` active |
| SMART | Monitoring both drives |
| mdmonitor | RAID health monitoring |
| Roon Bridge | Active with HDMI audio |
| HDMI Audio | Working via Loopback bridge |

## Quick Commands (SSH)

```bash
# RAID status
cat /proc/mdstat

# Disk usage
df -h /mnt/nas

# SMART health check
smartctl -a /dev/sda
smartctl -a /dev/sdb

# Samba connections
smbstatus

# Service status
systemctl status smbd smartmontools mdmonitor roonbridge hdmi-bridge

# Check audio bridge
journalctl -u hdmi-bridge -f
```

## Mac Connection

Finder → Go → Connect to Server (⌘K)
```
smb://192.168.100.83/xnas
```

## Roon Architecture (Working)

```
Windows Laptop (Roon Server)
     │
     │◄──── SMB (music files) ────── Pi 5 NAS (/mnt/nas)
     │
     └─── RAAT ───► Pi 5 Roon Bridge
                         │
                    [Loopback DEV=1] ◄── Roon plays here
                         │
                    [hdmi-bridge.sh] ◄── Reads from DEV=0
                         │
                    [hdmi: ALSA device]
                         │
                    [Mini HDMI cable]
                         │
                         ▼
                    Marantz SR5015 (Room 1)

     └─── RAAT ───► RPi 3 Bridge ───► FiiO K3 ───► PM6007 (Room 2)
```

### Current Server Setup
- Dedicated Roon Server now runs on a Windows laptop.
- Mac devices are used as Roon remotes/controllers, not as the active server.
- NAS storage remains on the Pi 5 and is accessed over SMB by the Windows server.

### Why Loopback Workaround?
- Pi 5 HDMI only supports IEC958_SUBFRAME_LE format (S/PDIF over HDMI)
- Roon sends standard PCM directly to hw: devices, bypassing ALSA plugins
- Loopback accepts PCM from Roon, bridge script converts to HDMI format

## HDMI Audio Configuration (Pi 5)

### Prerequisites (install these first)
```bash
apt-get update
apt-get install -y alsa-utils libasound2
```

**Note:** This uses pure ALSA, not PipeWire. DietPi default.

### Boot Config (`/boot/firmware/config.txt`)
```ini
dtparam=audio=on
dtoverlay=vc4-kms-v3d
```

### Kernel Module (`/etc/modules`)
```
snd-aloop
```

### ALSA Config (`/etc/asound.conf`)
```
# Loopback device for Roon - rate-adaptive configuration
# Roon writes to Loopback device 1, bridge reads from device 0
# No rate specified - accepts any rate from Roon (44.1k, 48k, 96k, 192k)
pcm.loopout {
    type plug
    slave.pcm "hw:Loopback,0,0"
    # No rate specified - accepts any rate from Roon
}

pcm.loopin {
    type plug
    slave.pcm "hw:Loopback,1,0"
    # No rate specified - accepts any rate from Roon
}

pcm.!default {
    type plug
    slave.pcm "hdmi:CARD=vc4hdmi1,DEV=0"
}

ctl.!default {
    type hw
    card vc4hdmi1
}
```

### Bridge Script (`/usr/local/bin/hdmi-bridge.sh`)
```bash
#!/bin/bash
# Bridge audio from loopback to HDMI - 192kHz for hi-res support
# Waits for HDMI connection AND Roon Bridge to start first

# Wait up to 30 seconds for HDMI to be connected
for i in {1..30}; do
    if [ "$(cat /sys/class/drm/card1-HDMI-A-2/status 2>/dev/null)" = "connected" ]; then
        break
    fi
    sleep 1
done

# Check if HDMI is connected
if [ "$(cat /sys/class/drm/card1-HDMI-A-2/status 2>/dev/null)" != "connected" ]; then
    echo "HDMI not connected, exiting"
    exit 0  # Exit cleanly, don't crash-loop
fi

# Wait for Roon Bridge to be running (so it can claim Loopback first)
for i in {1..60}; do
    if systemctl is-active --quiet roonbridge && pgrep -f RAATServer > /dev/null; then
        sleep 2  # Give Roon time to open Loopback device
        break
    fi
    sleep 1
done

# Bridge audio from Loopback device 0 (captures what Roon plays to device 1) to HDMI
# Uses plughw for automatic format/rate conversion - converts 44.1k/48k/96k to 192kHz
# Supports all sample rates: plughw: automatically converts to 192kHz
exec arecord -D plughw:Loopback,0,0 -f S32_LE -r 192000 -c 2 -t raw 2>/dev/null | \
     aplay -D plughw:vc4hdmi1,0 -f S32_LE -r 192000 -c 2 -t raw 2>/dev/null
```

### Systemd Service (`/etc/systemd/system/hdmi-bridge.service`)
```ini
[Unit]
Description=HDMI Audio Bridge from Loopback
After=sound.target roonbridge.service
Wants=roonbridge.service

[Service]
Type=simple
ExecStart=/usr/local/bin/hdmi-bridge.sh
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

**Important:** The `After=roonbridge.service` ensures Roon Bridge starts first, preventing rate locking conflicts.

### Roon Setup
1. Settings → Audio → Enable "Loopback" device
2. Rename to "Pi 5 HDMI" or similar
3. Play music - audio goes through HDMI to Marantz

## Troubleshooting HDMI Audio

```bash
# Check bridge is running
systemctl status hdmi-bridge

# Restart bridge
systemctl restart hdmi-bridge

# Check loopback module loaded
lsmod | grep snd_aloop

# Load loopback if missing
modprobe snd-aloop

# List audio devices
aplay -l

# Test HDMI directly (bypasses Roon)
speaker-test -D hdmi:CARD=vc4hdmi1,DEV=0 -c 2

# Check Roon Bridge logs
journalctl -u roonbridge -f
```

## ⚠️ Reliability Warning

This Loopback→HDMI workaround is **non-standard and potentially fragile**:

- **May break after:** Pi kernel updates, Roon Bridge updates, DietPi updates
- **If it breaks:** Re-run `modprobe snd-aloop` and restart hdmi-bridge service
- **Boot order:** Bridge waits for Roon Bridge to start first (prevents rate locking conflicts)
- **HDMI connection:** If NAS boots before Marantz is turned on, bridge waits 30 seconds then exits cleanly. Restart bridge service after turning on Marantz: `systemctl restart hdmi-bridge`
- **Rate conversion:** Bridge runs at 192kHz, `plughw:` plugin automatically converts 44.1k/48k/96k content to 192kHz - no Roon settings changes needed

**More robust alternative:** USB DAC connected to Pi 5 would avoid HDMI format issues entirely. Roon natively supports USB audio without workarounds.

**Why we used HDMI:** User wanted direct HDMI to Marantz without additional hardware cost.

## Troubleshooting: "FORMAT_NOT_SUPPORTED" After Shutdown

**Symptoms:**
- Roon shows "FORMAT_NOT_SUPPORTED" or "RAAT__OUTPUT_PLUGIN_STATUS_FORMAT_NOT_SUPPORTED" errors
- Bridge service is crash-looping: `systemctl status hdmi-bridge` shows repeated restarts
- Roon cannot connect to Loopback device

**Root Cause:**
After shutdown/reboot, if NAS boots before Marantz is turned on:
1. HDMI bridge starts → HDMI not connected → crash loop
2. During crash loop, bridge briefly locks Loopback device to wrong rate
3. Roon Bridge starts and cannot open Loopback device → format errors

**Fix Steps:**
```bash
# 1. Stop bridge service (stops crash loop)
systemctl stop hdmi-bridge

# 2. Restart Roon Bridge (so it can claim Loopback first)
systemctl restart roonbridge
sleep 5

# 3. Turn on Marantz (if not already on)
# Check HDMI connection:
cat /sys/class/drm/card1-HDMI-A-2/status
# Should show "connected"

# 4. Start bridge service (it will wait for HDMI and Roon)
systemctl start hdmi-bridge

# 5. Verify both services running
systemctl status hdmi-bridge roonbridge
# Both should show "active (running)"

# 6. Check Roon Bridge logs for connection
tail -20 /var/roon/RAATServer/Logs/RAATServer_log.txt | grep -E "Error|Warn|Loopback"
# Should show no errors, successful connection
```

**Prevention:**
- Turn on Marantz before booting NAS, OR
- Bridge automatically waits 30 seconds for HDMI, then exits cleanly
- After turning on Marantz, restart bridge: `systemctl restart hdmi-bridge`

**Why This Works:**
- Bridge waits for Roon Bridge to start first (service dependency: `After=roonbridge.service`)
- Bridge waits for HDMI connection before starting
- `plughw:` plugin automatically converts any sample rate to 192kHz
- Proper startup order prevents rate locking conflicts

## Verification Checklist (after reboot)

Run these to verify everything works after Pi restart:

```bash
# 1. Check loopback module loaded
lsmod | grep snd_aloop
# Expected: snd_aloop line present

# 2. Check hdmi-bridge service running
systemctl status hdmi-bridge
# Expected: active (running)

# 3. List audio devices
aplay -l
# Expected: Loopback AND vc4hdmi1 both present

# 4. Test HDMI audio directly (should hear white noise)
speaker-test -D hdmi:CARD=vc4hdmi1,DEV=0 -c 2 -l 1

# 5. Check Roon Bridge running
systemctl status roonbridge
# Expected: active (running)
```

**If any check fails:**
```bash
# Reload loopback module
modprobe snd-aloop

# Restart services
systemctl restart hdmi-bridge
systemctl restart roonbridge
```

## After Kernel/System Updates

If audio stops working after `apt upgrade`:

```bash
# 1. Reboot first
reboot

# 2. After reboot, check loopback loaded
lsmod | grep snd_aloop

# 3. If missing, load manually
modprobe snd-aloop

# 4. If still missing, verify /etc/modules contains snd-aloop
cat /etc/modules | grep snd-aloop

# 5. Restart bridge
systemctl restart hdmi-bridge
```

## Notes
- Pi 5 uses Mini HDMI port (need adapter or cable)
- HDMI1 (vc4hdmi1) is the one connected to Marantz
- Bridge auto-starts on boot via systemd
- If no sound, check Marantz input is set to correct HDMI
- **Alternative:** USB DAC avoids all HDMI format issues
