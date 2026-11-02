# Independent review brief

Give this whole file to a **separate reviewer agent** after `python3 tools/check_all.py` has passed. The code checks
cover everything that can be checked mechanically; this review covers what needs judgement. Past reviews found real
errors the tests missed: a tapped Greek word shown as its dictionary form (ἔστιν as εἰμί), a running-text note claiming
Acts 19:41 was missing, John 8 without its bracket note, Hebrew entries showing another word's definition, a lesson
note quoting "the kingdom of God" where the text has no "of God", and copyrighted text (NA28 wording, Online Bible
definitions) that every test had passed.
Session 14's review also found: correct Strong's definitions hidden for the commonest Hebrew words, editors' notes
inside definitions, a transliteration fix that missed accented words, a counting rule that dropped real occurrences,
לוֹ "for the him", Aramaic "king the", and two checks that could never fail. Look hardest at anything a fix or a rule
*removes* or *hides*: check what it caught that it shouldn't have.

## Ground rules for the reviewer

- **Report, don't edit.** List findings; the main session fixes them. Scratch files only under the session's scratchpad.
- Read `CLAUDE.md` first (Rules, the latest Session log entries, and the section for whatever changed).
- A local server runs at http://localhost:8765/. Playwright for Python is installed; Chromium is at
  `/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`. Use `service_workers="block"`. Phone size 390×844,
  iPad 1180×820; try light and dark, and Settings › Text size "Largest" at 320px wide.
- Don't re-run the long suites in `tools/` (the main session has). Prefer short scripts over clicking through.
- Data sources are in `/home/claude/src` (sblgnt, step, HebrewLexicon, lxx-swete, bsb, morphhb).
- Users: the owner and his retired mother, beginners, on iPhone, iPad and Android. Anything confusing to a beginner
  counts, not just what is technically wrong.

## What to review

1. **What changed since the last review.** `git log --stat` since the previous "full check" commit, and read the
   diff. For each change ask: is it right, and what else does it touch that nobody re-checked?
2. **Meaning, as a learner meets it.** Tap words in Today's verse, a lesson's Read step and the Reader (Greek, Hebrew,
   Aramaic, Septuagint). Is the word shown the word tapped? Is the English the meaning *in this verse*? Is the
   dictionary form and its meaning right and labelled as such? Joined words (κἀγώ, οὐκέτι, Μαράνα θά, Hebrew with
   prefixes) shown sensibly? Check at least two verses per screen, chosen differently each time.
3. **Notes and explanations are true.** Reader notes (missing verses, double brackets, Aramaic, qere/ketiv, psalm
   titles, Septuagint alignment), lesson explanations and Read-step notes, Letters guide, Settings text. Compare each
   claim with the actual text in `data/` (Greek = SBL Greek New Testament; Hebrew = Leningrad via STEPBible). Lesson
   notes quoting a verse in English must match what the Greek/Hebrew of that verse actually says.
4. **Dictionary entries.** Open entries across both languages, including split senses (H0430G/H, G2962G/H), names,
   Aramaic words, very common words and rare ones. Definition about this word? Counts plausible? Links work?
5. **Copyright and credits.** Every file under `data/` and every source in `tools/fetch_sources.sh`: is its licence
   one we may publish (public domain, CC BY, or the GPL Septuagint kept with its licence)? Read licence notes *inside*
   the source files, not just the repository licence (STEPBible's Hebrew "Meaning" column was Online Bible's).
   Nothing from NA28/NA27, LSB, NIV, NASB, Logos, Online Bible, or any other copyrighted edition. Credits in Settings ›
   About and README name each source, its licence (with a link) and what we changed.
6. **Wording.** British English, plain, sentence case, from the learner's point of view; no jargon left unexplained
   for a beginner; numbers quoted in text agree with the data.
7. **Devices.** Anything that would behave differently on an iPhone (Safari, home-screen app, iOS 15+), an iPad, or
   Android Chrome: tap targets, text size, the share sheet, speech, offline after an update (the service worker keeps
   the shell in `shell-<VERSION>` and data in the `DATA` cache named in `sw.js`).
8. **Anything else** that looks wrong, odd or confusing.

## How to report

A prioritised list, each with: where (file / screen / verse), what is wrong, evidence (what you saw vs what it should
be), and a suggested fix. Separate **definite errors** from **worth a look**. For areas where you found nothing, one
line saying what you checked.
