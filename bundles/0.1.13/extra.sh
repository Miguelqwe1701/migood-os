#!/usr/bin/env bash
# Runs on installed Migood OS PCs during the 0.1.13 update.
set -euo pipefail

chmod 755 /usr/lib/migood-os/migood-sleepd /usr/lib/migood-os/update /usr/lib/migood-os/migood-updates 2>/dev/null || true

if [ -f /opt/migood-games/resources/app.asar ]; then
  /usr/lib/migood-os/migood-sleepd --patch-app || true
fi

# Ensure Wi-Fi power saving is disabled so sleep check-ins never drop internet.
for p in /sys/class/net/wl*; do
  [ -e "$p" ] || continue
  iw dev "$(basename "$p")" set power_save off 2>/dev/null || true
done

systemctl daemon-reload 2>/dev/null || true
systemctl restart polkit.service 2>/dev/null || true
systemctl enable migood-sleepd.service 2>/dev/null || true
systemctl restart migood-sleepd.service 2>/dev/null || true

