# Writing the Guide

The Guide tab explains every word, sign and idea a beginner meets in the app. It is written by hand in
`guide/src/*.md` (one file per section, in file-name order) and built into `guide/guide.json` and
`guide/examples.json` by `python3 tools/build_guide.py`. Never edit the built files.

After any change: `python3 tools/build_guide.py`, then `python3 tools/check_guide.py` (format, links, spelling,
plain English, examples, numbers) and `node tools/check_guide.mjs` (every grammar label, abbreviation and sign the
app shows has an entry; voices). Bump `VERSION` in `sw.js`.

## A section

```
# greek-verbs | Greek verbs

One or more paragraphs introducing the section.
```

## An entry

```
## aorist | Aorist
lang: grc
aka: aor., simple past
match: aorist
see: tense, aspect, 2nd-aorist
lessons: grc-4
find: grc ^V-A
short: One sentence a complete beginner can follow.

Paragraphs, separated by blank lines.

- a list
- of points

Table: optional caption
| head | head |
| cell | cell |

> JHN 11:35 ἐδάκρυσεν | an optional note on this example
```

- `id`: lower case, digits and hyphens; never change it once published (links and searches use it).
- `lang`: `grc`, `he`, `arc` (Aramaic), `both`, or leave it out for ideas that apply to any language.
- `aka`: other names and abbreviations, comma-separated; all are searchable.
- `match`: the words in the app's grammar labels that this entry explains, separated by `;`. A phrase can carry a
  short meaning for the "What do these words mean?" page: `2nd singular=you (one person)`.
- `see`: related entries. `lessons`: lessons that teach this (`grc-4`). `app`: where the app shows it (free text ids).
- `find: LANG PATTERN [n=3]`: a regular expression on the Bible's grammar codes (Greek: each part of a code such as
  `V-2AAI-3S`; Hebrew and Aramaic: the whole code without its language letter, such as `C/Vqw3ms` for `HC/Vqw3ms`). The builder picks `n` examples and counts
  every word that matches; the entry shows the count.
- `count: KEY LANG PATTERN`: a number to use in the text as `{{KEY}}`. Numbers are never typed into the prose.
- `unattested`: textbook forms used in a table that don't occur in the Bible (like a lesson's).

Inside text:
- `[[id]]` or `[[id|words]]` links to another entry. The first time an entry uses a term that has its own entry,
  it must link to it (the checker insists), so a beginner can always tap through.
- `[JHN 3:16]` or `[JHN 3:16|words]` links to the Reader.
- Greek and Hebrew are found automatically, shown in the right font and direction, and can be tapped to hear them.
  Every word must be spelt as in the Bible (or listed in `unattested`); endings and stems are written with a hyphen
  (`-ομεν`, `λυ-`). A Hebrew word is said as the Reader says one real occurrence of it.
- `*words*` for emphasis, `**words**` for bold (the names of buttons and rows).

Write for someone who has never learned a language: English examples first, one idea per sentence, British spelling,
no Latin abbreviations (write "for example", not "e.g.").
