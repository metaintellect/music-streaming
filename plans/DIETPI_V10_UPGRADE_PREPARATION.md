# DietPi v10.2.x Update Review and Upgrade Runbook

**Created:** February 16, 2026  
**Last Reviewed:** April 15, 2026  
**Last Documented Installed Version:** DietPi v9.20.1  
**Latest Reviewed Upstream Release:** DietPi v10.2 (released March 23, 2026)  
**User-Reported Current/Target Build:** DietPi v10.2.3  
**Status:** ⚠️ **READY FOR A CONTROLLED UPDATE WINDOW** - reasonable to proceed once the NAS is reachable, backups are taken, and HDMI/Roon checks can be done immediately after the upgrade

---

## Review Outcome

### NAS Connection Details
- **SSH:** `ssh root@192.168.100.83`
- **SMB:** `smb://192.168.100.83/xnas`
- **Reference:** `nas-connection.md`

### What Was Checked On April 15, 2026
- Local NAS runbooks and connection details in this repo
- Official DietPi release information up to **v10.2**
- Existing project-specific risks around the custom HDMI bridge and Roon Bridge

### What Could Not Be Verified Live
- A read-only SSH check to `root@192.168.100.83` was attempted from this machine on **April 15, 2026**
- Result: `No route to host`
- Because of that, the currently installed DietPi version, kernel, and live service state were **not** confirmed during this review

### Safety Assessment
- **RAID/Samba/NAS basics:** low risk from the DietPi side based on current v10 release notes
- **Raspberry Pi 5 platform:** moderate risk because a DietPi update may also move kernel/packages
- **Custom HDMI bridge + ALSA loopback + Roon Bridge:** high risk, because this is custom local integration and the most likely place for a regression
- **Conclusion:** updating to current DietPi v10.2.x looks reasonable, but it is not a zero-risk update and should be treated as an audio-service maintenance window, not a casual package update

---

## Breaking Changes / Risk Areas

### System Requirements
- **Minimum Debian:** Debian 12 Bookworm
- **Minimum DietPi:** v8.0+ for direct upgrade
- **Hardware:** Raspberry Pi 5 supported ✅

