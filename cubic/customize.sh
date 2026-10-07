#!/usr/bin/env bash
# Turns a stock Ubuntu 24.04 desktop into Migood OS.
#
# Usually build/build-iso.sh runs this for you (no desktop needed).
# It also works by hand INSIDE Cubic's chroot terminal:
#   1. Drag this whole repo folder into the Cubic terminal window (Cubic copies
#      it into the chroot), so it ends up at /root/migood-os.
#   2. bash /root/migood-os/cubic/customize.sh
#
# Safe to run more than once. Optional things (one game emulator, the font, ...)
# only print a warning if they fail; the build keeps going.
#
# Settings (put in front of the command, e.g. BROWSER=chromium bash customize.sh):
#   BROWSER   chrome (default) or chromium
#   VERSION   Migood OS version to stamp (default 0.1.0)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ASSETS="$REPO/assets"
BROWSER="${BROWSER:-chrome}"
VERSION="${VERSION:-0.1.0}"
export DEBIAN_FRONTEND=noninteractive

say()  { printf '\n\033[1;32m== %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!! %s\033[0m\n' "$*"; WARNINGS+=("$*"); }
WARNINGS=()

# Install packages one by one so one missing package doesn't stop the rest.
try_install() {
  for p in "$@"; do
    apt-get install -y --no-install-recommends "$p" >/dev/null \
      && echo "   ok  $p" || warn "could not install $p"
  done
}

[ "$(id -u)" = 0 ] || { echo "run as root (Cubic's terminal already is)"; exit 1; }

say "1/10 Software sources (universe, multiverse, 32-bit for Steam)"
add-apt-repository -y universe >/dev/null
add-apt-repository -y multiverse >/dev/null
dpkg --add-architecture i386
apt-get update -q

say "2/10 Desktop pieces (shelf, launcher, phone link)"
try_install gnome-shell-extension-manager gnome-shell-extension-dash-to-panel \
  gnome-shell-extension-arc-menu gnome-shell-extension-gsconnect dconf-cli

say "3/10 Gaming + streaming"
# steam-installer asks to accept a licence; pre-answer it.
echo steam steam/question select "I AGREE" | debconf-set-selections
echo steam steam/license note '' | debconf-set-selections
try_install steam-installer wine64 gamemode mangohud xdotool \
  retroarch dolphin-emu ppsspp flatpak
if command -v flatpak >/dev/null; then
  flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo \
    && flatpak install -y --noninteractive flathub com.usebottles.bottles \
    || warn "Bottles (flatpak) not installed, can be added after install"
fi

say "4/10 System: low-RAM, snapshots, firewall"
try_install zram-tools timeshift ufw unattended-upgrades
if [ -f /etc/default/zramswap ]; then
  sed -i 's/^#\?ALGO=.*/ALGO=zstd/; s/^#\?PERCENT=.*/PERCENT=50/' /etc/default/zramswap
fi
# ufw can't start inside a chroot, so just mark it enabled for first boot.
[ -f /etc/ufw/ufw.conf ] && sed -i 's/^ENABLED=.*/ENABLED=yes/' /etc/ufw/ufw.conf

say "5/10 Browser: $BROWSER"
case "$BROWSER" in
  chrome)
    install -d /etc/apt/keyrings
    curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
      | gpg --dearmor --yes -o /etc/apt/keyrings/google-chrome.gpg
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list
    apt-get update -q && try_install google-chrome-stable
    BROWSER_DESKTOP=google-chrome.desktop ;;
  chromium)
    # On Ubuntu, chromium is a snap, and snaps can't install inside Cubic.
    # The snap gets installed on first boot instead (see TODO in docs/PLAN.md).
    warn "chromium is a snap on Ubuntu; it is not preinstalled by this script"
    BROWSER_DESKTOP=chromium_chromium.desktop ;;
  *) echo "BROWSER must be chrome or chromium"; exit 1 ;;
esac
# Firefox on Ubuntu is a snap stub; drop it so there is one browser.
apt-get purge -y firefox >/dev/null 2>&1 || true

say "6/10 Nunito font"
install -d /usr/share/fonts/truetype/nunito
if curl -fsSL -o /usr/share/fonts/truetype/nunito/Nunito.ttf \
     "https://github.com/google/fonts/raw/main/ofl/nunito/Nunito%5Bwght%5D.ttf"; then
  fc-cache -f >/dev/null
