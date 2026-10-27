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
- `js/hebrew.js` Hebrew helpers: word parts, pronunciation, punctuation, short/full grammar labels
- `js/dictionary.js` Words tab: search + entries (routes `#/words`, `#/words/KEY`) · `js/nav.js` back/return memory
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
- [x] 4 (27 Oct 2026): Hebrew/Aramaic Reader — right to left, word parts, Aramaic and ketiv/qere notes, whole-Bible picker.
- [x] 4b (27 Oct 2026): deep check — count keys, compounds, clearer labels, not-read glosses, book memory limit.
- [x] 5 (27 Oct 2026): Dictionary — search every way, full entries, every occurrence, joined to Reader and Today.
- [x] 5b (27 Oct 2026): deep check — written-form search, verse-English keywords, looser spelling, retry after offline, 21,234 entries swept.
- [x] 5c (27 Oct 2026): transliteration search of written words ("bereshit", "vayomer", phrases like "bara elohim").
- [ ] 6 ESV + LXX + parallel
- [ ] 7 Lesson engine · [ ] 8 Greek lessons · [ ] 9 Vocab trainer + audio
- [ ] 10 Hebrew lessons · [ ] 11 Today/media/progress · [ ] 12 Device testing + guide

## Data (Session 2)
- Rebuild: `tools/fetch_sources.sh <dir>` then `python3 tools/build_data.py <dir>`; verify with `python3 tools/check_data.py <dir>/sblgnt <dir>/morphhb` (37 checks).
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
- WORD_RE uses named groups (en, word, kind): adding an unnamed group once shifted numbers and broke Hebrew.

## Hebrew Reader (Session 4)
- Same screen as Greek; `state.he` switches word/chapter/sheet builders (heWordHTML, heChapterHTML, heWordSheetHTML).
  Chapter holder gets `lang-he`; each word-by-word verse is `dir="rtl"` with the BSB `dir="ltr" lang="en"`;
  English/pronunciation/grammar spans under Hebrew words are `dir="ltr"` (otherwise brackets and full stops flip).
- OT verse numbers = English numbering, so the BSB sits under the same number (check_data verifies both ways).
  Where Hebrew numbering differs, a small "Heb c:v" shows under the verse number. Psalm titles = verse 0, labelled
  "title", with the BSB title text (bsbChapter puts pre-verse-1 text at 0). Chapter title "Psalm 23" (not Psalms).
- after: keep maqaf ־ (next word joins with no space), sof pasuq ׃, paseq ׀ (with a space), inverted nun ׆;
  drop paragraph letters פ ס but use them for running-text paragraphs (heParagraphAfter).
- Notes, placed before the first verse concerned: Aramaic (ranges, "Aram." label per verse in mixed chapters),
  ° qere marker (sheet shows the written ketiv), grey written-not-read (k), [brackets] for words not in Leningrad (x).
- Word sheet: Word parts (prefix/main/suffix with glosses), dictionary form of the {main} key, Strong's only for
  real numbers (STEPBible H9001+ are prefix/suffix labels, not Strong's), full grammar of the main part, how common.
- Short grammar: stems capitalised (Qal, Piel, Hiphil, Peal…), forms in grammar-book terms (wayyiqtol, weqatal,
  pf., impf., ptc., inf. cstr.), person/gender/number as 3ms etc.; "and (narrative)" dropped before a wayyiqtol.
- Picker has an Old/New Testament switch (opens on the current book's Testament); prev/next runs across the Bible.
- englishHTML drops unmatched < > [ ] (3 source glosses: Isa 7:23, Ezk 36:23, Lev 11:40) — data left as published.
- Main parts: {braces}, never H9001+; 37 compounds have two (מַה־זֶּה) — the sheet lists both. heMainKey handles
  "{H4480A\H9014}" and "{H9003/H2022G}". Counts use countFor() = the builder's lookup() (H0430J → H0430G).
  Known source quirks for Session 5: H0430J ("my gods", Gen 31:30) resolves to the "God" sense; טֶרֶם tagged numeric.
- Labels: HTc covers כִּי and אִם → "conj. (if/for)"; numerical adjectives → "number"/"number (order)";
  paragogic hé/nun → "added ending". heEnglish turns "(from: written, not read)" into "from" (note explains).
- data.js keeps only the 6 most recent book files (gnt/hot/bsb) in memory (was unbounded: 54 MB after 16 OT books).
- Device baseline in practice: CSS uses flex gap (iOS 14.1), inset (14.5), :has (15.4, cosmetic). Every device
  that runs iOS 13 can update to iOS 15, so "keep iOS up to date" is the advice; JS stays at the 13.4 level.
- build_votd skips BSB heading/cross-ref lines and drops פ ס from Hebrew (Today once showed "Here Is Your God!").

## Dictionary (Session 5)
- Data: `tools/build_dictionary.py` (called at the end of build_data.py) rewrites lex/G|H/<nn>.json entries to
  [lemma, translit, morph, gloss, def, rel, occ, forms]; occ = {BOOK: "c.v.wi …"} in Reader numbering; forms =
  [[form, count, code]] (Hebrew: main part, cantillation removed, grouped ignoring dagesh/rafe, one row per grammar).
  Index = [key, lemma, translit, gloss, count, keywords]; count = occurrence count (single source of truth for the
  Reader's "how common" too); keywords = up to 12 English words from the definition (so "shepherd" finds רָעָה).
  Keys resolve like build_data.lookup(); Hebrew counts main parts only (H9001+ prefixes are never listed).
  G20447 ἐπίστασις and G20833 ὁμείρομαι had no lexicon entry: added from the book lexicon.
- Search: Strong's (G3056, H430, 430, H430G), Greek/Hebrew with or without accents/vowels (finals folded),
  pronunciation, English gloss (both parts of "general: specific"), then definition keywords; lexicon-only words last.
- Glosses "general: specific" show as "to love (lover)" unless one contains the other (glossText).
- Definitions: STEPBible markup → safe HTML (b, i, br, ref). NT refs link into the Reader; Abbott-Smith's OT refs
  follow LXX numbering so stay plain. Sense markers (__I. __1. __(a); Hebrew 1) 1a) 1a1)) become indented lines.
  Mentions of other entries (H0157H) link to them. Credits in entry footer, Settings > About, README.
