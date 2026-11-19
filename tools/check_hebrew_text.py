"""The Hebrew text, word by word, against the Open Scriptures Hebrew Bible (OSHB: Westminster Leningrad Codex with its
own lemmas and morphology), and against the rules of how pointed Hebrew is written.

    python3 tools/check_hebrew_text.py [SOURCES]      # SOURCES defaults to /home/claude/src (needs morphhb/)
    python3 tools/check_hebrew_text.py --self-test    # plants mistakes and shows each one is caught
    python3 tools/check_hebrew_text.py --write-baseline

Our Hebrew is STEPBible's TAHOT (Leningrad). check_data.py compares whole verses by consonants; this goes further,
word by word, so a slip in one word can't hide:
  1. Letters, vowels and other marks of every word (written form; for qere words the qere too), with and without the
     accents, against OSHB. Hebrew is compared with the marks on each letter sorted, never NFC (see CLAUDE.md).
  2. Strong's numbers of each part (prefix, main word, suffix) against OSHB's lemmas.
  3. The grammar code of each part against OSHB's.
  4. How the pointing is written, in our data alone: one vowel per letter (shewa + qamets on one letter is a slip),
     dagesh and shin/sin dots only on letters that take them, no mark before the first letter, final letters only at
     the end of a word, no Latin letters or stray characters.
Differences that are TAHOT's deliberate choices (qere readings OSHB doesn't print, verse divisions) are approved one
by one in tools/fixtures/hebrew_text_baseline.json; anything new fails.
"""
import collections, difflib, glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = next((a for a in sys.argv[1:] if not a.startswith("-")), os.environ.get("SOURCES", "/home/claude/src"))
BASELINE_FILE = os.path.join(ROOT, "tools", "fixtures", "hebrew_text_baseline.json")

OSHB_BOOK = {"GEN": "Gen", "EXO": "Exod", "LEV": "Lev", "NUM": "Num", "DEU": "Deut", "JOS": "Josh", "JDG": "Judg",
             "RUT": "Ruth", "1SA": "1Sam", "2SA": "2Sam", "1KI": "1Kgs", "2KI": "2Kgs", "1CH": "1Chr", "2CH": "2Chr",
             "EZR": "Ezra", "NEH": "Neh", "EST": "Esth", "JOB": "Job", "PSA": "Ps", "PRO": "Prov", "ECC": "Eccl",
             "SNG": "Song", "ISA": "Isa", "JER": "Jer", "LAM": "Lam", "EZK": "Ezek", "DAN": "Dan", "HOS": "Hos",
             "JOL": "Joel", "AMO": "Amos", "OBA": "Obad", "JON": "Jonah", "MIC": "Mic", "NAM": "Nah", "HAB": "Hab",
             "ZEP": "Zeph", "HAG": "Hag", "ZEC": "Zech", "MAL": "Mal"}

LETTERS = "א-ת"
ACCENTS = "֑-ֽ֯׀׃ׅׄ"  # cantillation, meteg, paseq, sof pasuq, upper/lower dots
VOWELS = "ְ-ׇֻ"  # shewa … qubuts, qamets qatan
POINTS = "ּֿׁׂ"  # dagesh/mappiq, shin dot, sin dot, rafe
PREFIX_STRONG = {"b": "9003", "c": "9002", "d": "9009", "i": "9008", "k": "9004", "l": "9005", "m": "9006",
                 "s": "9007", "e": "9010", "a": "9001"}


def clusters(word):
    """[letter + its marks sorted] — so the same pointing typed in a different order compares equal."""
    out = []
    for ch in word:
        if re.match(f"[{LETTERS}]", ch) or not out:
            out.append([ch, []])
        else:
            out[-1][1].append(ch)
    return ["".join([c] + sorted(m)) for c, m in out]


def norm(word, accents=True):
    w = re.sub(r"[/\\\s־]", "", word)
    if not accents:
        w = re.sub(f"[{ACCENTS}]", "", w)
    return "".join(clusters(w))


def consonants(word):
    return re.sub(f"[^{LETTERS}]", "", word)


