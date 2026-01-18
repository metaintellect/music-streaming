# Music Server Setup Guide - RPi 5 + Roon + Multi-Room Audio

> **⚠️ CRITICAL CORRECTION (January 2025)**
>
> **Roon Server (Core) does NOT support ARM64/Raspberry Pi.** This was an error in the original plan.
>
> - Roon Server requires x86/x64 (Intel/AMD) - runs on Mac, Windows, Linux x64, or NUC
> - Roon Bridge (endpoint only) works on ARM64/Pi
> - See: https://community.roonlabs.com/t/roon-server-on-linux-on-arm64-platform-including-but-not-limited-to-raspberry-pi-5/257502
>
> **Actual working architecture:**
> - **Mac** = Roon Core (server, library management, streaming engine)
> - **RPi 5** = NAS (storage) + Roon Bridge (audio endpoint)
> - Mac reads files from Pi NAS via SMB, streams audio to Pi Bridge via RAAT

## Project Overview

Building a NAS + audio endpoint using Raspberry Pi 5 with Radxa Penta SATA HAT for storing a high-resolution audio collection (2000+ CDs, DSD, SACD ISO, FLAC). Roon Core runs on Mac (or other x86 machine), with Pi serving as network storage and Roon Bridge endpoint.

## Table of Contents

