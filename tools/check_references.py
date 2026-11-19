"""Every Bible reference the app mentions points at a verse that exists.

    python3 tools/check_references.py [--self-test]

Looks through lessons (ref fields and their text), the Letters guides, the video list, the screens' text (js, html)
and the README for references written either way — "JHN 3:16" (the app's own ids) or "John 3:16", "Rom 16:25-27",
"1 Cor 13:4" — and checks the book exists, the chapter is in the book and each verse is in the chapter, in the
numbering the app shows (English/BSB numbering; Hebrew or SBL numbering also accepted where they differ, e.g. a
Hebrew-numbered "Joel 3:1"). A range must run forwards. Writes the number of references checked.
"""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
BOOKS = json.load(open("data/books.json"))
IDS = {b["id"]: b for b in BOOKS}
NAMES = {}
for b in BOOKS:
    for n in {b["name"], b["step"], b["id"].title(), b["id"]}:
        NAMES[n.lower().replace(" ", "")] = b["id"]
EXTRA = {"psalm": "PSA", "ps": "PSA", "pss": "PSA", "matt": "MAT", "mt": "MAT", "mk": "MRK", "lk": "LUK", "jn": "JHN",
         "jhn": "JHN", "rom": "ROM", "cor": None, "gal": "GAL", "eph": "EPH", "phil": "PHP", "col": "COL", "heb": "HEB",
         "jas": "JAS", "rev": "REV", "gen": "GEN", "exod": "EXO", "ex": "EXO", "lev": "LEV", "num": "NUM", "deut": "DEU",
         "isa": "ISA", "jer": "JER", "ezek": "EZK", "dan": "DAN", "hos": "HOS", "mic": "MIC", "zech": "ZEC", "mal": "MAL",
         "prov": "PRO", "eccl": "ECC", "song": "SNG", "songofsongs": "SNG", "songofsolomon": "SNG", "judg": "JDG",
         "josh": "JOS", "neh": "NEH", "esth": "EST", "lam": "LAM", "obad": "OBA", "hab": "HAB", "zeph": "ZEP",
         "hag": "HAG", "jon": "JON", "nah": "NAM", "amos": "AMO", "joel": "JOL", "ruth": "RUT", "job": "JOB", "acts": "ACT",
         "jude": "JUD", "phlm": "PHM", "philem": "PHM", "tit": "TIT", "luke": "LUK", "mark": "MRK", "john": "JHN"}
for k, v in EXTRA.items():
    if v:
        NAMES.setdefault(k, v)
NUMBERED = {"samuel": "SA", "sam": "SA", "kings": "KI", "kgs": "KI", "chronicles": "CH", "chr": "CH", "corinthians": "CO",
            "cor": "CO", "thessalonians": "TH", "thess": "TH", "timothy": "TI", "tim": "TI", "peter": "PE", "pet": "PE",
            "john": "JN", "jn": "JN"}

# every verse that exists, in each numbering the app uses
VERSES = set()
for f in glob.glob("data/gnt/*.json") + glob.glob("data/hot/*.json"):
    d = json.load(open(f))
    for ch, vs in d["ch"]:
        for it in vs:
            VERSES.add((d["id"], ch, it[0]))
            if len(it) > 2 and isinstance(it[2], str) and "." in it[2]:  # Hebrew numbering
                c, v = map(int, it[2].split("."))
                VERSES.add((d["id"], c, v))
            if len(it) > 2 and isinstance(it[2], list):
                for r in it[2]:
                    c, v = map(int, r.split("."))
                    VERSES.add((d["id"], c, v))
for f in glob.glob("data/bsb/*.json"):
    d = json.load(open(f))
    bid = os.path.basename(f)[:-5]
    for ci, chapter in enumerate(d.get("chapters", [])):
        for kind, items in chapter[0]:
            for x in items:
                if isinstance(x, int):
                    VERSES.add((bid, ci + 1, x))

# a sentence about a verse the text leaves out ("isn't in the original text (e.g. Matthew 17:21)") is right to name it
ABSENT = re.compile(r"isn't in|not in the|leaves? (?:it |this |them )?out|omits?|absent|no such verse|left out", re.I)
REF = re.compile(r"\b(?:(?P<num>[123])\s?)?(?P<book>[A-Z][A-Za-z]+(?: of (?:Songs|Solomon))?|[1-3]?[A-Z]{2,3})\.?\s(?P<ch>\d{1,3}):(?P<v>\d{1,3})(?:[-–](?P<v2>\d{1,3})(?::(?P<v3>\d{1,3}))?)?")


def book_id(num, name):
    key = name.lower().replace(" ", "")
    if num:
        stem = NUMBERED.get(key)
        if stem:
            return f"{num}{stem}" if f"{num}{stem}" in IDS else None
        key = num + key
    if name.isupper() and name in IDS:
        return name
    return NAMES.get(key)


def check_text(text, where):
    found, bad = 0, []
    for m in REF.finditer(text):
        b = book_id(m.group("num"), m.group("book"))
        if not b:
            continue  # not a book name ("Version 1:2", "Step 2:1")
        found += 1
        c, v = int(m.group("ch")), int(m.group("v"))
        if m.group("v3"):  # 7:53-8:11
            c2, v2 = int(m.group("v2")), int(m.group("v3"))
        else:
            c2, v2 = c, int(m.group("v2") or v)
        if (c2, v2) < (c, v):
            bad.append(f"{where}: {m.group(0)} runs backwards")
        for cc, vv in sorted({(c, v), (c2, v2)}):
            if (b, cc, vv) not in VERSES and not ABSENT.search(text[max(0, m.start() - 80):m.end() + 80]):
                bad.append(f"{where}: {m.group(0)} — {b} {cc}:{vv} doesn't exist")
    return found, bad


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


def main():
    if "--self-test" in sys.argv:
        tests = [("John 3:16", 0), ("John 3:46", 1), ("1 Cor 13:4", 0), ("1 Cor 17:4", 1), ("JHN 21:26", 1),
                 ("Romans 16:25-27", 0), ("Mark 16:9-20", 0), ("John 7:53-8:11", 0), ("Jude 1:26", 1), ("Joel 3:1", 0),
                 ("Psalm 151:1", 1), ("Acts 8:5-3", 1), ("Matthew 17:21 isn't in the SBL text", 0)]
        ok = 0
        for t, want in tests:
            n, bad = check_text(t, "test")
            right = (len(bad) > 0) == (want > 0) and n == 1
            print(("ok     " if right else "WRONG  ") + t + (f"  {bad}" if bad else ""))
            ok += right
        print(f"{ok}/{len(tests)} passed")
        sys.exit(0 if ok == len(tests) else 1)
    total, problems = 0, []
    files = sorted(glob.glob("lessons/**/*.json", recursive=True))
    for f in files:
        for s in strings(json.load(open(f))):
            n, bad = check_text(s, f)
            total += n
            problems += bad
    for f in sorted(glob.glob("js/*.js")) + ["index.html", "README.md"]:
        n, bad = check_text(open(f, encoding="utf-8").read(), f)
        total += n
        problems += bad
    print(f"{total:,} references checked in {len(files)} lesson files, the screens and the README")
    for p in problems:
        print("  ", p)
    print(f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
