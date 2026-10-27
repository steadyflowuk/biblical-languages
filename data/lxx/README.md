# Septuagint data (GPL-3.0)

The files in this folder are licensed under the GNU General Public License, version 3 (see LICENSE in this folder),
because they are derived from a GPL-3.0 database. The rest of this repository is not affected by that licence.

## Source

- Text: H. B. Swete, *The Old Testament in Greek according to the Septuagint* (Cambridge University Press;
  vol. I 4th ed. 1909, repr. 1925; vol. II 3rd ed. 1907; vol. III 4th ed. 1912, repr. 1930). Public domain.
- Digital text: [LXX-Swete-1930](https://github.com/eliranwong/LXX-Swete-1930) by Eliran Wong (BibleBento.com),
  text supplied by Pasquale Amicarelli; licensed GPL-3.0. Used: commit 1d3efc3 (17 June 2017),
  file `01-Swete_word_with_punctuations.csv` with `00-Swete_versification.csv`.
- Verse alignment with the Hebrew/English Bible uses STEPBible's TVTMS versification data (CC BY 4.0,
  STEPBible.org / Tyndale House Cambridge).

## Changes (27 October 2026, Aleph to Omega)

These files were produced from the source by `tools/build_lxx.py` in this repository (the full method is there):

- `text/<BOOK>.json`: the words joined into verses, grouped by book and chapter, in Swete's numbering.
  Swete's editorial marks ⸂ ⸃ ⸆ and subsection numbers such as [1] are left out, and accents are stored in
  standard Unicode form (NFC). The words themselves are unchanged.
- `ot/<BOOK>.json`: each verse of the Hebrew/English Old Testament matched to the Swete verse(s) it corresponds to.
- `books.json`: the list of books and chapters, and which Hebrew chapter each Septuagint chapter mostly matches.

You may copy, share and change these files under the terms of the GPL-3.0; keep this notice and the LICENSE with them.
