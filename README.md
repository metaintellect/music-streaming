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
| **Radxa Top Board** | OLED + Fan | [Berrybase.de](https://www.berrybase.de) | IP display, cooling |
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
- RPi 3 (repurpose as Roon Bridge for Room 2)

**Room 1 (Home Theater) Equipment:**
- Marantz SR5015 AV receiver (5.0 system)
- Panasonic DP-UB820 (4K/UHD + Blu-ray audio player)
- Reavon X110 (DSD multichannel SACD player)
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
        (Bridge)
           |
        FiiO K3
           ↓
      Marantz PM6007
```

### Network Details

- **MacBook Pro (Roon Core):** WiFi - reads from NAS, streams to endpoints
- **RPi 5 (NAS + Bridge):** Wired Gigabit - serves files via SMB, also audio endpoint
- **RPi 3 (Roon Bridge):** Wired - Room 2 audio endpoint
- **Marantz SR5015:** Wired Gigabit - Room 1 UPnP/AirPlay endpoint
- **TV:** Wired if used for video streaming

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

```
Mac (Roon Core)
    ↓ Network (RAAT)
RPi 5 (Roon Bridge)
    ↓ Loopback → hdmi-bridge
Mini HDMI cable
    ↓
Marantz SR5015 (AV Receiver - HDMI input)
    ↓ Speaker outputs
Speakers
```

**Connection:** HDMI from Pi 5 Roon Bridge to Marantz
**Why HDMI over network streaming:**
- UPnP/DLNA not supported by Roon (only AirPlay/Chromecast)
- AirPlay limited to CD quality (16-bit/44.1kHz)
- HDMI carries full quality audio from Roon Bridge

### Room 2 (Stereo Listening Room)

**Digital Path (Roon Streaming):**
```
Mac (Roon Core)
    ↓ Network (RAAT)
RPi 3 or RPi 5 (Roon Bridge)
    ↓ USB
Option A: Direct to PM6007 USB input (uses PM6007's DAC)
Option B: FiiO K3 (external DAC) → PM6007 analog input
    ↓
Marantz PM6007 (Integrated Amplifier)
    ↓ Speaker outputs
Stereo Speakers (preferred pair)
```

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
    ┌───────┼─────────────────────┬───────────────────┐
    │       │                     │                   │
    ↓       ↓                     ↓                   ↓
┌───────────────────┐ ┌─────────────┐ ┌─────────────────┐
│ RPi 5 (NAS +      │ │ Room 2      │ │ Control UI      │
│ Roon Bridge)      │ │ RPi 3       │ │ iPhone/iPad     │
│      ↓            │ │ (Bridge)    │ │ (Roon Remote)   │
│ Mini HDMI cable   │ │ + FiiO K3   │ └─────────────────┘
│      ↓            │ │      ↓      │
│ Marantz SR5015    │ │ Marantz     │
│ (Room 1 - HDMI)   │ │ PM6007      │
└───────────────────┘ └─────────────┘

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

```bash
# From Mac Terminal, or use Finder → Go → Connect to Server (⌘K)
open smb://192.168.100.83/xnas
# Enter credentials: user=x, pass=aeon
```

Or add to `/etc/fstab` for auto-mount (advanced).

#### 2.4 Configure Roon Storage

**In Roon on Mac:**
1. Settings → Storage → Add Folder
2. Navigate to mounted NAS share
3. Select the music folders (00_DSD, music, 00_flac_new, etc.)
4. Roon scans library (takes 1-2 hours for large collections)

#### 2.5 Enable Roon Bridge Endpoint

**In Roon on Mac:**
1. Settings → Audio
2. Look for **"DietPi"** (the RPi 5 Roon Bridge)
3. Click → **Enable**
4. Rename to preferred name (e.g., "Pi 5 Bridge")
5. Test playback

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

#### 3.5 DSD Playback

DSD files will be converted to PCM by Roon Core before streaming to the Bridge.
This is normal - the Marantz SR5015 DAC handles the final conversion to analog.

---

### Phase 4: Room 2 Setup (RPi 3 + FiiO K3)

#### 4.1 Install RoPieee on RPi 3

**Download:** https://ropieee.org

1. Flash RoPieee image to microSD card
2. Insert in RPi 3
3. Connect:
   - Ethernet or WiFi
   - FiiO K3 via USB
   - Power
4. Boot Pi (takes 2-3 minutes first time)

#### 4.2 Configure RoPieee

**Web interface:**
1. Browse to: `http://ropieee.local`
2. **Audio** tab:
   - Zone name: "Second Room" (or preferred)
   - USB DAC: Should auto-detect FiiO K3
   - Save
3. **Network** tab:
   - Configure WiFi if using wireless
4. Reboot

#### 4.3 Enable in Roon

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

### Primary Storage
- **14TB WD Red Pro** (internal in Radxa HAT)
- 5-year warranty
- 24/7 operation rated

### Backup Options

#### Option 1: Second Drive in Radxa HAT
- Add 2nd drive (10TB, 14TB, or 14TB)
- Configure automated rsync backup

**Backup script:**
```bash
#!/bin/bash
# /usr/local/bin/backup-music.sh

rsync -avh --delete /mnt/music/ /mnt/backup/music/

# Add to crontab for nightly backup:
# crontab -e
# 0 3 * * * /usr/local/bin/backup-music.sh
```

#### Option 2: External USB Drive (Occasional Backup)
- Use existing 14TB Seagate
- Manual sync when needed
- Cold storage backup

#### Option 3: Cloud Backup (Long-term)
- Backblaze B2, Wasabi, etc.
- For irreplaceable music (rare DSD, personal rips)
- Expensive for 14TB (~€60-100/year)

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
- Low power: **~20W 24/7**
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
- Some vendors offer only 12-month warranty (verify 5-year for WD Red Pro)

**B2B purchasing:**
- Pay full price with VAT
- Reclaim VAT through accountant/taxes
- Keep all invoices for business expenses

---

## Project Status

**Current Phase:** Fully Operational ✅

**Completed (January 2025):**
- [x] RPi 5 + Radxa SATA HAT assembled
- [x] 2x 14TB WD Red Pro in RAID 1 configured
- [x] DietPi OS installed
- [x] Samba NAS share configured (`smb://192.168.100.83/xnas`)
- [x] SMART + RAID monitoring enabled
- [x] Music library copied to NAS (~4.8TB)
- [x] ~~Roon Server on Pi~~ **NOT POSSIBLE** (ARM64 not supported)
- [x] Roon Bridge installed on Pi 5
- [x] HDMI audio working via Loopback workaround
- [x] Pi 5 → Marantz SR5015 audio path operational

**Architecture Change:**
- Original plan: Roon Core on Pi 5 (24/7 standalone server)
- Actual: Roon Core on Mac + Pi 5 as NAS + Roon Bridge
- Reason: Roon Server only supports x86/x64, not ARM64

**Current Working Setup:**
- **Pi 5:** NAS (Samba, RAID 1) + Roon Bridge + HDMI audio output
- **Mac:** Roon Core (must be running for playback)
- **Room 1:** Pi 5 → HDMI → Marantz SR5015 (full quality)
- **Room 2:** Pi 3 + FiiO K3 → PM6007 (Roon Bridge endpoint)

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
*Hardware: Raspberry Pi 5 (8GB) + Radxa Penta SATA HAT + 2x14TB RAID1*
*Network: TP-Link TL-SG108E 8-port Gigabit managed switch*
*Software: DietPi + Samba + Roon Bridge + hdmi-bridge service*
*Roon Core: Mac (required due to ARM64 limitation)*
*Audio: HDMI from Pi 5 to Marantz SR5015 via Loopback workaround*
