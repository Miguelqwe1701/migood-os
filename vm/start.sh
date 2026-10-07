#!/usr/bin/env bash
# Downloads the newest Migood OS ISO from the Releases tab (joining the parts),
# then starts the VM. Needs: docker, and gh (GitHub CLI, signed in).
#   bash vm/start.sh            newest release
#   bash vm/start.sh v0.1.0     a specific one
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -e /dev/kvm ]; then
  echo "!! /dev/kvm is missing: the VM will be VERY slow (no hardware virtualization)."
  echo "   In Codespaces, pick a bigger machine type (4+ cores) or try again later."
fi

if [ ! -s migood-os.iso ]; then
  TAG="${1:-$(gh release list --limit 1 --json tagName -q '.[0].tagName')}"
  [ -n "$TAG" ] || { echo "No release yet: run the 'Build Migood OS' workflow first."; exit 1; }
  echo "Downloading Migood OS $TAG..."
  rm -rf dl && mkdir dl
  gh release download "$TAG" -D dl -p 'migood-os-*.iso*'
  if ls dl/*.iso.part* >/dev/null 2>&1; then
    cat $(ls dl/*.iso.part* | sort) > migood-os.iso    # join the parts
  else
    mv dl/migood-os-*.iso migood-os.iso
  fi
  ( cd dl && [ -f ./*.sha256 ] && sed "s#  .*#  ../migood-os.iso#" ./*.sha256 | sha256sum -c - ) \
    || echo "(no checksum file to check)"
  rm -rf dl
fi

mkdir -p storage
echo "Starting the VM. Open port 8006 to see it (Ctrl+C here stops it)."
docker compose up --build
