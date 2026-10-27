"""Adds every occurrence and the forms used to each dictionary entry (Session 5).

Reads the files build_data.py wrote (data/gnt, data/hot, data/lex) and rewrites the lexicon chunks
data/lex/G/<nn>.json and data/lex/H/<nn>.json so each entry is:

    [lemma, translit, morph, gloss, def, rel, occ, forms]

The search index lex/<greek|hebrew>-index.json becomes [key, lemma, translit, gloss, count, keywords]
(keywords = English words from the definition, so "shepherd" finds רָעָה; count 0 is kept when keywords follow).

occ   = {"JHN": "1.1.4 1.14.2 …", …}   chapter.verse.word-index, as the Reader numbers them
        (Greek: NA28 verse numbers; Hebrew: English verse numbers, Psalm titles = verse 0)
forms = [[form, count, grammar code], …]  most common first

Keys are resolved exactly as build_data.lookup() does, so counts, occurrences and the Reader agree.
Hebrew: only the main word of each joined word counts (not prefixes, suffixes or STEPBible's H9001+ labels).

Run on its own with:  python3 tools/build_dictionary.py   (build_data.py also calls it at the end)
"""
import json, os, re, sys, unicodedata
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SUFFIXES = "GHIJKLMNOPQRSTUVWXYZABCDEF"
DOTS = re.compile("[\u05bc\u05bf]")  # dagesh and rafe
CANTILLATION = re.compile("[\u0591-\u05af\u05bd]")  # accents and meteg; vowel points stay


def load(path):
    with open(os.path.join(DATA, path), encoding="utf-8") as f:
        return json.load(f)


