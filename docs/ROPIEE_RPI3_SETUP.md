# RoPieeeXL RPi 3 Setup Guide

Complete setup for Raspberry Pi 3 with RoPieeeXL (Roon Bridge + touchscreen), including Roon integration.

**Hardware:** RPi 3 + Official 7" touchscreen + FiiO K3 USB DAC  
**Network:** Same subnet as Roon Core (wired or wireless)  
**Roon Core:** Mac (required; Roon Server does not run on ARM64)

---

## Quick Checklist (All Steps)

| # | Step | Where |
|---|------|-------|
| 1 | Download RoPieeeXL image | image.ropieee.io |
| 2 | Flash with Etcher | Mac |
| 3 | Boot wired, connect hardware | RPi 3 |
| 4 | Configure network (WiFi or keep wired) | RoPieee → Network |
| 5 | Router: DHCP reservation (static IP) | Router |
| 6 | Audio output + zone name | RoPieee → Audio |
| 7 | Display + Remote zone names | RoPieee → Display, Remote |
| 8 | Enable zone in Roon | Roon → Settings → Audio |
| 9 | **Enable RoPieee Extension** | Roon → Settings → Extensions |
| 10 | Reboot RoPieee | RoPieee → Advanced |

---

## 1. Download RoPieeeXL Image

**Important:** RoPieeeXL is *not* listed on the main 2026.01 download page. Use the direct image repository.

| Image | URL |
|-------|-----|
| **RoPieeeXL Pi 3** (compressed) | https://image.ropieee.io/ropieeexl_ose_pi3-2025.8.2-stable.20250909.2741.bin.xz |
| Image index | https://image.ropieee.io/ |

- **RoPieeeXL** = Roon Bridge + Now Playing display + touch + IR remote
- **RoPieee** (standard) = Headless only, no display support

---

## 2. Flash to microSD Card

Raspberry Pi Imager does not accept `.bin` files. Use **Balena Etcher**:

1. Download Etcher: https://etcher.balena.io/
2. Select the `.bin.xz` file (or decompress first with `xz -d file.bin.xz` if needed)
3. Select target microSD (8GB+ minimum)
4. Flash

Etcher handles both `.bin` and `.bin.xz` directly.

---

## 3. Initial Boot (Wired First)

### Physical connections (before power-on)

- **microSD** – RoPieeeXL image
- **Ethernet** – to router/switch (same network as Roon Core)
- **Official 7" touchscreen** – DSI connector
- **FiiO K3** – USB to Pi
- **Power** – 5V 2.5A minimum (display draws more)

### Boot

1. Power on; first boot takes 2–3 minutes
2. Web UI: `http://ropieee.local` or `http://<Pi-IP>` (check router DHCP list)
3. No password by default

---

## 4. Configure Network

**RoPieee web UI → Network tab**

**Wired:** Default DHCP. Skip to Section 5 if keeping Ethernet.

**Wireless:**
1. **Enable Wireless:** toggle **On**
2. Click **Wireless** sub-tab (not Wired)
3. **Network:** Select your SSID or use **SCAN**
4. **Password:** Enter WiFi password
5. Click **Apply**
6. **Advanced** tab → **Reboot**
7. Disconnect Ethernet. RoPieee will use WiFi.

---

## 5. Static IP (Router DHCP Reservation)

RoPieee does not support static IP in its web UI. Use a **DHCP reservation** on your router:

| Setting | Value |
|---------|-------|
| **IP** | e.g. 192.168.100.69 |
| **MAC** | From RoPieee Network tab (Wireless or Wired) |

Router: DHCP / LAN / Address Reservation → add entry for RoPieee’s MAC.

---

## 6. RoPieee Audio Tab (Output + Zone)

**RoPieee web UI → Audio tab**

1. **Output** – FiiO K3 should appear as USB DAC; select it
2. **Zone name** (if shown) – Use same name everywhere (e.g. `RPI3 main room`)
3. **Services** tab – Roon should be enabled; leave default if unsure

Click **Apply**.

---

## 7. RoPieee Zone Configuration (Display + Remote)

**Critical for touchscreen Now Playing.** If these show "unknown", type the zone name manually.

### Display tab

| Setting | Value |
|---------|-------|
| **Roon Default Zone** | e.g. `RPI3 main room` – type manually if it shows "unknown" |
| Orientation | Normal (or as needed) |
| Scroll Long Titles | On |
| Show Blurred Background | On |
| Screen Saver Timeout | 10 (minutes) |
| Show Clock | On (screensaver) |

### Remote tab (IR remote optional)

| Setting | Value |
|---------|-------|
| **Roon Control Zone** | Same as Display (e.g. `RPI3 main room`) |
| Follow Display Zone | Optional |

**Critical:** Zone names must match exactly (case, spaces) in Audio, Display, Remote, and Roon. If display shows "Connection Failure", check these first.

Click **Apply** in each tab. Reboot (Advanced → Reboot) after zone changes.

---

## 8. Roon Configuration

**Prerequisites:** Roon Core running on Mac, same network.

### 8.1 Enable Audio Zone

**Roon → Settings → Audio**

1. Find **ropieee** (e.g. 192.168.100.69) / **RPI3 main room**
2. **Enable** the zone (toggle on)
3. In Roon: tap zone selector at top → choose RPI3 → play music

### 8.2 Enable RoPieee Extension (for display) – required

Without this, the touchscreen stays on "Connection Failure" even when audio works.

**Roon → Settings → Extensions**

1. Confirm **RoPieee** / **RoPieee Remote Control** appears
2. **Enable** / **Authorize** it

### 8.3 Zone name consistency

Use the same zone name everywhere:

- Roon Settings → Audio (zone name)
- RoPieee Display → Roon Default Zone
- RoPieee Remote → Roon Control Zone (if used)

---

## 9. Shutdown / Reboot

**RoPieee web UI → Advanced tab**

- **Shutdown** (red button)
- **Reboot** (orange button)

No SSH: RoPieee does not support SSH by design.

---

## 10. Troubleshooting

### Connection Failure on display (audio works)

1. **Roon Settings → Extensions** – enable RoPieee
2. **Zone names** – must match exactly in Roon and RoPieee
3. **Wireless:** If discovery fails, test with Ethernet temporarily

### Roon Core not discovered

- Roon Core must be running on Mac
- Same subnet (e.g. 192.168.100.x)
- Disable VPNs or other network extensions that may block discovery

### Display shows "unknown" for zone

- RoPieee cannot discover zones (common on wireless)
- Enter the zone name manually in Display and Remote tabs

### Firewall

- Mac firewall disabled in tested setup
- If enabled: allow Roon (ports 9003, 9100–9200)

---

## 11. Reference

| Item | Value |
|------|-------|
| Web UI | http://ropieee.local or http://<Pi-IP> |
| RoPieee docs | https://ropieee.org |
| Roon community | https://community.roonlabs.com/c/audio-gear-talk/ropieee/56 |
| Image repository | https://image.ropieee.io/ |

---

*Created: February 2026. Tested with RoPieeeXL 2025.8.2, RPi 3, wired and wireless.*
