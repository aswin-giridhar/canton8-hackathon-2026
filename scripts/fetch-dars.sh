#!/usr/bin/env bash
# Copy the Splice token-standard DARs out of the LocalNet bundle into ./dars/,
# so agent-mandate/daml.yaml can reference them by a RELATIVE path and the
# project builds on any machine.
#
#   SPLICE_BUNDLE=/path/to/splice-node ./scripts/fetch-dars.sh
#
# Default assumes the bundle was extracted per LOCALNET.md.
set -euo pipefail
BUNDLE="${SPLICE_BUNDLE:-$HOME/localnet/splice-node}"
SRC="$BUNDLE/dars"
DEST="$(cd "$(dirname "$0")/.." && pwd)/dars"

if [ ! -d "$SRC" ]; then
  echo "Splice bundle not found at $SRC" >&2
  echo "Download it (see LOCALNET.md), or set SPLICE_BUNDLE=/path/to/splice-node" >&2
  exit 1
fi
mkdir -p "$DEST"
for d in splice-api-token-metadata-v1-current.dar \
         splice-api-token-holding-v1-current.dar \
         splice-api-token-transfer-instruction-v1-current.dar; do
  cp "$SRC/$d" "$DEST/$d"
  echo "  $d"
done
echo "DARs staged in ./dars/ - agent-mandate now builds."
