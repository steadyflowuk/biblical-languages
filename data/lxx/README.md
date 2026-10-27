# Septuagint data

Text: H. B. Swete, *The Old Testament in Greek according to the Septuagint* (Cambridge, 1909–1930), public domain.
Digital text: [LXX-Swete-1930](https://github.com/eliranwong/LXX-Swete-1930) by Eliran Wong (BibleBento), supplied by
Pasquale Amicarelli, licensed GPL-3.0 (see LICENSE in this folder). These files are reformatted from it by
`tools/build_lxx.py`; Swete's editorial marks ⸂ ⸃ ⸆ and subsection numbers are dropped, accents are stored
in standard Unicode form (NFC); the words are unchanged.

`ot/` lines the Septuagint up with the Hebrew/English verse numbers, using STEPBible's TVTMS versification data
(CC BY 4.0, STEPBible.org / Tyndale House Cambridge) plus the checks described in `tools/build_lxx.py`.
