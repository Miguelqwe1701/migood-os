#!/usr/bin/env bash
# Joins the Migood OS ISO parts from a GitHub release back into one .iso and
# checks it against the .sha256 file. (Releases split files over 2 GB.)
#
#   bash merge-iso.sh            parts are in this folder
#   bash merge-iso.sh ~/Downloads
set -euo pipefail
cd "${1:-.}"

shopt -s nullglob
parts=(migood-os-*.iso.part*)
if [ ${#parts[@]} -eq 0 ]; then
  if ls migood-os-*.iso >/dev/null 2>&1; then echo "Already one ISO, nothing to join."; exit 0; fi
  echo "No migood-os-*.iso.part* files here. Download all the parts from the release first."
  exit 1
fi
iso="${parts[0]%.part*}"                       # migood-os-0.1.0.iso.part00 -> migood-os-0.1.0.iso
mapfile -t sorted < <(printf '%s\n' "${parts[@]}" | sort)
echo "Joining ${#sorted[@]} parts into $iso ..."
cat "${sorted[@]}" > "$iso"

if [ -f "$iso.sha256" ]; then
  echo "Checking it..."
  if sha256sum -c "$iso.sha256"; then
    echo "Done: $iso is complete and correct. You can delete the .part files."
  else
    echo "!! The check failed: a part is missing or didn't download fully. Download the parts again."
    exit 1
  fi
else
  echo "Done: $iso (no .sha256 file here, so it wasn't checked)."
fi