def dump(path, obj):
    with open(os.path.join(DATA, path), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def resolver(keys):
    """Same rule as build_data.lookup(): exact key, else the bare number, else the first lettered sense."""
    cache = {}

    def lookup(key):
        if key in cache:
            return cache[key]
        found = None
        if key in keys:
            found = key
        else:
            m = re.match(r"^([GH])0*(\d+)", key)
            if m:
                num = f"{m.group(1)}{int(m.group(2)):04d}"
                found = num if num in keys else next((num + s for s in SUFFIXES if num + s in keys), None)
        cache[key] = found
        return found
    return lookup


def hebrew_main_parts(w):
    """(key, text, code) of the main word(s): the part(s) in {braces}, never an H9001+ label (see js/hebrew.js)."""
    texts = w[0].split("/")
    raw_keys = [k.split("\\")[0] for k in w[3].split("/")]
    segs = w[4].split("/")
    lang = segs[0][:1] or "H"
    parts = []
    for i, t in enumerate(texts):
        if not t.strip() or t.strip() == "\u05be":
            continue
        raw = raw_keys[i] if i < len(raw_keys) else ""
        key = re.sub(r"[{}+\s]", "", raw)
        code = segs[0] if i == 0 else (lang + segs[i] if i < len(segs) and segs[i] else "")
        parts.append((key, t, code, bool(re.search(r"[{}]", raw)) and not re.match(r"^H90\d\d", key)))
    mains = [p for p in parts if p[3]]
    if not mains:  # e.g. "{H4480A\H9014}" or no braces: first real key
        m = re.search(r"\{([^}]+)\}", w[3])
        cand = [k.strip("{} ") for k in re.split(r"[/\\+\s]", m.group(1) if m else w[3]) if k.strip("{} ")]
        key = next((k for k in cand if not k.startswith("H90")), cand[0] if cand else "")
        mains = [(key, w[0].replace("/", ""), segs[0], True)]
    return [(k, t, c) for k, t, c, _ in mains]


STOP = set("""a an the of to in on at by for from with and or as is be been being it its this that these those which who whom
what into upon out up down over under than then so such not no nor but if also very much many more most some any all each
other another one ones etc used use see esp especially lit literally fig figuratively prob probably perh perhaps viz cf
thing things person persons something someone used make made cause caused causing become became being have has had do does
did his her their them they he she him you your we our us i me my mine subst literal means act pass ptcp prep adj adv
noun verb intrans trans absol poss pron pers sing plur pl sg masc fem neut gen dat acc nom voc infin impf perf aor
pres fut mid dep comp superl one two""".split())


def keywords(entry, letter):
    """English words from a definition, for search: Greek = the bold glosses; Hebrew = the outline's words."""
    d = entry[4] if len(entry) > 4 else ""
    if letter == "G":
        text = " ".join(re.findall(r"<b>(.*?)</b>", d, flags=re.S))
    else:
        text = re.sub(r"\((?:Qal|Niphal|Piel|Pual|Hiphil|Hophal|Hithpael|Peal|Pael|Aphel|Hithpeel|Hithpaal|[A-Z][a-z]+)\)", " ", d)
    text = re.sub(r"<[^>]+>", " ", text)
    words, seen = [], set(re.findall(r"[a-z]+", str(entry[3] if len(entry) > 3 else "").lower()))
    for w in re.findall(r"[A-Za-z]+", text):
        w = w.lower()
        if len(w) < 3 or w in STOP or w in seen:
            continue
        seen.add(w)
        words.append(w)
    return " ".join(words[:12])


def build():
    books = load("books.json")
    out = {}
    for letter, name in (("G", "greek"), ("H", "hebrew")):
        index = load(f"lex/{name}-index.json")
        keys = {e[0] for e in index}
        lookup = resolver(keys)
        extra = {}  # words whose key has no lexicon entry but whose book file has one (e.g. G20447 ἐπίστασις)
        occ = defaultdict(lambda: defaultdict(list))   # key → book → ["c.v.w"]
        forms = defaultdict(Counter)                  # key → (form key) → count
        spellings = defaultdict(Counter)              # (key, form key) → spelling → count
        codes = defaultdict(Counter)
        unresolved = Counter()
        for b in books:
            if (b["lang"] == "grc") != (letter == "G"):
                continue
            src = load(f"{'gnt' if letter == 'G' else 'hot'}/{b['id']}.json")
            for c, verses in src["ch"]:
                for verse in verses:
                    v = verse[0]
                    for wi, w in enumerate(verse[1]):
                        if letter == "G":
                            ks, cs = w[3].split("+"), w[4].split("+") if len(w) > 4 else []
                            items = [(k, w[0], cs[i] if i < len(cs) else "") for i, k in enumerate(ks) if k]
                        else:
                            items = hebrew_main_parts(w)
                        seen = set()
                        for k, text, code in items:
                            key = lookup(k)
                            if not key and k in src["lex"]:
                                key = k
                                extra.setdefault(k, src["lex"][k])
                            if not key:
                                unresolved[k] += 1
                                continue
                            if key in seen:
                                continue  # a word counts once per entry
                            seen.add(key)
                            occ[key][b["id"]].append(f"{c}.{v}.{wi}")
                            if letter == "H":
                                # Group spellings that differ only by the dagesh/rafe dot (בָּרָא after a prefix is בָרָא)
                                # and keep each grammar separate; show the commonest spelling of each group.
                                form = CANTILLATION.sub("", text.replace("/", ""))
                                fkey = DOTS.sub("", unicodedata.normalize("NFC", form)) + "|" + code
                            else:
                                form = text
                                fkey = unicodedata.normalize("NFC", form).lower()  # for grouping only; display keeps the source form
                            forms[key][fkey] += 1
                            spellings[(key, fkey)][form] += 1
                            codes[(key, fkey)][code] += 1
        known = {e[0] for e in index}
        index += [[k, l[0], l[1] if len(l) > 1 else "", l[2] if len(l) > 2 else ""] for k, l in extra.items() if k not in known]
        full = {}
        for path in os.listdir(os.path.join(DATA, "lex", letter)):
            full.update(load(f"lex/{letter}/{path}"))
        for e in index:  # the occurrence list is the one source of truth for "how common"
            n = sum(len(r) for r in occ[e[0]].values()) if e[0] in occ else 0
            kw = keywords(full.get(e[0], []), letter)
            e[:] = (e + [""] * 4)[:4] + [n, kw]  # [key, lemma, translit, gloss, count, definition keywords]
            while e and e[-1] in ("", 0):
                e.pop()
        dump(f"lex/{name}-index.json", index)
        chunks = {}
        for k, l in extra.items():
            path = f"{k[1:3]}.json"
            chunk = load(f"lex/{letter}/{path}") if os.path.exists(os.path.join(DATA, "lex", letter, path)) else {}
            if k not in chunk:
                chunk[k] = [l[0], l[1] if len(l) > 1 else "", "", l[2] if len(l) > 2 else "", ""]
                dump(f"lex/{letter}/{path}", chunk)
        for path in sorted(os.listdir(os.path.join(DATA, "lex", letter))):
            chunk = load(f"lex/{letter}/{path}")
            for key, entry in chunk.items():
                entry = (entry + [""] * 6)[:6]
                if key in occ:
                    entry.append({bk: " ".join(refs) for bk, refs in occ[key].items()})
                    entry.append([[spellings[(key, f)].most_common(1)[0][0], n, codes[(key, f)].most_common(1)[0][0]]
                                  for f, n in forms[key].most_common()])
                chunk[key] = entry
            dump(f"lex/{letter}/{path}", chunk)
            chunks[path] = chunk
        total = sum(len(r.split(" ")) for k in occ for r in (" ".join(occ[k][bk]) for bk in occ[k]))
        out[name] = {"entries_with_occurrences": len(occ), "occurrences": total,
                     "added_entries": sorted(extra), "unresolved_keys": sum(unresolved.values()), "unresolved_examples": unresolved.most_common(5)}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__":
    build()
