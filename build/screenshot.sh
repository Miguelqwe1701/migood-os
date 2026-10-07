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
  chroot "$CH" pkill dbus-daemon 2>/dev/null || true
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

# The system message bus: on a real boot systemd starts it; GNOME won't
# start without it.
mkdir -p "$CH/run/dbus" && rm -f "$CH/run/dbus/pid"
chroot "$CH" dbus-daemon --system --fork

# A fresh user, so the screenshots show what a new account really gets.
chroot "$CH" useradd -m -s /bin/bash "$U" 2>/dev/null || true
UID_=$(chroot "$CH" id -u "$U")
chroot "$CH" install -d -o "$U" -m 700 "/run/user/$UID_"

# ubuntu session mode = what you get when logging in on the real OS.
# No "su" login here: that would try to start logind (only a real boot has
# it). Without /run/systemd/seats, GNOME uses its built-in stand-in.
rm -rf "$CH"/run/systemd/{seats,sessions,users}
as_user() {
  chroot --userspec="$U:$U" "$CH" /usr/bin/env -i HOME="/home/$U" USER="$U" \
    PATH=/usr/local/bin:/usr/bin:/bin DISPLAY=$DPY \
    XDG_DATA_DIRS=/var/lib/flatpak/exports/share:/usr/local/share:/usr/share \
    XDG_RUNTIME_DIR=/run/user/$UID_ XDG_SESSION_TYPE=x11 XDG_CURRENT_DESKTOP=ubuntu:GNOME \
    GNOME_SHELL_SESSION_MODE=ubuntu LIBGL_ALWAYS_SOFTWARE=1 "$@"
}
# The session bus address is saved so the apps below join the same session.
as_user sh -c 'cd && dbus-run-session -- sh -c "echo \$DBUS_SESSION_BUS_ADDRESS > /tmp/bus; exec gnome-shell --x11" >/tmp/shell.log 2>&1' &
app() {  # app <name> <command...>: open an app, screenshot it, close it
  local name=$1; shift
  as_user env DBUS_SESSION_BUS_ADDRESS="$(cat "$CH/tmp/bus")" "$@" >/dev/null 2>&1 &
  sleep 12
  shot "$name"
  chroot "$CH" pkill -u "$U" -f /usr/lib/migood-os/ 2>/dev/null || true
  sleep 2
}

shot() {
  DISPLAY=$DPY import -window root "$OUT/$1.png"
  # A plain one-colour picture means GNOME didn't draw anything.
  if [ "$(convert "$OUT/$1.png" -format '%k' info:)" -le 1 ]; then
    echo "!! $1 is blank, GNOME didn't start. Log: $(dirname "$CH")/shell.log"
    cp "$CH/tmp/shell.log" "$(dirname "$CH")/shell.log" 2>/dev/null || true
    exit 1
  fi
  echo "saved $OUT/$1.png"
}
click() { DISPLAY=$DPY xdotool mousemove "$1" "$2" click 1; }
key() { DISPLAY=$DPY xdotool key "$@"; }

echo "waiting for GNOME to start (slow without a graphics card)..."
sleep 60
key Escape  # close the overview GNOME opens on login
sleep 5
shot 1-desktop

key super                        # the Migood button / launcher (ArcMenu hotkey)
sleep 8
shot 2-launcher
key Escape
sleep 3

click $((W - 40)) 14             # status icons, top-right of the top bar
sleep 8
shot 3-quick-settings
key Escape
sleep 2

# The welcome / setup screens (as on the live USB) and the Migood apps.
for page in welcome wifi signin tour; do
  app "4-setup-$page" env MIGOOD_SETUP_PAGE=$page /usr/lib/migood-os/migood-setup --live
done
app 5-migood-updates /usr/lib/migood-os/migood-updates
app 6-migood-settings /usr/lib/migood-os/migood-settings

cp "$CH/tmp/shell.log" "$(dirname "$CH")/shell.log" 2>/dev/null || true
