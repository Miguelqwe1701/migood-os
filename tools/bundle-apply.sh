#!/usr/bin/env bash
# Goes inside every update bundle as apply.sh (tools/make-bundle.sh puts it
# there). The Migood updater runs it as root at shutdown, from the folder the
# bundle was unpacked into:
#   files/        new and changed Migood files, laid out like / (copied over)
#   deleted.txt   Migood files removed in this version (one path per line)
#   extra.sh      optional one-off steps for this version (bundles/<version>/)
#
# MIGOOD_ROOT=/some/folder installs into that folder instead of / (the tests
# use it). The system steps (schemas, dconf, ...) only run on a real system.
set -euo pipefail
ROOT="${MIGOOD_ROOT:-/}"
cd "$(dirname "$0")"

if [ -d files ]; then
  cp -a files/. "$ROOT/"
fi
if [ -f deleted.txt ]; then
  while IFS= read -r path; do
    [ -n "$path" ] && rm -f "$ROOT/$path"
  done < deleted.txt
fi

if [ "$ROOT" = / ]; then
  # The same follow-up steps customize.sh does after copying the overlay.
  chmod 600 /etc/netplan/*.yaml 2>/dev/null || true
  glib-compile-schemas /usr/share/glib-2.0/schemas
  dconf update
  systemctl daemon-reload
fi

if [ -f extra.sh ]; then
  MIGOOD_ROOT="$ROOT" bash extra.sh
fi
