#!/usr/bin/env bash
# 0.1.6: apps' sandboxes were blocked by AppArmor; the sysctl file comes with
# this bundle, apply it now so it works before the next restart too.
ROOT="${MIGOOD_ROOT:-/}"
if [ "$ROOT" = / ]; then sysctl -q -p /etc/sysctl.d/99-migood-userns.conf || true; fi
