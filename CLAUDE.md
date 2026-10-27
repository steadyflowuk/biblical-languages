# Aleph to Omega — project notes for Claude

Personal PWA for learning Biblical Hebrew (incl. Aramaic) and Koine Greek for Bible study.
Users: the owner and his mother (retired), on iPhone, iPad and Android. Beginner first; intermediate/advanced later.
Full research and plan: Claude Doc "Biblical Languages App — Research & Build Plan"
(https://claude.ai/artifact/6XUnCXehf36NFpjEky5anT).

## Rules
- Only public-domain or CC BY data is committed (site is public on GitHub Pages). No NA28, LSB or Logos text.
- ESV only via Crossway's API with the user's own key, entered in Settings and kept on the device. Never commit a key.
- Logos (user's Logos Max library) is a research tool only: lesson order, checking glosses/explanations. Write in our own words.
- Plain HTML/CSS/ES modules, no build step. Large data is converted by scripts in `tools/`, never pasted by hand.
- Bump `VERSION` in `sw.js` on every release and add any new shell file to `SHELL_FILES`.
- Copy: plain, sentence case, from the learner's point of view. British English.
- After every session, give the user a rundown of **what they'll see change** in the app and **what they won't see
  yet** (and which session brings it), on top of the usual summary. Remind them to close and reopen the home-screen
  app twice to pick up the update.

## Decisions
- Greek first; Hebrew joins once Greek basics settle (both tracks exist from the start).
- Pronunciation defaults: Erasmian (Greek, setting offers Restored Koine), Israeli-based academic (Hebrew).
  Alpha with Angela uses Erasmian (confirmed on freegreek.online, 26 Oct 2026) — matches our default.
  Its videos are CC BY-SA and downloadable; link out rather than bundle (share-alike).
- Lesson loop: hear and see → notice → practise → read real verses → review (FSRS via ts-fsrs, vendored).
- Lesson order follows Schwandt (Greek, 37 lessons) and Wegner (Hebrew, 65 lessons) — both in the user's Logos library.

## Design
- Palette: navy #1E2B45, sage #8FA08A (deep #56705A), gold #C4A052 (deep #8C6D24), beige #EDE6D8, white.
- Fonts (self-hosted WOFF, subset, OFL): Atkinson Hyperlegible (UI/English), Gentium Plus (Greek, scripture English),
  Noto Serif Hebrew (Hebrew with full points and cantillation). Ezra SIL was not downloadable here.
- Phones: bottom tab bar (Today, Learn, Read, Words, Review); ≥900px: navy side rail plus Videos and Settings.
- The one bold element: the verse panel on Today (navy, large original text, tap a word for its gloss).

## Structure
- `index.html`, `manifest.webmanifest`, `sw.js` (shell cache + `data-v1` cache for `/data/`)
- `css/app.css` — tokens at top, light/dark, text size via `html[data-size]`
- `js/app.js` hash router · `js/screens.js` all screens · `js/store.js` settings + backup (localStorage keys `ao:*`)
- `js/install.js` add-to-home-screen help · `js/verses.js` built-in fallback verses · `js/data.js` data loader
- `js/reader.js` Reader: chapter view, word sheet, picker, display options (sheet component lives here too)
- `assets/fonts`, `assets/icons`

## Testing
- `python3 -m http.server 8765` then Playwright with `/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`
  at 390×844 (phone) and 1180×820 (iPad), light and dark. Check console errors and service worker.
- Network here: GitHub (git) works; npm and PyPI do not. Fetch open data via `git clone --depth 1 --filter=blob:none --sparse`.

## Session log
- [x] 1 (26 Oct 2026): app shell, offline, install help, navigation, theme, text size, backup, starter verses, videos page.
- [x] 1b (26 Oct 2026): deep check — 44px tap targets, iOS backup via share sheet, fresh-file updates, verses checked against SBLGNT/WLC.
- [x] 2 (26 Oct 2026): data pipeline — `data/` built from STEPBible + BSB; Today uses `data/votd.json`.
- [x] 3 (27 Oct 2026): Greek Reader — `js/reader.js`, routes `#/read/BOOK/CH[/VERSE]`.
- [x] 3b (27 Oct 2026): deep check — BSB placement (own number wins), grammar tag labels, focus trap, contrast, iOS 13.4 baseline.
- [ ] 4 Hebrew/Aramaic Reader · [ ] 5 Dictionary · [ ] 6 ESV + LXX + parallel
- [ ] 7 Lesson engine · [ ] 8 Greek lessons · [ ] 9 Vocab trainer + audio
- [ ] 10 Hebrew lessons · [ ] 11 Today/media/progress · [ ] 12 Device testing + guide

## Data (Session 2)
- Rebuild: `tools/fetch_sources.sh <dir>` then `python3 tools/build_data.py <dir>`; verify with `python3 tools/check_data.py <dir>/sblgnt <dir>/morphhb` (28 checks).
- Greek = TAGNT words whose editions include NA28, plus 64 places where NA28's reading sits in TAGNT's variant column
  (e.g. Jude 5 Ἰησοῦς) and 9 NA28 spellings. 137,954 words, 7,942 verses, NA28 verse numbering. 92% of verses
  letter-identical to SBLGNT; the rest are NA28 bracketed words and known NA28/SBL differences.
- TAGNT refs: main = NA28 numbering; [x.y] = English numbering for part of a verse; {x.y} = where other editions
  put it (e.g. Rom 16:25{14.24}). Missing the {..} form once dropped John 7:53 and Rom 16:25-27 — check_data guards it.
- Greek "after" can contain ¶ (paragraph break, 2,240×) and once ¬ (Mat 11:17): never display them; ¶ is useful
  for Reader paragraphs. NA28 double brackets [[ ]] are kept in before/after (John 7:53-8:11 etc.).
- Hebrew = TAHOT (Leningrad), English verse numbering with Hebrew ref kept where different (2,090 verses).
  Qere shown, ketiv in word note (flag "q"); 14 written-but-not-read words flagged "k"; type X words (from other
  manuscripts, e.g. Gen 4:8) flagged "x". 305,648 words. Psalm titles are English verse 0.
  Hebrew is NOT Unicode-normalised (NFC reorders dagesh/vowel marks in 47% of words) — never NFC Hebrew in JS either;
  compare Hebrew by consonants or with both sides normalised.
  99.4% of verses match WLC consonants; the rest are verse-division differences. Aramaic = morph codes starting "A".
- BSB from communityofbrothers.github.io/assets/bsb.gz (ebible/bereanbible blocked here). Known issue: some BSB
  footnotes contain stray "a" words from that conversion (e.g. "Literally a day one"); only "a a" fixed. Replace
  from an official BSB file if the user allows ebible.org or bereanbible.com in Settings > Capabilities.
- Numbering differences the Reader must map: 3 John 1:15 and Rev 12:18 (no BSB verse), 2 Cor 13:14 (BSB) = NA28 13:13.
  BSB omits 15 verses that NA28 also omits (Mat 17:21 etc.).
- Lexicon glosses can be "general: specific" (e.g. "to hear: hear"); show the part after ": " in compact UI.
- STEPBible asks that data isn't changed (corrections go to them): we reformat; only grammar explanations are restyled.
  Credit required (Settings > About, README).
- Shell gotcha: `pkill -f "http.server 8765"` inside a command that also contains that text kills the command itself.

## Reader (Session 3)
- Layouts: word by word (Greek + English/pronunciation/grammar under each word, BSB under each verse) or running
  text (paragraphs from ¶; BSB shown in the word sheet). Prefs in store: readLayout, showEnglish, showTranslit,
  showGrammar, showBSB, lastRead.
- Greek verse item may carry a 3rd element: list of English (BSB) verse refs its words belong to (from TAGNT [x.y],
  KJV-based) — 38 verses. BSB_REF_OVERRIDES in build_data.py fixes where the BSB differs from KJV (Rev 12:18 → 12:17).
  The Reader gives each English verse to the first NA28 verse holding its words; check_data verifies full coverage.
- BSB placement: an English verse goes under the NA28 verse with the same number if that verse holds any of its
  words, else under the first NA28 verse holding them. Only 3 John 15 and Rev 12:18 then show "part of verse …".
- Grammar display: friendlyGrammar() dedupes and maps source tags in ONE regex pass (individual → name of a person,
  location → place, title, "… gentilic" → people group); "1st person" in pronouns is grammar, left alone.
  shortGrammar() abbreviates for under-word display. Strong's shown in familiar form via strongs() (G0025 → G25).
- Double brackets [[ ]]: a one-per-chapter note explains them (Mark 16:8 Shorter Ending, 16:9-20, John 7:53-8:11).
- Sheets make every other body child `inert` while open (focus stays inside; Escape closes; focus returns).
- Light-theme small text uses --accent-ink #765A1C and --sage-ink #476050 (≥5:1 on beige). color-mix() has rgba
  fallbacks. JS avoids ??= etc.: baseline is iOS 13.4 (optional chaining). Older iPads won't run the app.
- Hebrew books currently show "arrives in the next update" — Session 4 replaces that with RTL interlinear.
- WORD_RE uses named groups (en, word, kind): adding an unnamed group once shifted numbers and broke Hebrew.

## Checks
- `python3 tools/test_app.py` (server on :8765 first) — 85 end-to-end checks; run before every push.
- `python3 tools/test_reader_edges.py` — 22 Reader edge cases (odd links, fast switching, focus, back button, 320px).
- `python3 tools/sweep_reader.py` — opens all 260 NT chapters (~10 min); expect 0 issues and only 3JN 15 / REV 12:18 notes.
- No WebKit here: iPhone/iPad behaviour must be checked on the user's devices.