### Removed Software (Not Affecting Us)
- Pydio 8 (we don't use)
- Classic ownCloud (we don't use)
- RPi Cam Web Interface (we don't use)

### What Could Break Our Setup

1. **HDMI Bridge (HIGH RISK)**
   - Kernel updates → ALSA changes → Loopback device behavior
   - Systemd changes → Service startup order
   - **Impact:** Audio playback could stop working

2. **Roon Bridge (MEDIUM RISK)**
   - May need reinstall after kernel/system updates
   - ALSA device paths might change

3. **Network Configuration (LOW RISK)**
   - Static IP config should survive, but verify

4. **RAID/Samba (LOW RISK)**
   - Should be fine, but verify after upgrade

---

## Pre-Upgrade Checklist

### 0. Read-Only Precheck When The NAS Is Reachable Again
```bash
ssh root@192.168.100.83 '
hostname
echo "--- dietpi ---"
cat /boot/dietpi/.version
echo "--- kernel ---"
uname -r
echo "--- os ---"
. /etc/os-release && printf "%s %s\n" "$NAME" "$VERSION"
echo "--- services ---"
systemctl is-active hdmi-bridge roonbridge smbd mdmonitor
echo "--- raid ---"
cat /proc/mdstat
echo "--- storage ---"
df -h /mnt/nas
echo "--- audio ---"
aplay -l
lsmod | grep snd_aloop
'
```

Expected outcome before upgrading:
- NAS reachable over SSH
- RAID healthy and mounted at `/mnt/nas`
- `smbd`, `mdmonitor`, and `roonbridge` active
- `snd_aloop` present and HDMI/loopback devices visible in `aplay -l`

### 1. Full System Backup
```bash
# Backup critical configs to NAS
sudo tar -czf /mnt/nas/dietpi-pre-v10_2-upgrade-$(date +%Y%m%d).tar.gz \
  /etc/systemd/system/hdmi-bridge.service \
  /usr/local/bin/hdmi-bridge.sh \
  /etc/asound.conf \
  /etc/network/interfaces \
  /boot/dietpi.txt \
  /opt/RoonBridge \
  /etc/samba/smb.conf \
  /etc/mdadm/mdadm.conf \
  /etc/fstab

# Verify backup
ls -lh /mnt/nas/dietpi-pre-v10_2-upgrade-*.tar.gz
```

### 2. Document Current State
```bash
# Current versions
cat /boot/dietpi/.version
cat /opt/RoonBridge/VERSION
uname -r
cat /etc/os-release | grep VERSION

# Service status
systemctl status hdmi-bridge roonbridge smbd mdmonitor

# Audio devices
aplay -l
lsmod | grep snd_aloop
```

### 3. Test Current Functionality
- [ ] Roon playback works
- [ ] HDMI audio works
- [ ] Samba share accessible
- [ ] RAID status healthy
- [ ] Network connectivity stable

---

## Upgrade Procedure (When Ready)

### Step 1: Pre-Upgrade
```bash
# 1. Stop services (optional, but safer)
systemctl stop hdmi-bridge
systemctl stop roonbridge

# 2. Create backup (see above)

# 3. Check free space (need ~100MB minimum)
df -h /
```

### Step 2: Run Upgrade
```bash
# Refresh package metadata first
apt update

# Run DietPi update
sudo dietpi-update

# Follow prompts:
# - Accept the offered upgrade
# - Review changes
# - Let it complete (may take 10-30 minutes)
```

### Step 3: Post-Upgrade Verification

#### A. System Check
```bash
# Verify DietPi version
cat /boot/dietpi/.version
# Should show: G_DIETPI_VERSION_CORE=10
# and a v10.2.x sub/build value if updated to the current release branch

# Check kernel version
uname -r
# Note: Kernel may have updated

# Check Debian version
cat /etc/os-release | grep VERSION
# Should still be Debian 13 (Trixie)
```

#### B. Critical Services Check
```bash
# 1. Check loopback module loaded
lsmod | grep snd_aloop
# If missing: modprobe snd-aloop

# 2. Check audio devices
aplay -l
# Should show: Loopback and vc4hdmi1

# 3. Check HDMI connection
cat /sys/class/drm/card1-HDMI-A-2/status
# Should show: connected

# 4. Check services
systemctl status hdmi-bridge roonbridge smbd
# All should be: active (running)
```

#### C. Test HDMI Bridge
```bash
# Test HDMI audio directly
speaker-test -D hdmi:CARD=vc4hdmi1,DEV=0 -c 2 -l 1

# Check bridge logs
journalctl -u hdmi-bridge -n 50

# Check Roon Bridge logs
tail -50 /var/roon/RAATServer/Logs/RAATServer_log.txt | grep -E "Error|Warn|Loopback"
```

#### D. Test Roon Connection
1. Open Roon on Mac
2. Check Settings → Audio
3. Verify "RPI5 Bridge Loop" or "Loopback PCM" appears
4. Try playing a track
5. Check for errors in Roon

---

## If HDMI Bridge Breaks After Upgrade

### Symptoms
- Roon shows "FORMAT_NOT_SUPPORTED" errors
- Bridge service crash-looping
- No audio output

### Fix Steps
```bash
# 1. Stop bridge
systemctl stop hdmi-bridge

# 2. Restart Roon Bridge first
systemctl restart roonbridge
sleep 5

# 3. Check if bridge script needs update
cat /usr/local/bin/hdmi-bridge.sh
# Verify it matches current working version

# 4. Check ALSA config
cat /etc/asound.conf
# Verify loopback config is correct

# 5. Reload loopback module
modprobe -r snd-aloop
modprobe snd-aloop

# 6. Restart bridge
systemctl start hdmi-bridge

# 7. Check logs
journalctl -u hdmi-bridge -f
```

### If Still Broken
1. Restore bridge script from backup
2. Check kernel/ALSA changes in release notes
3. May need to adjust bridge script for new kernel
4. Check DietPi forums for similar issues

---

## If Roon Bridge Breaks After Upgrade

### Symptoms
- Roon Bridge not detected in Roon
- Service fails to start
- Connection errors

### Fix Steps
```bash
# 1. Check Roon Bridge version
cat /opt/RoonBridge/VERSION

# 2. Check service status
systemctl status roonbridge

# 3. Check logs
journalctl -u roonbridge -n 50

# 4. May need to reinstall Roon Bridge
cd /opt
# Download latest version
curl -O https://download.roonlabs.net/builds/roonbridge-installer-linuxarmv8.sh
chmod +x roonbridge-installer-linuxarmv8.sh
yes | ./roonbridge-installer-linuxarmv8.sh

# 5. Restart service
systemctl restart roonbridge
```

---

## Rollback Plan (If Upgrade Fails)

### Option 1: Restore from Backup
```bash
# Extract backup
cd /
sudo tar -xzf /mnt/nas/dietpi-v9-backup-YYYYMMDD.tar.gz

# Restore services
systemctl daemon-reload
systemctl restart hdmi-bridge roonbridge
```

### Option 2: Reinstall DietPi v9
- Flash fresh DietPi v9 image to SD card
- Restore configs from backup
- Reinstall Roon Bridge

---

## Recommended Timeline

**As of April 15, 2026:** ✅ **GO / CONTROLLED WINDOW**
- DietPi v10.2 was released on March 23, 2026
- The initial wait period after the first v10 release has passed
- No release-note item was found that directly flags Samba, mdadm RAID, or Raspberry Pi 5 support as blocked
- The remaining concern is the custom audio bridge, so the upgrade should only be done when audio can be tested right away

**When Ready to Upgrade:**
- Follow this guide step-by-step
- Have backup ready (see Pre-Upgrade Checklist)
- Test during low-usage period
- Be prepared to rollback
- Allow 1-2 hours for upgrade + testing

---

## Current Working Configuration (Reference)

### HDMI Bridge Service
**File:** `/etc/systemd/system/hdmi-bridge.service`
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

### HDMI Bridge Script
**File:** `/usr/local/bin/hdmi-bridge.sh`
```bash
#!/bin/bash
# Bridge audio from loopback to HDMI - 192kHz for hi-res support
# Waits for HDMI connection AND Roon to start first

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
    exit 0
fi

# Wait for Roon Bridge to be running (so it can claim Loopback first)
for i in {1..60}; do
    if systemctl is-active --quiet roonbridge && pgrep -f RAATServer > /dev/null; then
        sleep 2  # Give Roon time to open Loopback device
        break
    fi
    sleep 1
done

# Bridge audio from Loopback device 0 to HDMI at 192kHz
exec arecord -D plughw:Loopback,0,0 -f S32_LE -r 192000 -c 2 -t raw 2>/dev/null | \
     aplay -D plughw:vc4hdmi1,0 -f S32_LE -r 192000 -c 2 -t raw 2>/dev/null
```

### ALSA Config
**File:** `/etc/asound.conf`
```
# Loopback device for Roon - rate-adaptive configuration
pcm.loopout {
    type plug
    slave.pcm "hw:Loopback,0,0"
}

pcm.loopin {
    type plug
    slave.pcm "hw:Loopback,1,0"
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

### Network Config
**File:** `/etc/network/interfaces`
```
# Ethernet - Static IP
allow-hotplug eth0
iface eth0 inet static
address 192.168.100.83
netmask 255.255.255.0
gateway 192.168.100.1
dns-nameservers 192.168.100.1
```

---

## Resources

- **DietPi Release Notes Index:** https://dietpi.com/docs/releases/
- **DietPi GitHub Releases:** https://github.com/MichaIng/DietPi/releases
- **DietPi Forums:** https://dietpi.com/forum/
- **Roon Bridge Downloads:** https://roon.app/en/downloads
- **This Project Docs:** See `README.md` and `nas-connection.md`

---

## Monitoring Checklist (Before Upgrading)

Before upgrading, verify:

- [ ] NAS reachable over SSH at `192.168.100.83`
- [ ] Current installed DietPi version confirmed live
- [ ] No major HDMI/audio issues reported for current v10.x in DietPi forums/GitHub
- [ ] No breaking ALSA changes in current release notes
- [ ] Kernel version compatible with current setup
- [ ] Backup created and verified
- [ ] Low-usage period scheduled for upgrade
- [ ] Rollback plan ready

## Quick Status Check

```bash
# Check current DietPi version
cat /boot/dietpi/.version

# Check current kernel
uname -r

# Verify critical services
systemctl status hdmi-bridge roonbridge smbd

# Check RAID and NAS mount
cat /proc/mdstat
df -h /mnt/nas
```

---

## Notes

- Created: February 16, 2026
- Last Updated: April 15, 2026
- Last documented installed DietPi: v9.20.1
- Latest reviewed release: v10.2 / user-reported `v10.2.3`
- Status: Ready for a controlled update once the NAS is reachable and a backup window is available
- Next Action: Run the read-only SSH precheck, then perform the upgrade with immediate HDMI/Roon verification
