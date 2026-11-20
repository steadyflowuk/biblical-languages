"""Build the Guide (Guide tab, 19 Nov 2026) from its sources: guide/src/*.md → guide/guide.json + guide/examples.json.

    python3 tools/build_guide.py            # build
    python3 tools/build_guide.py --check    # build in memory and fail if the committed files differ

The guide is written by hand in guide/src/ (format: guide/README.md). This script turns it into the files the app
reads, and fills in everything that comes from the Bible data so nothing is typed by hand:
  • examples: each entry's "find" (a grammar code pattern) picks real words from the text — well-known, short verses
    first (the daily-verse pool), different books and dictionary forms; "> REF WORD" lines name an example by hand.
    Each example keeps its verse's words, dictionary entries and BSB English, so the app shows and says it exactly as
    the Reader does (js/votd.js buildVerse), offline;
  • counts: how many words of the text match the entry's pattern ("In the New Testament: 5,412 words"), and named
    counts written {{KEY}} in the text;
  • Bible references [JHN 3:16] get the book's name; Greek and Hebrew words in the text get a real occurrence each
    (guide/examples.json "words"), so their Listen button says them as the Reader says that word.
"""
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data")
SRC = os.path.join(ROOT, "guide", "src")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_votd_pool import bsb_verses, ALWAYS, UNSETTLING  # noqa: E402

META = {"lang", "aka", "match", "see", "lessons", "find", "count", "short", "unattested", "app"}
LANGS = {"grc", "he", "arc", "both", ""}
GREEK = re.compile("[Ͱ-Ͽἀ-῿]")
HEBREW = re.compile("[א-ת]")
# a run of Greek or Hebrew in English text (same as the app's): a word or words, inner spaces and marks allowed
GREEK_RUN = re.compile("[\u0370-\u03ff\u1f00-\u1fff][\u0370-\u03ff\u1f00-\u1fff\u0300-\u036f\u2019\u1fbd]*")
HEBREW_RUN = re.compile("[\u05d0-\u05ea][\u0591-\u05bd\u05bf-\u05c7\u05d0-\u05ea]*")  # a maqqef splits words
REF = re.compile(r"\[([1-3]?[A-Z]{2,3}) (\d+):(\d+)(?:\|([^\]]+))?\]")
# famous books first when picking examples (a beginner meets John and Genesis before Obadiah)
BOOK_RANK = {k: i for i, k in enumerate("JHN MRK MAT LUK ROM 1JN ACT GAL EPH PHP 1CO 2CO COL HEB JAS 1PE 1TH REV "
                                        "GEN PSA EXO DEU ISA RUT 1SA 2SA PRO JON 1KI JER NUM JOS JDG ECC DAN EZR".split())}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def greek_key(w):
    w = re.sub("[’ʼ᾽'᾿]", "", w)
    w = unicodedata.normalize("NFD", w).replace("̀", "́")
    w = re.sub(r"[^Ͱ-Ͽἀ-῿́-ͅ]", "", w)
    return unicodedata.normalize("NFC", w).lower()


def hebrew_key(w):
    """Consonants + vowels + dagesh/shin dots, no cantillation, marks sorted per letter (never NFC: see CLAUDE.md)."""
    w = re.sub("[\u0591-\u05af\u05bd\u05bf\u05c0\u05c3\u05c6\u05be/]", "", w)  # accents, meteg, rafe (a reading aid), maqqef
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


# ---------------------------------------------------------------- reading the sources
class SourceError(Exception):
    pass