# ---------------------------------------------------------------- reading
def load_oshb():
    out = {}
    for bk, osis in OSHB_BOOK.items():
        x = open(os.path.join(SRC, "morphhb", "wlc", f"{osis}.xml"), encoding="utf-8").read()
        for m in re.finditer(r'<verse osisID="([^"]+)">(.*?)</verse>', x, re.S):
            _, c, v = m.group(1).split(".")
            body = m.group(2)
            words = []
            # a ketiv <w> is followed by its qere inside <note type="variant">
            for wm in re.finditer(r'(<w [^>]*>.*?</w>)|<note type="variant">.*?<rdg type="x-qere">(.*?)</rdg>.*?</note>', body, re.S):
                if wm.group(1):
                    a = dict(re.findall(r'(\w+)="([^"]*)"', wm.group(1).split(">")[0]))
                    text = re.sub(r"<[^>]+>", "", wm.group(1))
                    words.append({"text": text, "lemma": a.get("lemma", ""), "morph": a.get("morph", ""),
                                  "ketiv": a.get("type") == "x-ketiv", "qere": []})
                else:
                    q = [{"text": re.sub(r"<[^>]+>", "", w), "lemma": dict(re.findall(r'(\w+)="([^"]*)"', w))["lemma"],
                          "morph": dict(re.findall(r'(\w+)="([^"]*)"', w)).get("morph", "")}
                         for w in re.findall(r"<w [^>]*>.*?</w>", wm.group(2))]
                    if words:
                        words[-1]["qere"] += q
            out[(bk, int(c), int(v))] = words
    return out


def load_ours():
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "hot", "*.json"))):
        d = json.load(open(f))
        for ch, verses in d["ch"]:
            for item in verses:
                v, words = item[0], item[1]
                hc, hv = map(int, item[2].split(".")) if len(item) > 2 else (ch, v)
                out.setdefault((d["id"], hc, hv), []).extend(
                    {"text": w[0], "key": w[3] if len(w) > 3 else "", "morph": w[4] if len(w) > 4 else "",
                     "flag": w[6] if len(w) > 6 else "", "ketiv": w[7] if len(w) > 7 else "", "ref": f"{d['id']} {ch}:{v}"}
                    for w in words)
    return out


def strongs_ours(key):
    """'H9003/{H7225G}\\H9016' → ['9003', '7225']: every part's number, letters and suffix labels dropped."""
    out = []
    for part in re.split(r"[/]", key):
        for k in re.findall(r"H(\d{4})", part.split("\\")[0]):
            if int(k) < 9013 or int(k) > 9030:  # H9013… are suffix/paragogic labels, not Strong's
                out.append(str(int(k)).zfill(4))
    return out


def strongs_oshb(lemma):
    out = []
    for part in lemma.split("/"):
        part = part.strip().rstrip("+").split(" ")[0]
        if part in PREFIX_STRONG:
            out.append(PREFIX_STRONG[part])
        elif re.match(r"^\d+", part):
            out.append(re.match(r"^\d+", part).group(0).zfill(4))
    return out


# ---------------------------------------------------------------- the rules of the pointing
VALID_DAGESH = set("בגדהוזטיכךלמנסעפףצקשתר") | set("אע")  # א ע ר: rare but attested (dagesh in alef, Gen 43:26)
FINALS = set("ךםןףץ")


def pointing_problems(word):
    """What is wrong with how a word is pointed (empty if nothing). A maqqef joins two words: each is checked."""
    if "\u05be" in word:
        return [p for part in word.split("\u05be") if part for p in pointing_problems(part)]
    out = []
    w = re.sub(r"[/\\־\s]", "", word)
    if re.search("[A-Za-z0-9]", w):
        out.append("Latin letter or digit")
    if re.search(f"[^{LETTERS}֑-ׇ‍⁠͏]", w):
        out.append("character that isn't Hebrew: " + " ".join(f"U+{ord(c):04X}" for c in set(re.findall(f"[^{LETTERS}֑-ׇ‍⁠͏]", w))))
    if w and not re.match(f"[{LETTERS}]", w):
        out.append("mark before the first letter")
    cl = clusters(w)
    for i, c in enumerate(cl):
        letter, marks = c[0], c[1:]
        vowels = [m for m in marks if re.match(f"[{VOWELS}]", m)]
        if len(vowels) > 1 and sorted(vowels) != ["ִ", "ַ"] and sorted(vowels) != ["ִ", "ָ"]:
            out.append("two vowels on one letter " + letter + "".join(vowels))
        if "ּ" in marks and letter not in VALID_DAGESH:
            out.append("dagesh on " + letter)
        if ("ׁ" in marks or "ׂ" in marks) and letter != "ש":
            out.append("shin/sin dot on " + letter)
        if "ׁ" in marks and "ׂ" in marks:
            out.append("both shin and sin dot")
        if marks.count("ּ") > 1:
            out.append("dagesh twice")
        if letter in FINALS and i < len(cl) - 1 and re.search(f"[{LETTERS}]", "".join(x[0] for x in cl[i + 1:])):
            out.append("final letter inside a word: " + letter)
    return out


