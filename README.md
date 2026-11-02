# Aleph to Omega

A personal app for learning Biblical Hebrew and Koine Greek for Bible study. It installs to the home screen of an iPhone, iPad or Android phone and works offline.

**Open it:** https://steadyflowuk.github.io/biblical-languages/

- **iPhone or iPad:** open the link in Safari, tap Share, then *Add to Home Screen*.
- **Android:** open the link in Chrome and tap *Install app*.

## Working on it

Project notes, decisions and the checks to run are in `CLAUDE.md`; how to write a lesson is in `lessons/README.md`.

## Credits

- Fonts: Gentium Plus, Noto Serif Hebrew and Atkinson Hyperlegible, under the SIL Open Font Licence (`assets/fonts/LICENSES.txt`).
- Review scheduling: [ts-fsrs](https://github.com/open-spaced-repetition/ts-fsrs) 5.4.2 by Open Spaced Repetition, MIT licence (`js/vendor/ts-fsrs.LICENSE`), bundled by `tools/vendor_fsrs.sh`.
- Greek New Testament: the [SBL Greek New Testament](https://github.com/LogosBible/SBLGNT), copyright 2010 Society of Biblical Literature and Logos Bible Software, CC BY 4.0: its words, spelling, punctuation, paragraphs and verse numbers, without the apparatus signs. Each word is matched to STEPBible's tagging by `tools/build_data.py` (a handful of words SBL reads differently from every tagged edition are tagged there by hand).
- Hebrew and Aramaic Old Testament (Leningrad Codex), and the word-by-word translations, grammar explanations and lexicons for both: [STEPBible Data](https://github.com/STEPBible/STEPBible-Data), created by STEPBible.org based on work at Tyndale House Cambridge, CC BY 4.0. Reformatted for this app by `tools/build_data.py`. The biblical text, word-by-word translations, grammar codes and lexicon entries are as published; the plain-English grammar explanations are lightly restyled (emphasis capitals lowered, stray quotation marks removed). Greek dictionary definitions are STEPBible's, based on Abbott-Smith's *Manual Greek Lexicon of the New Testament* (public domain; [digital edition](https://github.com/translatable-exegetical-tools/Abbott-Smith)); entries marked (ML) come from the Middle Liddell via the [Perseus Digital Library](https://www.perseus.tufts.edu) (CC BY-SA 3.0 US), and those definitions may be reused under that licence. Hebrew dictionary definitions are from Strong's Hebrew dictionary (1890, public domain) as edited by the [Open Scriptures Hebrew Bible Project](https://github.com/openscriptures/HebrewLexicon) (CC BY 4.0); STEPBible's own Hebrew definitions (Online Bible's Abridged BDB) are not used. `tools/build_dictionary.py` adds every occurrence and form to each entry.
- English: Berean Standard Bible, public domain, via communityofbrothers.github.io (a few footnotes there repeat the word "a"; the doubled cases are tidied).
- Septuagint: H. B. Swete, *The Old Testament in Greek according to the Septuagint* (1909–1930), public domain; digital text [LXX-Swete-1930](https://github.com/eliranwong/LXX-Swete-1930) by Eliran Wong, GPL-3.0: the files in `data/lxx` stay under that licence (see `data/lxx/README.md` for the source and changes). Lined up with the Hebrew using STEPBible's versification data (TVTMS, CC BY 4.0) by `tools/build_lxx.py`.
- ESV (optional, with your own free key from api.esv.org): Scripture quotations marked ESV are from the ESV® Bible (The Holy Bible, English Standard Version®), © 2001 by Crossway, a publishing ministry of Good News Publishers. Used by permission. All rights reserved. The ESV text is fetched on your device and is not part of this repository. [www.esv.org](https://www.esv.org)
- Videos and audio are links to their makers' own pages (Alpha with Angela and Aleph with Beth by Angela Taylor and Andrew and Bethany Case, and others listed in `lessons/media.json`); nothing of theirs is bundled.
- The Hebrew is checked against the Open Scriptures Hebrew Bible (CC BY 4.0).
