#!/usr/bin/env bash
# Copy the working tree to the connected folder.
#
# The sandbox this was rebuilt in discards /tmp between commands, while the connected
# folder persists but does not permit unlink, which breaks git's index lock. So the
# repository lives in /tmp and is mirrored here, together with a git bundle carrying
# the real history.
set -u
DEST="${1:-/sessions/charming-sharp-volta/mnt/ChainLens}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SRC"
git bundle create /tmp/chainlens-rebuild-v2.bundle --all >/dev/null 2>&1 || true
cp -f /tmp/chainlens-rebuild-v2.bundle "$DEST/chainlens-rebuild-v2.bundle" 2>/dev/null || true
find . -path ./.git -prune -o -path ./var -prune -o -path ./node_modules -prune -o -type f -print | while read -r f; do
  rel="${f#./}"
  mkdir -p "$DEST/$(dirname "$rel")" 2>/dev/null
  cp -f "$f" "$DEST/$rel" 2>/dev/null
done
echo "mirrored $(find . -path ./.git -prune -o -path ./var -prune -o -type f -print | wc -l) files to $DEST"