def parse_block(lines, where):
    """One body block: a table (| a | b |), a list (- item), examples (> REF WORD | note), a heading (### …) or a paragraph."""
    if lines[0].startswith("### "):
        return {"h": lines[0][4:].strip()}
    if lines[0].lower().startswith("table:") or lines[0].startswith("|"):
        caption = lines[0].split(":", 1)[1].strip() if lines[0].lower().startswith("table:") else ""
        # a | inside a link ([[id|words]], [JHN 3:16|words]) is not a cell border
        cells = lambda ln: [c.strip() for c in re.split(r"\|(?![^\[]*\])", ln.strip().strip("|"))]
        rows = [cells(ln) for ln in lines if ln.startswith("|")]
        if any(not ln.startswith("|") for ln in lines[1 if caption else 0:]):
            raise SourceError(f"{where}: a table's lines must all start with |")
        if len(rows) < 2 or len({len(r) for r in rows}) != 1:
            raise SourceError(f"{where}: a table needs a header and rows with the same number of cells")
        return {"table": {"caption": caption, "head": rows[0], "rows": rows[1:]}}
    if lines[0].startswith("- "):
        if any(not ln.startswith("- ") for ln in lines):
            raise SourceError(f"{where}: every line of a list starts with '- '")
        return {"ul": [ln[2:].strip() for ln in lines]}
    if lines[0].startswith("> "):
        ex = []
        for ln in lines:
            m = re.match(r"^> ([1-3]?[A-Z]{2,3}) (\d+):(\d+) (\S+)(?: \| (.+))?$", ln)
            if not m:
                raise SourceError(f"{where}: example lines are '> BOOK c:v WORD' or '> BOOK c:v WORD | note': {ln}")
            ex.append({"book": m.group(1), "ch": int(m.group(2)), "v": int(m.group(3)), "word": m.group(4), "note": m.group(5) or ""})
        return {"examples": ex}
    return {"p": " ".join(ln.strip() for ln in lines)}


def read_sources(src=SRC):
    sections, entries = [], []
    for name in sorted(os.listdir(src)):
        if not name.endswith(".md"):
            continue
        text = open(os.path.join(src, name), encoding="utf-8").read()
        section, entry, meta_open, block = None, None, False, []

        def flush():
            nonlocal block
            while entry is not None and len(block) > 1 and re.match(r"^(unattested|count): ", block[-1]):
                tail = block.pop()  # a meta line written straight after a paragraph or table
                saved, block = block, [tail]
                flush()
                block = saved
            if block and entry is not None and len(block) == 1 and re.match(r"^(unattested|count): ", block[0]):
                k, v = block[0].split(": ", 1)  # a meta line on its own further down an entry
                if k == "unattested":
                    entry["unattested"] += [x.strip() for x in v.split(",") if x.strip()]
                else:
                    f = v.split()
                    if len(f) != 3:
                        raise SourceError(f"{name}: {entry['id']}: count: KEY LANG PATTERN")
                    entry["counts"][f[0]] = {"lang": f[1], "pattern": f[2]}
                block = []
                return
            if block:
                where = f"{name}: {entry['id'] if entry else section['id'] if section else '?'}"
                b = parse_block(block, where)
                if entry is None:
                    if "p" not in b:
                        raise SourceError(f"{where}: a section's introduction is plain paragraphs")
                    section["intro"].append(b["p"])
                elif "examples" in b:
                    entry["examples"] += b["examples"]
                else:
                    entry["body"].append(b)
            block = []

        for n, raw in enumerate(text.split("\n"), 1):
            line = raw.rstrip()
            if line.startswith("# "):
                flush()
                m = re.match(r"^# ([a-z0-9-]+) \| (.+)$", line)
                if not m:
                    raise SourceError(f"{name}:{n}: a section starts '# id | Title'")
                section = {"id": m.group(1), "title": m.group(2).strip(), "intro": [], "file": name}
                sections.append(section)
                entry = None
                continue
            if line.startswith("## "):
                flush()
                m = re.match(r"^## ([a-z0-9-]+) \| (.+)$", line)
                if not m or section is None:
                    raise SourceError(f"{name}:{n}: an entry starts '## id | Title', inside a section")
                entry = {"id": m.group(1), "title": m.group(2).strip(), "section": section["id"], "lang": "", "aka": [],
                         "match": [], "see": [], "lessons": [], "find": [], "counts": {}, "short": "", "unattested": [],
                         "app": [], "body": [], "examples": [], "line": n, "file": name}
                entries.append(entry)
                meta_open = True
                continue
            if entry is not None and meta_open:
                m = re.match(r"^([a-z]+): (.*)$", line)
                if m and m.group(1) in META:
                    k, v = m.group(1), m.group(2).strip()
                    if k == "lang":
                        entry["lang"] = v
                    elif k in ("aka", "see", "lessons", "unattested", "app"):
                        entry[k] += [x.strip() for x in v.split(",") if x.strip()]
                    elif k == "match":
                        entry["match"] += [x.strip() for x in v.split(";") if x.strip()]
                    elif k == "short":
                        entry["short"] = v
                    elif k == "find":
                        f = v.split()
                        if len(f) < 2 or f[0] not in ("grc", "he", "arc"):
                            raise SourceError(f"{name}:{n}: find: LANG PATTERN [n=3]")
                        spec = {"lang": f[0], "pattern": f[1], "n": 3}
                        for opt in f[2:]:  # n=2, key=REGEX (only these dictionary entries), nokey=REGEX (not these)
                            k2, _, v2 = opt.partition("=")
                            if k2 == "n":
                                spec["n"] = int(v2)
                            elif k2 in ("key", "nokey"):
                                spec[k2] = v2
                            elif k2 == "avoid":  # verses not to pick: avoid=JHN2:5,MRK9:16
                                spec["avoid"] = v2.split(",")
                            else:
                                raise SourceError(f"{name}:{n}: find option {opt}: n=, key=, nokey= or avoid=")
                        entry["find"].append(spec)
                    elif k == "count":
                        f = v.split()
                        if len(f) != 3 or f[1] not in ("grc", "he", "arc"):
                            raise SourceError(f"{name}:{n}: count: KEY LANG PATTERN")
                        entry["counts"][f[0]] = {"lang": f[1], "pattern": f[2]}
                    continue
                if line == "":
                    meta_open = False
                    continue
                meta_open = False
            if line == "":
                flush()
            else:
                block.append(line)
        flush()
    return sections, entries


