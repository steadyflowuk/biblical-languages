"""Small slips in the text a learner reads, everywhere outside the Bible texts' own checks.

    python3 tools/check_text_hygiene.py [--self-test] [--write-baseline]

  Greek words (headwords, definitions, word lists, lessons, the Letters guide, Today's verses, built-in verses, the
  New Testament itself): the rules of printed Greek from tools/check_lxx_text.py (grave only on the last syllable,
  breathing on the first vowel, no capital inside a word, accent within three syllables, …), plus σ/ς in the right
  places, iota subscript only under α η ω, diaeresis only on ι υ, written in composed form (NFC).
  Hebrew words (headwords, word lists, lessons, the Letters guide): the rules of pointing from check_hebrew_text.py.
  Every string: no control characters, no U+FFFD (a character lost in conversion), no zero-width characters, no
  word mixing Latin with Greek or Cyrillic look-alikes (ο for o, Cyrenaїc), no HTML entities shown as text
  (&amp;), no doubled spaces or spaces before punctuation in English, brackets and quotes that pair up.
Known, deliberate cases (Abbott-Smith's dictionary citing a form with an unusual mark, a lexicon entry for a
punctuation sign) are approved one by one in tools/fixtures/text_hygiene_baseline.json.
"""
import collections, glob, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_lxx_text as greek_rules  # noqa: E402
import check_hebrew_text as hebrew_rules  # noqa: E402

BASELINE_FILE = os.path.join(ROOT, "tools", "fixtures", "text_hygiene_baseline.json")
_GL = "\u0386\u0388-\u03FF\u1F00-\u1FBC\u1FBE\u1FC2-\u1FCC\u1FD0-\u1FDB\u1FE0-\u1FEC\u1FF2-\u1FFC"
# whole words, not endings (-ου) or stems (προσ-) written with a hyphen
GREEK_WORD = re.compile(f"(?<![-\\w])[{_GL}][{_GL}\u0300-\u036F\u0345]*(?![-\\w])")
HEBREW_WORD = re.compile(r"[א-ת][א-ת֑-ׇװ-״]*")
CYR = "Ѐ-ӿ"


