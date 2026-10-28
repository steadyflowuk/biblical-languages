"""Check every lesson in lessons/ against the format and against the Bible data.

python3 tools/check_lessons.py

Checks: the index and files agree; each lesson has the five steps in order (hear, notice, practise, read, review);
every card is a known type with what it needs; answers are among the options; verses exist; review words exist in the
dictionary with the same spelling; Greek pronunciations stress the accented syllable; Greek words quoted in a verse
note are in that verse; every Greek and Hebrew word in a lesson is spelt as it is written in the Bible
(Greek accents and Hebrew vowels included); every lesson file is in sw.js SHELL_FILES so it works offline.
"""
import json, os, re, shutil, subprocess, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
STEPS = ["hear", "notice", "practise", "read", "review"]
CARDS = {
    "hear": {"scene", "video"},
    "notice": {"explain"},
    "practise": {"choose", "match", "build", "parse"},
    "read": {"verse"},
    "review": {"words"},
}
GREEK = re.compile("[Ͱ-Ͽἀ-῿]")
HEBREW = re.compile("[א-ת]")
problems = []
SKIP_SPELL = False


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def bad(where, msg):
    problems.append(f"{where}: {msg}")


# ---------------------------------------------------------------- spelling sources
def greek_key(w):
    """Compare Greek with accents and breathings, but grave = acute (καὶ in a sentence = καί) and no punctuation."""
    w = unicodedata.normalize("NFD", w).replace("̀", "́")
    w = re.sub(r"[^\ẁ-ͯ]", "", w)
    return unicodedata.normalize("NFC", w).lower()


def hebrew_key(w):
    """Compare Hebrew consonants + vowels + dagesh/shin dots, without cantillation or meteg; marks sorted per letter
    (never Unicode-normalised: the order of marks varies between sources)."""
    w = re.sub("[֑-ֽ֯׀׃׆־/]", "", w)
    out, marks = [], []
    for ch in w:
        if "ְ" <= ch <= "ׇ":
            marks.append(ch)
        else:
            out.append("".join(sorted(marks)))
            marks = []
            out.append(ch)
    out.append("".join(sorted(marks)))
    return "".join(out).strip()


books = load(os.path.join(DATA, "books.json"))
greek_forms, hebrew_forms, verses = set(), set(), {}
for b in books:
    d = load(os.path.join(DATA, "gnt" if b["lang"] == "grc" else "hot", f"{b['id']}.json"))
    for c, vs in d["ch"]:
        for v in vs:
            verses[f"{b['id']} {c}:{v[0]}"] = (b["lang"], v[1])
            for w in v[1]:
                if b["lang"] == "grc":
                    greek_forms.add(greek_key(w[0]))
                else:
                    hebrew_forms.add(hebrew_key(w[0]))
index = {}
for lang, f in (("grc", "greek-index.json"), ("he", "hebrew-index.json")):
    for e in load(os.path.join(DATA, "lex", f)):
        index[e[0]] = e
        (greek_forms if lang == "grc" else hebrew_forms).add(greek_key(e[1]) if lang == "grc" else hebrew_key(e[1]))


ALLOWED = set()  # per lesson: textbook forms that don't happen to occur in the Bible (lesson "unattested" list)


def spell(where, text, lang):
    """Every Greek/Hebrew word in text must be written as in the Bible (or be a dictionary form)."""
    if SKIP_SPELL:
        return
    for tok in re.split(r"[\s,.;:·()“”‘’!?—–׃־\"/=+…]+", text or ""):
        if not tok or tok in ALLOWED or tok.startswith("-") or tok.endswith("-"):
            continue  # "-ομεν", "πιστευ-": endings and stems written as such
        if lang == "grc" and GREEK.search(tok) and greek_key(tok) not in greek_forms:
            bad(where, f"Greek word not found as written in the Bible: {tok}")
        if lang == "he" and HEBREW.search(tok) and hebrew_key(tok) not in hebrew_forms:
            bad(where, f"Hebrew word not found as written in the Bible: {tok}")


# ---------------------------------------------------------------- pronunciation stress (Greek)
DIPHTHONGS = {"αι", "ει", "οι", "υι", "αυ", "ευ", "ου", "ηυ"}


