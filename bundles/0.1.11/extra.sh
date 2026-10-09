#!/usr/bin/env bash
# 0.1.11: Restart migood-sleepd so the running service picks up login token support immediately.
ROOT="${MIGOOD_ROOT:-/}"
if [ "$ROOT" = / ]; then
  systemctl restart migood-sleepd.service 2>/dev/null || true
fi
