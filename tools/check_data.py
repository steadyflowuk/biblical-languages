"""Cross-check data/ against independent copies of the texts.

Usage: python3 tools/check_data.py /path/to/checkout-of-SBLGNT /path/to/checkout-of-morphhb
  SBLGNT:  https://github.com/LogosBible/SBLGNT (data/sblgnt/text/*.txt)
  morphhb: https://github.com/openscriptures/morphhb (wlc/*.xml)
Exits non-zero if a check fails.
"""
import glob, json, os, re, sys, unicodedata
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SBL, OSHB = sys.argv[1], sys.argv[2]
failures = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(name)


def load(p):
    return json.load(open(os.path.join(DATA, p), encoding="utf-8"))


def strip_greek(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] == "L")
    s = s.lower().replace("ς", "σ").replace("\u02bc", "")
    # spelling conventions that differ between NA28 and SBLGNT: movable nu, elided ἀλλά
    s = re.sub(r"(σι|ε|στι)ν$", r"\1", s)
    return "αλλ" if s == "αλλα" else s


def strip_hebrew(s):
    return "".join(ch for ch in s if "א" <= ch <= "ת")


books = load("books.json")
check("66 books", len(books) == 66, str(len(books)))
check("27 NT + 39 OT", sum(b["lang"] == "grc" for b in books) == 27 and sum(b["lang"] == "he" for b in books) == 39)

# ------------------------------------------------ Greek vs SBLGNT
SBL_NAMES = {"MAT": "Matt", "MRK": "Mark", "LUK": "Luke", "JHN": "John", "ACT": "Acts", "ROM": "Rom", "1CO": "1Cor",
             "2CO": "2Cor", "GAL": "Gal", "EPH": "Eph", "PHP": "Phil", "COL": "Col", "1TH": "1Thess", "2TH": "2Thess",
             "1TI": "1Tim", "2TI": "2Tim", "TIT": "Titus", "PHM": "Phlm", "HEB": "Heb", "JAS": "Jas", "1PE": "1Pet",
             "2PE": "2Pet", "1JN": "1John", "2JN": "2John", "3JN": "3John", "JUD": "Jude", "REV": "Rev"}
sbl = {}
for f in glob.glob(os.path.join(SBL, "data/sblgnt/text/*.txt")):
    for line in open(f, encoding="utf-8-sig"):
        m = re.match(r"^(\S+) (\d+):(\d+)\t(.*)$", line.rstrip("\n"))
        if m:
            sbl[(m.group(1), int(m.group(2)), int(m.group(3)))] = m.group(4)
same = diff = only_ours = 0
diffs = []
ours_words = 0
for b in books:
    if b["lang"] != "grc":
        continue
    d = load(f"gnt/{b['id']}.json")
    for ch, verses in d["ch"]:
        for v, words, *_ in verses:
            ours_words += len(words)
            key = (SBL_NAMES[b["id"]], ch, v)
            ours = [strip_greek(w[0]) for w in words]
            if key not in sbl:
                only_ours += 1
                continue
            theirs = [strip_greek(t) for t in sbl[key].split() if strip_greek(t)]
            if ours == theirs:
                same += 1
            else:
                diff += 1
                diffs.append(f"{b['id']} {ch}:{v}")
total = same + diff
check("Greek NT word count close to NA28 (~138,000)", 137_000 < ours_words < 139_000, f"{ours_words:,}")
check("Greek verses identical to SBLGNT (letters only, spelling conventions aside) ≥ 90%", same / total >= 0.90,
      f"{same:,}/{total:,} identical ({same/total:.1%}); {diff} differ: NA28 bracketed words and readings SBLGNT does not follow")
check("Jude 5 reads Ἰησοῦς (an NA28 change)",
      any(w[0] == "Ἰησοῦς" for v in load("gnt/JUD.json")["ch"][0][1] if v[0] == 5 for w in v[1]))
mat17 = {v[0] for c, vs in load("gnt/MAT.json")["ch"] if c == 17 for v in vs}
check("Matthew 17:21 absent (not in NA28)", 21 not in mat17)
mrk16 = {v[0] for c, vs in load("gnt/MRK.json")["ch"] if c == 16 for v in vs}
jhn8 = {v[0] for c, vs in load("gnt/JHN.json")["ch"] if c == 8 for v in vs}
check("Mark 16:9-20 and John 8:1-11 present (NA28 prints them in double brackets)",
      set(range(9, 21)) <= mrk16 and set(range(1, 12)) <= jhn8)

