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
- `js/install.js` add-to-home-screen help · `js/verses.js` starter verses (replace with real data in Session 2)
- `assets/fonts`, `assets/icons`

## Testing
- `python3 -m http.server 8765` then Playwright with `/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`
  at 390×844 (phone) and 1180×820 (iPad), light and dark. Check console errors and service worker.
- Network here: GitHub (git) works; npm and PyPI do not. Fetch open data via `git clone --depth 1 --filter=blob:none --sparse`.

## Session log
- [x] 1 (26 Oct 2026): app shell, offline, install help, navigation, theme, text size, backup, starter verses, videos page.
- [x] 1b (26 Oct 2026): deep check — 44px tap targets, iOS backup via share sheet, fresh-file updates, verses checked against SBLGNT/WLC.
- [ ] 2 Data pipeline: STEPBible TAGNT/TAHOT + TBESG/TBESH + BSB → per-book JSON in `data/`, counts checked.
- [ ] 3 Greek Reader · [ ] 4 Hebrew/Aramaic Reader · [ ] 5 Dictionary · [ ] 6 ESV + LXX + parallel
- [ ] 7 Lesson engine · [ ] 8 Greek lessons · [ ] 9 Vocab trainer + audio
- [ ] 10 Hebrew lessons · [ ] 11 Today/media/progress · [ ] 12 Device testing + guide

## Checks
- `python3 tools/test_app.py` (server on :8765 first) — 61 end-to-end checks; run before every push.
- No WebKit here: iPhone/iPad behaviour must be checked on the user's devices.
