#!/usr/bin/env bash
# Builds a Migood OS live ISO from scratch on the command line (no Cubic, no
# desktop needed). Runs on any Ubuntu 24.04 machine as root: a VM, a cloud
# box, or GitHub Actions.
#
#   sudo bash build/build-iso.sh            -> out/migood-os-0.1.0.iso
#   sudo VERSION=0.2.0 bash build/build-iso.sh
#   sudo BASE_ISO=old.iso VERSION=0.2.0 bash build/build-iso.sh
#       -> starts from an existing Migood OS ISO and only applies the changes
#          (like Cubic does). Much faster than building Ubuntu from scratch.
#
# What it does, the same as Cubic does under the hood:
#   1. debootstrap: download a minimal Ubuntu 24.04 into work/chroot
#   2. install the desktop, kernel and casper (casper = "boot the live ISO")
#   3. run cubic/customize.sh inside it, which makes it Migood OS
#   4. pack it into one squashfs file and make a bootable ISO (BIOS + UEFI)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${VERSION:-0.1.0}"
WORK="${WORK:-$REPO/work}"
OUT="${OUT:-$REPO/out}"
MIRROR="${MIRROR:-http://archive.ubuntu.com/ubuntu}"
CH="$WORK/chroot"
ISO="$WORK/iso"
export DEBIAN_FRONTEND=noninteractive

say() { printf '\n\033[1;32m### %s\033[0m\n' "$*"; }
[ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 1; }

# The chroot borrows the host's /proc, /sys and /dev while we work in it.
mounts() {
  for d in proc sys dev dev/pts; do mountpoint -q "$CH/$d" || mount --bind "/$d" "$CH/$d"; done
}
unmounts() {
  for d in dev/pts dev sys proc; do mountpoint -q "$CH/$d" && umount -l "$CH/$d"; done; true
}
trap unmounts EXIT
# Passes the host's proxy setting through, if it has one (corporate networks,
# cloud sandboxes); on a normal machine these are empty and do nothing.
in_chroot() { chroot "$CH" /usr/bin/env -i HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin \
  DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 \
  ${HTTPS_PROXY:+HTTPS_PROXY=$HTTPS_PROXY https_proxy=$HTTPS_PROXY} "$@"; }