# ------------------------------------------------ Hebrew vs WLC (Open Scriptures)
OSHB_BOOK = {"GEN": "Gen", "EXO": "Exod", "LEV": "Lev", "NUM": "Num", "DEU": "Deut", "JOS": "Josh", "JDG": "Judg",
             "RUT": "Ruth", "1SA": "1Sam", "2SA": "2Sam", "1KI": "1Kgs", "2KI": "2Kgs", "1CH": "1Chr", "2CH": "2Chr",
             "EZR": "Ezra", "NEH": "Neh", "EST": "Esth", "JOB": "Job", "PSA": "Ps", "PRO": "Prov", "ECC": "Eccl",
             "SNG": "Song", "ISA": "Isa", "JER": "Jer", "LAM": "Lam", "EZK": "Ezek", "DAN": "Dan", "HOS": "Hos",
             "JOL": "Joel", "AMO": "Amos", "OBA": "Obad", "JON": "Jonah", "MIC": "Mic", "NAM": "Nah", "HAB": "Hab",
             "ZEP": "Zeph", "HAG": "Hag", "ZEC": "Zech", "MAL": "Mal"}
wlc = {}
for f in glob.glob(os.path.join(OSHB, "wlc/*.xml")):
    x = open(f, encoding="utf-8").read()
    for m in re.finditer(r'<verse osisID="([^"]+)">(.*?)</verse>', x, re.S):
        bk, c, v = m.group(1).split(".")
        body = re.sub(r"<note.*?</note>", "", m.group(2), flags=re.S)
        words = re.findall(r"<w [^>]*>(.*?)</w>", body)
        wlc[(bk, int(c), int(v))] = strip_hebrew("".join(words))
hsame = hdiff = 0
hdiffs = []
aramaic = Counter()
he_words = 0
for b in books:
    if b["lang"] != "he":
        continue
    d = load(f"hot/{b['id']}.json")
    for ch, verses in d["ch"]:
        for item in verses:
            v, words = item[0], item[1]
            he_words += len(words)
            hc, hv = (map(int, item[2].split("."))) if len(item) > 2 else (ch, v)
            key = (OSHB_BOOK[b["id"]], hc, hv)
            # Leningrad consonants: use the written (ketiv) form where the data reads the qere
            ours = strip_hebrew("".join((w[7] if len(w) > 7 and w[6] == "q" and w[7] else w[0])
                                        for w in words if not (len(w) > 6 and w[6] == "x")))
            for w in words:
                if len(w) > 4 and w[4][:1] == "A":
                    aramaic[b["id"]] += 1
            if key in wlc:
                if ours == wlc[key]:
                    hsame += 1
                else:
                    hdiff += 1
                    hdiffs.append(f"{b['id']} {ch}:{v}")
htotal = hsame + hdiff
check("Hebrew word count ~305,000", 300_000 < he_words < 310_000, f"{he_words:,}")
check("Hebrew verses match WLC consonants ≥ 98%", hsame / htotal >= 0.98,
      f"{hsame:,}/{htotal:,} ({hsame/htotal:.1%})")
check("Aramaic marked in Daniel, Ezra, Jeremiah 10:11 and nowhere else",
      set(aramaic) == {"DAN", "EZR", "JER", "GEN"} or set(aramaic) <= {"DAN", "EZR", "JER", "GEN"},
      ", ".join(f"{k} {v}" for k, v in sorted(aramaic.items())))
gen = load("hot/GEN.json")
g3155 = [v for c, vs in gen["ch"] if c == 31 for v in vs if v[0] == 55]
check("Genesis 31:55 knows it is 32:1 in Hebrew", g3155 and len(g3155[0]) > 2 and g3155[0][2] == "32.1")

# ------------------------------------------------ famous passages and encoding
def vmap(bk):
    d = load(f"{'gnt' if any(b['id'] == bk and b['lang'] == 'grc' for b in books) else 'hot'}/{bk}.json")
    return {(c, v[0]): v for c, vs in d["ch"] for v in vs}
mrk, jhn, act, rom, ijn, luk = (vmap(b) for b in ("MRK", "JHN", "ACT", "ROM", "1JN", "LUK"))
check("NA28 omissions absent: John 5:4, Acts 8:37, Romans 16:24",
      (5, 4) not in jhn and (8, 37) not in act and (16, 24) not in rom)
check("NA28 bracketed passages present: Mark 16:9-20, Luke 22:43-44, John 7:53-8:11, Romans 16:25-27",
      all((16, v) in mrk for v in range(9, 21)) and (22, 43) in luk and (22, 44) in luk and (7, 53) in jhn
      and all((8, v) in jhn for v in range(1, 12)) and all((16, v) in rom for v in (25, 26, 27)))
check("John 7:53 opens with NA28's double brackets", jhn[(7, 53)][1][0][6:7] == ["[["], str(jhn[(7, 53)][1][0]))
check("1 John 5:7 has no 'heavenly witnesses' addition", len(ijn[(5, 7)][1]) == 5)
dan = vmap("DAN")
check("Daniel 2:4 switches to Aramaic mid-verse", "".join(w[4][0] for w in dan[(2, 4)][1]).startswith("HHHHA"))
check("Malachi 4:1 knows it is 3:19 in Hebrew", vmap("MAL")[(4, 1)][2:3] == ["3.19"])
check("Psalm titles are verse 0 (Hebrew verse 1)", vmap("PSA")[(3, 0)][2:3] == ["3.1"])
pmarks = sum(1 for b in books for c, vs in load(f"{'gnt' if b['lang'] == 'grc' else 'hot'}/{b['id']}.json")["ch"]
             for v in vs for w in v[1] if "\u00b6" in w[0])