def word_rules(ours):
    problems = collections.defaultdict(list)
    n = 0
    for key, words in ours.items():
        for w in words:
            for form, label in ((w["text"], ""), (w["ketiv"], " (written form)")):
                if not form:
                    continue
                n += 1
                for p in pointing_problems(form):
                    problems[p.split(":")[0].split(" ")[0] + " " + " ".join(p.split(" ")[1:3])].append(f"{w['ref']} {form}{label}: {p}")
    return n, problems


# ---------------------------------------------------------------- comparing
def same_marks(word):
    """Spellings of the same pointing: holam for vav (U+05BA) = holam; a pashta written twice in Leningrad, the first
    as qadma in OSHB (U+05A8) or as pashta in TAHOT (U+0599)."""
    w = word.replace("\u05ba", "\u05b9")
    if "\u0599" in w:
        w = w.replace("\u05a8", "\u0599")
    return w


def verb_part(code):
    """The verb in a code: stem, form, person, gender, number (HC/Vqw3ms → qw3ms); '' if no verb. TAHOT's finer
    forms are folded into OSHB's: weqatal q = perfect p, weyiqtol u = imperfect i, cohortative c + person = h,
    infinitive construct cc = c, absolute aa = a; jussive j and imperfect i look alike in most forms (= i)."""
    m = re.search(r"(?:^[HA]|/)V(\w)(\w+)", code or "")
    if not m:
        return ""
    stem, rest = m.groups()
    rest = re.sub(r"^cc", "c", rest)
    rest = re.sub(r"^aa", "a", rest)
    rest = re.sub(r"^c(?=[123])", "h", rest)
    rest = re.sub(r"^q", "p", rest)
    rest = re.sub(r"^[uj]", "i", rest)
    return stem + rest


def morph_norm(code):
    # TAHOT gives proper names a kind (Npm person, Npl place, Npf woman …); OSHB writes Np
    return re.sub(r"Np[a-z]", "Np", code)


def reading(words, oshb=False):
    """The words as they are read: qere instead of ketiv, without written-not-read or added words."""
    out = []
    for w in words:
        if oshb:
            if w["qere"]:
                out += [dict(q, ref=w.get("ref", "")) for q in w["qere"]]
            elif not w["ketiv"]:
                out.append(w)
        elif w["flag"] not in ("k", "x"):
            out.append(w)
    return out


def compare(ours, oshb):
    problems = collections.defaultdict(list)
    pairs = collections.Counter()
    global kinds, examples
    kinds, examples = collections.Counter(), {}
    words = 0
    # whole books, so a verse divided differently (1 Sam 20:42 = Hebrew 20:42 + 21:1, Ps 51 title) still lines up
    def chapters(d):  # whole books, in the order of the text (ours: English verse order; OSHB: Hebrew)
        out = collections.defaultdict(list)
        for k in d:
            out[(k[0],)] += d[k]
        return out
    ours_c, oshb_c = chapters({k: [dict(w, v=k[2]) for w in v] for k, v in ours.items()}), chapters(oshb)
    for key in sorted(set(ours_c) | set(oshb_c)):
        o, m = reading(ours_c.get(key, [])), reading(oshb_c.get(key, []), True)
        if not o or not m:
            problems["chapter only on one side"].append(f"{key}: ours {len(o)} words, OSHB {len(m)}")
            continue
        a = [consonants(w["text"]) for w in o]
        b = [consonants(w["text"]) for w in m]
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                if "".join(a[i1:i2]) != "".join(b[j1:j2]):
                    where = o[i1]["ref"] if i1 < len(o) else o[-1]["ref"]
                    problems["words differ"].append(f"{where}: ours {' '.join(w['text'] for w in o[i1:i2])!r} · "
                                                    f"OSHB {' '.join(w['text'] for w in m[j1:j2])!r}")
                continue
            for i, j in zip(range(i1, i2), range(j1, j2)):
                words += 1
                w, x = o[i], m[j]
                ref = f"{w['ref']} {w['text']}"
                if norm(same_marks(w["text"]), False) != norm(same_marks(x["text"]), False):
                    problems["vowels differ"].append(f"{ref} · OSHB {x['text']}")
                elif norm(same_marks(w["text"])) != norm(same_marks(x["text"])):
                    problems["accents differ"].append(f"{ref} · OSHB {x['text']}")
                so, sx = strongs_ours(w["key"]), strongs_oshb(x["lemma"])
                if so and sx and so != sx:
                    pairs[(" ".join(so), " ".join(sx))] += 1
                vo, vx = verb_part(w["morph"]), verb_part(x["morph"])
                if vo and vx and vo != vx:
                    kinds[f"{vo} · OSHB {vx}"] += 1
                    examples.setdefault(f"{vo} · OSHB {vx}", f"{ref} ours {w['morph']} · OSHB {x['morph']}")
    return words, problems, pairs