- [Hardware Components](#hardware-components)
- [Network Topology](#network-topology)
- [Audio Signal Paths](#audio-signal-paths)
- [Software Architecture](#software-architecture)
- [Setup Instructions](#setup-instructions)
  - [Phase 1: Core System Assembly](#phase-1-core-system-assembly)
  - [Phase 2: Roon Setup](#phase-2-roon-setup)
  - [Phase 3: Room 1 Setup (Pi 5 HDMI → Marantz SR5015)](#phase-3-room-1-setup-pi-5-hdmi--marantz-sr5015)
  - [Phase 4: Room 2 Setup (RPi 3 + FiiO K3)](#phase-4-room-2-setup-rpi-3--fiio-k3)
- [Roon Multi-Room Features](#roon-multi-room-features)
- [Roon Interface Overview](#roon-interface-overview)
- [Music Library Management](#music-library-management)
- [Backup Strategy](#backup-strategy)
- [Performance Expectations](#performance-expectations)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)
- [Future Expansion Ideas](#future-expansion-ideas)
- [Resources](#resources)
- [Philosophy: Ownership vs Subscription](#philosophy-ownership-vs-subscription)
- [Notes & Tips](#notes--tips)
- [Project Status](#project-status)

---

## Hardware Components

### Core System (RPi 5 Music Server)

| Component | Model | Source | Notes |
|-----------|-------|--------|-------|
| **Raspberry Pi 5** | 8GB RAM | [Berrybase.de](https://www.berrybase.de) | 4x A76 @ 2.4GHz |
| **Radxa Penta SATA HAT** | 5-port SATA | [Berrybase.de](https://www.berrybase.de) | Includes SATA cables |
| **Radxa Top Board** | OLED + Fan | [Berrybase.de](https://www.berrybase.de) | ⚠️ NOT USED - incompatible with 3.5" HDDs |
| **Active Cooler** | Official Pi 5 | [Berrybase.de](https://www.berrybase.de) | CPU cooling |
| **12V Power Supply** | MeanWell 6.67A | [Berrybase.de](https://www.berrybase.de) | Powers drives |
| **USB-C Power Supply** | Official 5V 5A | [Berrybase.de](https://www.berrybase.de) | Powers Pi 5 |
| **Hard Drive** | WD Red Pro 14TB (x2) | [Reichelt.de](https://www.reichelt.de) | WD140KFBX, 5yr warranty, RAID 1 |
| **Network Switch** | TP-Link TL-SG108E | [Chipoteka.hr](https://www.chipoteka.hr) | 8-port Gigabit managed |

### Already Owned

**Raspberry Pi & Storage:**
- 64GB microSD card (for Pi 5 OS)
- Ethernet cables
- 14TB Seagate external drive (backup/secondary storage)
- RPi 3 with official 7" touchscreen (Roon Bridge + Now Playing display for Room 2)
- USB IR receiver (for Marantz CD remote control)

**Room 1 (Home Theater) Equipment:**
- Marantz SR5015 AV receiver (5.0 system)
- Panasonic DP-UB820 (4K/UHD + Blu-ray audio player)
- Reavon UBR X110 (Universal Blu-ray player - native DSD/multichannel playback)
  - HDMI audio → Marantz SR5015 (for DSD playback)
  - HDMI video → TV (for UI/navigation)
  - Ethernet → Switch (wired network)
  - ⚠️ **SMB/CIFS client BROKEN** - Cannot authenticate to NAS (beta feature never finished)
  - **USB drive required** for DSD file access
  - Note: Company defunct, no future firmware updates
- Sony BDP-S390 (SACD ripper - rare capability!)

**Room 2 (Stereo Listening) Equipment:**
- Marantz PM6007 integrated amplifier (Class A/B, digital inputs)
- Marantz CD6007 CD player
- ONKYO A-9110 integrated amplifier (Class A/B, pure analog)
- FiiO K3 USB DAC
- Pro-Ject Debut Carbon Esprit turntable (Ortofon 2M Red cartridge)
- ifi Zen Phono preamp (dedicated phono stage, MM/MC)
- Sony TC-K661S cassette deck (3-head)

**Collection Size:**
- ~700 vinyl records
- ~2200+ CDs (including 200+ from 8 King Crimson complete boxsets)
- ~1000 cassettes
- ~700 4K/Blu-ray/DVD (450 movies, 250 concerts/documentaries)
- Plus numerous CD/DVD and CD/Blu-ray hybrid releases
- **Total: ~4600+ physical media items**

---

## Network Topology

```
Main Router (WiFi only access)
         |
    ┌────┴────┐
    |         |
 MacBook   TP-Link AC750
  Pro        (WiFi Bridge)
 (WiFi)          |
  CORE    TP-Link TL-SG108E Switch (8-port Gigabit)
    |            |
    |     ┌──────┼─────────┬──────────┐
    |     |      |         |          |
    └─────┤    RPi5     Marantz      TV
   (SMB)  |   (NAS +    SR5015
          |   Bridge)   (HDMI in)
          |     |  \
          |   14TB  Mini HDMI ───► Marantz
          |   RAID1
          |
         RPi3
    (Bridge + Display)
      7" Touchscreen
       + IR Remote
           |
        FiiO K3
           ↓
      Marantz PM6007
```

### Network Details

- **MacBook Pro (Roon Core):** WiFi - reads from NAS, streams to endpoints
- **RPi 5 (NAS + Bridge):** Wired Gigabit - serves files via SMB, also audio endpoint
- **RPi 3 (Roon Bridge):** Wired - Room 2 audio endpoint with touchscreen display
- **Reavon UBR X110:** Wired Gigabit - DSD player, **USB drive only** (SMB broken)
- **Marantz SR5015:** Wired Gigabit - Room 1 receiver (HDMI inputs from Pi 5 + Reavon)
- **TV:** Wired - for Reavon UI/navigation

### Data Flow

```
Mac (Core) ◄──── SMB ──── RPi 5 NAS (/mnt/nas)
    │                         │
    │                         │
    ├─── RAAT (audio) ───────►│ Roon Bridge
    │                         │     ↓
    │                         │ [Loopback → hdmi-bridge → HDMI]
    │                         │     ↓
    │                         └───► Marantz SR5015 (HDMI input)
    │
    └─── RAAT ───► RPi 3 (Bridge) → FiiO K3 → PM6007
```

**Why this works despite Mac on WiFi:**
- SMB file access is buffered (not real-time)
- RAAT protocol buffers ~5 seconds ahead
- Audio dropouts unlikely unless WiFi is very unstable

**HDMI Audio Path (Pi 5 → Marantz):**
- Roon Bridge plays to ALSA Loopback device
- hdmi-bridge service pipes Loopback → HDMI
- Mini HDMI cable connects Pi 5 to Marantz HDMI input

---

## Audio Signal Paths

### Room 1 (Living Room - Main System)

**Path 1: Roon Streaming (PCM/FLAC)**
```
Mac (Roon Core)
    ↓ Network (RAAT)
RPi 5 (Roon Bridge)
    ↓ Loopback → hdmi-bridge
Mini HDMI cable
    ↓
Marantz SR5015 (AV Receiver - HDMI input 1)
    ↓ Speaker outputs
Speakers
```

**Connection:** HDMI from Pi 5 Roon Bridge to Marantz
**Why HDMI over network streaming:**
- UPnP/DLNA not supported by Roon (only AirPlay/Chromecast)
- AirPlay limited to CD quality (16-bit/44.1kHz)
- HDMI carries full quality audio from Roon Bridge

**Path 2: Native DSD Playback (DSD64/multichannel)**
```
USB Drive (with DSD files copied from NAS)
    ↓
Reavon UBR X110
    ↓ HDMI audio
Marantz SR5015 (AV Receiver - HDMI input 2)
    ↓ Speaker outputs
Speakers (including multichannel 5.1 for SACD)
```

**Why Reavon for DSD:**
- **Native DSD playback** - No PCM conversion (Roon converts DSD→PCM)
- **Multichannel support** - 5.1 SACD playback from DSD files
- **Plays DSF/DFF/ISO files** from USB drive
- **Better for audiophile DSD** - Preserves native DSD bitstream

**Why USB instead of NAS:**
- Reavon's SMB/CIFS client is broken (beta feature never completed)
- Company defunct (no future firmware updates)
- USB is only reliable method for file access

**Use Reavon when:**
- Playing DSD64 files (SACD rips)
- Want multichannel SACD audio (5.1)
- Prefer native DSD without conversion

**Use Roon when:**
- Playing FLAC, WAV, MP3 (standard formats)
- Want multi-room sync or playlists
- PCM conversion acceptable (still high quality)

### Room 2 (Stereo Listening Room)

**Digital Path (Roon Streaming):**
```
Mac (Roon Core)
    ↓ Network (RAAT)
RPi 3 (RoPieeeXL - Roon Bridge + Display)
    ├─ 7" Touchscreen (Now Playing display)
    ├─ USB IR receiver (Marantz remote control)
    └─ USB audio output
         ↓
Option A: Direct to PM6007 USB input (uses PM6007's DAC)
Option B: FiiO K3 (external DAC) → PM6007 analog input
    ↓
Marantz PM6007 (Integrated Amplifier)
    ↓ Speaker outputs
Stereo Speakers (preferred pair)
```

**Display features:**
- Shows album art, track info, time remaining
- Touch controls: play/pause, skip, volume
- IR remote: Control playback from couch with Marantz CD remote
- Screensaver dims after inactivity

**Analog Sources:**
```
Pro-Ject Debut Carbon Esprit
    ↓
ifi Zen Phono (dedicated preamp, bypasses PM6007 internal phono)
    ↓ Line level
PM6007 Line Input

Sony TC-K661S (cassette) → PM6007 Tape/Aux input
Marantz CD6007 → PM6007 Digital or Analog inputs
```

**Alternative Amplifier:**
- ONKYO A-9110 (Class A/B, pure analog) available for A/B comparison or specific source preferences
- Can use speaker selector switch to toggle between PM6007 and Onkyo A-9110

**Note:** PM6007 has built-in DAC (AK4490), USB input, and digital inputs (coaxial/optical), making external DAC optional.

---

## Software Architecture

### Roon Client-Server Model (Corrected)

```
┌─────────────────────────────────────────┐
│    MacBook Pro - Roon Core (Server)     │
│  • Music library management             │
│  • Metadata enrichment                  │
│  • Audio streaming engine               │
│  • Reads from: smb://192.168.100.83/xnas│
└───────────┬─────────────────────────────┘
            │
       Network (WiFi to wired)
            │
    ┌───────┼─────────────────────┬───────────────────┬───────────────────┐
    │       │                     │                   │                   │
    ↓       ↓                     ↓                   ↓                   ↓
┌───────────────────┐ ┌─────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ RPi 5 (NAS +      │ │ Room 2      │ │ Control UI      │ │ Reavon UBR X110 │
│ Roon Bridge)      │ │ RPi 3       │ │ iPhone/iPad     │ │ (DSD Player)    │
│      ↓            │ │ (Bridge)    │ │ (Roon Remote)   │ │  ↓ HDMI audio   │
│ Mini HDMI cable   │ │ + FiiO K3   │ └─────────────────┘ │  ↓ HDMI video   │
│      ↓            │ │      ↓      │                     │  ├──► Marantz    │
│ Marantz SR5015 ◄──┼─────────────────────────────────────┤  └──► TV         │
│ (Room 1 - HDMI)   │ │ Marantz     │                     │ (NAS via SMB)   │
└───────────────────┘ │ PM6007      │                     └─────────────────┘
                      └─────────────┘

Storage:
┌─────────────────────────────────────────┐
│    RPi 5 - NAS (DietPi + Samba)         │
│  • 2x 14TB WD Red Pro in RAID 1         │
│  • Mount: /mnt/nas                      │
│  • Share: smb://192.168.100.83/xnas     │
│  • Also runs: Roon Bridge               │
└─────────────────────────────────────────┘
```

**Key Principle:**
- **Roon Core** (Mac) = Heavy lifting, must be running for playback
- **Roon Bridge** (RPi 5, RPi 3) = Lightweight audio endpoints
- **NAS** (RPi 5) = Storage server, accessible via SMB
- **Audio path:** Mac Core → Network → Bridge → DAC

**Limitation:** Mac must be on and Roon running for any playback. This is unavoidable without x86 hardware for Core.

---

## Setup Instructions

### Phase 1: Core System Assembly

#### 1.1 Hardware Assembly

**Stack order (bottom to top):**
1. Raspberry Pi 5 with Active Cooler installed
2. Radxa Penta SATA HAT (connects via GPIO + FFC PCIe cable)
3. Radxa Top Board (OLED display + fan)
4. Hard drives mounted in Radxa HAT bays

**Connections:**
- 14TB WD Red Pro → SATA port on Radxa HAT (cable included)
- 12V PSU → Radxa HAT power input
- USB-C PSU → Raspberry Pi 5 power
- Ethernet cable → Pi 5 → TP-Link switch
- MicroSD card with OS → Pi 5

**Assembly time:** ~30 minutes

#### 1.2 Operating System Installation

**Recommended OS:** DietPi (lightweight) or Raspberry Pi OS Lite

```bash
# Flash DietPi to microSD card
# Insert card, power on Pi 5
# SSH into Pi (default: dietpi/dietpi)
ssh dietpi@192.168.1.xxx

# Update system
sudo apt update && sudo apt upgrade -y

# Check drive detection
lsblk
# Should see /dev/sda (14TB drive)

# Format drive (if new)
sudo mkfs.ext4 /dev/sda

# Create mount point
sudo mkdir -p /mnt/music

# Mount drive
sudo mount /dev/sda /mnt/music

# Add to fstab for auto-mount
echo "/dev/sda /mnt/music ext4 defaults 0 2" | sudo tee -a /etc/fstab

# Verify
df -h
```

#### 1.3 Samba (SMB) File Share Setup

```bash
# Install Samba
sudo apt install samba samba-common-bin -y

# Configure Samba
sudo nano /etc/samba/smb.conf

# Add at end of file:
[music]
   path = /mnt/music
   browseable = yes
   read only = no
   guest ok = no
   valid users = yourusername
   create mask = 0775
   directory mask = 0775

# Set Samba password
sudo smbpasswd -a yourusername

# Restart Samba
sudo systemctl restart smbd

# Enable on boot
sudo systemctl enable smbd
```

**Test from Mac:**
- Finder → Go → Connect to Server (Cmd+K)
- `smb://192.168.1.xxx/music`
- Enter credentials

---

### Phase 2: Roon Setup

> **⚠️ IMPORTANT:** Roon Server (Core) does NOT run on ARM64/Raspberry Pi.
> The Pi runs Roon Bridge (endpoint only). Core must run on Mac/PC/NUC.

#### 2.1 Install Roon Bridge on RPi 5

```bash
# SSH into Pi
ssh root@192.168.100.83

# Install dependencies
apt-get install -y bzip2 alsa-utils libasound2

# Download and run Roon Bridge installer
cd /opt
curl -O https://download.roonlabs.net/builds/roonbridge-installer-linuxarmv8.sh
chmod +x roonbridge-installer-linuxarmv8.sh
yes | ./roonbridge-installer-linuxarmv8.sh

# Verify running
systemctl status roonbridge
```

#### 2.2 Install Roon Core on Mac

1. Download Roon from https://roon.app/en/downloads
2. Install and open Roon app
3. Sign in or create Roon account
4. Start 14-day trial (or enter license)

#### 2.3 Mount NAS on Mac

**One-time setup:**
```bash
# From Mac Terminal, or use Finder → Go → Connect to Server (⌘K)
open smb://192.168.100.83/xnas
# Enter credentials: user=x, pass=aeon
# Check "Remember this password in my keychain"
```

**Auto-mount on login (optional):**
1. System Settings → General → Login Items
2. Click "+" and add the mounted share
3. OR: Just connect once with "Remember password" - macOS often auto-reconnects

**Note:** `/etc/fstab` doesn't work reliably for SMB on macOS. Use Login Items instead.

#### 2.4 Configure Roon Storage

**In Roon on Mac:**
1. Settings → Storage → Add Folder
2. Navigate to mounted NAS share
3. Select the music folders (00_DSD, music, 00_flac_new, etc.)
4. Roon scans library (takes 1-2 hours for large collections)

> **Next:** Proceed to **Phase 3** (HDMI audio setup) or **Phase 4** (Room 2 setup).

---

### Phase 3: Room 1 Setup (Pi 5 HDMI → Marantz SR5015)

> **Note:** Roon doesn't support UPnP/DLNA streaming to receivers like the Marantz SR5015.
> AirPlay is limited to CD quality. HDMI from Pi 5 Roon Bridge provides full quality.

#### 3.1 Enable HDMI Audio on Pi 5

**SSH into Pi 5:**
```bash
ssh root@192.168.100.83
```

**Install prerequisites (ALSA, not PipeWire):**
```bash
apt-get update
apt-get install -y alsa-utils libasound2
```

**Edit boot config:**
```bash
nano /boot/firmware/config.txt
```

Add/modify:
```ini
dtparam=audio=on
dtoverlay=vc4-kms-v3d
```

**Enable loopback module (persistent):**
```bash
echo "snd-aloop" >> /etc/modules
modprobe snd-aloop
```

**Create ALSA config:**
```bash
cat > /etc/asound.conf << 'EOF'
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
EOF
```

#### 3.2 Create HDMI Bridge Service

**Create bridge script:**
```bash
cat > /usr/local/bin/hdmi-bridge.sh << 'EOF'
#!/bin/bash
# Bridge audio from loopback device 0 (captures what plays to device 1) to HDMI
exec arecord -D hw:Loopback,0,0 -f cd -t raw 2>/dev/null | aplay -D hdmi:CARD=vc4hdmi1,DEV=0 -f cd -t raw 2>/dev/null
EOF
chmod +x /usr/local/bin/hdmi-bridge.sh
```

**Create systemd service:**
```bash
cat > /etc/systemd/system/hdmi-bridge.service << 'EOF'
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
EOF
```

**Enable and start:**
```bash
systemctl daemon-reload
systemctl enable hdmi-bridge
systemctl start hdmi-bridge
```

**Reboot for HDMI audio:**
```bash
reboot
```

#### 3.3 Configure Roon for HDMI

**In Roon Remote:**
1. Settings → Audio
2. Look for **"Loopback"** under DietPi
3. Click → **Enable**
4. Rename to: "Pi 5 HDMI" or "Living Room"
5. Connect Mini HDMI cable from Pi 5 to Marantz HDMI input
6. Set Marantz input to correct HDMI
7. Test playback

**Signal path:**
```
Roon Core (Mac) → RAAT → Pi 5 Bridge → Loopback → hdmi-bridge → HDMI → Marantz
```

#### 3.4 Why Loopback Workaround is Needed

**The problem:**
- Pi 5 HDMI audio only supports IEC958_SUBFRAME_LE format (S/PDIF over HDMI)
- Roon sends standard PCM (S16_LE, S24_LE) directly to `hw:` devices
- Roon bypasses ALSA plugins like `hdmi:` that handle format conversion
- Result: "FORMAT_NOT_SUPPORTED" errors when Roon tries direct HDMI

**The solution:**
- Loopback device accepts standard PCM formats from Roon
- Bridge script reads from Loopback and plays through `hdmi:` device
- `hdmi:` ALSA plugin handles IEC958 format conversion
- Audio flows: Roon → Loopback → Bridge → hdmi: → HDMI cable → Marantz

**Limitations:**
- Fixed at CD quality (16-bit/44.1kHz) in current config
- For higher resolution, modify `-f cd` in bridge script to match source format

**⚠️ Reliability Warning:**
This Loopback→HDMI workaround is non-standard and may break after:
- Pi kernel updates
- Roon Bridge updates
- DietPi system updates

**More robust alternative:** USB DAC connected directly to Pi 5 avoids all HDMI format issues. Roon natively supports USB audio. However, HDMI was chosen to avoid additional hardware cost.

See `nas-connection.md` for verification checklist and recovery steps.

#### 3.5 Roon DSD Playback Limitation

**Important:** Roon converts DSD files to PCM before streaming to Roon Bridge endpoints.

- DSD → PCM conversion happens at Roon Core (Mac)
- Converted PCM is streamed to Pi 5 Bridge
- Still high quality, but not native DSD
- For native DSD playback, use Reavon UBR X110 (see below)

---

### Phase 3.5: Reavon UBR X110 DSD Player Setup

> **Note:** For native DSD playback (DSD64, multichannel SACD) without PCM conversion.
> **⚠️ IMPORTANT:** Reavon's SMB client is broken. USB drive is required.

#### 3.5.1 Reavon Hardware Setup

**Physical connections:**
1. Connect HDMI (audio) from Reavon to Marantz SR5015 input 2
2. Connect HDMI (video) from Reavon to TV (for UI/navigation)
3. Connect Ethernet to TP-Link switch (optional - not used for file access)
4. Power on Reavon

#### 3.5.2 USB Drive Preparation (Primary Method)

**⚠️ Reavon SMB/CIFS is broken - USB is the only working method.**

**Prepare USB drive on Mac:**
1. Format USB drive: exFAT or FAT32 (for compatibility)
2. Copy DSD files from NAS to USB:
   ```bash
   # Mount NAS if not already mounted
   open smb://x@192.168.100.83/xnas

   # Copy DSD folder to USB (replace YOUR_USB with drive name)
   rsync -avh --progress /Volumes/xnas/00_DSD/ /Volumes/YOUR_USB/DSD/

   # Or copy specific albums
   cp -R /Volumes/xnas/00_DSD/Artist/Album /Volumes/YOUR_USB/DSD/
   ```
3. Safely eject USB drive
4. Plug into Reavon USB port

**On Reavon:**
1. Navigate to: USB or Storage menu
2. Browse to DSD folder
3. Select album/track to play

**File formats supported:**
- DSF (DSD64 stereo/multichannel)
- DFF (DSD64 stereo/multichannel)
- ISO (SACD disc images - may work depending on Reavon firmware)

**Workflow for adding new DSD files:**
1. Rip SACD to NAS (using Sony BDP-S390)
2. Periodically sync USB drive with new rips:
   ```bash
   rsync -avh --progress /Volumes/xnas/00_DSD/ /Volumes/YOUR_USB/DSD/
   ```
3. Update USB drive in Reavon

#### 3.5.3 SMB Access (Broken - Documented for Reference)

**⚠️ DO NOT ATTEMPT - SMB/CIFS client is non-functional.**

**Testing performed:**
- Firmware: Latest available (no future updates - company defunct)
- Server discovery: Works (sees "DietPi" server)
- Authentication: **FAILS** with all credential formats tested:
  - `x` / `aeon`
  - `DIETPI\x` / `aeon`
  - `WORKGROUP\x` / `aeon`
  - Guest access (blank credentials)
- Result: "Login Error" on all attempts
- Mac/Windows SMB access: Works fine (issue is Reavon-specific)
- Conclusion: Beta SMB feature was never completed before company closure

**Why it failed:**
- Reavon SMB/CIFS client is beta quality
- Company (Reavon) went out of business
- No future firmware updates possible
- Feature was never finished/debugged

#### 3.5.4 Marantz SR5015 Input Configuration

**Set up HDMI input for Reavon:**
1. Marantz menu → Input Settings
2. Select HDMI input (e.g., HDMI 2)
3. Rename to: "Reavon DSD" or "SACD Player"
4. Audio input: HDMI (not analog)
5. Save

**Switching between sources:**
- **Pi 5 (Roon):** Select HDMI input 1 on Marantz
- **Reavon (DSD):** Select HDMI input 2 on Marantz

---

### Phase 4: Room 2 Setup (RPi 3 + Touchscreen Display + FiiO K3)

> **Note:** This setup uses RPi 3 with official touchscreen for Now Playing display and touch/IR remote control.

#### 4.1 Install RoPieeeXL on RPi 3

**Download:** https://ropieee.org (select XL version)

**RoPieeeXL vs RoPieee:**
- **RoPieee:** Basic Roon Bridge (headless endpoint)
- **RoPieeeXL:** Roon Bridge + Now Playing display + touch controls + IR remote support ✅

**Installation:**
1. Flash RoPieeeXL image to microSD card (use Etcher/RPi Imager)
2. Insert in RPi 3
3. Connect hardware:
   - Official RPi touchscreen (DSI connector)
   - Ethernet cable (or WiFi)
   - FiiO K3 USB DAC via USB
   - USB IR receiver (for Marantz CD remote control)
   - Power (5V 2.5A minimum)
4. Boot Pi (takes 2-3 minutes first time)
5. Screen shows RoPieeeXL boot, then Now Playing interface

#### 4.2 Configure RoPieeeXL

**Web interface:**
1. Browse to: `http://ropieee.local` (from Mac/phone on same network)
2. **Audio** tab:
   - Zone name: "Second Room" or "Stereo Room"
   - USB DAC: Should auto-detect FiiO K3
   - Save
3. **Display** tab (XL only):
   - Enable display: **On**
   - Display type: **Official 7" touchscreen** (auto-detected)
   - Rotation: Adjust if needed (0°, 90°, 180°, 270°)
   - Brightness: Adjust to preference
   - Screensaver: Optional (dims after inactivity)
   - Save
4. **Remote** tab (XL only):
   - Enable IR remote: **On**
   - Remote type: Generic or test buttons
   - Test: Press buttons on Marantz remote, verify RoPieeeXL responds
   - Mapping: Map play/pause/skip/volume to remote buttons
   - Save
5. **Network** tab:
   - Configure WiFi if using wireless (Ethernet preferred)
6. Reboot

**Touchscreen Controls:**
- Tap album art to open zone selector
- Swipe left/right to skip tracks
- Tap play/pause button
- Tap volume slider to adjust
- Shows album art, track info, time remaining

**IR Remote Controls (with USB receiver):**
- Play/Pause: Marantz remote play button
- Skip: Next/Previous track buttons
- Volume: Up/Down buttons
- Zone switching: Configurable

#### 4.3 Physical Setup

**Mounting options:**
1. Official RPi touchscreen case
2. Desktop stand (angled for viewing)
3. Wall mount (VESA adapter available)

**Cable management:**
- Ethernet to switch
- USB to FiiO K3 DAC
- USB to IR receiver (small dongle)
- Power cable (use official RPi PSU or 5V 2.5A+)

#### 4.4 Enable in Roon

**In Roon Remote:**
1. Settings → Audio
2. **"RoPieee"** or **"Second Room"** appears
3. Enable
4. Test playback

**Signal path:**
```
Roon Core (Mac) → Network → RPi 3 (Roon Bridge) → USB → FiiO K3 → PM6007
```

---

## Roon Multi-Room Features

### Independent Playback (Different Music Per Room)

**In Roon Remote:**

1. Tap zone selector at top
2. Choose **"Living Room"**
3. Play album/playlist A
4. Tap zone selector again
5. Choose **"Second Room"**
6. Play album/playlist B

**Result:** Different music in each room simultaneously.

**Use cases:**
- Jazz in living room, rock in office
- Quiet classical while working, louder music elsewhere
- Different family member preferences

### Grouped Zones (Synchronized Audio)

**Create group:**
1. Settings → Audio
2. Select both zones
3. Click **"Group"**
4. Name: "Whole House" or "Both Rooms"

**Playing to group:**
1. Tap zone selector
2. Choose **"Whole House"** (grouped zone)
3. Play music
4. **Both rooms play identical audio, perfectly synced**

**Volume control:**
- Master volume: controls both
- Individual: adjust per room

**Use cases:**
- Party/gathering (same music everywhere)
- Background music throughout home
- Moving between rooms (music follows)

### Zone Transfer

**While playing in one room:**
1. Tap zone selector
2. Choose different room
3. Music **transfers** to new room
4. Previous room stops

**Quick switch:** Swipe between zones in Now Playing screen.

---

## Roon Interface Overview

### Now Playing Screen

```
┌─────────────────────────────┐
│  Zone: Living Room      [▼] │ ← Tap to switch/group zones
├─────────────────────────────┤
│                             │
│     [Album Art]             │
│                             │
│  Track: Blue in Green       │
│  Album: Kind of Blue        │
│  Artist: Miles Davis        │
│                             │
│  ●━━━━━○━━━━━━━━━━━━  3:42 │
│                             │
│      ⏮  ⏸  ⏭               │
│                             │
│  🔊 ▬▬▬▬▬▬○▬▬▬▬▬  Volume   │
│                             │
│  Signal Path: Lossless  [i] │ ← Tap for audio path details
└─────────────────────────────┘
```

### Zone Selector

```
┌─────────────────────────────┐
│  Select Audio Zone          │
├─────────────────────────────┤
│  ♪ Living Room   [Playing]  │
│     Miles Davis - Kind...   │
│                             │
│  ○ Second Room   [Ready]    │
│                             │
│  ⊕ Whole House   [Group]    │
│     (Both rooms synced)     │
│                             │
│  + Transfer to Zone...      │
└─────────────────────────────┘
```

### Multi-Zone Control

**In Browse/Library view:**
- See all zones at bottom
- Tap zone to see what's playing
- Drag tracks to zones to play
- Queue management per zone

**Queue management:**
- Each zone has independent queue
- See upcoming tracks
- Reorder, remove, add to queue

---

## Music Library Management

### Current Library Organization (January 2026)

**Library structure on NAS (`/mnt/nas/`):**
```
CD_RIP/                    → Staging area (empty - for new rips only)
music/
  ├── metal/               → 23 artists, 64 albums
  ├── exyu/                → 241 albums (ex-Yugoslavia music)
  ├── Basil Poledouris/    → Conan soundtrack
  ├── Miyako/              → Metal on piano
  ├── classical/           → (not yet imported to Roon)
  ├── jazz/                → (future)
  └── [other albums]
```

**Naming convention (all albums):**
- Format: `Artist/Album (Year)/tracks`
- Multi-disc: `Artist/Album (Year)/CD01/tracks`, `/CD02/`, etc.
- No disc count suffixes in folder names (e.g., no "(2CD)", "(Single)")

**Workflow:**
1. Rip CDs to `CD_RIP/Artist/Album (Year)/`
2. Run `/root/fix-multidisc.sh` if multi-disc (adds zero-padding)
3. Move to appropriate genre folder (`music/metal/`, `music/exyu/`, etc.)
4. Roon auto-detects new albums in watched `music/` folder

**Scripts available:**
- `fix-multidisc.sh` - Renames CD1-CD9 → CD01-CD09, cleans ._ files
- `restructure-exyu.sh` - Converts old naming to new format (already run)

**Roon Configuration:**
- **Watched folder:** `/mnt/nas/music/` (all subfolders)
- **Not watched:** `/mnt/nas/CD_RIP/` (staging only)

See `plans/2026_01_17_PLAN-music-library-organization.md` for full details.

### SACD Ripping with Sony BDP-S390

**Special capability - SACD ISO extraction:**

The Sony BDP-S390 is one of the rare Blu-ray players capable of ripping SACD discs to ISO format (DSD layer). This allows:
- Digital preservation of SACD collection
- Store on 14TB drive alongside other music
- Play via Roon, Audirvana, or compatible players
- Keep physical disc as backup

**SACD ripping workflow:**
1. Insert SACD disc into Sony BDP-S390
2. Use SACD ripper software/method (various tools available)
3. Extract to ISO file (preserves DSD layer)
4. Store on music server (14TB drive)
5. Add to Roon library for streaming access

**Result:** Own the music physically (disc) AND digitally (ISO on your hardware).

---

### Organizing Files on Disk

**Recommended structure:**
```
/mnt/music/
├── Artist Name/
│   ├── Album Name (Year)/
│   │   ├── 01 - Track Title.flac
│   │   ├── 02 - Track Title.flac
│   │   └── cover.jpg
│   └── Another Album/
├── Various Artists/
└── Singles/
```

**File naming tips:**
- Use consistent format
- Include track numbers
- Avoid special characters
- Embed album art in files (or folder.jpg)

### Roon Library Scanning

**After adding files to /mnt/music:**
1. Roon auto-scans every few minutes
2. Or: Settings → Storage → [music folder] → **"Force Rescan"**

**Roon processing:**
- Reads file tags (artist, album, genre, etc.)
- Matches to online databases (MusicBrainz, Rovi, AllMusic)
- Fetches high-res album art
- Adds artist bios, reviews, credits
- Links related artists/albums

### Handling Duplicates

**Roon duplicate detection:**
1. Browse → Albums
2. Focus → Inspector → **"Duplicates"**
3. Shows all duplicate albums
4. View file paths for each version
5. Choose: Keep both or merge

### Manual Metadata Editing

**Edit album info:**
1. Browse to album
2. Click **"..."** menu → **"Edit"**
3. Edit:
   - Title, artist, date
   - Genre, tags
   - Credits (producer, engineer, etc.)
   - Album art (drag & drop)

**Identify/Re-identify album:**
1. Album menu → **"Identify Album"**
2. Search by title/artist/barcode
3. Select correct match
4. Roon updates metadata

### Tags and Organization

**Custom tags:**
- Create tags: "DSD", "SACD", "Favorites", "Party", etc.
- Apply to albums or tracks
- Filter library by tags
- Use in playlists

---

## Backup Strategy

### Current Setup

**Primary Storage:**
- 2x 14TB WD Red Pro in RAID 1 (mirrored)
- ~14TB usable capacity
- 5-year warranty, 24/7 operation rated

**Important:** RAID 1 provides **redundancy** (protects against drive failure), NOT **backup** (protects against deletion/corruption/ransomware). If you accidentally delete files or they get corrupted, both RAID drives are affected.

### Backup Options

#### Option 1: External USB Drive (Current - 14TB Seagate)
**Recommended approach:**
- Keep external drive **disconnected** when not backing up
- Periodic manual sync (weekly/monthly)

**Backup script:**
```bash
#!/bin/bash
# Plug in Seagate, then run:
rsync -avh --delete /mnt/nas/ /mnt/backup/

# When done, unmount and disconnect drive for offline protection
umount /mnt/backup
```

**Why offline?** Protects against:
- Accidental deletion
- Ransomware
- Filesystem corruption

#### Option 2: Cloud Backup (For irreplaceable content)
- Backblaze B2, Wasabi, etc.
- For rare DSD, personal rips, out-of-print recordings
- Expensive for full 14TB (~€60-100/year)
- Consider backing up only irreplaceable content (~1-2TB)

---

## Performance Expectations

### Current Setup (RPi 3 + USB 2.0)
- Library browsing: Slow, laggy
- File transfers: ~30 MB/s max
- Network + USB shared bus: Bottleneck
- Roon Server: Struggles

### Actual Setup (Mac Core + RPi 5 NAS/Bridge)
- Library browsing: **Fast** (depends on Mac)
- NAS file transfers: **~100 MB/s** (Gigabit Ethernet)
- Roon Core on Mac: **Smooth** (Mac handles processing)
- RPi 5 as NAS: **24/7 storage server**
- RPi 5 as Bridge: **Lightweight endpoint**

**RPi 5 NAS benefits:**
- RAID 1: **14TB mirrored** (data protection)
- PCIe SATA: **Fast local disk I/O**
- Low power: **~21-25W 24/7** (RPi 5 + 2x HDDs)
- Wired network: **Reliable streaming**

**Limitation:**
- Mac must be running for Roon playback
- WiFi dependency for Mac → NAS file reads (buffered, usually fine)

---

## Troubleshooting

### Common Issues

#### Roon Core Issues (Mac)
- Ensure Roon app is running on Mac
- Check Mac has network connectivity
- Verify NAS is mounted: `ls /Volumes/xnas` or check Finder
- Restart Roon app if needed
- Check firewall: Roon needs ports 9003, 9100-9200

#### Roon Bridge Not Detected
- Check RPi 5 is powered and booted
- Verify network connectivity: `ping 192.168.100.83`
- Check Roon Bridge status: `ssh root@192.168.100.83 'systemctl status roonbridge'`
- Restart service: `ssh root@192.168.100.83 'systemctl restart roonbridge'`

#### Drive Not Mounting
- Check physical SATA connection
- Verify power to Radxa HAT (12V PSU)
- Check drive detection: `lsblk`
- Check filesystem: `sudo fsck /dev/sda`
- Re-mount: `sudo mount -a`

#### Slow Network Performance
- Verify Gigabit link: `ethtool eth0` (should show 1000Mb/s)
- Check switch ports (green lights = gigabit)
- Test speed: `iperf3` between devices
- Replace Cat5 cables with Cat6 if needed

#### Audio Dropouts/Stuttering
- Check network stability
- Verify RPi 5 isn't thermal throttling: `vcgencmd measure_temp`
- Reduce Roon DSP processing if enabled
- Try wired connection instead of WiFi

#### Marantz Not Appearing in Roon
- **Note:** Roon does NOT support UPnP/DLNA - use HDMI from Pi 5 instead
- AirPlay is limited to CD quality (16-bit/44.1kHz)
- For full quality: use Pi 5 Roon Bridge → HDMI → Marantz

#### HDMI Audio Not Working (Pi 5 → Marantz)
```bash
# Check bridge service is running
ssh root@192.168.100.83 'systemctl status hdmi-bridge'

# Restart bridge service
ssh root@192.168.100.83 'systemctl restart hdmi-bridge'

# Check loopback module is loaded
ssh root@192.168.100.83 'lsmod | grep snd_aloop'

# Load loopback if missing
ssh root@192.168.100.83 'modprobe snd-aloop'

# List audio devices (should show Loopback and vc4hdmi)
ssh root@192.168.100.83 'aplay -l'

# Test HDMI audio directly
ssh root@192.168.100.83 'speaker-test -D hdmi:CARD=vc4hdmi1,DEV=0 -c 2'

# Check Roon Bridge logs
ssh root@192.168.100.83 'journalctl -u roonbridge -f'

# Check bridge logs
ssh root@192.168.100.83 'journalctl -u hdmi-bridge -f'
```

**Common HDMI issues:**
- Wrong HDMI port: Pi 5 has two Mini HDMI ports, use the one configured as vc4hdmi1
- Marantz input: Ensure receiver is set to correct HDMI input
- Bridge not running: Restart hdmi-bridge service
- Loopback not loaded: Run `modprobe snd-aloop`
- Roon wrong device: In Roon Settings → Audio, enable "Loopback" not "vc4hdmi"

---

## Maintenance

### Regular Tasks

**Weekly:**
- Check system temperature (Radxa OLED display)
- Verify adequate free space: `df -h`

**Monthly:**
- Update system: `sudo apt update && sudo apt upgrade`
- Check Roon Server for updates (auto-updates usually)
- Verify backup integrity

**Quarterly:**
- Test drive SMART status: `sudo smartctl -a /dev/sda`
- Clean dust from fans/heatsinks
- Verify backup drives working

**Annually:**
- Review storage capacity needs
- Consider additional drive if space low
- Update passwords/credentials

---

## Future Expansion Ideas

### Additional Zones (Rooms)

**Room 3, 4, 5...:**
- Add Raspberry Pi Zero 2 W (~€15) + RoPieee
- Or use existing devices (old phone, tablet with Roon Remote)
- Radxa supports up to 5 internal drives

### Storage Expansion

**Add drives to Radxa HAT:**
- Bay 2: 10-14TB for backup (RAID 1 mirror)
- Bay 3: 8TB for video library
- Bay 4-5: Future expansion

**NAS features:**
- Jellyfin for video streaming
- PhotoPrism for photos
- NextCloud for file sync

### Audio Quality Upgrades

**Better endpoints:**
- Dedicated Roon Ready streamer (Bluesound, Cambridge)
- USB DAC upgrade (RME ADI-2, Chord Qutest)
- External Roon Bridge with HAT (Allo DigiOne)

### Automation

**Home Assistant integration:**
- Trigger music on presence detection
- Voice control via Alexa/Google
- Automated scene lighting + music

---

## Resources

### Official Documentation
- **Roon:** https://roon.app/en/
- **Radxa Penta HAT:** https://wiki.radxa.com/penta
- **RoPieee:** https://ropieee.org
- **DietPi:** https://dietpi.com

### Community Forums
- **Roon Community:** https://community.roonlabs.com
- **Raspberry Pi Forums:** https://forums.raspberrypi.com
- **Reddit r/roon:** https://reddit.com/r/roon

### Tools
- **dBpoweramp CD Ripper:** https://www.dbpoweramp.com
- **MusicBrainz Picard:** https://picard.musicbrainz.org (auto-tagging)
- **Etcher:** https://www.balena.io/etcher (SD card flashing)

---

## Philosophy: Ownership vs Subscription

**Core principle:** Own your music, don't rent it.

**What this means:**
- Physical media (CDs, vinyl, SACDs, Blu-rays) = owned ✅
- Digital files on YOUR hardware (14TB drive) = owned ✅
- Streaming services (Spotify, Tidal) = renting ❌

**The 14TB drive is physical storage:**
- Bits stored magnetically on physical platters
- In your home, under your control
- Not "the cloud" - it's YOUR hardware
- Files can't disappear if a service shuts down

**Roon subscription is different:**
- Roon provides software/UI (like buying software)
- But YOUR music stays on YOUR drive
- If Roon shuts down, you still have all files
- Can use Audirvana, VLC, or any other player
- Roon doesn't own your music, you do

**Result:** Building a permanent library, not renting temporary access.

---

## Notes & Tips

### From Planning Discussion

**Key decisions made:**
- 10TB vs 14TB → **14TB** (local purchase, full warranty)
- Managed vs unmanaged switch → **Managed** (TP-Link TL-SG108E)
- Active Cooler → **Yes** (worth it for 24/7 operation)
- RTC Battery → **No** (not essential for always-on server)
- Top Board → **Yes** (OLED display useful for headless server)

**Equipment corrections:**
- Initial assumption: PM6004/CD6004 (older generation)
- Actual equipment: PM6007/CD6007 (2020s generation, better DACs)
- PM6007 has digital inputs (USB, coaxial, optical) - more versatile than assumed

**Avoided pitfalls:**
- RPi 4 PSU: Insufficient power for Pi 5 (need 5V 5A)
- TerraPi case: Not compatible with Pi 5
- **Radxa Top Board:** Only works with 2.5" SSDs, NOT 3.5" HDDs (can't stack large drives)
- Some vendors offer only 12-month warranty (verify 5-year for WD Red Pro)

**B2B purchasing:**
- Pay full price with VAT
- Reclaim VAT through accountant/taxes
- Keep all invoices for business expenses

---

## Project Status

**Current Phase:** Fully Operational ✅

**Completed (January 2025-2026):**
- [x] RPi 5 + Radxa SATA HAT assembled
- [x] 2x 14TB WD Red Pro in RAID 1 configured
- [x] DietPi OS installed
- [x] Samba NAS share configured (`smb://192.168.100.83/xnas`)
- [x] SMART + RAID monitoring enabled
- [x] Music library copied to NAS (~4.8TB)
- [x] ~~Roon Server on Pi~~ **NOT POSSIBLE** (ARM64 not supported)
- [x] Roon Bridge installed on Pi 5
- [x] HDMI audio working via Loopback workaround
- [x] Pi 5 → Marantz SR5015 audio path operational (HDMI input 1)
- [x] RPi 3 + RoPieeeXL + touchscreen configured for Room 2
- [x] Music library organized by genre (metal, exyu folders)
- [x] Reavon UBR X110 connected for native DSD playback (HDMI input 2)
- [x] ~~Test Reavon SMB/CIFS access to NAS~~ **FAILED** - SMB client broken, USB required

**Architecture Change:**
- Original plan: Roon Core on Pi 5 (24/7 standalone server)
- Actual: Roon Core on Mac + Pi 5 as NAS + Roon Bridge
- Reason: Roon Server only supports x86/x64, not ARM64

**Current Working Setup:**
- **Pi 5:** NAS (Samba, RAID 1) + Roon Bridge + HDMI audio output
- **Mac:** Roon Core (must be running for playback)
- **Room 1 - Dual Path:**
  - Pi 5 → HDMI → Marantz SR5015 (Roon streaming - PCM/FLAC)
  - Reavon UBR X110 → HDMI → Marantz SR5015 (native DSD playback)
- **Room 2:** Pi 3 + 7" touchscreen + IR remote + FiiO K3 → PM6007 (RoPieeeXL)

**Music Library (January 2026):**
- **Metal:** 64 albums (23 artists) in `/music/metal/`
- **Exyu:** 241 albums in `/music/exyu/`
- **DSD:** Available in `/00_DSD/`, `/00_DSD_NO_ISO/` folders
- **Total:** 375+ albums imported to Roon
- **Format:** Consistent `Artist/Album (Year)/` structure
- **Scripts:** Automated cleanup and organization tools created

**DSD Playback:**
- **Via Roon:** DSD converted to PCM (still high quality)
- **Via Reavon:** Native DSD64, multichannel support (audiophile path)
- **Access:** USB drive only (Reavon SMB client broken/unusable)

**Network:**
- TP-Link TL-SG108E 8-port Gigabit managed switch

**Services on Pi 5:**
- `smbd` - Samba file sharing
- `smartmontools` - Disk health monitoring
- `mdmonitor` - RAID health monitoring
- `roonbridge` - Roon audio endpoint
- `hdmi-bridge` - Loopback to HDMI audio routing

**Future Option:**
- Add dedicated x86 machine (Intel NUC, Mac Mini) as 24/7 Roon Core
- Pi 5 NAS/Bridge remains unchanged - just point new Core to same SMB share

---

*Document created: December 2024*
*Updated: January 2025 (architecture correction + HDMI audio solution)*
*Updated: January 2026 (music library organization + Room 2 touchscreen + Reavon DSD player)*
*Hardware: Raspberry Pi 5 (8GB) + Radxa Penta SATA HAT + 2x14TB RAID1*
*Room 1: Pi 5 (Roon) + Reavon UBR X110 (DSD via USB) → Marantz SR5015 (dual HDMI inputs)*
*Room 2: RPi 3 + Official 7" touchscreen + USB IR receiver (RoPieeeXL)*
*Network: TP-Link TL-SG108E 8-port Gigabit managed switch*
*Software: DietPi + Samba + Roon Bridge + hdmi-bridge service*
*Roon Core: Mac (required due to ARM64 limitation)*
*Audio Paths:*
  *- Room 1 Roon: Pi 5 → HDMI (Loopback) → Marantz input 1*
  *- Room 1 DSD: USB drive → Reavon UBR X110 → HDMI → Marantz input 2 (native DSD64/multichannel)*
  *- Room 2: RPi 3 → FiiO K3 → PM6007*
*Library: 375+ albums (64 metal, 241 exyu) + DSD collection - organized by genre in /music/*
*Note: Reavon SMB/CIFS broken (beta feature never completed, company defunct) - USB drive required*
