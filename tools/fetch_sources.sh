#!/usr/bin/env bash
# Download the open-licensed source data used by build_data.py.
# Usage: tools/fetch_sources.sh /path/to/sources
# Sources are large and are NOT committed to this repository.
set -euo pipefail
DEST="${1:?give a folder for the sources}"
mkdir -p "$DEST" && cd "$DEST"

# STEPBible Data (CC BY 4.0) — Tyndale House Cambridge / STEPBible.org
if [ ! -d step ]; then
  git clone -q --depth 1 --filter=blob:none --no-checkout https://github.com/STEPBible/STEPBible-Data step
  (cd step && git config gc.auto 0 && git sparse-checkout init --no-cone &&
   git sparse-checkout set --no-cone \
     '/Translators Amalgamated OT+NT/TAGNT*' '/Translators Amalgamated OT+NT/TAHOT*' \
     '/Lexicons/TBES*' '/Morphology codes/*' '/Versification/*' &&
   git checkout -q HEAD)
fi

# Swete's Septuagint (text public domain, 1909-1930; this database GPL-3.0) — Eliran Wong / BibleBento
if [ ! -d lxx-swete ]; then
  git clone -q --depth 1 https://github.com/eliranwong/LXX-Swete-1930 lxx-swete
fi

# Berean Standard Bible (public domain), as prepared for communityofbrothers.github.io
if [ ! -f bsb/bsb.json ]; then
  rm -rf cob && git clone -q --depth 1 --filter=blob:none --no-checkout \
    https://github.com/communityofbrothers/communityofbrothers.github.io cob
  (cd cob && git sparse-checkout init --no-cone && git sparse-checkout set --no-cone /assets/bsb.gz && git checkout -q HEAD)
  mkdir -p bsb && gunzip -c cob/assets/bsb.gz > bsb/bsb.json
fi

# Independent copies used only by tools/check_data.py
if [ ! -d sblgnt ]; then
  git clone -q --depth 1 --filter=blob:none --no-checkout https://github.com/LogosBible/SBLGNT sblgnt
  (cd sblgnt && git sparse-checkout init --no-cone && git sparse-checkout set --no-cone '/data/sblgnt/text/*' && git checkout -q HEAD)
fi
if [ ! -d morphhb ]; then
  git clone -q --depth 1 --filter=blob:none --no-checkout https://github.com/openscriptures/morphhb morphhb
  (cd morphhb && git sparse-checkout init --no-cone && git sparse-checkout set --no-cone '/wlc/*.xml' && git checkout -q HEAD)
fi
echo "Check sources ready: python3 tools/check_data.py $DEST/sblgnt $DEST/morphhb"