# ---------------------------------------------------------------- the Bible data
class Bible:
    def __init__(self):
        self.books = load(os.path.join(DATA, "books.json"))
        self.by_id = {b["id"]: b for b in self.books}
        pool = load(os.path.join(DATA, "votd-pool.json"))
        self.pool = {f"{bk} {r.replace('.', ':')}" for lang in ("grc", "he") for bk, refs in pool[lang].items() for r in refs.split()}
        self.orig, self.bsb = {}, {}
        # words by code: lang → code → [(book, ch, v, wi)]
        self.codes = {"grc": {}, "he": {}, "arc": {}}
        self.forms = {"grc": {}, "he": {}}  # key(form) → first (book, ch, v, wi)
        for b in self.books:
            d = load(os.path.join(DATA, "gnt" if b["lang"] == "grc" else "hot", f"{b['id']}.json"))
            self.orig[b["id"]] = d
            for c, vs in d["ch"]:
                for v, words in ((x[0], x[1]) for x in vs):
                    for wi, w in enumerate(words):
                        code = w[4] if len(w) > 4 else ""
                        lang = "grc" if b["lang"] == "grc" else ("arc" if code.startswith("A") else "he")
                        self.codes[lang].setdefault(code, []).append((b["id"], c, v, wi))
                        key = greek_key(w[0]) if lang == "grc" else hebrew_key(w[0])
                        self.forms["grc" if lang == "grc" else "he"].setdefault(key, (b["id"], c, v, wi))

    def by_key(self, lang, rx):
        out = []
        for b in self.books:
            if (b["lang"] == "grc") != (lang == "grc"):
                continue
            for c, vs in self.orig[b["id"]]["ch"]:
                for v, words in ((x[0], x[1]) for x in vs):
                    for wi, w in enumerate(words):
                        code = w[4] if len(w) > 4 else ""
                        if lang != "grc" and (code.startswith("A") != (lang == "arc")):
                            continue
                        keys = re.findall(r"\{([GH]\d{4,5}[A-Za-z]?)\}", w[3]) if lang != "grc" else w[3].split("+")
                        if any(rx.search(k) for k in keys):
                            out.append((b["id"], c, v, wi))
        return out

    def verse(self, bk, c, v):
        if not hasattr(self, "_vi"):
            self._vi = {(b, ch, x[0]): x[1] for b, d in self.orig.items() for ch, vs in d["ch"] for x in vs}
        return self._vi.get((bk, c, v))

    def english(self, bk, c, v):
        if bk not in self.bsb:
            self.bsb[bk] = load(os.path.join(DATA, "bsb", f"{bk}.json"))
        key = (bk, c)
        cache = self.bsb.setdefault("_ch", {})
        if key not in cache:
            cache[key] = bsb_verses(self.bsb[bk], c)
        return cache[key].get(v, "")

    def matching(self, lang, pattern, key=None, nokey=None):
        """Every word whose code matches: (book, ch, v, wi), in Bible order. Greek codes joined with + match by part.
        key / nokey: keep only words whose dictionary entry matches (or doesn't match) this pattern."""
        places = self._matching(lang, pattern)
        if key or nokey:
            krx, nrx = re.compile(key) if key else None, re.compile(nokey) if nokey else None
            def keys_of(p):
                w = self.verse(*p[:3])[p[3]]
                return re.findall(r"\{([GH]\d{4,5}[A-Za-z]?)\}", w[3]) if lang != "grc" else w[3].split("+")
            places = [p for p in places if (not krx or any(krx.search(k) for k in keys_of(p))) and not (nrx and any(nrx.search(k) for k in keys_of(p)))]
        return places

    def _matching(self, lang, pattern):
        if pattern.startswith("flag="):  # Hebrew words by their note: q read differently, k not read, x supplied
            return [p for code, places in self.codes[lang].items() for p in places
                    if (lambda w: len(w) > 6 and w[6] == pattern[5:])(self.verse(*p[:3])[p[3]])]
        if pattern.startswith("key="):  # by dictionary entry (Strong's key) instead of grammar
            return self.by_key(lang, re.compile(pattern[4:]))
        rx = re.compile(pattern)
        out = []
        for code, places in self.codes[lang].items():
            parts = code.split("+") if lang == "grc" else [code[1:]]  # Hebrew/Aramaic: without the language letter
            if any(rx.search(p) for p in parts):
                out += places
        order = {b["id"]: i for i, b in enumerate(self.books)}
        return sorted(out, key=lambda p: (order[p[0]], p[1], p[2], p[3]))


