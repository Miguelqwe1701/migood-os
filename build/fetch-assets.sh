#!/usr/bin/env bash
# Downloads the newest Migood Games Linux app into assets/ so the build can
# put it in the image. The brand images are already in the repo (assets/).
# Tries each server in turn, because Cloudflare can block the main site.
set -euo pipefail
ASSETS="$(cd "$(dirname "$0")/.." && pwd)/assets"
SERVERS="${SERVERS:-https://www.welltypers.it.com https://wth5zs3z-3001.usw3.devtunnels.ms}"

for s in $SERVERS; do
  # latest-linux.yml is the app's own update file: "version: 3.9.1" + "path: ...".
  yml="$(curl -fsS -m 30 "$s/downloads/desktop/latest-linux.yml" 2>/dev/null)" || continue
  file="$(sed -n 's/^path: *//p' <<<"$yml" | tr -d '\r')"
  [ -n "$file" ] || continue
  # Name it migood-games-<version>.tar.gz, which is what customize.sh looks for.
  ver="$(sed -n 's/^version: *//p' <<<"$yml" | tr -d '\r')"
  out="$ASSETS/migood-games-$ver.tar.gz"
  if [ -s "$out" ]; then echo "already have $out"; exit 0; fi
  echo "downloading $file from $s"
  if curl -fL -m 900 -C - -o "$out.part" "$s/downloads/desktop/$file"; then
    mv "$out.part" "$out"
    echo "saved $out"
    exit 0
  fi
done
echo "!! could not download the Migood Games app; the image will be built without it"
