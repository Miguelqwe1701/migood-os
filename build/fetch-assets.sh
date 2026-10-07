#!/usr/bin/env bash
# Downloads the newest Migood Games Linux app into assets/ so the build can
# put it in the image. The brand images are already in the repo (assets/).
#
# The server describes the newest Linux build in /downloads/desktop/linux.json:
#   {"version":"3.9.1","file":"Migood-Games-3.9.1.tar.gz",
#    "url":"/downloads/desktop/Migood-Games-3.9.1.tar.gz","size":109597637,"sha256":"..."}
# The download must match that size and sha256 exactly: a half-downloaded or
# swapped file must never end up in an image.
#
# Exit codes (build-iso.sh uses them):
#   0  downloaded (or already had it), checked
#   1  downloaded but the size or sha256 is wrong: STOP the build
#   2  no server answered: build without a new app (an image made from an
#      earlier Migood OS keeps the app it already has)
# Tries each server in turn, because Cloudflare can block the main site.
set -euo pipefail
ASSETS="${ASSETS:-$(cd "$(dirname "$0")/.." && pwd)/assets}"
SERVERS="${SERVERS:-https://www.welltypers.it.com https://wth5zs3z-3001.usw3.devtunnels.ms}"

# One field from the JSON on stdin (python3 is on every build machine).
field() { python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"; }

for s in $SERVERS; do
  info="$(curl -fsS -m 30 "$s/downloads/desktop/linux.json" 2>/dev/null)" || continue
  ver="$(field version <<<"$info")" && url="$(field url <<<"$info")" \
    && size="$(field size <<<"$info")" && sha="$(field sha256 <<<"$info")" || continue
  # Only plain values: they end up in a file name and a URL.
  [[ "$ver" =~ ^[0-9A-Za-z.+-]+$ && "$url" == /* && "$size" =~ ^[0-9]+$ && "$sha" =~ ^[0-9a-f]{64}$ ]] || continue

  out="$ASSETS/migood-games-$ver.tar.gz"
  if [ -s "$out" ] && [ "$(sha256sum "$out" | cut -d' ' -f1)" = "$sha" ]; then
    echo "already have $out (sha256 ok)"
  else
    echo "downloading Migood Games $ver from $s$url"
    curl -fL -m 900 -C - -o "$out.part" "$s$url" || { echo "download from $s failed"; continue; }
    got_size="$(stat -c %s "$out.part")"
    got_sha="$(sha256sum "$out.part" | cut -d' ' -f1)"
    if [ "$got_size" != "$size" ] || [ "$got_sha" != "$sha" ]; then
      rm -f "$out.part"
      echo "!! Migood Games $ver does NOT match linux.json (size $got_size vs $size, sha256 $got_sha vs $sha)."
      echo "!! Stopping: a broken or swapped app must never ship in an image."
      exit 1
    fi
    mv "$out.part" "$out"
    echo "saved $out (size and sha256 match)"
  fi
  # Release notes say which app the image carries.
  echo "$ver" > "$ASSETS/migood-games.version"
  exit 0
done
echo "!! could not reach a Migood server for the app; the image keeps the app it already has (if any)"
exit 2