def greek_stress(word):
    """(number of vowel sounds, which one carries the accent counted from the end) — diphthongs count once."""
    letters = []
    for ch in unicodedata.normalize("NFD", word):
        if unicodedata.combining(ch):
            if letters:
                letters[-1][1].append(ch)
        else:
            letters.append([ch.lower(), []])
    groups, i = [], 0
    while i < len(letters):
        b, m = letters[i]
        if b in "αεηιουω":
            nxt = letters[i + 1] if i + 1 < len(letters) else None
            if nxt and b + nxt[0] in DIPHTHONGS and "̈" not in nxt[1] and "ͅ" not in m:
                groups.append(m + nxt[1])
                i += 2
                continue
            groups.append(m)
        i += 1
    acc = None
    for k, m in enumerate(groups):
        if any(x in m for x in ("́", "̀", "͂")):
            acc = len(groups) - 1 - k
    return len(groups), acc


def check_say(where, text, say):
    """The capitalised syllable of a pronunciation must be the accented one, with one part per vowel sound."""
    words = [x for x in re.split(r"\s+", re.sub(r"[.,;·:!?()“”]", "", text or "")) if GREEK.search(x)]
    says = (say or "").split()
    if len(words) != len(says):
        return  # a note in the pronunciation ("kai (rhymes with eye)")
    SAY_PAIRS.append((where, " ".join(words), say))
    for word, sy in zip(words, says):
        n, acc = greek_stress(word)
        parts = sy.split("-")
        caps = [k for k, p in enumerate(parts) if re.search("[A-ZÜ]", p) and p.upper() == p]
        if acc is None or n < 2:
            continue
        if not caps:
            bad(where, f"{sy}: no stressed syllable in capitals for {word}")
        elif len(parts) - 1 - caps[-1] != acc:
            bad(where, f"{sy}: the stress should fall on the accented syllable of {word}")
        elif len(parts) != n:
            bad(where, f"{sy}: {word} has {n} syllables")


_deck = load(os.path.join(DATA, "decks", "hebrew.json"))
HE_DECK_SAY = {w[0]: w[4] for w in _deck["words"]}  # Hebrew review words say what the flashcard says
HE_DECK_ALIAS = _deck["alias"]
SAY_PAIRS = []  # (where, Greek, say): compared with the app's own respelling (js/sound.js greekSay) at the end


def check_note(where, note, ref):
    """Greek or Hebrew quoted in a verse note must be in that verse (as written, or as the dictionary form of a word in
    it). Hebrew is compared without accents, with each letter's marks sorted, and maqaf-joined words split."""
    if ref not in verses:
        return
    if verses[ref][0] == "he":
        words = verses[ref][1]
        ok = set()
        for w in words:
            for word in re.split("[־ ]", w[0]):
                parts = word.split("/")  # prefixes/main/suffixes: "הָאָרֶץ" counts inside "וְ/הָ/אָרֶץ"
                for i in range(len(parts)):
                    for j in range(i + 1, len(parts) + 1):
                        ok.add(hebrew_key("".join(parts[i:j])))
            for k in re.findall(r"H\d+[A-Z]?", str(w[3])):
                if k in index:
                    ok.add(hebrew_key(index[k][1]))
        for m in re.finditer(r"[\u05d0-\u05ea][\u0591-\u05bd\u05bf-\u05c7\u05d0-\u05ea]*", note or ""):
            before, after = note[m.start() - 1:m.start()], note[m.end():m.end() + 1]
            if len(re.sub("[^\u05d0-\u05ea]", "", m.group())) < 2 or "-" in (before, after) or re.match("[\u0591-\u05c7]", before):
                continue
            if hebrew_key(m.group()) not in ok:
                bad(where, f"the note quotes {m.group()}, which isn't in {ref}")
        return
    words = verses[ref][1]
    ok = {greek_key(w[0]) for w in words} | {greek_key(index[w[3]][1]) for w in words if w[3] in index}
    for m in re.finditer(r"[Ͱ-Ͽἀ-῿]+", note or ""):
        before, after = note[m.start() - 1:m.start()], note[m.end():m.end() + 1]
        if len(m.group()) < 2 or "-" in (before, after):
            continue  # endings and stems ("-οι", "ζητε-")
        if greek_key(m.group()) not in ok:
            bad(where, f"the note quotes {m.group()}, which isn't in {ref}")


