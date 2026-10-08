#!/usr/bin/env bash
# Checks that a Migood OS ISO is whole: the system file inside it
# (casper/filesystem.squashfs) is complete, and EVERY file in it can be read.
#
#   sudo bash build/check-iso.sh out/migood-os-0.1.6.iso
#
# Why: 0.1.5 booted, but Migood Games, Dolphin and Chromium wouldn't open, and
# the installer failed with "rsync failed with error code 11" (a read error):
# parts of the system file couldn't be read. The build runs this on the base
# ISO it starts from and on the ISO it makes, so a broken one is never
# released or used as the base for the next version.
#
# Exit 0 = good. Anything else = broken (the reason is printed).
set -euo pipefail
ISO="${1:?usage: check-iso.sh FILE.iso}"
[ "$(id -u)" = 0 ] || { echo "run as root (it mounts the ISO)"; exit 2; }

MNT="$(mktemp -d)"
cleanup() {
  mountpoint -q "$MNT/fs" 2>/dev/null && umount "$MNT/fs"
  mountpoint -q "$MNT/iso" 2>/dev/null && umount "$MNT/iso"
  rm -rf "$MNT"
}
trap cleanup EXIT
mkdir -p "$MNT/iso" "$MNT/fs"

# Mount the ISO (GitHub's runners, a normal PC). Containers often can't mount
# ISOs: then copy the system file out of it with xorriso instead.
if mount -o loop,ro "$ISO" "$MNT/iso" 2>/dev/null; then
  SQ="$MNT/iso/casper/filesystem.squashfs"
  SUMS="$MNT/iso/casper/filesystem.squashfs.sha256"
else
  echo "(can't mount the ISO here; copying the system file out of it)"
  SQ="$MNT/filesystem.squashfs"; SUMS="$MNT/filesystem.squashfs.sha256"
  xorriso -osirrox on -indev "$ISO" -extract /casper/filesystem.squashfs "$SQ" >/dev/null 2>&1 || true
  xorriso -osirrox on -indev "$ISO" -extract /casper/filesystem.squashfs.sha256 "$SUMS" >/dev/null 2>&1 || true
fi
[ -f "$SQ" ] || { echo "!! $ISO has no casper/filesystem.squashfs"; exit 1; }

# 1. Complete? squashfs says how many bytes it needs; the file must have them.
need="$(unsquashfs -s "$SQ" | sed -n 's/^Filesystem size \([0-9]*\) bytes.*/\1/p')"
have="$(stat -c %s "$SQ")"
echo "system file: $have bytes on the ISO, squashfs needs $need"
if [ -z "$need" ] || [ "$have" -lt "$need" ]; then
  echo "!! the system file is cut short (truncated)"; exit 1
fi
if [ -f "$SUMS" ]; then
  echo "checking its sha256..."
  [ "$(sha256sum "$SQ" | cut -d' ' -f1)" = "$(cut -d' ' -f1 "$SUMS")" ] \
    || { echo "!! sha256 doesn't match"; exit 1; }
fi

# 2. Readable? Decompress and read every file. (Into a pipe: tar skips the
# reading when it writes to /dev/null.)
echo "reading every file in the system (a few minutes)..."
if mount -t squashfs -o loop,ro "$SQ" "$MNT/fs" 2>/dev/null; then
  read_all() { tar -C "$MNT/fs" -cf - .; }
elif command -v sqfs2tar >/dev/null; then
  read_all() { sqfs2tar "$SQ"; }
else
  echo "!! can't mount squashfs and sqfs2tar is missing (apt install squashfs-tools-ng)"; exit 2
fi
bytes="$(read_all 2>"$MNT/errors" | wc -c)" || true
# tar notes like "socket ignored" aren't errors; anything else is.
grep -v -e 'socket ignored' -e '^$' "$MNT/errors" > "$MNT/real-errors" || true
if [ -s "$MNT/real-errors" ] || [ "${bytes:-0}" -eq 0 ]; then
  echo "!! some files can't be read:"; head -20 "$MNT/real-errors"; exit 1
fi
echo "ok: $ISO is whole ($((bytes / 1024 / 1024)) MB of files read without errors)"
