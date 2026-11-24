#!/usr/bin/env bash
# Runs on installed Migood OS PCs during the 0.1.16 update.
# Hybrid AMD/Intel + NVIDIA laptops froze on the boot screen unless the dGPU was on.
set -euo pipefail
ROOT="${MIGOOD_ROOT:-/}"
chmod 755 "$ROOT/usr/lib/migood-os/migood-gpu-check" "$ROOT/usr/lib/migood-os/migood-graphics-setup" \
  "$ROOT/usr/lib/migood-os/migood-drivers" 2>/dev/null || true
[ "$ROOT" = / ] || exit 0
systemctl daemon-reload || true
systemctl enable migood-gpu-check.service || true
# 1. "nomodeset" copied from the installer's Safe graphics switched the AMD/Intel driver off.
if grep -qw nomodeset /etc/default/grub 2>/dev/null; then
  sed -i 's/\bnomodeset\b//g' /etc/default/grub
  update-grub || true
fi
# 2. The next online boot installs the newer (HWE) kernel and sets NVIDIA on-demand.
rm -f /var/lib/migood-os/drivers-checked
# 3. A PC stuck in NVIDIA-only PRIME mode can't show a screen when the dGPU is off.
/usr/lib/migood-os/migood-gpu-check || true