# ---------------------------------------------------------------- lessons
lesson_index = load(os.path.join(ROOT, "lessons", "index.json"))
sw = open(os.path.join(ROOT, "sw.js"), encoding="utf-8").read()
for f in ("js/lessons.js", "lessons/index.json"):
    if f'"{f}"' not in sw:
        bad("sw.js", f"{f} is not in SHELL_FILES")
seen_ids = set()
for lang, entries in lesson_index.items():
    if lang not in ("grc", "he"):
        bad("index", f"unknown language {lang}")
    for entry in entries:
        lid = entry.get("id", "?")
        if lid in seen_ids:
            bad("index", f"duplicate id {lid}")
        seen_ids.add(lid)
        if not entry.get("title") or not entry.get("sub"):
            bad(lid, "index entry needs a title and sub")
        f = entry.get("file")
        if not f:
            continue  # planned lesson, not written yet
        if f'"{f}"' not in sw:
            bad(lid, f"{f} is not in sw.js SHELL_FILES (it would not work offline)")
        path = os.path.join(ROOT, f)
        if not os.path.exists(path):
            bad(lid, f"missing file {f}")
            continue
        L = load(path)
        ALLOWED.clear()
        for f in L.get("unattested", []):
            ALLOWED.add(f)
            if lang == "grc" and greek_key(f) in greek_forms:
                bad(lid, f"{f} is listed as unattested but does occur in the Bible: remove it from the list")
        if L.get("id") != lid or L.get("lang") != lang:
            bad(lid, f"file says id {L.get('id')} / lang {L.get('lang')}")
        steps = [s.get("step") for s in L.get("steps", [])]
        if steps != STEPS:
            bad(lid, f"steps should be {STEPS}, found {steps}")
        drills = 0
        for s in L.get("steps", []):
            st = s.get("step")
            if not s.get("cards"):
                bad(lid, f"step {st} has no cards")
            for i, c in enumerate(s.get("cards", [])):
                w = f"{lid} {st} card {i + 1} ({c.get('type')})"
                t = c.get("type")
                SKIP_SPELL = bool(c.get("letters"))  # "letters": true — cards about single letters and sounds
                if t not in CARDS.get(st, set()):
                    bad(w, f"card type {t} doesn't belong in step {st}")
                    continue
                if t == "scene":
                    if not (c.get("text") and c.get("en") and c.get("say")):
                        bad(w, "needs text, say and en")
                    spell(w, c.get("text"), lang)
                    if lang == "grc" and not SKIP_SPELL:
                        check_say(w, c.get("text"), c.get("say"))
                elif t == "video":
                    if not str(c.get("href", "")).startswith("https://") or not c.get("title"):
                        bad(w, "needs an https href and a title")
                elif t == "explain":
                    if not c.get("title") or not c.get("body"):
                        bad(w, "needs a title and body")
                    for ex in c.get("examples", []):
                        if not (ex.get("t") and ex.get("en")):
                            bad(w, "each example needs t and en")
                        spell(w, ex.get("t"), lang)
                        if lang == "grc" and not SKIP_SPELL and ex.get("say"):
                            check_say(w, ex.get("t"), ex.get("say"))
                    tb = c.get("table")
                    if tb:
                        if not tb.get("rows") or any(len(r) != len(tb.get("head") or tb["rows"][0]) for r in tb["rows"]):
                            bad(w, "table rows must all have as many cells as the head")
                        for r in tb.get("rows", []):
                            for x in r:
                                spell(w, x, lang)
                elif t == "choose":
                    drills += 1
                    opts = c.get("options", [])
                    if len(opts) < 2 or len(set(opts)) != len(opts):
                        bad(w, "needs at least two different options")
                    if not isinstance(c.get("answer"), int) or not 0 <= c["answer"] < len(opts):
                        bad(w, "answer must be the index of one of the options")
                    if not c.get("prompt") or not c.get("explain"):
                        bad(w, "needs a prompt and an explain")
                    if not c.get("fragments"):  # "fragments": true when the options are parts of words on purpose
                        for o in opts:
                            spell(w, o, lang)
                elif t == "match":
                    drills += 1
                    pairs = c.get("pairs", [])
                    if len(pairs) < 2 or len({a for a, _ in pairs}) != len(pairs) or len({b for _, b in pairs}) != len(pairs):
                        bad(w, "needs at least two pairs, each side different")
                    for a, _ in pairs:
                        spell(w, a, lang)
                elif t == "build":
                    drills += 1
                    tiles = c.get("tiles", [])
                    if len(tiles) < 2:
                        bad(w, "needs at least two tiles")
                    if not c.get("prompt") or not c.get("explain"):
                        bad(w, "needs a prompt and an explain")
                    spell(w, "".join(tiles) if c.get("join") == "" else " ".join(tiles), lang)
                elif t == "parse":
                    drills += 1
                    if not c.get("word") or not c.get("fields") or not c.get("explain"):
                        bad(w, "needs a word, fields and an explain")
                    spell(w, c.get("word"), lang)
                    for fl in c.get("fields", []):
                        if fl.get("answer") not in fl.get("options", []):
                            bad(w, f"field {fl.get('label')}: answer is not one of the options")
                elif t == "verse":
                    ref = c.get("ref")
                    if ref not in verses:
                        bad(w, f"verse {ref} not found")
                    elif verses[ref][0] != lang:
                        bad(w, f"verse {ref} is not in this lesson's language")
                    else:
                        check_note(w, c.get("note"), ref)
                elif t == "words":
                    if not c.get("items"):
                        bad(w, "needs items")
                    for it in c.get("items", []):
                        e = index.get(it.get("k"))
                        if not e:
                            bad(w, f"dictionary key {it.get('k')} not found")
                            continue
                        same = greek_key(e[1]) == greek_key(it.get("t", "")) if lang == "grc" else hebrew_key(e[1]) == hebrew_key(it.get("t", ""))
                        if not same:
                            bad(w, f"{it.get('k')} is {e[1]} in the dictionary, not {it.get('t')}")
                        if not it.get("en") or not it.get("say"):
                            bad(w, f"{it.get('k')} needs say and en")
                        elif lang == "grc":
                            check_say(w, it.get("t"), it.get("say"))
                        else:
                            card = HE_DECK_SAY.get(HE_DECK_ALIAS.get(it.get("k"), it.get("k")))
                            if card and card != it.get("say"):
                                bad(w, f"{it.get('t')}: say is {it.get('say')}, but the review card says {card} (data/decks/hebrew.json): make them agree")
        if drills < 3:
            bad(lid, f"only {drills} drills; a lesson needs at least 3")

# The app respells any other Greek word itself (dictionary, Reader, review cards): lessons must agree with it.
if shutil.which("node") and SAY_PAIRS:
    out = subprocess.run(["node", os.path.join(ROOT, "tools", "greek_say.mjs")], input="\n".join(g for _, g, _ in SAY_PAIRS),
                         capture_output=True, text=True, encoding="utf-8")
    if out.returncode:
        bad("tools/greek_say.mjs", out.stderr.strip()[:300])
    else:
        for (where, g, say), auto in zip(SAY_PAIRS, out.stdout.split("\n")):
            if auto.replace("?", "") != say.replace("?", ""):
                bad(where, f"{say}: the app would respell {g} as {auto}; make them agree (lesson or js/sound.js)")
else:
    print("(node not found: lesson pronunciations not compared with the app's respelling)")

lessons_written = sum(1 for es in lesson_index.values() for e in es if e.get("file"))
if problems:
    print(f"{len(problems)} problems in {lessons_written} lessons:")
    for p in problems:
        print("  ", p)
    sys.exit(1)
print(f"All {lessons_written} lessons pass ({len(greek_forms):,} Greek and {len(hebrew_forms):,} Hebrew spellings checked against).")
