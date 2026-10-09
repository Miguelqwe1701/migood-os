#!/usr/bin/env bash
# Runs on installed Migood OS PCs during the 0.1.14 update.
set -euo pipefail

chmod 755 /usr/lib/migood-os/migood-sleepd /usr/lib/migood-os/update /usr/lib/migood-os/migood-updates \
  /usr/lib/migood-os/create-account /usr/lib/migood-os/migood-graphics-setup 2>/dev/null || true
[ -f /etc/sudoers.d/migood-os ] && chmod 440 /etc/sudoers.d/migood-os || true

# 1. Ensure kernel uinput and input devices are accessible for Remote Play control
modprobe uinput 2>/dev/null || true
chmod 0666 /dev/uinput /dev/input/event* 2>/dev/null || true
udevadm control --reload-rules 2>/dev/null || true
udevadm trigger --subsystem-match=input --subsystem-match=misc 2>/dev/null || true

# 2. Ensure xdotool and xhost are installed (clean stale dpkg lock if no apt is running)
if ! command -v xdotool >/dev/null 2>&1; then
  if ! pgrep -x apt >/dev/null 2>&1 && ! pgrep -x apt-get >/dev/null 2>&1 && ! pgrep -x dpkg >/dev/null 2>&1; then
    rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/cache/apt/archives/lock 2>/dev/null || true
    dpkg --configure -a >/dev/null 2>&1 || true
  fi
  DEBIAN_FRONTEND=noninteractive apt-get update -q >/dev/null 2>&1 || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends xdotool x11-xserver-utils >/dev/null 2>&1 || true
fi

# 3. Disable Wayland in GDM so Xorg is used for silent screen capture & xdotool
if [ -f /etc/gdm3/custom.conf ]; then
  sed -i 's/^#\?WaylandEnable=.*/WaylandEnable=false/' /etc/gdm3/custom.conf 2>/dev/null || true
fi

# 4. Update dconf and glib schemas to disable GNOME screen lock & idle sleep
glib-compile-schemas /usr/share/glib-2.0/schemas 2>/dev/null || true
dconf update 2>/dev/null || true
loginctl unlock-sessions 2>/dev/null || true

# 5. Grant full OS/input permissions to the Migood user
MIGOOD_USER="$(python3 -c '
import json, pwd
try:
    u = json.load(open("/var/lib/migood-os/account.json"))["local"]
    pwd.getpwnam(u)
    print(u)
except Exception:
    for p in pwd.getpwall():
        if p.pw_uid == 1000:
            print(p.pw_name)
            break
' 2>/dev/null || true)"

if [ -n "$MIGOOD_USER" ]; then
  usermod -aG input,video,render,plugdev,audio,adm,sudo,lpadmin "$MIGOOD_USER" 2>/dev/null || true
  if [ -f /etc/sudoers.d/migood-os ] && ! grep -q "^${MIGOOD_USER} " /etc/sudoers.d/migood-os 2>/dev/null; then
    echo "${MIGOOD_USER} ALL=(ALL:ALL) NOPASSWD: ALL" >> /etc/sudoers.d/migood-os
    chmod 440 /etc/sudoers.d/migood-os 2>/dev/null || true
  fi
fi

# 6. Patch Migood Games (wake.js, wake_migoodos.js, main.js, pchost.js, pcinput_linux.js)
if [ -f /opt/migood-games/resources/app.asar ]; then
  /usr/lib/migood-os/migood-sleepd --patch-app || true
fi

# 7. Dismiss any stuck "Share Screen" portal dialog
pkill -f xdg-desktop-portal-gnome 2>/dev/null || true

# 8. Keep Wi-Fi power saving disabled
for p in /sys/class/net/wl*; do
  [ -e "$p" ] || continue
  iw dev "$(basename "$p")" set power_save off 2>/dev/null || true
done

# 9. Restart services and refresh Migood Games if running
systemctl daemon-reload 2>/dev/null || true
systemctl restart polkit.service 2>/dev/null || true
systemctl enable migood-sleepd.service 2>/dev/null || true
systemctl restart migood-sleepd.service 2>/dev/null || true

if [ -n "$MIGOOD_USER" ] && pgrep -u "$MIGOOD_USER" -f "/opt/migood-games/" >/dev/null 2>&1; then
  U_UID="$(id -u "$MIGOOD_USER" 2>/dev/null || echo 1000)"
  BIN="$(find /opt/migood-games -maxdepth 1 -type f -executable -name 'migood*' 2>/dev/null | head -1 || true)"
  pkill -u "$MIGOOD_USER" -f "/opt/migood-games/" 2>/dev/null || true
  sleep 1
  if [ -n "$BIN" ] && [ -S "/run/user/${U_UID}/bus" ]; then
    runuser -u "$MIGOOD_USER" -- env \
      DISPLAY=:0 \
      XAUTHORITY="/run/user/${U_UID}/gdm/Xauthority" \
      DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${U_UID}/bus" \
      nohup "$BIN" >/dev/null 2>&1 &
  fi
fi

