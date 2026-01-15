# NAS Setup on DietPi - Manual OMV Alternative

This document covers how to manually replicate OpenMediaVault features on DietPi for a Pi 5 NAS with Roon.

## Hardware Setup
- Raspberry Pi 5
- RADXA SATA HAT (4 bays + eSATA)
- 2x WD Red Pro 14TB (WD142KFGX) in RAID 1

---

## 1. RAID 1 Setup with mdadm

### Initial RAID Creation
```bash
# Install mdadm
apt-get install mdadm

# Create RAID 1 array
mdadm --create /dev/md0 --level=1 --raid-devices=2 /dev/sda /dev/sdb

# Save RAID configuration
mdadm --detail --scan >> /etc/mdadm/mdadm.conf
update-initramfs -u

# Format as ext4
mkfs.ext4 /dev/md0

# Create mount point
mkdir -p /mnt/nas

# Mount
mount /dev/md0 /mnt/nas
```

### Auto-mount on Boot
Add to `/etc/fstab`:
```
/dev/md0    /mnt/nas    ext4    defaults,noatime    0    2
```

### Monitor RAID Status
```bash
# Check RAID status
cat /proc/mdstat

# Detailed info
mdadm --detail /dev/md0

# Monitor continuously
watch -n 1 cat /proc/mdstat
```

---

## 2. SMART Monitoring for Disk Health

### Install and Configure smartmontools
```bash
# Install
apt-get install smartmontools

# Enable daemon
systemctl enable smartd
systemctl start smartd
```

### Configure Email Alerts
Edit `/etc/smartd.conf`:
```
# Monitor all disks, test daily, email on failure
DEVICESCAN -d auto -a -o on -S on -s (S/../.././02|L/../../6/03) -m your-email@example.com -M exec /usr/share/smartmontools/smartd-runner
```

### Manual SMART Checks
```bash
# Check disk health
smartctl -a /dev/sda
smartctl -a /dev/sdb

# Run short test
smartctl -t short /dev/sda

# Run long test
smartctl -t long /dev/sda
```

---

## 3. File Sharing (SMB/Samba)

### Install and Configure Samba
```bash
# Install
apt-get install samba samba-common-bin

# Backup original config
cp /etc/samba/smb.conf /etc/samba/smb.conf.backup
```

### Configure Shares
Edit `/etc/samba/smb.conf`:
```ini
[global]
   workgroup = WORKGROUP
   server string = Pi5 NAS
   security = user
   map to guest = Bad User

[nas]
   path = /mnt/nas
   browseable = yes
   writable = yes
   create mask = 0775
   directory mask = 0775
   valid users = your-username
```

### Add Samba User
```bash
# Add system user (if not exists)
useradd -M -s /bin/false nasuser

# Add to Samba
smbpasswd -a nasuser

# Restart Samba
systemctl restart smbd
systemctl enable smbd
```

---

## 4. NFS Sharing (Optional)

### Install NFS Server
```bash
apt-get install nfs-kernel-server
```

### Configure Exports
Edit `/etc/exports`:
```
/mnt/nas    192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
```

### Apply and Start
```bash
exportfs -ra
systemctl enable nfs-server
systemctl start nfs-server
```

---

## 5. User Management

### Create NAS Users
```bash
# Create user with no login shell
useradd -M -s /bin/false username

# Set password
passwd username

# Add to Samba
smbpasswd -a username
```

### Set Permissions
```bash
# Create group for NAS users
groupadd nasusers

# Add users to group
usermod -aG nasusers username

# Set ownership
chown -R root:nasusers /mnt/nas
chmod -R 775 /mnt/nas
```

---

## 6. Email Notifications

### Install and Configure Postfix
```bash
# Install
apt-get install postfix mailutils

# Configure for internet site (during install)
```

### Configure Gmail Relay (Example)
Edit `/etc/postfix/main.cf`:
```
relayhost = [smtp.gmail.com]:587
smtp_use_tls = yes
smtp_sasl_auth_enable = yes
smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd
smtp_sasl_security_options = noanonymous
```

Create `/etc/postfix/sasl_passwd`:
```
[smtp.gmail.com]:587    your-email@gmail.com:your-app-password
```

Apply:
```bash
chmod 600 /etc/postfix/sasl_passwd
postmap /etc/postfix/sasl_passwd
systemctl restart postfix
```

### Test Email
```bash
echo "Test email from Pi NAS" | mail -s "Test" your-email@example.com
```

---

## 7. Scheduled Tasks (Cron)

### RAID Scrub (Monthly)
```bash
crontab -e
```
Add:
```
# RAID scrub on 1st of each month at 2 AM
0 2 1 * * echo check > /sys/block/md0/md/sync_action
```

