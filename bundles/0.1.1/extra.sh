#!/usr/bin/env bash
# One-off steps for PCs updating to 0.1.1: the parts of the 0.1.1 fixes that
# customize.sh does (they aren't overlay files, so make-bundle can't see them).
# Runs as root at shutdown, after apply.sh copied the new files.
#
# Not here on purpose: removing the "guest" account. That was only a problem on
# the live USB; on an installed PC Guest mode needs that account.
set -euo pipefail
ROOT="${MIGOOD_ROOT:-/}"

# Ubuntu's "Welcome to Ubuntu" wizard: gone, and switched off in GDM.
rm -f "$ROOT/etc/xdg/autostart/gnome-initial-setup-first-login.desktop" \
      "$ROOT/etc/xdg/autostart/gnome-initial-setup-copy-worker.desktop"
GDM="$ROOT/etc/gdm3/custom.conf"
if [ -f "$GDM" ] && ! grep -q '^InitialSetupEnable' "$GDM"; then
  sed -i 's/^\[daemon\]$/[daemon]\nInitialSetupEnable=false/' "$GDM"
fi

# Name some tools show.
LSB="$ROOT/etc/lsb-release"
if [ -f "$LSB" ]; then
  sed -i 's/^DISTRIB_DESCRIPTION=.*/DISTRIB_DESCRIPTION="Migood OS 0.1.1 (based on Ubuntu 24.04)"/' "$LSB"
fi
