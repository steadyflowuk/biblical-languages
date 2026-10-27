# Writing a lesson

Each lesson is one JSON file, `lessons/<lang>/<n>.json` (`grc` = Greek, `he` = Hebrew), listed in `lessons/index.json`.
The app (`js/lessons.js`) turns it into the five-step loop. After adding or changing a lesson:

1. Add it to `lessons/index.json` with a `file` (entries without one show as "Coming soon").
2. Add the file to `SHELL_FILES` in `sw.js` and bump `VERSION`, so it works offline.
3. Run `python3 tools/check_lessons.py`. It checks the format and spells every Greek and Hebrew word against the
   Bible text (Greek accents and Hebrew vowels included), checks verse references and dictionary keys, and checks
   that every answer is one of the options. For Greek it also checks that the capitalised syllable in each `say` is
   the accented one (one hyphenated part per vowel sound), and that Greek quoted in a verse `note` is in that verse.

## The index

```json
{ "id": "grc-1", "title": "The alphabet and its sounds", "sub": "24 letters, reading aloud, writing them",
  "minutes": 15, "file": "lessons/grc/1.json" }
```

The number after the dash is shown on the Learn path. Lessons appear in the order listed.

## The lesson file

```json
{ "id": "grc-1", "lang": "grc", "title": "…", "steps": [ hear, notice, practise, read, review ] }
```

All five steps, in that order. Each step is `{ "step": "hear", "intro": "optional line shown first", "cards": [ … ] }`.
Any Greek or Hebrew inside English text is picked out automatically and shown in the right font and direction.

### Hear and see (`hear`)

- `scene`: a picture and a sentence. `picture` (an emoji), `text` (Greek or Hebrew), `say` (pronunciation,
  stressed syllable in capitals: `en ar-KHAY`), `en` (English, hidden until asked for).
- `video`: `title`, `href` (https), `note`.

### Notice (`notice`)

- `explain`: `title`, `body` (a list of short paragraphs), `examples` (optional list of `{ "t", "say", "en" }`).
  Write explanations in your own words (Logos is for checking, not copying).

Explain cards can also carry a `table`: `{ "head": ["who", "ending", "λύω"], "rows": [["I", "-ω", "λύω"], …] }`
(every row as long as the head). Write endings and stems with a hyphen (`-ομεν`, `πιστεύ-`): the checker skips them.

### Spelling exceptions

- `"letters": true` on a card: it is about single letters, letter pairs or sounds, so its Greek/Hebrew isn't spell-checked.
- `"unattested": ["λύεις", "λύομεν"]` at the top of a lesson: textbook forms that happen not to occur in the Bible. The
  checker complains if a listed form does occur, so the list stays honest.
- Find verses for the Read step with `python3 tools/find_verses.py <lesson id> [extra keys…]`: it ranks New Testament
  verses by how many of their words the learner knows by the end of that lesson.

### Practise (`practise`), at least three drills

- `choose`: `prompt`, `options`, `answer` (the index of the right option, counted from 0), `explain`.
  Options are shuffled on screen. Add `"fragments": true` if the options are parts of words on purpose.
- `match`: `prompt`, `pairs` (`[["λόγος", "word"], …]`). Both columns are shuffled.
- `build`: `prompt`, `tiles` in the right order, `explain`. The tiles are shuffled; Hebrew runs right to left.
  Add `"join": ""` when the tiles make one word (letters, or stem + ending): they're spelt and shown joined.
- `parse`: `prompt`, `word`, `fields` (`{ "label", "options", "answer" }`), `explain`.

A drill missed the first time comes back once at the end of the practice ("Have another go"). The score on the
Learn path counts first tries only.

### Read (`read`)

- `verse`: `ref` like `"JHN 1:1"` or `"GEN 1:1"` (book ids from `data/books.json`, English verse numbers), and an
  optional `note`. The verse comes from the Bible data, word by word with the BSB; words the learner has met are
  underlined in gold.

### Review (`review`)

- `words`: `items` of `{ "k": "G3056", "t": "λόγος", "say": "LO-gos", "en": "word" }`. `k` is the dictionary key
  (see `data/lex/*-index.json`); `t` must match the dictionary spelling. On finishing, these go into the review list.

## Progress

Saved on the device under `ao:lessons` (place in the lesson, first-try results, best score) and `ao:reviewQueue`
(the words), so backups include them.