def ref_name(bible, bk, c, v):
    b = bible.by_id[bk]
    return f"{'Psalm' if bk == 'PSA' else b['name']} {c}:{v}"


def lex_for(bible, bk, words, lang, wi):
    """The dictionary entries an example needs: every word's (the Hebrew voice reads each word's dictionary form)."""
    lex = bible.orig[bk]["lex"]
    keys = set()
    for i, w in enumerate(words):
        if lang == "grc" and i != wi:
            continue
        for k in re.findall(r"[GH]\d{4,5}[A-Za-z]?", w[3] if len(w) > 3 else ""):
            keys.add(k)
    return {k: lex[k] for k in sorted(keys) if k in lex}


def make_example(bible, bk, c, v, wi, note=""):
    words = bible.verse(bk, c, v)
    lang = "grc" if bible.by_id[bk]["lang"] == "grc" else "he"
    return {"ref": ref_name(bible, bk, c, v), "book": bk, "ch": c, "v": v, "wi": wi, "note": note,
            "lang": lang, "words": words, "english": bible.english(bk, c, v), "lex": lex_for(bible, bk, words, lang, wi)}


def main_key(w):
    keys = re.findall(r"\{([GH]\d{4,5}[A-Za-z]?)", w[3]) or re.findall(r"[GH]\d{4,5}[A-Za-z]?", w[3])
    return keys[0] if keys else w[3]


# verses a beginner shouldn't meet as a grammar example (on top of the daily verse's UNSETTLING list)
GUIDE_AVOID = re.compile(r"drunk|sorcer|put to death|pregnant|naked|harlot|prostitut|uncovered|whore|adulter|rape|slaughter", re.I)
NEGATIVE_GREEK = re.compile(r"^PRT-N$")