else
  warn "Nunito download failed, desktop falls back to the default font"
fi

say "7/10 Migood files (updater, theme defaults, services)"
cp -r "$REPO/overlay/." /
chmod 755 /usr/lib/migood-os/update
sed -i "s/google-chrome.desktop/$BROWSER_DESKTOP/" /etc/dconf/db/local.d/00-migood
install -d -m 700 /var/lib/migood-os
install -d /usr/share/migood-os /usr/share/backgrounds/migood
[ -f "$ASSETS/migood-launcher.svg" ] && cp "$ASSETS/migood-launcher.svg" /usr/share/migood-os/ \
  || warn "assets/migood-launcher.svg missing (launcher button icon)"
[ -f "$ASSETS/wallpaper.png" ] && cp "$ASSETS/wallpaper.png" /usr/share/backgrounds/migood/default.png \
  || warn "assets/wallpaper.png missing (default wallpaper)"
dconf update
systemctl enable migood-os-update.timer migood-os-apply.service

say "8/10 Name: Migood OS $VERSION (based on Ubuntu)"
. /usr/lib/os-release   # read Ubuntu's values, e.g. VERSION_CODENAME
cat > /usr/lib/os-release <<EOF
PRETTY_NAME="Migood OS $VERSION (based on Ubuntu 24.04)"
NAME="Migood OS"
VERSION_ID="$VERSION"
VERSION="$VERSION"
VERSION_CODENAME=$VERSION_CODENAME
ID=migood-os
ID_LIKE="ubuntu debian"
UBUNTU_CODENAME=$UBUNTU_CODENAME
HOME_URL="https://github.com/Miguelqwe1701/migood-os"
LOGO=migood-os
EOF
ln -sf ../usr/lib/os-release /etc/os-release
echo "Migood OS $VERSION \\n \\l" > /etc/issue
echo "Migood OS $VERSION" > /etc/issue.net

say "9/10 Remove Ubuntu branding + Migood boot logo"
apt-get purge -y 'ubuntu-wallpapers*' >/dev/null 2>&1 || true
if [ -f "$ASSETS/migood-square.png" ]; then
  T=/usr/share/plymouth/themes/migood
  rm -rf "$T" && cp -r /usr/share/plymouth/themes/spinner "$T"
  cp "$ASSETS/migood-square.png" "$T/watermark.png"
  rm -f "$T/bgrt-fallback.png"
  mv "$T/spinner.plymouth" "$T/migood.plymouth"
  sed -i 's/^Name=.*/Name=Migood OS/; s#/spinner#/migood#g' "$T/migood.plymouth"
  update-alternatives --install /usr/share/plymouth/themes/default.plymouth \
    default.plymouth "$T/migood.plymouth" 200
  update-alternatives --set default.plymouth "$T/migood.plymouth"
  update-initramfs -u
else
  warn "assets/migood-square.png missing, boot logo not replaced"
fi

say "10/10 Migood Games desktop app"
APP_TGZ="$(ls "$ASSETS"/migood-games-*.tar.gz 2>/dev/null | sort -V | tail -1 || true)"
if [ -n "$APP_TGZ" ]; then
  rm -rf /opt/migood-games && install -d /opt/migood-games
  tar -xzf "$APP_TGZ" -C /opt/migood-games --strip-components=1
  BIN="$(find /opt/migood-games -maxdepth 1 -type f -executable -name 'migood*' | head -1)"
  cat > /usr/share/applications/migood-games.desktop <<EOF
[Desktop Entry]
Name=Migood Games
Exec=$BIN %U
Icon=/usr/share/migood-os/migood-launcher.svg
Type=Application
Categories=Game;
EOF
  install -d /etc/xdg/autostart
  cp /usr/share/applications/migood-games.desktop /etc/xdg/autostart/
else
  warn "no assets/migood-games-*.tar.gz, desktop app not installed"
fi

apt-get autoremove -y >/dev/null && apt-get clean
say "Done. Migood OS $VERSION is ready for Cubic's next pages."
if [ ${#WARNINGS[@]} -gt 0 ]; then
  printf '\033[1;33mWarnings (%d):\033[0m\n' "${#WARNINGS[@]}"
  printf '  - %s\n' "${WARNINGS[@]}"
fi
