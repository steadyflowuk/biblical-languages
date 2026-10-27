"""Builds the Septuagint (Swete's text) for the app and lines it up with the Hebrew/English verse numbers.

Usage:  python3 tools/build_lxx.py <sources>        (sources from tools/fetch_sources.sh: lxx-swete, step)
Writes:
  data/lxx/books.json            Septuagint books (Swete's order, ids, names, chapters)
  data/lxx/text/<ID>.json        {id, ch: [[c, [[v, "text"], …]], …]}  in Swete's own numbering
  data/lxx/ot/<OT ID>.json       for each Hebrew OT book, by English chapter and verse:
                                 {id, ch: [[c, {"lxx": "PSA 22", "weak": 0|1, "v": [[v, "Psa.22:1", "text"] | [v, null], …]}]]}
  data/lxx/LICENSE, data/lxx/README.md

How verses are lined up (English/Hebrew → Swete):
  1. STEPBible's TVTMS versification table (CC BY): its "Greek" column, e.g. Psalm 23:1 → Psalm 22:1.
  2. Swete sometimes numbers like the English or Hebrew Bible instead (e.g. Joel), so for each chapter three
     numberings are tried (table, English, Hebrew) and the one whose verses translate each other best is kept.
     "Translate each other" uses Hebrew→Greek word pairs learned from the chapters that line up well.
  3. Small local corrections (a verse off by one) and two hand-checked passages (Malachi 4:4-6, Daniel 4:1-3).
  4. Chapters that still line up poorly are marked weak (the app shows a note and a link instead of
     verse-by-verse text), and single verses with no recognisable match are left out.
"""
import collections, glob, json, os, re, statistics, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "lxx")