def strings(x, path=""):
    if isinstance(x, str):
        yield path, x
    elif isinstance(x, dict):
        for k, v in x.items():
            yield from strings(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from strings(v, f"{path}[{i}]")


def untag(html):
    """A definition as it reads: line breaks are spaces, inline tags (b, i, ref) vanish."""
    return re.sub(r"<[^>]+>", "", re.sub(r"<\s*br\s*/?>|<lb\s*/?>", " ", html, flags=re.I))


def sources():
    """(where, text, kind) for everything checked: kind 'en' text, 'greek' word list, 'hebrew' word list, 'mixed'."""
    for f in sorted(glob.glob("data/lex/G/*.json")):
        for k, e in json.load(open(f)).items():
            yield f"{k} headword", e[0], "greek"
            yield f"{k} gloss", e[3] if len(e) > 3 else "", "en"
            if len(e) > 4 and e[4]:
                yield f"{k} definition", untag(e[4]), "mixed"
    for f in sorted(glob.glob("data/lex/H/*.json")):
        for k, e in json.load(open(f)).items():
            yield f"{k} headword", e[0], "hebrew"
            yield f"{k} gloss", e[3] if len(e) > 3 else "", "en"
            if len(e) > 4 and e[4]:
                yield f"{k} definition", untag(e[4]), "mixed"
    for lang, f in (("greek", "data/decks/greek.json"), ("hebrew", "data/decks/hebrew.json")):
        for w in json.load(open(f))["words"]:
            yield f"{f} {w[0]}", w[1], lang
            yield f"{f} {w[0]} gloss", w[2], "en"
    for f in sorted(glob.glob("lessons/**/*.json", recursive=True)) + ["data/votd.json", "guide/guide.json"]:
        for path, s in strings(json.load(open(f))):
            yield f"{f}{path}", s, "mixed"
    for f in sorted(glob.glob("data/gnt/*.json")):
        d = json.load(open(f))
        for ch, vs in d["ch"]:
            for it in vs:
                for w in it[1]:
                    yield f"{d['id']} {ch}:{it[0]}", w[0], "greek"
                    yield f"{d['id']} {ch}:{it[0]} English", w[2], "en"
    for f in sorted(glob.glob("data/hot/*.json")):
        d = json.load(open(f))
        for ch, vs in d["ch"]:
            for it in vs:
                for w in it[1]:
                    yield f"{d['id']} {ch}:{it[0]} English", w[2], "en"
    for f in sorted(glob.glob("data/morph/*.json")):
        for k, v in json.load(open(f)).items():
            yield f"{f} {k}", " · ".join(x for x in v if x), "en"
    text = open("js/verses.js", encoding="utf-8").read()
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', text):
        yield "js/verses.js", m.group(1), "mixed"


CRASIS = {"ταὐτά", "ταὐτὰ", "ταὐτό", "ταὐτὸ", "τοὐναντίον", "τοὔνομα", "ταὐτὸν", "τοὖργον", "τοὔλαιον", "τοὐπίσω"}


def greek_problems(word, nfc=True):
    w = unicodedata.normalize("NFC", word)
    out = []
    if w in CRASIS or w in greek_rules.ALLOWED:  # two words run together (τὸ ὄνομα): a breathing inside is right
        return out
    if w != word and nfc:
        out.append("not in composed form (NFC)")
    out += greek_rules.problems_of(w)
    letters = re.sub(r"[̀-ͯ]", "", unicodedata.normalize("NFD", w))
    if "ς" in letters[:-1]:
        out.append("final ς inside a word")
    if letters.endswith("σ") and len(letters) > 1:
        out.append("σ at the end of a word (should be ς)")
    for base, m in greek_rules.marks(w):
        if "ͅ" in m and base.lower() not in "αηω":
            out.append(f"iota subscript under {base}")
        if "̈" in m and base.lower() not in "ιυ":
            out.append(f"diaeresis on {base}")
    return out


def check(text, kind, where):
    out = []
    if not text:
        return out
    if re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", text):
        out.append(("control character", where, text[:80]))
    if "�" in text:
        out.append(("lost character U+FFFD", where, text[:80]))
    if re.search("[​‌‍  ﻿]", text):
        out.append(("zero-width or line-separator character", where, text[:80]))
    for m in re.finditer(rf"\b\w*(?:[A-Za-z][{CYR}Ͱ-Ͽ]|[{CYR}Ͱ-Ͽ][A-Za-z])\w*", text):
        out.append(("Latin mixed with Greek or Cyrillic in one word", where, m.group(0)))
    if re.search(f"[{CYR}]", text):
        out.append(("Cyrillic letter", where, text[:80]))
    if re.search(r"&(?:amp|lt|gt|quot|#\d+|#x[0-9a-f]+);", text, re.I) and "definition" not in where:  # definitions decode them
        out.append(("HTML entity shown as text", where, text[:80]))
    shown_tidied = where.endswith(" English")  # a word's English: the Reader tidies its spaces and end punctuation
    if kind in ("en", "mixed"):
        plain = re.sub(GREEK_WORD, "G", re.sub(HEBREW_WORD, "H", text))
        if re.search(r"\S  +\S", plain) and "definition" not in where and not shown_tidied:  # definitions: HTML
            out.append(("doubled space", where, text[:80]))
        if re.search(r"[\w)\]] [,;:.!?)\]](?:\s|$)", plain) and not shown_tidied and not re.search(r"\b(?:p|pp|cf|al|ib|op|viz)\s[.,]", plain):
            out.append(("space before punctuation", where, text[:80]))
        if "definition" not in where:  # dictionary senses are numbered "1)", "1a)": not pairs
            for a, b in ("()", "[]", "{}"):
                if plain.count(a) != plain.count(b):
                    out.append((f"unpaired {a}{b}", where, text[:80]))
            if plain.count("“") != plain.count("”"):
                out.append(("unpaired “ ”", where, text[:80]))
    if kind in ("greek", "mixed", "en"):
        for m in GREEK_WORD.finditer(text):
            g = m.group(0)
            if len(g) < 2 and kind != "greek":
                continue
            for p in greek_problems(g, nfc="definition" not in where):
                if "definition" in where and "no breathing" in p and len(g) <= 4:
                    continue  # an ending cited after a headword (ἅγιος, α, ον)
                out.append((f"Greek: {p.split(':')[0]}", where, g))
    if kind in ("hebrew", "mixed"):
        for m in HEBREW_WORD.finditer(text):
            for p in hebrew_rules.pointing_problems(m.group(0)):
                out.append((f"Hebrew: {p.split(':')[0]}", where, m.group(0)))
    return out


def run(items):
    found = collections.defaultdict(list)
    n = 0
    for where, text, kind in items:
        n += 1
        for name, w, t in check(text, kind, where):
            found[name].append(f"{w}: {t}")
    return n, found


def main():
    if "--self-test" in sys.argv:
        planted = [("Greek grave inside a word", "λὸγος", "greek"), ("Greek σ at the end", "λογοσ", "greek"),
                   ("Greek breathing inside a word", "λογἐω", "greek"), ("Cyrillic in English", "Cyrenaїc word", "en"),
                   ("Latin o inside Greek", "λoγος", "greek"), ("HTML entity", "salt &amp; light", "en"),
                   ("two vowels on a Hebrew letter", "בְָּרִית", "hebrew"), ("unpaired bracket", "the (son of David", "en"),
                   ("doubled space", "the  son", "en"), ("iota subscript under ε", "λεͅγω", "greek")]
        ok = 0
        for desc, text, kind in planted:
            caught = bool(check(text, kind, "planted"))
            print(("caught " if caught else "MISSED ") + desc)
            ok += caught
        print(f"{ok}/{len(planted)} passed")
        sys.exit(0 if ok == len(planted) else 1)
    n, found = run(sources())
    if "--write-baseline" in sys.argv:
        json.dump(found, open(BASELINE_FILE, "w"), ensure_ascii=False, indent=1, sort_keys=True)
        print("Baseline written")
        return
    known = json.load(open(BASELINE_FILE)) if os.path.exists(BASELINE_FILE) else {}
    print(f"{n:,} pieces of text checked")
    fails = 0
    for name in sorted(set(found) | set(known), key=lambda k: -len(found.get(k, []))):
        now, before = found.get(name, []), known.get(name, [])
        new = [x for x in now if x not in before]
        gone = [x for x in before if x not in now]
        print(f"  {len(now):6}  {name}" + (f"  ({len(new)} new)" if new else "") + (f"  ({len(gone)} gone)" if gone else ""))
        for x in new[:20]:
            print("         NEW ", x[:200])
        for x in gone[:5]:
            print("         GONE", x[:200])
        fails += len(new) + len(gone)
    print(f"\n{fails} problems" if fails else "\n0 problems")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
