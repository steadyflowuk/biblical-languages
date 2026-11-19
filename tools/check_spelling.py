"""Typing slips in the English a learner reads: every word's English (STEPBible's glosses), the dictionaries' short
meanings, the grammar wording, the word lists, the lessons, the Letters guides and the screens' own text.

    python3 tools/check_spelling.py [--self-test] [--write-baseline]

There is no dictionary file here, so the reference is a large, carefully edited English text the app already has:
the Berean Standard Bible (every word of it), with the app's grammar wording and a short list of words the BSB
doesn't use (KEEP). A word that the BSB never uses but that is one letter away from a word the BSB uses at least
five times ("opressors" / oppressors, "belonginging") is a likely slip. The slips found are put right where the text
is ours, or by data.morph()'s list of source spelling slips where it is STEPBible's; real words that merely look
like slips (names, Greek and Latin terms) are approved in tools/fixtures/spelling_baseline.json.
"""
import collections, glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
BASELINE_FILE = os.path.join(ROOT, "tools", "fixtures", "spelling_baseline.json")
WORD = re.compile(r"[A-Za-z][a-z]+(?:'[a-z]+)?")


def bsb_words():
    c = collections.Counter()
    for f in glob.glob("data/bsb/*.json"):
        d = json.load(open(f))
        for chapter in d["chapters"]:
            for kind, items in chapter[0]:
                for x in items:
                    if isinstance(x, str):
                        c.update(w.lower() for w in WORD.findall(x))
            for note in (chapter[1] if len(chapter) > 1 else []):
                if isinstance(note, str):
                    c.update(w.lower() for w in WORD.findall(note))
    return c


def edits1(w):
    letters = "abcdefghijklmnopqrstuvwxyz"
    splits = [(w[:i], w[i:]) for i in range(len(w) + 1)]
    out = set()
    for a, b in splits:
        if b:
            out.add(a + b[1:])
            for c in letters:
                out.add(a + c + b[1:])
        if len(b) > 1:
            out.add(a + b[1] + b[0] + b[2:])
        for c in letters:
            out.add(a + c + b)
    return out


def texts():
    """(where, text) for the English a learner reads."""
    fixes = slips_fixed_in_app()
    for f in sorted(glob.glob("data/gnt/*.json")) + sorted(glob.glob("data/hot/*.json")):
        d = json.load(open(f))
        for ch, vs in d["ch"]:
            for it in vs:
                for w in it[1]:
                    yield f"{d['id']} {ch}:{it[0]}", fixes(w[2])
        for k, v in d["lex"].items():
            yield f"{k} meaning", fixes(str(v[2]) if len(v) > 2 else "")
    for f in sorted(glob.glob("data/lex/*/*.json")):
        for k, e in json.load(open(f)).items():
            yield f"{k} gloss", fixes(str(e[3]) if len(e) > 3 else "")
    for f in sorted(glob.glob("data/morph/*.json")):
        for k, v in json.load(open(f)).items():
            yield f"{f} {k}", fixes(" ".join(x for x in v if x))
    for f in sorted(glob.glob("data/decks/*.json")):
        for w in json.load(open(f))["words"]:
            yield f"{f} {w[0]}", w[2]

    def strings(x):
        if isinstance(x, str):
            yield x
        elif isinstance(x, dict):
            for v in x.values():
                yield from strings(v)
        elif isinstance(x, list):
            for v in x:
                yield from strings(v)
    for f in sorted(glob.glob("lessons/**/*.json", recursive=True)):
        for s in strings(json.load(open(f))):
            if not re.search(r"https?://", s):
                yield f, s
    for f in sorted(glob.glob("js/*.js")) + ["index.html"]:
        text = re.sub(r"//[^\n]*|/\*.*?\*/", "", open(f, encoding="utf-8").read(), flags=re.S)
        for m in re.finditer(r"([\"'`])((?:(?!\1)[^\\\n]|\\.){3,})\1", text):
            s = m.group(2)
            if " " in s and not re.search(r"^[\w.#\-:\s>*\[\]=\"']+$|\$\{|=>|\\u", s):
                yield f, re.sub(r"<[^>]+>", " ", s)


def slips_fixed_in_app():
    """data.morph()'s list of source spelling slips (js/data.js), applied as the app applies them."""
    text = open("js/data.js", encoding="utf-8").read()
    pairs = re.findall(r'\[/(\\b)?([A-Za-z]+)(\\b)?/g?i?,\s*"([^"]*)"\]', text)
    reps = [(re.compile((r"\b" if a else "") + w + (r"\b" if b else "")), r) for a, w, b, r in pairs]

    def fix(s):
        for rx, r in reps:
            s = rx.sub(r, s)
        return s
    return fix


