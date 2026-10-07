#!/usr/bin/env bash
# Takes screenshots of the Migood OS desktop from a finished build
# (work/chroot), without booting a VM:
#   - starts a virtual screen (Xvfb) on this machine
#   - runs GNOME from inside the built system on that screen
#   - takes pictures: desktop, launcher open, Quick Settings open
#
#   sudo bash build/screenshot.sh        -> docs/screenshots/*.png
#
# Run it after build/build-iso.sh. It doesn't change the ISO; the throwaway
# user it makes is deleted at the end.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
CH="${WORK:-$REPO/work}/chroot"
OUT="${SHOTS:-$REPO/docs/screenshots}"
W=1920 H=1080 DPY=:99 U=shot
[ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 1; }
[ -x "$CH/usr/bin/gnome-shell" ] || { echo "no build in $CH, run build-iso.sh first"; exit 1; }
mkdir -p "$OUT"

apt-get install -y -q xvfb imagemagick xdotool >/dev/null

XPID=""
cleanup() {
  chroot "$CH" pkill -u "$U" 2>/dev/null || true
  sleep 1
  chroot "$CH" userdel -r "$U" >/dev/null 2>&1 || true
  [ -n "$XPID" ] && kill "$XPID" 2>/dev/null || true
  for d in tmp/.X11-unix dev/pts dev sys proc; do
    mountpoint -q "$CH/$d" && umount -l "$CH/$d"
  done
  true
}
trap cleanup EXIT

for d in proc sys dev dev/pts; do mountpoint -q "$CH/$d" || mount --bind "/$d" "$CH/$d"; done
mkdir -p /tmp/.X11-unix "$CH/tmp/.X11-unix"
mount --bind /tmp/.X11-unix "$CH/tmp/.X11-unix"

Xvfb "$DPY" -screen 0 "${W}x${H}x24" +extension GLX -nolisten tcp &
XPID=$!
sleep 2

# A fresh user, so the screenshots show what a new account really gets.
chroot "$CH" useradd -m -s /bin/bash "$U" 2>/dev/null || true
UID_=$(chroot "$CH" id -u "$U")
chroot "$CH" install -d -o "$U" -m 700 "/run/user/$UID_"

# ubuntu session mode = what you get when logging in on the real OS.
chroot "$CH" su - "$U" -c "
  export DISPLAY=$DPY XDG_RUNTIME_DIR=/run/user/$UID_ XDG_SESSION_TYPE=x11 \
         XDG_CURRENT_DESKTOP=ubuntu:GNOME GNOME_SHELL_SESSION_MODE=ubuntu \
         LIBGL_ALWAYS_SOFTWARE=1
  dbus-run-session -- gnome-shell --x11 >/tmp/shell.log 2>&1" &

shot() { DISPLAY=$DPY import -window root "$OUT/$1.png"; echo "saved $OUT/$1.png"; }
click() { DISPLAY=$DPY xdotool mousemove "$1" "$2" click 1; }

echo "waiting for GNOME to start (slow without a graphics card)..."
sleep 60
DISPLAY=$DPY xdotool key Escape  # close the overview GNOME opens on login
sleep 5
shot 1-desktop

click 24 $((H - 24))            # Migood button, bottom-left of the shelf
sleep 8
shot 2-launcher
DISPLAY=$DPY xdotool key Escape
sleep 3

click $((W - 60)) $((H - 24))   # system area, bottom-right of the shelf
sleep 8
shot 3-quick-settings
DISPLAY=$DPY xdotool key Escape

cp "$CH/tmp/shell.log" "$(dirname "$CH")/shell.log" 2>/dev/null || true