- Navigation: nav.js counts screens (Back = history.back when there is history, else #/words); entry remembers open
  books + scroll; Reader word → dictionary remembers the word (nav.remember) and highlights it on return; dictionary
  verse link → `#/read/BOOK/CH/V/WORD` highlights the word and shows "‹ Back to …" (nav.offerReturn/takeReturn).
- Today's verse words carry "k" (dictionary key) → "Look it up in the dictionary".
- Store: dictLang (both|G|H), recentWords (12 keys).
- Deep check (5b): index keywords are "verse English|definition words" (tg ranks 1.2, kw 2.5) — "Yahweh" → יהוה,
  "church" → ἐκκλησία. lex/<greek|hebrew>-forms.json = {normalised written form: [keys]} (77/221 KB gz), loaded only
  when Greek/Hebrew is typed: ἠγάπησεν, בְּרֵאשִׁית find their entry, labelled "Form in the text". Python
  greek_norm/hebrew_norm in build_dictionary.py must match greekNorm/hebrewNorm in dictionary.js.
  looseNorm (y/u, ph/f, ch/kh/h, w/v, doubles) for pronunciations: kyrios, huios (source "uhios"), nefesh, chesed.
  A gloss's slash parts match exactly ("in" → ἐν "in/on/among"). Multi-word English needs every word.
- NT reference links use a fixed BOOK_BY_STEP + NT_CHAPTERS table (6 source typos like "Mat.92.6" stay plain; 39
  refs to verses NA28 omits still link — the Reader explains the gap). 34,381 links, all checked by audit.
- Failed loads (offline) aren't cached: prepared/keyMaps/formLists and the Reader's counts retry next time.
- data.js memory groups: Bible books keep 6, dictionary chunks keep 8. Results announce only "N matches" (role=status).
- Transliteration of written words (5c): lex/<greek|hebrew>-sounds.json = {looseNorm(TAHOT/TAGNT translit of the word):
  [keys]} (66/230 KB gz), only where it differs from the lemma's. Loaded in the background on the first Latin-letter
  search (search() returns {hits, pending}; draw() redraws when pending resolves). Exact sound → 0.7 "Form in the
  text"; same consonants (skeleton) within edit distance ≤2 → 1.6+ "Sounds like a word in the text" (bereishit,
  b'reshit, vayomer); phrases look up each word (sound or lemma trL), ranked in typed order. looseNorm now also maps
  tz→ts ('A.retz = erets) — loose_norm() in build_dictionary.py must stay identical.
- Source quirks kept as published: G2199H "[wife of Zebedee]" has no headword (we show the transliteration);
  κύριος/πνεῦμα/γυνή etc. are split into senses (counts per sense; together they match NA28 totals).

## Checks
- `python3 tools/test_app.py` (server on :8765 first) — 101 end-to-end checks; run before every push.
- `python3 tools/test_reader_edges.py` — 28 Reader edge cases (odd links, fast switching incl. OT↔NT, offline Hebrew, focus, back button, 320px).
- `python3 tools/sweep_reader.py [nt|ot|all]` — opens every chapter at 360px (NT ~10 min, OT ~35 min); expect
  0 issues and only 3JN 15 / REV 12:18 notes.
- `tools/check_data.py` now has 37 checks (5 for the dictionary) (incl. OT BSB alignment both ways, psalm titles, Today's verses).
- `python3 tools/test_dictionary.py` — 51 Dictionary checks (search, entries, links both ways, offline, 320px).
- `python3 tools/sweep_dictionary.py [G|H|all] [every-nth]` — opens every entry at 360px (~11 min); expect 0 issues.
- No WebKit here: iPhone/iPad behaviour must be checked on the user's devices.