# Swete code → (app id, name, group). Order is Swete's.
BOOKS = [
    ("Gen", "GEN", "Genesis", "Law"), ("Exo", "EXO", "Exodus", "Law"), ("Lev", "LEV", "Leviticus", "Law"),
    ("Num", "NUM", "Numbers", "Law"), ("Deu", "DEU", "Deuteronomy", "Law"),
    ("Jos", "JOS", "Joshua", "History"), ("Jdg", "JDG", "Judges", "History"), ("Rut", "RUT", "Ruth", "History"),
    ("1Sa", "1SA", "1 Samuel (1 Kingdoms)", "History"), ("2Sa", "2SA", "2 Samuel (2 Kingdoms)", "History"),
    ("1Ki", "1KI", "1 Kings (3 Kingdoms)", "History"), ("2Ki", "2KI", "2 Kings (4 Kingdoms)", "History"),
    ("1Ch", "1CH", "1 Chronicles", "History"), ("2Ch", "2CH", "2 Chronicles", "History"),
    ("1Es", "1ES", "1 Esdras", "History"), ("Ezr", "EZR", "Ezra", "History"), ("Neh", "NEH", "Nehemiah", "History"),
    ("Psa", "PSA", "Psalms", "Poetry and wisdom"), ("Pro", "PRO", "Proverbs", "Poetry and wisdom"),
    ("Ecc", "ECC", "Ecclesiastes", "Poetry and wisdom"), ("Sol", "SNG", "Song of Songs", "Poetry and wisdom"),
    ("Job", "JOB", "Job", "Poetry and wisdom"), ("Wis", "WIS", "Wisdom of Solomon", "Poetry and wisdom"),
    ("Sip", "SIP", "Sirach (prologue)", "Poetry and wisdom"), ("Sir", "SIR", "Sirach", "Poetry and wisdom"),
    ("Est", "ESG", "Esther (Greek)", "History"), ("Jdt", "JDT", "Judith", "History"),
    ("Tob", "TOB", "Tobit", "History"), ("Tbs", "TBS", "Tobit (Sinaiticus)", "History"),
    ("Hos", "HOS", "Hosea", "Prophets"), ("Amo", "AMO", "Amos", "Prophets"), ("Mic", "MIC", "Micah", "Prophets"),
    ("Joe", "JOL", "Joel", "Prophets"), ("Oba", "OBA", "Obadiah", "Prophets"), ("Jon", "JON", "Jonah", "Prophets"),
    ("Nah", "NAM", "Nahum", "Prophets"), ("Hab", "HAB", "Habakkuk", "Prophets"), ("Zep", "ZEP", "Zephaniah", "Prophets"),
    ("Hag", "HAG", "Haggai", "Prophets"), ("Zec", "ZEC", "Zechariah", "Prophets"), ("Mal", "MAL", "Malachi", "Prophets"),
    ("Isa", "ISA", "Isaiah", "Prophets"), ("Jer", "JER", "Jeremiah", "Prophets"), ("Bar", "BAR", "Baruch", "Prophets"),
    ("Lam", "LAM", "Lamentations", "Prophets"), ("Epj", "LJE", "Letter of Jeremiah", "Prophets"),
    ("Eze", "EZK", "Ezekiel", "Prophets"), ("Dat", "DAN", "Daniel (Theodotion)", "Prophets"),
    ("Dan", "DAG", "Daniel (Old Greek)", "Prophets"), ("Sut", "SUT", "Susanna (Theodotion)", "Prophets"),
    ("Sus", "SUS", "Susanna (Old Greek)", "Prophets"), ("Bet", "BET", "Bel and the Dragon (Theodotion)", "Prophets"),
    ("Bel", "BEL", "Bel and the Dragon (Old Greek)", "Prophets"),
    ("1Ma", "1MA", "1 Maccabees", "History"), ("2Ma", "2MA", "2 Maccabees", "History"),
    ("3Ma", "3MA", "3 Maccabees", "History"), ("4Ma", "4MA", "4 Maccabees", "History"),
    ("Pss", "PSS", "Psalms of Solomon", "Poetry and wisdom"), ("Ode", "ODE", "Odes", "Poetry and wisdom"),
    ("1En", "ENO", "1 Enoch", "Other"),
]
# Hebrew OT ids whose TVTMS code differs from the obvious one, and TVTMS → Swete codes
TV_OF = {"SNG": "Sng", "EZK": "Ezk", "JOL": "Jol", "NAM": "Nam"}
SW_OF = {"Sng": "Sol", "Ezk": "Eze", "Jol": "Joe", "Nam": "Nah", "Dan": "Dat"}
# Hand-checked (English → Swete) where Swete's order differs from every numbering tried
OVERRIDES = {
    "MAL 4:4": ["Mal.4:6"], "MAL 4:5": ["Mal.4:4"], "MAL 4:6": ["Mal.4:5"],  # Elijah 4:4, hearts 4:5, law of Moses 4:6
    "DAN 4:1": ["Dat.3:98"], "DAN 4:2": ["Dat.3:99"], "DAN 4:3": ["Dat.3:100"],  # Theodotion keeps these in ch. 3
}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def clean(word):
    """NFC, and drop Swete's editorial marks (⸂ ⸃ ⸆ and [1]-style subsection numbers); keep [α] supplied letters."""
    w = unicodedata.normalize("NFC", re.sub("[\u2e02\u2e03\u2e06]", "", word))  # Greek only: NFC is safe (ύ oxia → tonos, as in the NT data)
    return "" if re.fullmatch(r"\[\d+\]", w) else w


def gnorm(w):
    w = unicodedata.normalize("NFD", w)
    w = "".join(c for c in w if not unicodedata.combining(c)).lower().replace("ς", "σ")
    return re.sub("[^α-ω]", "", w)


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python3 tools/build_lxx.py <sources folder from tools/fetch_sources.sh>")
    build(sys.argv[1])