def example_ok(words, wi, lang, negated_ok=False):
    """A word worth showing on its own: its English is real English (not <the> or <obj.>, which aren't translated),
    and it isn't the verb of “do not …”, whose English on its own says the opposite (μὴ φοβεῖσθε, “do fear”)."""
    w = words[wi]
    en = str(w[2] if len(w) > 2 else "").strip()
    if not en or re.fullmatch(r"(\[[^\]]*\]\s*)?<[^>]*>(\s*\[[^\]]*\])?", en):
        return False
    if not negated_ok and wi > 0:
        prev = words[wi - 1]
        code = prev[4] if len(prev) > 4 else ""
        if (lang == "grc" and any(NEGATIVE_GREEK.match(c) for c in code.split("+"))) or (lang != "grc" and re.search(r"(^|/)Tn$", code[1:])):
            return False
    return True


def pick(bible, lang, places, n, taken, negated_ok=False):
    """n examples: well-known and daily-pool verses first, then short verses in famous books; different books and
    dictionary forms; not a word written but not read (k), supplied (x), or inside ⟦ ⟧; nothing unsettling."""
    lo, hi = (4, 18) if lang == "grc" else (3, 12)
    cands = []
    for bk, c, v, wi in places:
        ref = f"{bk} {c}:{v}"
        words = bible.verse(bk, c, v)
        w = words[wi]
        known = ref in ALWAYS
        if not known and not lo <= len(words) <= hi:
            continue
        if len(w) > 6 and w[6] in ("k", "x"):
            continue
        if not example_ok(words, wi, lang, negated_ok):
            continue
        if any("⟦" in str(x[5:7]) or "⟧" in str(x[5:7]) for x in words):
            continue
        cands.append(((0 if known else 1, 0 if ref in bible.pool else 1, BOOK_RANK.get(bk, 99), len(words), c, v, wi), (bk, c, v, wi)))
    cands.sort()
    out, books, keys = [], set(), set()
    for strict in (True, False):
        for _, (bk, c, v, wi) in cands:
            if len(out) >= n:
                break
            k = main_key(bible.verse(bk, c, v)[wi])
            if (bk, c, v) in taken or (strict and (bk in books or k in keys)):
                continue
            en = bible.english(bk, c, v)  # checked only for the verses that come up, best first
            if not en or UNSETTLING_RX.search(en) or GUIDE_AVOID.search(en):
                continue
            out.append((bk, c, v, wi))
            taken.add((bk, c, v))
            books.add(bk)
            keys.add(k)
    return out


UNSETTLING_RX = re.compile("|".join(f"(?:{p})" for p in UNSETTLING), re.I)


def find_word(bible, ex, where):
    words = bible.verse(ex["book"], ex["ch"], ex["v"])
    if not words:
        raise SourceError(f"{where}: no verse {ex['book']} {ex['ch']}:{ex['v']}")
    if ex["word"].startswith("#"):
        wi = int(ex["word"][1:]) - 1
        if not 0 <= wi < len(words):
            raise SourceError(f"{where}: {ex['book']} {ex['ch']}:{ex['v']} has no word {ex['word']}")
        return wi
    grc = bible.by_id[ex["book"]]["lang"] == "grc"
    key = greek_key(ex["word"]) if grc else hebrew_key(ex["word"])
    for wi, w in enumerate(words):
        if (greek_key(w[0]) if grc else hebrew_key(w[0])) == key:
            return wi
    raise SourceError(f"{where}: {ex['word']} is not in {ex['book']} {ex['ch']}:{ex['v']}")


_BIBLE = None
NEGATED_OK = {"negative", "prohibition"}  # entries about “not”, whose examples may be the words after it


def fmt(n):
    return f"{n:,}"


