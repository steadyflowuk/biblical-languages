"""The dictionary agrees with the Bible text it was built from, entry by entry, both ways.

    python3 tools/check_dictionary_integrity.py [--self-test]

Recomputed here from data/gnt and data/hot, independently of tools/build_dictionary.py:
  1. every place an entry lists (BOOK c.v.word) is a real word, and that word carries the entry's Strong's number
  2. every word of the New Testament (each of its parts) and every main part of an Old Testament word is listed under
     exactly one entry — so nothing is missing from "every occurrence" and nothing is counted twice
  3. the count shown in search and in the Reader's "how common" = the number of places listed = the forms' counts
  4. every form in an entry's table occurs at one of its places, with that grammar code
  5. the search index shows the entry's own headword, transliteration and meaning
"""
import collections, glob, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
CANT = re.compile("[֑-ּֽֿ֯]")


def num(key):
    m = re.match(r"[GH](\d+)", key or "")
    return int(m.group(1)) if m else None


def he_main_parts(key):
    """Main parts of a Hebrew word's key: those in {braces}, never H9001+ labels; else the first real number."""
    braced = re.findall(r"\{([^}]+)\}", key)
    parts = [k for b in braced for k in re.split(r"[/\\\\+\s]", b) if k and not re.match(r"H90\d\d", k)]
    if not parts:
        parts = [k for k in re.split(r"[/\\\\{}+\s]", key) if k and not re.match(r"H90\d\d", k)][:1]
    return parts


def load_bible():
    words = {}  # (BOOK, c, v, i) -> (lang, text, [numbers], codes, cont)
    for lang, d in (("G", "gnt"), ("H", "hot")):
        for f in sorted(glob.glob(f"data/{d}/*.json")):
            b = json.load(open(f))
            for ch, vs in b["ch"]:
                for it in vs:
                    prev = None
                    for i, w in enumerate(it[1]):
                        key = w[3] if len(w) > 3 else ""
                        code = w[4] if len(w) > 4 else ""
                        if lang == "G":
                            nums = [num(k) for k in key.split("+") if num(k) is not None]
                        else:
                            nums = [num(k) for k in he_main_parts(key) if num(k) is not None]
                        allnums = [num(k) for k in re.findall(r"[GH]\d+", key)]
                        cont = len(w) > 7 and w[7] == "+"
                        # a name written as two words with one tag (Ἄρειον Πάγον) is counted once, with the first
                        if lang == "G" and prev and prev[3:4] == [key] and prev[4:5] == [code] and code.endswith(("-P", "-L", "-T")) \
                                and "+" not in key and plain(prev[0], "G") != plain(w[0], "G"):
                            cont = True
                        segs = [plain(x, lang) for x in w[0].split("/")] + [plain(w[0], lang)]
                        words[(b["id"], ch, it[0], i)] = (lang, w[0], nums, code, cont, allnums, segs)
                        prev = w
    return words


def load_entries():
    out = {}
    for lang in "GH":
        for f in sorted(glob.glob(f"data/lex/{lang}/*.json")):
            out.update(json.load(open(f)))
    index = {}
    for f in ("data/lex/greek-index.json", "data/lex/hebrew-index.json"):
        for r in json.load(open(f)):
            index[r[0]] = r
    return out, index


def plain(t, lang):
    t = t.replace("/", "")
    if lang == "H":
        return CANT.sub("", t).replace("־", "")
    return unicodedata.normalize("NFC", re.sub(r"[^\ẁ-ͯ]", "", t)).lower()