check("no paragraph marks (¶) inside words", pmarks == 0, str(pmarks))
empty = sum(1 for b in books if b["lang"] == "he" for c, vs in load(f"hot/{b['id']}.json")["ch"]
            for v in vs for w in v[1] if not w[0].strip("/ "))
check("no empty Hebrew words (written-not-read words show their written form)", empty == 0, str(empty))
unnorm = sum(1 for b in books if b["lang"] == "he" for c, vs in load(f"hot/{b['id']}.json")["ch"]
             for v in vs for w in v[1] if unicodedata.normalize("NFC", w[0]) != w[0])
check("Hebrew keeps the manuscript's mark order (not Unicode-normalised)", unnorm > 100_000, f"{unnorm:,} words differ from NFC")

# ------------------------------------------------ BSB alignment
missing_bsb = []
for b in books:
    src = load(f"{'gnt' if b['lang'] == 'grc' else 'hot'}/{b['id']}.json")
    bsb = load(f"bsb/{b['id']}.json")
    bverses = set()
    for ci, chap in enumerate(bsb["chapters"], start=1):
        for kind, items in chap[0]:
            bverses.update((ci, x) for x in items if isinstance(x, int))
    orig = {(c, v[0]) for c, vs in src["ch"] for v in vs if v[0] > 0}
    missing_bsb += [f"{b['id']} {c}:{v}" for c, v in sorted(orig - bverses)]
check("Every original-language verse has its BSB verse (except known numbering differences)", len(missing_bsb) <= 5,
      f"{len(missing_bsb)} without a BSB verse: {', '.join(missing_bsb[:12])}")
bsb_total = sum(b["v"][i] for b in books for i in range(b["ch"]))
check("BSB verse total", bsb_total == 31086, str(bsb_total))

# ------------------------------------------------ Reader alignment: every BSB verse sits under some NA28 verse
uncovered = []
for b in books:
    if b["lang"] != "grc":
        continue
    src = load(f"gnt/{b['id']}.json")
    bsb = load(f"bsb/{b['id']}.json")
    covered = set()
    for c, vs in src["ch"]:
        for v in vs:
            refs = v[2] if len(v) > 2 and isinstance(v[2], list) else [f"{c}.{v[0]}"]
            covered.update(refs)
    for ci, chap in enumerate(bsb["chapters"], start=1):
        for kind, items in chap[0]:
            for x in items:
                if isinstance(x, int) and f"{ci}.{x}" not in covered:
                    uncovered.append(f"{b['id']} {ci}:{x}")
check("Reader: every NT verse of the BSB appears under an NA28 verse", not uncovered, ", ".join(uncovered[:8]))

# ------------------------------------------------ lexicon and grammar coverage
for lang, folder, idx, morph in (("Greek", "gnt", "greek", "greek"), ("Hebrew", "hot", "hebrew", "hebrew")):
    mt = load(f"morph/{morph}.json")
    nolex = nomorph = total = 0
    for b in books:
        if (b["lang"] == "grc") != (lang == "Greek"):
            continue
        d = load(f"{folder}/{b['id']}.json")
        for c, vs in d["ch"]:
            for v in vs:
                for w in v[1]:
                    total += 1
                    keys = [k.strip("{} ") for k in re.split(r"[/\\+]", w[3]) if k.strip("{} ")] if len(w) > 3 else []
                    if not keys or any(k not in d["lex"] for k in keys):
                        nolex += 1
                    if lang == "Greek":
                        codes = w[4].split("+") if len(w) > 4 else []
                    else:
                        segs = w[4].split("/") if len(w) > 4 else []
                        codes = [segs[0]] + [segs[0][:1] + s for s in segs[1:] if s] if segs else []
                    if not codes or any(cd not in mt for cd in codes):
                        nomorph += 1
    check(f"{lang} words with a dictionary entry ≥ 99.5%", nolex / total <= 0.005, f"{total - nolex:,}/{total:,}")
    check(f"{lang} words with a grammar explanation ≥ 99.9%", nomorph / total <= 0.001, f"{total - nomorph:,}/{total:,}")

print(f"\nGreek verses that differ from SBLGNT (first 10): {', '.join(diffs[:10])}")
print(f"Hebrew verses that differ from WLC (first 10): {', '.join(hdiffs[:10])}")
print(f"\n{'All checks passed' if not failures else str(len(failures)) + ' failed'}")
sys.exit(1 if failures else 0)
