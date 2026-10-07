#!/usr/bin/env bash
# One-off steps for PCs updating to 0.1.5 (runs as root at shutdown, after
# apply.sh copied the new files: migood-sleepd, its hook, migood-cli).
set -euo pipefail
ROOT="${MIGOOD_ROOT:-/}"

# Sleep & wake from anywhere: the service has to be switched on once.
chmod 755 "$ROOT/usr/lib/migood-os/migood-sleepd" "$ROOT/usr/bin/migood-cli" \
  "$ROOT/usr/lib/systemd/system-sleep/migood"
if [ "$ROOT" = / ]; then
  systemctl daemon-reload
  systemctl enable migood-sleepd.service
fi

# Earlier fixes that only came with new images (0.1.2): turn off Ubuntu's
# crash popup, and give Migood Games its AppArmor profile if it's missing.
if [ -f "$ROOT/etc/default/apport" ]; then
  sed -i 's/^enabled=.*/enabled=0/' "$ROOT/etc/default/apport"
fi
BIN="$ROOT/opt/migood-games/migood-games"
if [ -x "$BIN" ] && [ ! -f "$ROOT/etc/apparmor.d/migood-games" ]; then
  cat > "$ROOT/etc/apparmor.d/migood-games" <<'PROFILE'
# Lets Migood Games use its sandbox on Ubuntu 24.04 (see customize.sh).
abi <abi/4.0>,
include <tunables/global>

profile migood-games /opt/migood-games/migood-games flags=(unconfined) {
  userns,

  include if exists <local/migood-games>
}
PROFILE
fi