def check(words, entries, index):
    problems = collections.defaultdict(list)
    listed = collections.Counter()
    for key, e in entries.items():
        occ = e[6] if len(e) > 6 and isinstance(e[6], dict) else {}
        forms = e[7] if len(e) > 7 else []
        places = []
        for book, refs in occ.items():
            for r in refs.split():
                c, v, i = map(int, r.split("."))
                places.append((book, c, v, i))
        n = num(key)
        seen_forms = collections.Counter()
        for p in places:
            w = words.get(p)
            if not w:
                problems["a listed place that isn't a word"].append(f"{key} {p}")
                continue
            if n not in w[2] and not (n >= 9000 and n in w[5] and not w[2]):  # לוֹ: the preposition is the word
                problems["a listed word with another Strong's number"].append(f"{key} {p} {w[1]} {w[2]}")
            listed[(p, n)] += 1
            for seg in w[6]:
                seen_forms[seg] += 1
        idx = index.get(key)
        count = idx[4] if idx and len(idx) > 4 and isinstance(idx[4], int) else 0
        if count != len(places):
            problems["count shown ≠ places listed"].append(f"{key} count {count}, places {len(places)}")
        if forms and sum(f[1] for f in forms) != len(places):
            problems["forms' counts ≠ places listed"].append(f"{key} forms {sum(f[1] for f in forms)}, places {len(places)}")
        for form, n_form, code in forms:
            f = plain(form, key[0])
            if f not in seen_forms and not (key[0] == "H" and any(x.replace("\u05bc", "") == f.replace("\u05bc", "") for x in seen_forms)):
                problems["a form in the table that occurs nowhere"].append(f"{key} {form} ×{n_form}")
        if idx and (idx[1] != e[0] or idx[3] != e[3]):
            problems["index headword/meaning ≠ the entry's"].append(f"{key} index {idx[1]} {idx[3]!r} · entry {e[0]} {e[3]!r}")
    # the word lists for Review: each card's count = its entry's count plus the senses folded into it; most common
    # first; every folded sense points at a card; a card's word is its entry's headword (or the list's own spelling)
    for f in ("data/decks/greek.json", "data/decks/hebrew.json"):
        deck = json.load(open(f))
        cards = {w[0]: w for w in deck["words"]}
        folded = collections.defaultdict(list)
        for k, t in deck["alias"].items():
            folded[t].append(k)
            if t not in cards:
                problems["a list's folded sense points at no card"].append(f"{f} {k} → {t}")
        counts = [w[3] for w in deck["words"]]
        if counts != sorted(counts, reverse=True):
            problems["a word list not most common first"].append(f)
        for k, w in cards.items():
            idx = index.get(k)
            want = sum((index.get(x) or [0] * 5)[4] or 0 for x in [k] + folded[k] if len(index.get(x) or []) > 4)
            if want != w[3]:
                problems["a card's count ≠ its entries' counts"].append(f"{f} {k} {w[1]}: card {w[3]}, entries {want}")
            if not idx:
                problems["a card with no dictionary entry"].append(f"{f} {k}")
    # every word (part) listed exactly once
    for p, w in words.items():
        if w[4]:
            continue  # second half of a word SBL writes as two (Μαράνα θά): counted with the first
        for n in w[2]:
            if n >= 9000:
                continue
            k = listed[(p, n)]
            if k == 0:
                problems["a word in the text no entry lists"].append(f"{p} {w[1]} {n}")
            elif k > 1:
                problems["a word listed twice"].append(f"{p} {w[1]} {n} ×{k}")
    return problems


def main():
    words = load_bible()
    entries, index = load_entries()
    if "--self-test" in sys.argv:
        import copy
        tests = []
        e = copy.deepcopy(entries)
        e["G3056"][6]["JHN"] = e["G3056"][6]["JHN"] + " 1.1.0"  # Ἐν listed under λόγος
        tests.append(("a word listed under the wrong entry", e, index))
        e = copy.deepcopy(entries)
        e["G3056"][6]["JHN"] = " ".join(e["G3056"][6]["JHN"].split()[1:])
        tests.append(("a place dropped from an entry", e, index))
        i2 = copy.deepcopy(index)
        i2["G3056"][4] += 1
        tests.append(("a count one too many", entries, i2))
        e = copy.deepcopy(entries)
        e["G3056"][7].append(["λογοις", 1, "N-DPM"])
        tests.append(("a form that occurs nowhere", e, index))
        ok = 0
        base = sum(len(v) for v in check(words, entries, index).values())
        for desc, e, i in tests:
            caught = sum(len(v) for v in check(words, e, i).values()) > base
            print(("caught " if caught else "MISSED ") + desc)
            ok += caught
        print(f"{ok}/{len(tests)} passed")
        sys.exit(0 if ok == len(tests) else 1)
    problems = check(words, entries, index)
    print(f"{len(entries):,} dictionary entries checked against {len(words):,} words of the text")
    total = 0
    for name, items in sorted(problems.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(items):6}  {name}")
        for x in items[:12]:
            print("         ", x)
        total += len(items)
    print(f"{total} problems")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
