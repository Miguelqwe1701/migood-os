#!/usr/bin/env bash
# Makes an update bundle: the file that moves an installed Migood OS from one
# version to the next (the updater downloads it and installs it at shutdown).
#
#   bash tools/make-bundle.sh 0.1.0 0.1.1
#
# It looks at what changed in overlay/ between the git tags v0.1.0 and v0.1.1
# (or the current code, if there is no v0.1.1 tag yet)
# and packs it into out/migood-os-0.1.1-update.tar.gz (+ .sha256):
#   files/        every overlay file that is new or changed in 0.1.1
#   deleted.txt   overlay files 0.1.1 removed
#   apply.sh      copies them into place (tools/bundle-apply.sh)
#   extra.sh      bundles/0.1.1/extra.sh, if you wrote one: for changes that
#                 aren't overlay files (e.g. something customize.sh does)
#   debs/         bundles/0.1.1/debs/*.deb, if any: packages to install
set -euo pipefail

[ $# -eq 2 ] || { echo "usage: $0 <old version> <new version>   (e.g. 0.1.0 0.1.1)"; exit 1; }
FROM="${1#v}"; TO="${2#v}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$REPO/out}"
cd "$REPO"

git rev-parse -q --verify "v$FROM^{commit}" >/dev/null || { echo "no git tag v$FROM (try: git fetch --tags)"; exit 1; }
# The new version's tag doesn't exist yet while GitHub Actions is building it;
# then the code as it is right now (HEAD) is the new version.
if git rev-parse -q --verify "v$TO^{commit}" >/dev/null; then NEW="v$TO"; else NEW=HEAD; fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# A = added, M = modified, D = deleted, R = renamed (old path gone, new path added).
git diff --name-status --no-renames "v$FROM" "$NEW" -- overlay/ |
while IFS=$'\t' read -r status path; do
  rel="${path#overlay/}"
  case "$status" in
    D) echo "$rel" >> "$STAGE/deleted.txt" ;;
    *) mkdir -p "$STAGE/files/$(dirname "$rel")"
       git show "$NEW:$path" > "$STAGE/files/$rel"
       # Keep the "can run" permission (100755 in git) for scripts.
       mode="$(git ls-tree "$NEW" -- "$path" | cut -d' ' -f1)"
       if [ "$mode" = 100755 ]; then chmod 755 "$STAGE/files/$rel"; else chmod 644 "$STAGE/files/$rel"; fi ;;
  esac
done

cp tools/bundle-apply.sh "$STAGE/apply.sh"
EXTRA="bundles/$TO"
[ -f "$EXTRA/extra.sh" ] && cp "$EXTRA/extra.sh" "$STAGE/extra.sh"
if ls "$EXTRA"/debs/*.deb >/dev/null 2>&1; then
  mkdir -p "$STAGE/debs" && cp "$EXTRA"/debs/*.deb "$STAGE/debs/"
fi

mkdir -p "$OUT"
NAME="migood-os-$TO-update.tar.gz"
tar -czf "$OUT/$NAME" -C "$STAGE" --owner=0 --group=0 .
(cd "$OUT" && sha256sum "$NAME" > "$NAME.sha256")

echo "Made $OUT/$NAME ($FROM -> $TO). Inside:"
tar -tzf "$OUT/$NAME" | grep -v '/$' | sed 's#^\./#  #'
echo "sha256: $(cut -d' ' -f1 "$OUT/$NAME.sha256")  size: $(stat -c %s "$OUT/$NAME") bytes"