def build(src):
    sw = os.path.join(src, "lxx-swete")
    tv_path = glob.glob(os.path.join(src, "step", "Versification", "TVTMS*.txt"))[0]

    # ---- Swete text
    words = [clean(l.rstrip("\n").split("\t")[1]) for l in open(os.path.join(sw, "01-Swete_word_with_punctuations.csv"), encoding="utf-8")]
    rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(sw, "00-Swete_versification.csv"), encoding="utf-8")]
    verses, order = {}, []
    for i, (n, ref) in enumerate(rows):
        start = int(n)
        end = int(rows[i + 1][0]) if i + 1 < len(rows) else len(words) + 1
        verses[ref] = [w for w in words[start - 1:end - 1] if w]
        order.append(ref)
    text = {ref: " ".join(ws) for ref, ws in verses.items()}
    gw = {ref: {x for x in (gnorm(w) for w in ws) if len(x) > 2} for ref, ws in verses.items()}

    # ---- books and per-book text files (Swete numbering)
    by_code = collections.defaultdict(lambda: collections.OrderedDict())
    for ref in order:
        m = re.match(r"^(.+?)\.(\d+):(\d+)$", ref)
        code, c, v = m.group(1), int(m.group(2)), int(m.group(3))
        by_code[code].setdefault(c, []).append([v, text[ref]])
    books_out = []
    for code, bid, name, group in BOOKS:
        chs = by_code[code]
        dump(os.path.join(OUT, "text", f"{bid}.json"), {"id": bid, "ch": [[c, vs] for c, vs in chs.items()]})
        books_out.append({"id": bid, "swete": code, "name": name, "group": group, "ch": len(chs),
                          "first": min(chs), "chapters": list(chs)})
    dump(os.path.join(OUT, "books.json"), books_out)

    # ---- TVTMS: English → Greek
    lines = open(tv_path, encoding="utf-8").read().split("\n")
    st = next(i for i, l in enumerate(lines) if l.startswith("#DataStart(Condensed)"))
    en = next((i for i, l in enumerate(lines) if l.startswith("#DataEnd") and i > st), len(lines))
    REF = re.compile(r"^(\w+)\.(\d+):(Title|\d+)(?:\.\d+)?(?:-(\d+)(?::(\d+))?)?$")

    def expand(cell):
        cell = re.sub(r"\s*\[=.*\]", "", cell).strip()
        m = REF.match(cell) if "--" not in cell else None
        if not m or m.group(5) is not None:
            return None
        b, c, v, a = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        v = 0 if v == "Title" else int(v)
        return [(b, c, v)] if a is None else [(b, c, x) for x in range(v, int(a) + 1)]

    table, header = {}, None
    for l in lines[st + 1:en]:
        cells = [c.strip() for c in l.split("\t")]
        if l.startswith("$"):
            header = cells if len([c for c in cells if c]) > 1 else None
            continue
        if cells[0] == "BIBLES":
            header = cells
            continue
        if not cells[0] or cells[0].startswith(("TEST", "#", "'", ">", ",")) or header is None:
            continue
        gi = next((i for i, h in enumerate(header) if h.rstrip("*") == "Greek"), None)
        ei = next((i for i, h in enumerate(header) if h.startswith("English")), None)
        if gi is None or ei is None or gi >= len(cells):
            continue
        E = expand(cells[ei])
        if E is None:
            continue
        g = cells[gi]
        if g.startswith("Absent"):
            for r in E:
                table[r] = []
            continue
        G = expand(g)
        if G is None:
            continue
        if len(G) != len(E):
            if len(G) == 1:
                G = G * len(E)
            elif len(E) == 1:
                table[E[0]] = G
                continue
            else:
                continue
        for r, gr in zip(E, G):
            table[r] = [gr]

    ot = [b for b in load(os.path.join(DATA, "books.json")) if b["lang"] == "he"]
    tvcode = {b["id"]: TV_OF.get(b["id"], (b["id"][:2] + b["id"][2:].lower()) if b["id"][0].isdigit()
                                 else b["id"][0] + b["id"][1:].lower()) for b in ot}
    hot = {b["id"]: load(os.path.join(DATA, "hot", f"{b['id']}.json")) for b in ot}

    def refs_for(bid, c, v, how, heb):
        t = tvcode[bid]
        sb = SW_OF.get(t, t)
        if how == "english":
            return [f"{sb}.{c}:{v}"]
        if how == "hebrew":
            hc, hv = (map(int, heb.split("."))) if heb else (c, v)
            return [f"{sb}.{hc}:{hv}"]
        if (t, c, v) in table:
            return [f"{SW_OF.get(gb, gb)}.{gc}:{gv}" for gb, gc, gv in table[(t, c, v)]]
        return [f"{sb}.{c}:{v}"]

    def heb_keys(v):
        return {k for w in v[1] for k in re.findall(r"\{(H\d{4})", w[3])}

    def pairs(bid, c, how):
        out = []
        for v in dict(hot[bid]["ch"])[c]:
            heb = v[2] if len(v) > 2 and isinstance(v[2], str) else None
            out.append((v, [g for g in refs_for(bid, c, v[0], how, heb) if g in verses]))
        return out

    # 2a. first guess per chapter: verse lengths that rise and fall together
    first = {}
    for b in ot:
        for c, vs in hot[b["id"]]["ch"]:
            best = None
            for how in ("table", "english", "hebrew"):
                xs, ys = [], []
                for v, gs in pairs(b["id"], c, how):
                    if gs:
                        xs.append(len(v[1]))
                        ys.append(sum(len(verses[g]) for g in gs))
                r = statistics.correlation(xs, ys) if len(xs) > 3 and len(set(xs)) > 1 and len(set(ys)) > 1 else (1.0 if len(xs) == len(vs) else 0)
                score = r * len(xs) / len(vs)
                if best is None or score > best[0] + 0.02:
                    best = (score, how)
            first[(b["id"], c)] = best[1]

    # 2b. learn Hebrew → Greek word pairs from the chapters the table lines up
    co, hf, gf = collections.Counter(), collections.Counter(), collections.Counter()
    for (bid, c), how in first.items():
        if how != "table":
            continue
        for v, gs in pairs(bid, c, "table"):
            if not gs:
                continue
            H, G = heb_keys(v), set().union(*(gw[g] for g in gs))
            hf.update(H)
            gf.update(G)
            co.update((h, g) for h in H for g in G)
    trans = collections.defaultdict(list)
    for (h, g), k in co.items():
        if k >= 3:
            dice = 2 * k / (hf[h] + gf[g])
            if dice > 0.25:
                trans[h].append((dice, g))
    trans = {h: [g for _, g in sorted(x, reverse=True)[:4]] for h, x in trans.items()}

    def score(v, gs):
        H = [h for h in heb_keys(v) if h in trans]
        if not H or not gs:
            return None, 0, len(H)
        G = set().union(*(gw[g] for g in gs))
        hits = sum(1 for h in H if any(t in G for t in trans[h]))
        return hits / len(H), hits, len(H)

    # 2c. best numbering per chapter by translation pairs; 3. local corrections and overrides
    result = {}
    for b in ot:
        bid = b["id"]
        sb = SW_OF.get(tvcode[bid], tvcode[bid])
        for c, vs in hot[bid]["ch"]:
            def chapter_score(how):
                sc = [score(v, gs)[0] for v, gs in pairs(bid, c, how)]
                return sum(s for s in sc if s is not None) / len(sc)
            how = max(("table", "english", "hebrew"), key=lambda h: (chapter_score(h), h == first[(bid, c)]))
            out, scores = [], []
            for v, gs in pairs(bid, c, how):
                key = f"{bid} {c}:{v[0]}"
                s, hits, n = score(v, gs)
                if key in OVERRIDES:
                    gs = OVERRIDES[key]
                elif n >= 4 and hits == 0:
                    # nothing in common: try a verse or two either side (a local numbering offset)
                    near = set()
                    for g in gs or [f"{sb}.{c}:{v[0]}"]:
                        if g in verses:
                            i = order.index(g)
                            near.update(r for r in order[max(0, i - 3):i + 4] if r.startswith(sb + "."))
                    cand = max(((score(v, [r])[0] or 0, r) for r in near), default=(0, None))
                    if cand[0] >= 0.75 and score(v, [cand[1]])[1] >= 4:
                        gs = [cand[1]]
                    else:
                        gs = []  # no recognisable match: leave it out rather than show the wrong verse
                s2 = score(v, gs)[0]
                scores.append(s2 if s2 is not None else (1 if gs else 0))
                out.append([v[0], ",".join(gs) if gs else None, " ".join(text[g] for g in gs) if gs else None])
            mean = sum(scores) / len(scores) if scores else 0
            chs = collections.Counter(re.match(r"^(.+?)\.(\d+)", g).groups() for _, r, _ in out if r for g in r.split(","))
            main = chs.most_common(1)[0][0] if chs else (sb, str(c))
            lxx_id = next(x[1] for x in BOOKS if x[0] == main[0])
            result.setdefault(bid, []).append([c, {"lxx": f"{lxx_id} {main[1]}", "weak": 1 if mean < 0.3 else 0,
                                                   "v": [[v, r, t] if r else [v, None] for v, r, t in out]}])
    for bid, chs in result.items():
        dump(os.path.join(OUT, "ot", f"{bid}.json"), {"id": bid, "ch": chs})
    # For each Septuagint chapter, the English chapter it mostly lines up with ("Compare with the Hebrew")
    back = collections.defaultdict(collections.Counter)
    code_to_id = {code: bid for code, bid, _, _ in BOOKS}
    for bid, chs in result.items():
        for c, d in chs:
            for x in d["v"]:
                for g in (x[1].split(",") if x[1] else []):
                    gb, gc = re.match(r"^(.+?)\.(\d+):", g).groups()
                    back[(code_to_id[gb], int(gc))][(bid, c)] += 1
    for b in books_out:
        heb = {str(c): list(back[(b["id"], c)].most_common(1)[0][0]) for c in b["chapters"] if back[(b["id"], c)]}
        if heb:
            b["heb"] = heb
    dump(os.path.join(OUT, "books.json"), books_out)

    # ---- licence and notes travel with the data
    with open(os.path.join(sw, "LICENSE"), encoding="utf-8") as f:
        lic = f.read()
    with open(os.path.join(OUT, "LICENSE"), "w", encoding="utf-8") as f:
        f.write(lic)
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write("""# Septuagint data

Text: H. B. Swete, *The Old Testament in Greek according to the Septuagint* (Cambridge, 1909–1930), public domain.
Digital text: [LXX-Swete-1930](https://github.com/eliranwong/LXX-Swete-1930) by Eliran Wong (BibleBento), supplied by
Pasquale Amicarelli, licensed GPL-3.0 (see LICENSE in this folder). These files are reformatted from it by
`tools/build_lxx.py`; Swete's editorial marks ⸂ ⸃ ⸆ and subsection numbers are dropped, accents are stored
in standard Unicode form (NFC); the words are unchanged.

`ot/` lines the Septuagint up with the Hebrew/English verse numbers, using STEPBible's TVTMS versification data
(CC BY 4.0, STEPBible.org / Tyndale House Cambridge) plus the checks described in `tools/build_lxx.py`.
""")
    total = sum(len(v) for chs in by_code.values() for v in chs.values())
    weak = [f"{bid} {c}" for bid, chs in result.items() for c, d in chs if d["weak"]]
    missing = sum(1 for chs in result.values() for _, d in chs for v in d["v"] if v[1] is None)
    ot_verses = sum(len(d["v"]) for chs in result.values() for _, d in chs)
    print(json.dumps({"books": len(books_out), "verses": total, "words": sum(len(v) for v in verses.values()),
                      "ot_verses": ot_verses, "lined_up": ot_verses - missing, "weak_chapters": weak,
                      "word_pairs": len(trans)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
