#!/bin/sh
# Rebuild js/vendor/ts-fsrs.js from the ts-fsrs release (MIT): one ES2019 module, no build step in the app itself.
# Usage: tools/vendor_fsrs.sh <work dir>   (needs git and esbuild; npm isn't reachable here, esbuild ships in /opt/npm-tools)
set -e
TAG=v5.4.2
WORK=${1:?work dir}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ESBUILD=${ESBUILD:-/opt/npm-tools/node_modules/esbuild/bin/esbuild}
rm -rf "$WORK/tsf" && git clone -q --depth 1 --branch "$TAG" https://github.com/open-spaced-repetition/ts-fsrs.git "$WORK/tsf"
(cd "$WORK/tsf/packages/fsrs" && "$ESBUILD" src/index.ts --bundle --format=esm --target=es2019 --log-level=error --outfile="$WORK/ts-fsrs.mjs")
COMMIT=$(git -C "$WORK/tsf" rev-parse --short HEAD)
{ printf '/*! ts-fsrs %s (commit %s), MIT licence: see ts-fsrs.LICENSE. https://github.com/open-spaced-repetition/ts-fsrs\n    Bundled for the browser (ES2019, one file) by tools/vendor_fsrs.sh; do not edit by hand. */\n' "${TAG#v}" "$COMMIT"; cat "$WORK/ts-fsrs.mjs"; } > "$ROOT/js/vendor/ts-fsrs.js"
cp "$WORK/tsf/LICENSE" "$ROOT/js/vendor/ts-fsrs.LICENSE"
echo "js/vendor/ts-fsrs.js rebuilt from $TAG ($COMMIT)"
