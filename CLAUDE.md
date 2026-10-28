# Aleph to Omega — project notes for Claude

Personal PWA for learning Biblical Hebrew (incl. Aramaic) and Koine Greek for Bible study.
Users: the owner and his mother (retired), on iPhone, iPad and Android. Beginner first; intermediate/advanced later.
Full research and plan: Claude Doc "Biblical Languages App — Research & Build Plan"
(https://claude.ai/artifact/6XUnCXehf36NFpjEky5anT).

## Rules
- Only public-domain or CC BY data is committed (site is public on GitHub Pages). No NA28, LSB or Logos text.
  One exception (Session 6): `data/lxx` is Swete's public-domain Septuagint from the GPL-3.0 LXX-Swete-1930 database,
  committed with its LICENSE and README. Keep that folder's LICENSE/README with it. The user confirmed keeping it
  (27 Oct 2026). GPL duties: licence + credit + dated notice of changes (written by build_lxx.py into
  data/lxx/README.md) + the files stay GPL; the rest of the repo isn't affected.
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
- `js/esv.js` ESV key + API + small offline store · Septuagint screen (`#/lxx/ID/CH[/V]`) lives in `js/reader.js`
- `js/lessons.js` lesson engine (route `#/lesson/LANG/ID`) · `lessons/` index + one JSON file per lesson (format: lessons/README.md)
- `js/review.js` Review trainer (#/review) · `js/sound.js` respelling + voice text (no DOM; Node can import it) ·
  `js/audio.js` Listen buttons (one capture-phase click handler in app.js) · `js/vendor/ts-fsrs.js` (MIT, tools/vendor_fsrs.sh)
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
- [x] 6 (27 Oct 2026): ESV (own key), Septuagint lined up with the Hebrew + its own screen, side-by-side layout.
- [x] 6b (27 Oct 2026): deep check — ESV half-book limit, brackets, 3 John 15; Septuagint runs/boundaries re-aligned; better look-ups.
- [x] 7 (27 Oct 2026): lesson engine — five steps, 4 drill types, retries, resume, progress, review list; two taster lessons.
- [x] 7b (27 Oct 2026): deep check — focus to Continue after answering, Back to an answered drill stays open, lesson
  signature (`sig`: steps and card counts) restarts a changed lesson cleanly, short step labels under 380px.
- [x] 8 (27 Oct 2026): Greek lessons grc-1…9 (Schwandt 1–8; alphabet split in two); tables, letter cards, joined tiles.
- [x] 8b (27 Oct 2026): deep check — quotations aren't capitalised in our text (lesson 3 fixed), Isaiah's smooth
  breathing, ω respelt "oh" everywhere, core words (ὁ, λόγος, καί, ἐν, θεός) also in course review lists, largest-text
  fixes (step labels, Continue, tables), joined builds say "pieces", Settings explains Restored Koine.
- [x] 9 (28 Oct 2026): review trainer (FSRS, lesson words + frequency lists of 316 Greek / 745 Hebrew words), Listen
  buttons everywhere with the phone's voices (Erasmian respelt for the Greek voice, Koine, Israeli Hebrew).
- [x] 10 (28 Oct 2026): Hebrew course he-1…10 (Wegner 1–12): letters, vowels, shewa/gutturals, syllables/dagesh,
  nouns, article, prepositions, וְ, adjectives and verbless sentences.
- [x] 9b/10b (28 Oct 2026): deep check — speech starts inside the tap (iOS needs it; no waiting for the voice list,
  help if nothing starts in 3 s), 60 simulated days of FSRS on a fake clock, list cards follow list corrections,
  clearer/British list meanings ("to be able", Sheol, honour), phrase entries dropped (743 Hebrew), Hebrew read-step
  underline also by dictionary form (טוֹב in Gen 1 is tagged as the verb), three Hebrew explanations tightened.
- [ ] 11 Today/media/progress · [ ] 12 Device testing + guide

## Data (Session 2)
- Rebuild: `tools/fetch_sources.sh <dir>` then `python3 tools/build_data.py <dir>`; verify with `python3 tools/check_data.py <dir>/sblgnt <dir>/morphhb` (46 checks).
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
- data.js retries a failed load once after 1.2 s; Reader and Septuagint load errors offer "Try again" (6b).
- data.js memory groups: Bible books keep 6, dictionary chunks keep 8. Results announce only "N matches" (role=status).
- Transliteration of written words (5c): lex/<greek|hebrew>-sounds.json = {looseNorm(TAHOT/TAGNT translit of the word):
  [keys]} (66/230 KB gz), only where it differs from the lemma's. Loaded in the background on the first Latin-letter
  search (search() returns {hits, pending}; draw() redraws when pending resolves). Exact sound → 0.7 "Form in the
  text"; same consonants (skeleton) within edit distance ≤2 → 1.6+ "Sounds like a word in the text" (bereishit,
  b'reshit, vayomer); phrases look up each word (sound or lemma trL), ranked in typed order. looseNorm now also maps
  tz→ts ('A.retz = erets) — loose_norm() in build_dictionary.py must stay identical.
- Source quirks kept as published: G2199H "[wife of Zebedee]" has no headword (we show the transliteration);
  κύριος/πνεῦμα/γυνή etc. are split into senses (counts per sense; together they match NA28 totals).

## Translations (Session 6)
- ESV: `js/esv.js`. Key in localStorage "esv:key" (not "ao:", so never in backups); Settings saves only after a test
  fetch (John 3:16). One request per chapter (`q=BBCCC001-BBCCC999`, book number = position in books.json, 1–66).
  Offline store "esv:chapters" ≤ 450 verses in all AND < half of each book (so one-chapter books are never stored),
  30 days; checked before fetching. In-memory: only the 2 chapters on the page. Crossway: ≤ 500 verses or half a
  book, whichever is less, per query/page/storage; 5,000 requests a day, 1,000 an hour, 60 a minute. parseChapter splits on [n];
  text before [1] is verse 0 only in Psalms; Song of Songs speaker labels and Psalm 119 letter headings (short
  standalone lines) are dropped. "[[" and the bracketed note just before it ("[Some of the earliest manuscripts…]")
  move to the start of the next verse (Mark 16:9, John 7:53); other bracketed lines stay (Psalm 145:13).
  Versification checked against the real API (all 1,189 chapters, 6b): ESV = BSB numbering except Mat 12:47 (ESV omits)
  and 3 John 1:15 (ESV has it, BSB folds it into 14). esvExtras() gives any ESV verse no row carries to the row
  with its number, else the one before (redraws once when that changes).
  Every page showing ESV text carries the credit + www.esv.org link; full notice in Settings. Never commit a key;
  tests mock api.esv.org (tools/test_translations.py).
- Septuagint data: `tools/build_lxx.py` (called by build_data.py when `<src>/lxx-swete` exists).
  data/lxx/books.json (60 books; app ids, DAN = Theodotion, DAG = Old Greek, ESG = Greek Esther, heb = {lxxCh: [OT id, ch]}),
  text/<ID>.json (Swete numbering), ot/<OTID>.json (each Hebrew/English verse → Swete ref + text, or null).
  Text is NFC (Swete source uses oxia ύ; NFC gives tonos as in the NT data). Alignment: TVTMS Greek column, then a
  per-chapter choice of numbering by verse lengths and learned Strong's→Greek word pairs; only local moves; hand
  OVERRIDES for Mal 4:4–6 and Dan 4:1–3. 3b (6b): shift_runs() picks an offset (−2..+2) per verse by dynamic
  programming, paying 0.8 per change of offset, so only consistent runs move (Ecc 7 is +1, Exo 25:11–33 −1,
  1 Kgs 6, Exo 39, Job 16/41, Song 6); 3c: two neighbouring verses sharing one Greek verse take the unused Greek
  verse between them and their neighbour (Deu 12:32 = Swete 12:32, Dan 5:31). 13 "weak" chapters (EXO 37,
  JOB 5/40/41, PRO 1/13/17/19/20/24/28/30/31) aren't lined up: a note links to the Septuagint screen instead.
  A whole-book word search was tried and removed (false moves like Gen 2:1 → 1:1). `tools/audit_lxx.py <src>`
  scores every verse against its neighbours (21 flags left, checked: noise in repetitive lists, not offsets).
- Reader: display options "Translations" (showBSB, showESV, showLXX; off in running text). Lines get a small tag
  (BSB tag only when another translation shows). LXX label "22:1" when numbering differs; psalm titles inside LXX
  verse 1 get a note. Load problems are kept in state.esvMsg / state.lxxMsg so redraws keep them.
- Side by side (readLayout "parallel"): `.pv` rows, `.cols.nN`; stacked with labels on phones, columns ≥ 760px with
  a header row; the Reader screen gets `.wide` (76rem). Words stay tappable.
- Septuagint words aren't tagged: a tap runs dictionary.lookupForm: NT forms list and headwords for the word and its
  Swete spellings (ει→ι, unassimilated συν-/ἐν-, without augment: ἐκληρονόμησαν → κληρονομ-); else guesses —
  stem + usual ending with ξ/ψ/σ swaps (μισοῦντας → μισέω, στενάξουσιν → στενάζω) or longest shared start; names
  only match names. On 1,500 random words: 87% exact, 8% labelled guesses (~85% right), 4% nothing. Offers a
  dictionary search. Septuagint screen: picker tab "Septuagint", prev/next across books, "Compare with the Hebrew",
  store lastLxx; the Read tab stays current.

## Lessons (Session 7)
- Lessons are data: `lessons/index.json` ({grc: [...], he: [...]}, entries without `file` = "Coming soon") and
  `lessons/<lang>/<n>.json` with the five steps in order: hear (scene, video) · notice (explain) · practise (choose,
  match, build, parse) · read (verse) · review (words). Authoring guide: lessons/README.md.
- `tools/check_lessons.py`: format, answers among options, verse refs, dictionary keys + spelling of review words,
  every Greek/Hebrew word spelt as in the Bible (Greek with accents, grave = acute; Hebrew consonants + vowels with
  marks sorted per letter, no cantillation — never NFC), lesson files in SHELL_FILES. `"fragments": true` on a choose
  card skips spelling its options (parts of words on purpose).
- Engine: options/pairs/tiles shuffled (never left in written order); a drill missed first time is appended once at
  the end of Practise ("Have another go"); score = first tries only. Progress `ao:lessons` {id: {v:1, pos, retries,
  first, done, best, completed}}; finished lessons restart from the start. Finish adds review words to
  `ao:reviewQueue` (dedup by key) — Session 9 adds FSRS scheduling to these items. Store `learnLang` picks the path
  shown on Learn and the "Next lesson" row on Today.
- Read step: verse from gnt/hot + BSB (reader.js exports bsbChapter, englishHTML); words whose Strong's number is in
  the review list or this lesson's words are underlined gold ("You know N of M words"); tap → lemma, gloss, grammar,
  dictionary link.
- Taster lessons (not the courses): grc-0 John 1:1, he-0 Genesis 1:1. Pronunciation in `say`, stressed syllable in
  capitals (Erasmian for Greek). Session 8 writes grc-1… following Schwandt; Session 10 he-1… following Wegner.
- Leaving and re-entering the same hash doesn't re-render (router): tests reach lessons via Learn.

## Greek course (Session 8)
- Order follows Schwandt (Logos: LLS:INTROGKGRAMEXREV; TOC at app.logos.com …/references/page.v): grc-1/2 alphabet
  (α–μ, ν–ω + vowel pairs; Schwandt 1), grc-3 breathings/accents/punctuation (2), grc-4 present active (3), grc-5 -έω
  contract verbs (4), grc-6 second declension nom/acc (5), grc-7 article + gen/dat + prepositions (6), grc-8 neuter (7),
  grc-9 first declension γραφή/ἡμέρα + whole article (8). Coming soon: grc-10 (Schwandt 9: δόξα, masc. 1st decl.),
  grc-11 (10: adjectives, εἰμί). Schwandt prints Koine first with Erasmian alternatives; the app teaches Erasmian.
- Pronunciation respelling (Erasmian): η ay, ει ay, ου oo, υ ü, ω oh, χ kh, ζ dz, ευ eu, αι ai, οι oi; stress in caps.
- Vocabulary: high-frequency NT words fitting each topic (not Schwandt's lists); keys checked against greek-index
  (split senses: τηρέω G5083G, κύριος G2962G, φωνή G5456G, οἶκος G3624G). Read verses chosen with tools/find_verses.py.
- check_lessons also checks Greek pronunciations (capitalised syllable = accented one, one part per vowel sound;
  skipped when the say has a note in it) and that Greek quoted in a verse note is in that verse (form or dictionary
  form; endings/stems with "-" skipped). Our NT text doesn't capitalise quotations (110 of 4,004 after "·").
- Short step labels show up to 460px (and to 680px at larger/largest text); lesson tables tighten and hyphenate
  English under 460px so every column stays in view; don't put long English in Greek table columns.
- Explain cards can carry `table`; `"letters": true` skips spelling; lesson `"unattested"` lists paradigm forms
  absent from the NT (λύεις, λύομεν); build `"join": ""` joins tiles into one word. Endings written "-ομεν" skip spelling.

## Hebrew course (Session 10)
- Order follows Wegner, A Simplified Grammar of Biblical Hebrew (Logos LLS:HBRWWRKBKLSS165; contents at
  app.logos.com/books/LLS%3AHBRWWRKBKLSS165/references/page.v — click the "Lesson n" links, they go to page.N; typing
  art= URLs doesn't work). he-1/2 letters (Wegner 1, split א–כ / ל–ת + finals + בגדכפת), he-3 vowels (2), he-4 shewa
  and throat letters (3, 5), he-5 syllables, stress, dagesh, maqqef (4, 6), he-6 nouns (7, 8), he-7 article (9),
  he-8 prepositions (10), he-9 וְ (11), he-10 adjectives + verbless sentences (12). Coming soon: he-11 construct (13),
  he-12 Qal perfect (14).
- Pronunciation (Israeli-based academic, like the decks): ch = ח, kh = spirant כ, v/f for spirant ב/פ, ts = צ,
  k = ק, vocal shewa e, qamets hatuf o, א/ע silent, stressed syllable in capitals, יהוה said a-do-NAI. Review words'
  say must equal the flashcard's (data/decks/hebrew.json) — check_lessons enforces it.
- Spelling: copy pointed forms from the data (TAHOT, without accents) rather than typing them; check_lessons compares
  consonants + vowels with marks sorted. Dictionary lemmas sometimes differ from the text: בֵּין is listed as בַּיִן,
  חָכְמָה as חׇכְמָה (qamets hatuf sign) — such words stay out of review lists. Psalm titles are verse 0.
- check_lessons also checks Hebrew quoted in verse notes (prefix/suffix parts count: הָאָרֶץ inside וְהָאָרֶץ;
  maqqef splits; endings written after "-" skipped). "letters": true on explain/choose/match/build cards with bare
  letters or vowel marks. find_verses.py works for he-… lessons (OT, main part of each word).

## Review and audio (Session 9)
- FSRS: ts-fsrs 5.4.2 (MIT) bundled to one ES2019 module by tools/vendor_fsrs.sh (git clone + esbuild from
  /opt/npm-tools; npm itself is blocked here). Defaults: FSRS-6 weights, retention 0.9, fuzz on, max 10 years.
- Store: cards {"grc:G3056": {id, lang, k, t, say, en, src lesson|deck, lesson, n, added, f: FSRS card (dates as
  ISO text)}}, reviewLog {day: {r, n}} (~100 days), reviewDecks {grc, he}, newPerDay 10, reviewLang, reviewAutoPlay,
  speechRate slow|normal. A word becomes a card only when first answered. The review day starts at 4am; "due today"
  = due before the next 4am. Words due again within 20 min return in the same session (a few cards later).
- New words: lesson words first (reviewQueue order), then switched-on lists, most common first, up to newPerDay
  minus today's new. Card id = deck's main sense (deck alias maps split senses: lesson key G2962H → G2962G); a list
  card later met in a lesson takes the lesson's wording.
- plan() refreshes list cards (src deck) from the current deck: wording, say and count follow corrections.
- store.get() returns a fresh copy of object defaults (a mutated default {} once leaked cards across a reset).
- Decks: tools/build_decks.py (also run by build_data.py) → data/decks/greek.json (316: Mounce's 319 minus split
  senses) and hebrew.json (743; Aramaic-only, H9001+ and the two "[כִּי] אם" phrase entries left out; "be X" → "to be X"). [key, lemma, gloss, count, say]; Greek say empty
  (the app respells), Hebrew say from the commonest standalone TAHOT translit (last capitalised syllable = stress;
  'E at the start can be hataf) → "ME-lekh"; ph → f; YHWH say "a-do-NAI". OVERRIDES = our wording where the brief
  gloss misleads on a card (keyed by lemma; Hebrew compared with marks sorted). In SHELL_FILES (offline from install).
- greekSay (js/sound.js): English-style syllables (one consonant to the next syllable; of two or more the first
  closes the syllable, except π β κ γ τ δ + λ/ρ and φ θ χ + ρ stay together; ξ splits k|s), ι = "ee" when open
  and stressed or before a vowel, γγ = ng|g. Matches all 176 hand-written lesson respellings; check_lessons runs
  tools/greek_say.mjs (Node) so lessons and app stay in step.
- Voices: Greek el-GR, Hebrew he/iw. Erasmian = respelt in Modern Greek letters (β μπ, δ ντ, γ γκ, ζ τζ, η/ει έι|εϊ,
  υ ου, αι άι|αϊ, οι όι|οϊ, αυ άου, ευ έου, no h); one-syllable words keep the mark so έι stays one sound. Koine =
  monotonic text. Hebrew: no cantillation/meteg/sof pasuq, maqaf → space, יהוה (also after one-letter prefixes) →
  Adonai, with hiriq → Elohim. Rate 0.75 (slow) or 1. No voice → toast explaining how to add one (iOS / Android).
  speak() is synchronous (phones only allow speech started inside the tap): voices not listed yet → set lang only
  (el-GR / he-IL) and let the phone choose; onfail toast if nothing starts within 3 s. warmUpVoices() at start.
- Listen buttons: lesson scenes, examples (not letter cards), word lists, verse ("Listen to the verse") and its
  word gloss, review cards, dictionary entries, Reader word sheets (Greek, Hebrew, Septuagint), Today's verse gloss,
  Settings "Try Greek/Hebrew". Real voices can only be judged on the devices (Session 12).

## Checks
- `python3 tools/test_app.py` (server on :8765 first) — 101 end-to-end checks; run before every push.
- `python3 tools/test_reader_edges.py` — 28 Reader edge cases (odd links, fast switching incl. OT↔NT, offline Hebrew, focus, back button, 320px).
- `python3 tools/sweep_reader.py [nt|ot|all]` — opens every chapter at 360px (NT ~10 min, OT ~35 min); expect
  0 issues and only 3JN 15 / REV 12:18 notes.
- `python3 tools/test_review.py` — 46 review/audio checks (incl. a week on a fake clock, speech before voices load) (voices replaced by a recorder; FSRS sessions, limits,
  lists, aliases, both languages, offline, 320px largest dark).
- `tools/check_data.py` now has 46 checks (5 for the dictionary, 5 for the Septuagint, 4 for the decks) (incl. OT BSB alignment both ways, psalm titles, Today's verses).
- `python3 tools/check_lessons.py` — validates every lesson (run after any lesson change).
- `python3 tools/test_lessons.py` — 77 lesson engine checks (drills, retries, resume, scores, review list, Hebrew RTL,
  keyboard, offline, 320px; every written lesson, Greek and Hebrew, finished with right answers at 320px; largest text at 320px).
- `python3 tools/test_dictionary.py` — 51 Dictionary checks (search, entries, links both ways, offline, 320px).
- `python3 tools/test_translations.py` — 70 ESV/Septuagint/side-by-side checks (ESV API mocked with real verse counts;
  ~12 min).
- `python3 tools/sweep_lxx.py [ot|lxx|all]` — every OT chapter side by side with the Septuagint + every Septuagint
  chapter at 360px (~40 min); expect 0 issues.
- `python3 tools/sweep_dictionary.py [G|H|all] [every-nth]` — opens every entry at 360px (~11 min); expect 0 issues.
- No WebKit here: iPhone/iPad behaviour must be checked on the user's devices.
