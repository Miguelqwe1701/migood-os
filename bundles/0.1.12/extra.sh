#!/usr/bin/env bash
# 0.1.12: Patch Migood Games' app.asar for Remote Play sleep auth, restart
# migood-sleepd, and reload systemd/polkit for the updated Migood Updates services.
ROOT="${MIGOOD_ROOT:-/}"
if [ "$ROOT" = / ]; then
  /usr/lib/migood-os/migood-sleepd --patch-app 2>/dev/null || true
  systemctl daemon-reload 2>/dev/null || true
  systemctl restart migood-sleepd.service 2>/dev/null || true
fi