### SMART Long Test (Weekly)
```
# SMART test every Sunday at 3 AM
0 3 * * 0 /usr/sbin/smartctl -t long /dev/sda && /usr/sbin/smartctl -t long /dev/sdb
```

### Backup Script (Daily)
```
# Daily backup at 4 AM
0 4 * * * /usr/local/bin/backup-script.sh
```

---

## 8. System Monitoring

### Install Monitoring Tools
```bash
# System stats
apt-get install htop iotop ncdu

# Disk usage alerts
apt-get install pydf
```

### Disk Space Monitoring Script
Create `/usr/local/bin/check-disk-space.sh`:
```bash
#!/bin/bash
THRESHOLD=90
USAGE=$(df -h /mnt/nas | awk 'NR==2 {print $5}' | sed 's/%//')

if [ $USAGE -gt $THRESHOLD ]; then
    echo "WARNING: Disk usage at ${USAGE}%" | mail -s "NAS Disk Space Alert" your-email@example.com
fi
```

Make executable and schedule:
```bash
chmod +x /usr/local/bin/check-disk-space.sh

# Add to crontab (daily at 8 AM)
0 8 * * * /usr/local/bin/check-disk-space.sh
```

---

## 9. Web Dashboard (Optional)

### Option A: Cockpit
```bash
apt-get install cockpit
systemctl enable --now cockpit.socket

# Access: https://pi-ip:9090
```

### Option B: Webmin
```bash
wget https://www.webmin.com/download/webmin-current.deb
dpkg -i webmin-current.deb
apt-get install -f

# Access: https://pi-ip:10000
```

---

## 10. Roon Server Setup (Core)

### Install Roon Server on RPi 5
```bash
# Download Roon Server for ARM64
cd /opt
wget https://download.roonlabs.net/builds/roonserver-installer-linuxarmv8.sh

# Make executable
chmod +x roonserver-installer-linuxarmv8.sh

# Run installer
./roonserver-installer-linuxarmv8.sh
```

### Create Systemd Service
```bash
nano /etc/systemd/system/roonserver.service
```

Add:
```ini
[Unit]
Description=Roon Server
After=network.target

[Service]
Type=simple
User=root
ExecStart=/opt/RoonServer/start.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Enable and Start
```bash
systemctl daemon-reload
systemctl enable roonserver
systemctl start roonserver
systemctl status roonserver
```

### Configure Roon
- Open Roon Remote app on Mac/Phone
- Detects Roon Core on network automatically
- Add music folder: `/mnt/nas` (or `/mnt/music`)
- Let Roon scan library

**Note:** Roon Bridge (for endpoints/other rooms) is different - install on RPi 3 with RoPieee

---

## 11. Maintenance Commands Reference

### RAID Management
```bash
# Add failed disk
mdadm --manage /dev/md0 --add /dev/sdc

# Remove failed disk
mdadm --manage /dev/md0 --fail /dev/sdb
mdadm --manage /dev/md0 --remove /dev/sdb

# Check rebuild progress
cat /proc/mdstat
```

### Disk Health Checks
```bash
# View all SMART attributes
smartctl -A /dev/sda

# Check for errors
smartctl -l error /dev/sda

# Temperature
smartctl -A /dev/sda | grep Temperature
```

### Network Shares
```bash
# List SMB connections
smbstatus

# List NFS exports
showmount -e localhost

# Restart services
systemctl restart smbd nmbd
systemctl restart nfs-server
```

---

## 12. Backup Strategy

### Backup Critical Config Files
```bash
# Create backup directory
mkdir -p /mnt/nas/system-backups

# Backup script
cat > /usr/local/bin/backup-configs.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/mnt/nas/system-backups/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Backup important configs
cp /etc/fstab $BACKUP_DIR/
cp /etc/mdadm/mdadm.conf $BACKUP_DIR/
cp -r /etc/samba $BACKUP_DIR/
cp /etc/exports $BACKUP_DIR/
cp /etc/smartd.conf $BACKUP_DIR/

echo "Backup completed: $BACKUP_DIR"
EOF

chmod +x /usr/local/bin/backup-configs.sh
```

---

## Quick Reference Commands

```bash
# System status
systemctl status mdmonitor smartd smbd roonbridge

# Disk usage
df -h /mnt/nas

# RAID status
cat /proc/mdstat

# Active connections
smbstatus
ss -tuln | grep :445

# Logs
journalctl -u mdmonitor -f
journalctl -u smartd -f
tail -f /var/log/syslog
```

---

## Notes

- All commands assume root/sudo access
- Replace IP addresses, emails, and usernames with your actual values
- Test email notifications before relying on them
- Keep RAID monitoring active - check /proc/mdstat regularly
- Document any changes you make to configs