# If the host trusts extra certificates (e.g. a proxy that inspects HTTPS),
# the chroot needs them too while downloading. They're removed before packing
# so they never end up in the ISO.
EXTRA_CA=/usr/local/share/ca-certificates
add_host_cas() {
  ls "$EXTRA_CA"/*.crt >/dev/null 2>&1 || return 0
  mkdir -p "$CH$EXTRA_CA/build-host"
  cp "$EXTRA_CA"/*.crt "$CH$EXTRA_CA/build-host/"
  in_chroot update-ca-certificates >/dev/null 2>&1 || true
}
remove_host_cas() {
  [ -d "$CH$EXTRA_CA/build-host" ] || return 0
  rm -rf "$CH$EXTRA_CA/build-host"
  in_chroot update-ca-certificates --fresh >/dev/null 2>&1 || true
}

say "Build tools"
apt-get update -q
apt-get install -y -q debootstrap squashfs-tools xorriso grub-pc-bin \
  grub-efi-amd64-bin grub-common mtools dosfstools >/dev/null

if [ -n "${BASE_ISO:-}" ]; then
  say "1. Start from $BASE_ISO"
  unmounts
  rm -rf "$CH" "$WORK/base.squashfs"
  xorriso -osirrox on -indev "$BASE_ISO" \
    -extract /casper/filesystem.squashfs "$WORK/base.squashfs" >/dev/null 2>&1
  unsquashfs -no-progress -d "$CH" "$WORK/base.squashfs" >/dev/null
  rm -f "$WORK/base.squashfs"
else
  say "1. Base Ubuntu 24.04 (debootstrap)"
  if [ ! -x "$CH/usr/bin/apt-get" ]; then
    rm -rf "$CH" && mkdir -p "$CH"
    debootstrap --arch=amd64 --variant=minbase noble "$CH" "$MIRROR"
  fi
fi
mounts
# The build's own DNS, so apt can download. rm first: in an image it is a link
# to systemd-resolved, and cp would follow that link.
rm -f "$CH/etc/resolv.conf"
cp /etc/resolv.conf "$CH/etc/resolv.conf"
cat > "$CH/etc/apt/sources.list" <<EOF
deb $MIRROR noble main restricted universe multiverse
deb $MIRROR noble-updates main restricted universe multiverse
deb $MIRROR noble-security main restricted universe multiverse
EOF
# Stop packages from trying to start services inside the chroot.
printf '#!/bin/sh\nexit 101\n' > "$CH/usr/sbin/policy-rc.d"; chmod +x "$CH/usr/sbin/policy-rc.d"
echo migood-os > "$CH/etc/hostname"

say "2. Kernel, live-boot (casper) and GNOME desktop"
in_chroot apt-get update -q
in_chroot apt-get install -y -q --no-install-recommends \
  linux-generic casper discover laptop-detect os-prober \
  network-manager wpasupplicant locales sudo curl ca-certificates gpg \
  software-properties-common fontconfig dconf-cli plymouth plymouth-theme-spinner \
  >/dev/null
in_chroot apt-get install -y -q ubuntu-desktop-minimal >/dev/null
# The live session logs in as "migood" automatically.
cat > "$CH/etc/casper.conf" <<'EOF'
export USERNAME="migood"
export USERFULLNAME="Migood OS"
export HOST="migood-os"
export BUILD_SYSTEM="Ubuntu"
export FLAVOUR="Migood OS"
EOF

say "3. Make it Migood OS (cubic/customize.sh)"
add_host_cas
# 0 = new app ok, 2 = no server answered (keep the app already in the image),
# 1 = the download didn't match linux.json's size/sha256: stop the build.
rc=0; bash "$REPO/build/fetch-assets.sh" || rc=$?
[ "$rc" = 1 ] && { echo "!! Migood Games download failed its check, not building"; exit 1; }
rm -rf "$CH/root/migood-os" && mkdir -p "$CH/root/migood-os"
cp -r "$REPO/cubic" "$REPO/overlay" "$REPO/assets" "$CH/root/migood-os/"
in_chroot env VERSION="$VERSION" BROWSER="${BROWSER:-chromium}" \
  bash /root/migood-os/cubic/customize.sh
# Which Migood Games app the image carries (for the release notes).
cp "$CH/usr/share/migood-os/migood-games.version" "$WORK/migood-games.version" 2>/dev/null \
  || echo unknown > "$WORK/migood-games.version"
rm -rf "$CH/root/migood-os"
in_chroot update-initramfs -u -k all >/dev/null

say "4. Pack the ISO"
remove_host_cas
rm -f "$CH/usr/sbin/policy-rc.d" "$CH/etc/resolv.conf"
# Name lookups (DNS) go through systemd-resolved on the finished system.
ln -s ../run/systemd/resolve/stub-resolv.conf "$CH/etc/resolv.conf"
in_chroot apt-get clean
rm -rf "$CH"/tmp/* "$CH"/var/lib/apt/lists/*
unmounts

rm -rf "$ISO" && mkdir -p "$ISO/casper" "$ISO/boot/grub" "$OUT"
cp "$(ls "$CH"/boot/vmlinuz-* | sort -V | tail -1)" "$ISO/casper/vmlinuz"
cp "$(ls "$CH"/boot/initrd.img-* | sort -V | tail -1)" "$ISO/casper/initrd"
chroot "$CH" dpkg-query -W --showformat='${Package} ${Version}\n' > "$ISO/casper/filesystem.manifest"
du -sx --block-size=1 "$CH" | cut -f1 > "$ISO/casper/filesystem.size"
mksquashfs "$CH" "$ISO/casper/filesystem.squashfs" -noappend -comp zstd \
  -e boot/vmlinuz boot/initrd.img >/dev/null
# Its fingerprint, so the installer can tell a damaged USB stick and download
# a good copy (named like this on the Migood server) instead.
(cd "$ISO/casper" && echo "$(sha256sum filesystem.squashfs | cut -d' ' -f1)  migood-os-$VERSION-filesystem.squashfs" \
  > filesystem.squashfs.sha256)
mkdir -p "$ISO/.disk"
echo "Migood OS $VERSION (based on Ubuntu 24.04)" > "$ISO/.disk/info"

cat > "$ISO/boot/grub/grub.cfg" <<EOF
set timeout=5
set default=0
insmod all_video
menuentry "Try Migood OS $VERSION" {
  linux /casper/vmlinuz boot=casper quiet splash ---
  initrd /casper/initrd
}
menuentry "Try Migood OS $VERSION (safe graphics)" {
  linux /casper/vmlinuz boot=casper nomodeset ---
  initrd /casper/initrd
}
EOF
# grub-mkrescue makes one ISO that boots on old BIOS PCs and on UEFI PCs.
NAME="migood-os-$VERSION.iso"
grub-mkrescue -o "$OUT/$NAME" "$ISO" -- -volid "MIGOOD_OS" >/dev/null 2>&1
(cd "$OUT" && sha256sum "$NAME" > "$NAME.sha256")
say "Done: $OUT/$NAME ($(du -h "$OUT/$NAME" | cut -f1))"