def build(src=SRC):
    sections, entries = read_sources(src)
    global _BIBLE
    if _BIBLE is None:
        _BIBLE = Bible()  # loaded once per run (the checker's self-test builds many times)
    bible = _BIBLE
    ids = [e["id"] for e in entries]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise SourceError(f"entry ids used twice: {sorted(dup)}")
    examples, words_said = {}, {}
    taken = set()
    for e in entries:
        where = f"{e['file']}: {e['id']}"
        exs = []
        for ex in e["examples"]:
            wi = find_word(bible, ex, where)
            exs.append(make_example(bible, ex["book"], ex["ch"], ex["v"], wi, ex["note"]))
            taken.add((ex["book"], ex["ch"], ex["v"]))
        e["count"] = []
        for f in e["find"]:
            places = bible.matching(f["lang"], f["pattern"], f.get("key"), f.get("nokey"))
            if not places:
                raise SourceError(f"{where}: find {f['lang']} {f['pattern']} matches no word")
            e["count"].append({"lang": f["lang"], "n": len(places)})
            have = {(x["book"], x["ch"], x["v"]) for x in exs}
            mine = sum(1 for x in exs if x["lang"] == ("grc" if f["lang"] == "grc" else "he"))
            avoid = set(f.get("avoid", []))
            for bk, c, v, wi in pick(bible, "grc" if f["lang"] == "grc" else "he", [p for p in places if p[:3] not in have and f"{p[0]}{p[1]}:{p[2]}" not in avoid],
                                     max(0, f["n"] - mine), taken, negated_ok=e["id"] in NEGATED_OK):
                exs.append(make_example(bible, bk, c, v, wi))
        e["countValues"] = {}
        for key, cnt in e["counts"].items():
            n = len(bible.matching(cnt["lang"], cnt["pattern"]))
            if not n:
                raise SourceError(f"{where}: count {key} matches no word")
            e["countValues"][key] = fmt(n)
        if exs:
            examples[e["id"]] = exs
        # the Greek and Hebrew written in the text: a real occurrence each, for its Listen button
        texts = [e["short"]] + [json.dumps(b, ensure_ascii=False) for b in e["body"]]
        for t in texts:
            for m in HEBREW_RUN.finditer(t):
                k = hebrew_key(m.group(0))
                if k in bible.forms["he"] and m.group(0) not in words_said:
                    bk, c, v, wi = bible.forms["he"][k]
                    w = bible.verse(bk, c, v)[wi]
                    lex = bible.orig[bk]["lex"]
                    mk = main_key(w)
                    words_said[m.group(0)] = [w, lex[mk][0] if mk in lex else ""]
    # book names for [REF] links
    names = {b["id"]: ("Psalm" if b["id"] == "PSA" else b["name"]) for b in bible.books}
    guide = {
        "sections": [{"id": s["id"], "title": s["title"], "intro": s["intro"],
                      "entries": [e["id"] for e in entries if e["section"] == s["id"]]} for s in sections],
        "entries": [{k: e[k] for k in ("id", "title", "section", "lang", "aka", "match", "see", "lessons", "short", "body", "app",
                                      "unattested") if e[k] != [] and e[k] != ""}
                    | ({"count": e["count"]} if e["count"] else {}) | ({"counts": e["countValues"]} if e["countValues"] else {})
                    for e in entries],
        "books": names,
    }
    return guide, {"examples": examples, "words": words_said}


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def main():
    check = "--check" in sys.argv
    try:
        guide, ex = build()
    except SourceError as err:
        print("Guide source problem:", err)
        sys.exit(1)
    out = {os.path.join(ROOT, "guide", "guide.json"): dump(guide), os.path.join(ROOT, "guide", "examples.json"): dump(ex)}
    if check:
        diff = [p for p, s in out.items() if not os.path.exists(p) or open(p, encoding="utf-8").read() != s]
        print("Guide files up to date." if not diff else f"Out of date (run tools/build_guide.py): {diff}")
        sys.exit(1 if diff else 0)
    for p, s in out.items():
        with open(p, "w", encoding="utf-8") as f:
            f.write(s)
    n_ex = sum(len(v) for v in ex["examples"].values())
    print(f"Guide: {len(guide['sections'])} sections, {len(guide['entries'])} entries, {n_ex} examples, "
          f"{len(ex['words'])} Hebrew words with a voice; guide.json {len(out[list(out)[0]]) // 1024} KB, "
          f"examples.json {len(out[list(out)[1]]) // 1024} KB")


if __name__ == "__main__":
    main()
