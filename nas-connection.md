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
Mac (Roon Core)
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
pcm.loopout {
    type hw
    card Loopback
    device 0
    subdevice 0
}

pcm.loopin {
    type hw
    card Loopback
    device 1
    subdevice 0
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
# Bridge audio from loopback device 0 (captures what plays to device 1) to HDMI
exec arecord -D hw:Loopback,0,0 -f cd -t raw 2>/dev/null | aplay -D hdmi:CARD=vc4hdmi1,DEV=0 -f cd -t raw 2>/dev/null
```

### Systemd Service (`/etc/systemd/system/hdmi-bridge.service`)
```ini
[Unit]
Description=HDMI Audio Bridge from Loopback
After=sound.target

[Service]
Type=simple
ExecStart=/usr/local/bin/hdmi-bridge.sh
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

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
- **No automatic recovery:** If bridge crashes mid-playback, must manually restart

**More robust alternative:** USB DAC connected to Pi 5 would avoid HDMI format issues entirely. Roon natively supports USB audio without workarounds.

**Why we used HDMI:** User wanted direct HDMI to Marantz without additional hardware cost.

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