KEEP = {  # English words the BSB doesn't happen to use: not slips
    "learner", "learners", "flashcard", "flashcards", "erasmian", "koine", "transliteration", "septuagint", "app",
    "online", "offline", "wayyiqtol", "weqatal", "qatal", "yiqtol", "cohortative", "jussive", "aorist", "deponent",
    "dagesh", "shewa", "qamets", "patah", "segol", "tsere", "hiriq", "holam", "qubuts", "shureq", "maqqef", "meteg",
    "niphal", "piel", "pual", "hiphil", "hophal", "hithpael", "qal", "genitive", "dative", "accusative", "vocative",
}


def definition_words():
    """The English of the dictionaries' definitions (Abbott-Smith, Middle Liddell, Strong's): more real words."""
    c = collections.Counter()
    for f in glob.glob("data/lex/*/*.json"):
        for e in json.load(open(f)).values():
            if len(e) > 4 and e[4]:
                c.update(w.lower() for w in WORD.findall(re.sub(r"<[^>]+>", " ", str(e[4]))))
    return c


def real_word(lw, known):
    """Known as it stands, or as a known word with an ending (s, ed, ing, er, ly …), or in its US/UK spelling."""
    if lw in known:
        return True
    for suf, back in (("s", ""), ("es", ""), ("ed", ""), ("ed", "e"), ("d", ""), ("ing", ""), ("ing", "e"), ("er", ""),
                      ("er", "e"), ("ers", ""), ("ers", "e"), ("ly", ""), ("ness", ""), ("ings", ""), ("ings", "e"),
                      ("ment", ""), ("able", ""), ("ful", ""), ("less", "")):
        if lw.endswith(suf) and len(lw) - len(suf) >= 3:
            stem = lw[:-len(suf)] + back
            if stem in known or (stem[-1:] == stem[-2:-1] and stem[:-1] in known):  # travelled, wrapper
                return True
    us = re.sub(r"our$", "or", lw.replace("ll", "l").replace("pp", "p"))
    us2 = re.sub(r"is(e|ed|es|ing|ation)$", r"iz\1", lw)  # British -ise
    return (us != lw and us in known) or (us2 != lw and real_word(us2, known))


def run(items, bsb):
    common = {w for w, n in bsb.items() if n >= 5}
    known = set(bsb) | KEEP | {w for w, n in DEFS.items() if n >= 2}
    seen = collections.Counter()
    where = {}
    for src, text in items:
        text = re.sub(r"(\w)[<\[](\w+)[>\]]", r"\1\2", text or "")  # hundred<s>, year[s], properti<es>: one word
        text = re.sub(r"'s\b", "", text)  # possessives
        for w in WORD.findall(text):
            lw = w.lower()
            seen[lw] += 1
            where.setdefault(lw, f"{src}: {text[:90]}")
    out = {}
    for lw, n in seen.items():
        if len(lw) < 5 or n > 3 or real_word(lw, known):
            continue
        near = sorted(x for x in edits1(lw) if x in common and x != lw)
        if near:
            out[lw] = f"{lw!r} ×{n} (did you mean {', '.join(near[:3])}?) — {where[lw]}"
    return len(seen), out


DEFS = collections.Counter()


def main():
    bsb = bsb_words()
    DEFS.update(definition_words())
    if "--self-test" in sys.argv:
        planted = [("opressors", True), ("becasue", True), ("hevaen", True), ("shepherd", False), ("Pharoah", True), ("travelled", False)]
        ok = 0
        for w, should in planted:
            _, out = run([("test", f"the {w} came")], bsb)
            caught = w.lower() in out
            right = caught == should
            print(("ok     " if right else "WRONG  ") + w + (" flagged" if caught else " passed"))
            ok += right
        print(f"{ok}/{len(planted)} passed")
        sys.exit(0 if ok == len(planted) else 1)
    n, out = run(texts(), bsb)
    if "--write-baseline" in sys.argv:
        json.dump(sorted(out), open(BASELINE_FILE, "w"), ensure_ascii=False, indent=0)
        print("Baseline written")
        return
    known = set(json.load(open(BASELINE_FILE))) if os.path.exists(BASELINE_FILE) else set()
    new = {k: v for k, v in out.items() if k not in known}
    gone = known - set(out)
    print(f"{n:,} different English words checked against the {len(bsb):,} words of the BSB")
    print(f"  {len(out)} look like slips; {len(out) - len(new)} approved in the baseline (names, Greek and Latin terms, real words)")
    for k in sorted(new):
        print("   NEW ", new[k])
    for k in sorted(gone):
        print("   GONE", k, "(put right? update the baseline)")
    print(f"{len(new) + len(gone)} problems")
    sys.exit(1 if new or gone else 0)


if __name__ == "__main__":
    main()
