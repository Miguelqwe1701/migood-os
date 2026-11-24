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

# 4. Migood Home (the new full-screen home screen). Its packages, then people's
#    next login goes to it (the desktop is one button away). Only if it can run.
chmod 755 /usr/lib/migood-os/migood-home /usr/lib/migood-os/migood-home-session /usr/lib/migood-os/migood-switch 2>/dev/null || true
DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends \
  gir1.2-webkit-6.0 matchbox-window-manager mate-polkit x11-xserver-utils gnome-keyring >/dev/null 2>&1 || true
if python3 -c "import gi; gi.require_version('WebKit', '6.0')" 2>/dev/null && command -v matchbox-window-manager >/dev/null; then
  for home in /home/*; do
    user="$(basename "$home")"
    id -u "$user" >/dev/null 2>&1 || continue
    [ "$(id -u "$user")" -ge 1000 ] && [ "$user" != guest ] || continue
    python3 - "$user" <<'PY'
import sys, importlib.machinery, importlib.util
loader = importlib.machinery.SourceFileLoader("ca", "/usr/lib/migood-os/create-account")
spec = importlib.util.spec_from_loader("ca", loader)
ca = importlib.util.module_from_spec(spec)
loader.exec_module(ca)
ca.start_in_home(sys.argv[1])
PY
  done
fi