def main():
    if not os.path.isdir(os.path.join(SRC, "morphhb", "wlc")):
        print(f"FAIL OSHB not found in {SRC}/morphhb (tools/fetch_sources.sh fetches it)")
        sys.exit(1)
    ours, oshb = load_ours(), load_oshb()
    if "--self-test" in sys.argv:
        return self_test(ours, oshb)
    words, problems, pairs = compare(ours, oshb)
    nforms, rules = word_rules(ours)
    for k, v in rules.items():
        problems["pointing: " + k] = v
    problems["Strong's numbers differ (pairs)"] = [f"{a} · OSHB {b} ×{n}" for (a, b), n in sorted(pairs.items())]
    problems["verb grammar differs (kinds)"] = [f"{k} ×{n}  e.g. {examples[k]}" for k, n in sorted(kinds.items())]
    if "--write-baseline" in sys.argv:
        json.dump({k: v for k, v in problems.items() if v}, open(BASELINE_FILE, "w"), ensure_ascii=False, indent=1, sort_keys=True)
        print("Baseline written:", BASELINE_FILE)
        return
    known = json.load(open(BASELINE_FILE)) if os.path.exists(BASELINE_FILE) else {}
    print("Approved in the baseline (19 Nov 2026), as STEPBible publishes them: Strong's numbering conventions (TAHOT's")
    print("H0582 for אֲנָשִׁים, H1980 for every הלך; OSHB 376, 3212), TAHOT's own verb analyses, the Decalogue's second set")
    print("of accents, qere readings OSHB doesn't mark (and the reverse), TAHOT's letter slips (2 Kgs 10:2 בְּבֹא for כְּבֹא,")
    print("2 Kgs 15:2 Jerusalem with a sin dot) and Leningrad's own oddities (Isa 9:6 לְםַרְבֵּה with a final mem).")
    print(f"{words:,} Hebrew words lined up with OSHB; {nforms:,} written forms checked against the rules of pointing")
    fails = 0
    for name in sorted(set(problems) | set(known), key=lambda k: -len(problems.get(k, []))):
        now, before = problems.get(name, []), known.get(name, [])
        new = [x for x in now if x not in before]
        gone = [x for x in before if x not in now]
        print(f"  {len(now):6}  {name}" + (f"  ({len(new)} new)" if new else "") + (f"  ({len(gone)} gone)" if gone else ""))
        for x in new[:25]:
            print("         NEW ", x)
        for x in gone[:8]:
            print("         GONE", x)
        fails += len(new) + len(gone)
    print(f"\n{fails} problems" if fails else "\n0 problems")
    sys.exit(1 if fails else 0)


def self_test(ours, oshb):
    import copy
    tests = []

    def plant(desc, key, idx, field, fn):
        o = copy.deepcopy(ours[key])
        o[idx][field] = fn(o[idx][field])
        tests.append((desc, key, o))

    plant("a vowel changed (patah for qamets)", ("GEN", 1, 1), 1, "text", lambda t: t.replace("ָ", "ַ", 1))
    plant("an accent dropped", ("GEN", 1, 1), 2, "text", lambda t: re.sub("[֑-֯]", "", t))
    plant("wrong Strong's number", ("GEN", 1, 1), 1, "key", lambda k: "{H1254B}".replace("1254B", "1255"))
    plant("wrong grammar code", ("GEN", 1, 1), 1, "morph", lambda m: "HVqp3fs")
    plant("two vowels on one letter", ("GEN", 1, 3), 0, "text", lambda t: t[:2] + "ְ" + t[2:])
    plant("dagesh on a throat letter", ("GEN", 1, 1), 2, "text", lambda t: t[:1] + "ּ" + t[1:].replace("ֱ", "ֱ", 1))
    plant("a word missing", ("GEN", 1, 2), 0, "text", lambda t: "")
    ok = 0
    keys = sorted({t[1] for t in tests})
    sub_oshb = {k: oshb[k] for k in keys}

    def count(o):
        _, p, pr = compare(o, sub_oshb)
        _, r = word_rules(o)
        return sum(len(v) for v in p.values()) + len(pr) + sum(kinds.values()) + sum(len(v) for v in r.values())
    base = count({k: ours[k] for k in keys})
    for desc, key, o in tests:
        o2 = {k: ours[k] for k in keys}
        o2[key] = o
        caught = count(o2) > base
        print(("caught " if caught else "MISSED ") + desc)
        ok += caught
    print(f"{ok}/{len(tests)} passed")
    sys.exit(0 if ok == len(tests) else 1)


if __name__ == "__main__":
    main()
