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
#   BROWSER   chromium (default) or chrome
#   VERSION   Migood OS version to stamp (default 0.1.0)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ASSETS="$REPO/assets"
BROWSER="${BROWSER:-chromium}"
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
# Teach Ubuntu's tools that "migood-os" uses Ubuntu's software sources, or
# add-apt-repository (PPAs) fails with "no distribution template for Migood-os".
T=/usr/share/python-apt/templates
[ -f "$T/Ubuntu.info" ] && cp "$T/Ubuntu.info" "$T/Migood-os.info" && cp "$T/Ubuntu.mirrors" "$T/Migood-os.mirrors"
[ -f /usr/share/distro-info/ubuntu.csv ] && ln -sf ubuntu.csv /usr/share/distro-info/migood-os.csv
add-apt-repository -y universe >/dev/null
add-apt-repository -y multiverse >/dev/null
dpkg --add-architecture i386
apt-get update -q

say "2/10 Desktop pieces (shelf, launcher, phone link)"
try_install gnome-shell-extension-manager gnome-shell-extension-gsconnect dconf-cli unzip
# Dash to Panel (shelf) and ArcMenu (launcher) aren't Ubuntu packages, so they
# come from extensions.gnome.org, the version made for this GNOME.
SHELL_VER="$(dpkg-query -W -f='${Version}' gnome-shell | cut -d. -f1)"
for uuid in dash-to-panel@jderose9.github.com arcmenu@arcmenu.com; do
  url="$(curl -fsS "https://extensions.gnome.org/extension-info/?uuid=$uuid&shell_version=$SHELL_VER" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["download_url"])')" \
    && curl -fsSL -o /tmp/ext.zip "https://extensions.gnome.org$url" \
    && rm -rf "/usr/share/gnome-shell/extensions/$uuid" \
    && unzip -q -o /tmp/ext.zip -d "/usr/share/gnome-shell/extensions/$uuid" \
    && glib-compile-schemas "/usr/share/gnome-shell/extensions/$uuid/schemas" \
    && cp "/usr/share/gnome-shell/extensions/$uuid"/schemas/*.xml /usr/share/glib-2.0/schemas/ \
    && chmod -R a+rX "/usr/share/gnome-shell/extensions/$uuid" \
    && echo "   ok  $uuid" || warn "could not install $uuid"
  rm -f /tmp/ext.zip
done
glib-compile-schemas /usr/share/glib-2.0/schemas
# Dash to Panel shows "has been updated!" when its saved version differs from
# the installed one; preset it so new users don't get that popup.
DTP=/usr/share/gnome-shell/extensions/dash-to-panel@jderose9.github.com/metadata.json
if [ -f "$DTP" ]; then
  install -d /etc/dconf/db/local.d
  printf '[org/gnome/shell/extensions/dash-to-panel]\nextension-version=%s\n' \
    "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$DTP")" \
    > /etc/dconf/db/local.d/01-migood-versions
fi

say "3/10 Gaming + streaming"
# steam-installer asks to accept a licence; pre-answer it.
echo steam steam/question select "I AGREE" | debconf-set-selections
echo steam steam/license note '' | debconf-set-selections
try_install steam-installer wine64 gamemode mangohud xdotool \
  retroarch flatpak
if command -v flatpak >/dev/null; then
  flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo \
    || warn "Flathub not added"
  # Bottles (Windows .exe games), Dolphin (GameCube/Wii) and PPSSPP (PSP) aren't Ubuntu
  # 24.04 packages, so they come from Flathub.
  for app in com.usebottles.bottles org.DolphinEmu.dolphin-emu org.ppsspp.PPSSPP; do
    flatpak install -y --noninteractive flathub "$app" || warn "$app (flatpak) not installed"
  done
fi

say "4/10 System: low-RAM, snapshots, firewall"
try_install zram-tools timeshift ufw unattended-upgrades
# Installer (Calamares) + what it needs to put GRUB on BIOS and UEFI PCs,
# encrypt the disk (optional) and use Btrfs (for Timeshift snapshots).
try_install calamares calamares-settings-ubuntu-common grub-efi-amd64-signed shim-signed \
  grub-pc-bin grub-efi-amd64-bin grub2-common efibootmgr os-prober cryptsetup \
  cryptsetup-initramfs btrfs-progs dosfstools x11-xserver-utils
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
    # Ubuntu's own chromium is a snap, and snaps can't install during a build.
    # The Flathub Chromium is a normal flatpak, so it can be preinstalled.
    flatpak install -y --noninteractive flathub org.chromium.Chromium \
      || warn "Chromium (flatpak) not installed"
    BROWSER_DESKTOP=org.chromium.Chromium.desktop ;;
  *) echo "BROWSER must be chrome or chromium"; exit 1 ;;
esac
# Firefox on Ubuntu is a snap stub; drop it so there is one browser.
apt-get purge -y firefox >/dev/null 2>&1 || true
# Make it the default for web links for every user.
install -d /etc/xdg
cat > /etc/xdg/mimeapps.list <<EOF
[Default Applications]
text/html=$BROWSER_DESKTOP
x-scheme-handler/http=$BROWSER_DESKTOP
x-scheme-handler/https=$BROWSER_DESKTOP
EOF

say "6/10 Nunito font"
# Bundled in assets/fonts (SIL Open Font License, see OFL.txt there).
install -d /usr/share/fonts/truetype/nunito
cp "$ASSETS"/fonts/Nunito-*.ttf "$ASSETS/fonts/OFL.txt" /usr/share/fonts/truetype/nunito/ \
  && fc-cache -f >/dev/null || warn "Nunito not installed, desktop uses the default font"

say "7/10 Migood files (updater, theme defaults, services)"
cp -r "$REPO/overlay/." /
chmod 755 /usr/lib/migood-os/update
sed -i "s/org.chromium.Chromium.desktop/$BROWSER_DESKTOP/" /etc/dconf/db/local.d/00-migood
install -d -m 700 /var/lib/migood-os
install -d /usr/share/migood-os /usr/share/backgrounds/migood
[ -f "$ASSETS/migood-square.png" ] && cp "$ASSETS/migood-square.png" /usr/share/migood-os/migood-launcher.png \
  || warn "assets/migood-square.png missing (launcher button icon)"
[ -f "$ASSETS/wallpaper.png" ] && cp "$ASSETS/wallpaper.png" /usr/share/backgrounds/migood/default.png \
  || warn "assets/wallpaper.png missing (default wallpaper)"
# Ubuntu's Software Updater is replaced by Migood Updates (dpkg excludes are
# in the overlay; this removes the copies already on disk).
rm -f /usr/share/applications/update-manager.desktop /etc/xdg/autostart/update-notifier.desktop
install -d -m 755 /var/cache/migood-os
dconf update
systemctl enable migood-os-update.timer migood-os-apply.service migood-firstboot.service
cp "$ASSETS/migood-logo.png" /usr/share/migood-os/ 2>/dev/null || true
cp "$ASSETS/migood-button.svg" "$ASSETS/migood-button.png" /usr/share/migood-os/
B=/usr/share/calamares/branding/migood
cp "$ASSETS/migood-button.png" "$B/migood-button.png"
cp "$ASSETS/wallpaper.png" "$B/welcome.png"
# Guest mode: a "guest" account with no password and no admin rights. Its home
# lives in memory and is wiped at sign-out (guest-session + PAM + logind).
id guest >/dev/null 2>&1 || useradd -m -s /bin/bash -c "Guest" guest
passwd -d guest >/dev/null
pam-auth-update --package --enable migood-guest

say "8/10 Name: Migood OS $VERSION (based on Ubuntu)"
# Read only the codename ("noble") from Ubuntu's file. A subshell, because the
# file also has VERSION=, which would overwrite ours.
CODENAME="$(. /usr/lib/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")"
cat > /usr/lib/os-release <<EOF
PRETTY_NAME="Migood OS $VERSION (based on Ubuntu 24.04)"
NAME="Migood OS"
VERSION_ID="$VERSION"
VERSION="$VERSION"
VERSION_CODENAME=$CODENAME
ID=migood-os
ID_LIKE="ubuntu debian"
UBUNTU_CODENAME=$CODENAME
HOME_URL="https://github.com/Miguelqwe1701/migood-os"
LOGO=migood-os
EOF
ln -sf ../usr/lib/os-release /etc/os-release
echo "Migood OS $VERSION \\n \\l" > /etc/issue
echo "Migood OS $VERSION" > /etc/issue.net

say "9/10 Remove Ubuntu branding + Migood boot logo"
# Ubuntu's wallpapers can't be uninstalled (GNOME depends on that package and
# would be removed with it), so tell dpkg never to put those files on disk.
cat > /etc/dpkg/dpkg.cfg.d/migood-no-ubuntu-wallpapers <<'EOF'
path-exclude=/usr/share/backgrounds/*
path-exclude=/usr/share/gnome-background-properties/*ubuntu*
EOF
find /usr/share/backgrounds -mindepth 1 -maxdepth 1 ! -name migood -exec rm -rf {} +
rm -f /usr/share/gnome-background-properties/*ubuntu*
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
  # Electron's sandbox helper must be owned by root with the setuid bit.
  [ -f /opt/migood-games/chrome-sandbox ] && chown root:root /opt/migood-games/chrome-sandbox \
    && chmod 4755 /opt/migood-games/chrome-sandbox
  cat > /usr/share/applications/migood-games.desktop <<EOF
[Desktop Entry]
Name=Migood Games
Exec=$BIN %U
Icon=/usr/share/migood-os/migood-launcher.png
Type=Application
Categories=Game;
EOF
  install -d /etc/xdg/autostart
  cp /usr/share/applications/migood-games.desktop /etc/xdg/autostart/
else
  warn "no assets/migood-games-*.tar.gz, desktop app not installed"
fi

apt-get autoremove -y >/dev/null && apt-get clean

# Safety check: the desktop must still be there (an earlier version removed
# GNOME by accident and still "succeeded").
for p in gnome-shell gdm3 ubuntu-session; do
  dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" \
    || { echo "!! $p is missing, the desktop would be broken. Stopping."; exit 1; }
done
say "Done. Migood OS $VERSION customized."
if [ ${#WARNINGS[@]} -gt 0 ]; then
  printf '\033[1;33mWarnings (%d):\033[0m\n' "${#WARNINGS[@]}"
  printf '  - %s\n' "${WARNINGS[@]}"
fi
