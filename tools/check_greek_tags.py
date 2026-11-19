"""Greek tagging against a second, independent tagging of the same text.

    python3 tools/check_greek_tags.py [SOURCES]        # SOURCES defaults to /home/claude/src (needs morphgnt/)
    python3 tools/check_greek_tags.py --self-test      # plants mistakes and shows each one is caught

Our Greek words carry STEPBible's TAGNT tagging, matched word by word onto the SBLGNT text (Session 13). MorphGNT
(CC BY-SA, used here only to check, never copied into the app) tags the same SBLGNT text independently. For every
word this lines the two up and compares:
  - the word itself (both are SBLGNT: must be identical, letter for letter)
  - part of speech (noun, verb, article, pronoun …), allowing the usual differences of convention (BASELINE_POS)
  - case, number and gender for nouns, adjectives, articles, pronouns and participles
  - tense, voice, mood, person and number for verbs (TAGNT's "deponent" voices match MorphGNT's middle/passive)
  - the dictionary form (our key's headword vs MorphGNT's lemma), allowing the usual spelling conventions
A difference the two traditions both defend (e.g. one parses a form as middle, the other as passive) is listed in
BASELINE with a count; anything else is printed and the run fails. A word tagged by the wrong row when the SBL text
was matched to TAGNT (the risky step of Session 13) shows up as several features disagreeing at once.
"""
import collections, difflib, glob, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = next((a for a in sys.argv[1:] if not a.startswith("-")), os.environ.get("SOURCES", "/home/claude/src"))

MGNT_BOOKS = ["MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL", "1TH", "2TH",
              "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"]


def strip(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^\w]|[\u02bc\u2019\u1fbd]", "", s).lower().replace("ς", "σ")


def plain(s):  # letters with accents, no punctuation, final sigma folded, grave = acute, elision marks alike
    s = unicodedata.normalize("NFD", s).replace("\u0300", "\u0301")
    s = unicodedata.normalize("NFC", s)
    s = re.sub("[\u02bc\u2019\u1fbd]", "\u2019", s)
    return re.sub("[^\\w\u0300-\u036f\u2019]", "", s).replace("ς", "σ").lower()


# ---------- reading the two taggings into one shape ----------
# features: pos, case, num, gen, tense, voice, mood, person

def ours_features(code):
    f = {}
    head = code.split("-")[0]
    parts = code.split("-")
    if "+" in head:
        return {"pos": "joined"}
    if head == "V":
        f["pos"] = "verb"
        tvm = parts[1]
        m = re.match(r"2?([PIFARL])([AMPEDONQX])([ISOMNP])$", tvm)
        if not m:
            return {"pos": "verb?"}
        f["tense"] = {"P": "pres", "I": "impf", "F": "fut", "A": "aor", "R": "perf", "L": "plpf"}[m.group(1)]
        f["voice"] = {"A": "act", "M": "mid", "P": "pass", "E": "mp", "D": "mid", "O": "pass", "N": "mp",
                      "Q": "pass", "X": "none"}[m.group(2)]
        f["mood"] = {"I": "ind", "S": "subj", "O": "opt", "M": "imp", "N": "inf", "P": "ptc"}[m.group(3)]
        rest = parts[2] if len(parts) > 2 else ""
        if f["mood"] == "ptc":
            m2 = re.match(r"([NGDAV])([SP])([MFN])", rest)
            if m2:
                f["case"], f["num"], f["gen"] = m2.groups()
        elif f["mood"] != "inf":
            m2 = re.match(r"([123])([SP])", rest)
            if m2:
                f["person"], f["num"] = m2.groups()
        return f
    posmap = {"N": "noun", "A": "adj", "T": "art", "P": "pron", "R": "rel", "D": "dem", "C": "recip", "F": "refl",
              "I": "interr", "X": "indef", "Q": "correl", "K": "correl", "S": "poss",
              "CONJ": "conj", "COND": "conj", "PREP": "prep", "ADV": "adv", "PRT": "prt", "INJ": "inj",
              "HEB": "foreign", "ARAM": "foreign"}
    f["pos"] = posmap.get(head, head)
    if len(parts) > 1:
        body = parts[1]
        if head in ("P",) and re.match(r"[123]", body):  # P-1NS personal pronoun
            f["person"] = body[0]
            m2 = re.match(r"[123]([NGDAV])([SP])", body)
            if m2:
                f["case"], f["num"] = m2.groups()
        elif head == "S":  # S-1SNSF possessive: person, possessor number, then case number gender
            m2 = re.match(r"([123])[SP]([NGDAV])([SP])([MFN])", body)
            if m2:
                f["person"], f["case"], f["num"], f["gen"] = m2.groups()
        elif head == "F":  # F-3GSM reflexive
            m2 = re.match(r"([123])([NGDAV])([SP])([MFN])?", body)
            if m2:
                f["person"], f["case"], f["num"] = m2.group(1), m2.group(2), m2.group(3)
                if m2.group(4):
                    f["gen"] = m2.group(4)
        else:
            m2 = re.match(r"([NGDAV])([SP])([MFN])?", body)
            if m2:
                f["case"], f["num"] = m2.group(1), m2.group(2)
                if m2.group(3):
                    f["gen"] = m2.group(3)
    return f


def mgnt_features(pos, parse):
    f = {}
    p = {"A-": "adj", "C-": "conj", "D-": "adv", "I-": "inj", "N-": "noun", "P-": "prep", "RA": "art", "RD": "dem",
         "RI": "interr", "RP": "pron", "RR": "rel", "V-": "verb", "X-": "prt"}[pos]
    f["pos"] = p
    person, tense, voice, mood, case, num, gen, deg = parse
    if person != "-":
        f["person"] = person
    if tense != "-":
        f["tense"] = {"P": "pres", "I": "impf", "F": "fut", "A": "aor", "X": "perf", "Y": "plpf"}[tense]
    if voice != "-":
        f["voice"] = {"A": "act", "M": "mid", "P": "pass"}[voice]
    if mood != "-":
        f["mood"] = {"I": "ind", "S": "subj", "O": "opt", "D": "imp", "N": "inf", "P": "ptc"}[mood]
    if case != "-":
        f["case"] = case
    if num != "-":
        f["num"] = num
    if gen != "-":
        f["gen"] = gen
    return f


# Parts of speech the two traditions name differently for the same word (counted, not failed)
POS_SAME = {
    ("conj", "adv"), ("prt", "adv"), ("adv", "prt"), ("conj", "prt"), ("prt", "conj"), ("adv", "conj"),
    ("prep", "adv"), ("adv", "prep"), ("inj", "prt"), ("prt", "inj"), ("inj", "adv"), ("adv", "inj"),
    ("dem", "pron"), ("refl", "pron"), ("recip", "pron"), ("poss", "adj"), ("correl", "adj"), ("correl", "rel"),
    ("correl", "dem"), ("correl", "interr"), ("indef", "interr"), ("interr", "interr"), ("rel", "rel"),
    ("adj", "noun"), ("noun", "adj"), ("adj", "interr"), ("interr", "adj"), ("adj", "dem"), ("adj", "pron"),
    ("noun", "pron"), ("pron", "adj"), ("adv", "adj"), ("adj", "adv"), ("noun", "adv"), ("adv", "noun"),
    ("foreign", "noun"), ("foreign", "verb"), ("foreign", "adj"), ("foreign", "prt"), ("foreign", "adv"), ("foreign", "inj"),
    ("noun", "inj"), ("inj", "noun"), ("conj", "rel"), ("adv", "rel"), ("rel", "adv"), ("interr", "adv"), ("adv", "interr"),
    ("indef", "adv"), ("prt", "interr"), ("interr", "prt"), ("dem", "adv"), ("adj", "prt"), ("prt", "adj"),
    ("noun", "prt"), ("dem", "adj"), ("pron", "dem"), ("rel", "pron"), ("indef", "adj"), ("prep", "conj"), ("conj", "prep"),
    ("prep", "prt"), ("verb", "inj"), ("inj", "verb"), ("verb", "adv"), ("noun", "verb"), ("verb", "noun"),
}


def compare(o, m):
    """Names of the features that disagree."""
    out = []
    if o["pos"] in ("joined", "verb?"):
        return out
    if o["pos"] != m["pos"]:
        if (o["pos"], m["pos"]) not in POS_SAME:
            out.append(f"pos {o['pos']}→{m['pos']}")
        if "verb" not in (o["pos"], m["pos"]):
            pass
        else:
            return out
    for k in ("case", "num", "gen", "person", "tense", "mood"):
        if k in o and k in m and o[k] != m[k]:
            out.append(f"{k} {o[k]}→{m[k]}")
    if "voice" in o and "voice" in m:
        ov, mv = o["voice"], m["voice"]
        if not (ov == mv or (ov == "mp" and mv in ("mid", "pass")) or ov == "none"):
            out.append(f"voice {ov}→{mv}")
    return out


def kind(diff):
    """A difference's kind for the baseline: features without the values that vary word to word."""
    return " / ".join(sorted(diff))


def lemma_ok(our_lemma, mg_lemma):
    if "," in our_lemma:  # "Μωϋσῆς, Μωσῆς": either spelling
        return any(lemma_ok(x, mg_lemma) for x in our_lemma.split(","))
    a, b = strip(our_lemma), strip(mg_lemma)
    if a == b:
        return True
    # usual conventions: -ω/-ομαι deponents, ει/ι, assimilation, movable ν, -ττ/-σσ, names with/without endings
    def fold(x):
        x = re.sub(r"ομαι$", "ω", x)
        x = re.sub(r"(ειμι|ημι|υμι)$", "μι", x)
        x = x.replace("ει", "ι").replace("ττ", "σσ").replace("γγ", "νγ").replace("γκ", "νκ").replace("μπ", "νπ")
        x = x.replace("μμ", "νμ").replace("λλ", "νλ").replace("ρρ", "ρ").replace("η", "ε").replace("ω", "ο")
        x = x.replace("υ", "ι").replace("θ", "τ").replace("ν", "")
        return x
    if fold(a) == fold(b):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def load_ours():
    lexicon = {}
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "data/gnt/*.json"))):
        d = json.load(open(f))
        lexicon.update(d["lex"])
        for ch, vs in d["ch"]:
            for item in vs:
                v, ws = item[0], item[1]
                out[(d["id"], ch, v)] = ws
    return out, lexicon


def load_mgnt():
    out = collections.defaultdict(list)
    for f in sorted(glob.glob(os.path.join(SRC, "morphgnt", "*-morphgnt.txt"))):
        for line in open(f, encoding="utf-8"):
            bcv, pos, parse, text, word, norm, lemma = line.split()
            b, c, v = int(bcv[:2]), int(bcv[2:4]), int(bcv[4:])
            out[(MGNT_BOOKS[b - 1], c, v)].append((word, pos, parse, lemma))
    return out


def align(ours, theirs):
    """Pairs (i, j) of words that are the same written word, in order."""
    a = [strip(w[0]) for w in ours]
    b = [strip(w[0]) for w in theirs]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    pairs, gaps = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            pairs += [(i1 + k, j1 + k) for k in range(i2 - i1)]
        else:
            gaps.append((tag, ours[i1:i2], theirs[j1:j2]))
    return pairs, gaps


def run(ours, lexicon, mgnt, report=True):
    problems = collections.defaultdict(list)
    kinds = collections.Counter()
    words = 0
    lemma_diff = collections.Counter()
    for ref in sorted(set(ours) | set(mgnt)):
        o, m = ours.get(ref, []), mgnt.get(ref, [])
        if not o or not m:
            problems["verse missing on one side"].append(f"{ref}: ours {len(o)} words, MorphGNT {len(m)}")
            continue
        pairs, gaps = align(o, m)
        for tag, ow, mw in gaps:
            # a word SBL writes as two, marked "+" on its second half, lines up with two MorphGNT words
            ojoin = "".join(strip(w[0]) for w in ow)
            mjoin = "".join(strip(w[0]) for w in mw)
            if ojoin != mjoin:
                problems["words differ"].append(f"{ref}: ours {' '.join(w[0] for w in ow)!r} · MorphGNT {' '.join(w[0] for w in mw)!r}")
        for i, j in pairs:
            words += 1
            w = o[i]
            word, pos, parse, lemma = m[j]
            if plain(w[0]) != plain(word):
                problems["accents differ"].append(f"{ref} {w[0]} · {word}")
            fo, fm = ours_features(w[4]), mgnt_features(pos, parse)
            d = compare(fo, fm)
            if d:
                kinds[kind([x.split(" ")[0] + " " + x.split(" ")[1] for x in d])] += 1
                if len(d) >= 3:
                    problems["three or more features differ (wrong row?)"].append(
                        f"{ref} {w[0]} ours {w[4]} {w[3]} · MorphGNT {pos} {parse} {lemma}: {', '.join(d)}")
                else:
                    problems["_differ"].append((kind(d), f"{ref} {w[0]} ours {w[4]} · MorphGNT {pos} {parse}: {', '.join(d)}"))
            key = w[3].split("+")[0]
            if key in lexicon and "+" not in w[3] and fo.get("pos") not in ("joined",):
                if not lemma_ok(lexicon[key][0], lemma):
                    lemma_diff[(lexicon[key][0], lemma)] += 1
    return words, problems, kinds, lemma_diff


BASELINE_FILE = os.path.join(ROOT, "tools", "fixtures", "greek_tags_baseline.json")
# Why the differences in the baseline are allowed (every instance is listed in the baseline file, so a new one fails)
REASONS = {
    "case V→N": "TAGNT calls a word addressed to someone vocative even when its form is nominative (οἱ ἄνδρες); MorphGNT goes by form",
    "pos poss→pron": "TAGNT tags emphatic ἐμοῦ (\"of me\") as a possessive under ἐγώ; MorphGNT as the personal pronoun",
    "voice mid→pass": "TAGNT's 'deponent' on -θη- aorists and futures (ἀπεκρίθη); MorphGNT calls them passive",
    "tense pres→perf": "οἶδα: present in meaning (TAGNT), perfect in form (MorphGNT)",
    "*": "a form that allows both readings (gender of ὅτου, mood of contracted -ῶσι, πλήρης for any case …), or MorphGNT's slip where the printed form settles it for us (κρεμάμενος, παρακαλέσῃ, βασιλεύουσιν); each looked at on 19 Nov 2026",
    "lemmas": "the dictionaries' headword conventions: Strong's/TBESG list εἶπον, εἴδω, εὐθέως, δεῖ, the possessives under ἐγώ/σύ; MorphGNT follows BDAG (λέγω, ὁράω, εὐθύς, δέω, ἐμός)",
    "verse missing on one side": "MorphGNT leaves out John 7:53-8:11, which SBLGNT prints in double brackets",
}
KNOWN = json.load(open(BASELINE_FILE)) if os.path.exists(BASELINE_FILE) else {"kinds": {}, "lemmas": {}, "problems": {}}


def main():
    if not os.path.isdir(os.path.join(SRC, "morphgnt")):
        print(f"FAIL MorphGNT not found in {SRC}/morphgnt (tools/fetch_sources.sh fetches it)")
        sys.exit(1)
    ours, lexicon = load_ours()
    mgnt = load_mgnt()
    if "--self-test" in sys.argv:
        return self_test(ours, lexicon, mgnt)
    words, problems, kinds, lemma_diff = run(ours, lexicon, mgnt)
    differ = problems.pop("_differ", [])
    by_kind = collections.defaultdict(list)
    for k, line in differ:
        by_kind[k].append(line)
    lem = {f"{a}|{b}": n for (a, b), n in lemma_diff.items()}
    if "--write-baseline" in sys.argv:
        json.dump({"kinds": by_kind, "lemmas": lem, "problems": {k: v for k, v in problems.items() if v}},
                  open(BASELINE_FILE, "w"), ensure_ascii=False, indent=1, sort_keys=True)
        print("Baseline written:", BASELINE_FILE)
        return
    fails = 0
    print(f"{words:,} Greek words lined up with MorphGNT ({sum(len(v) for v in ours.values()):,} ours, "
          f"{sum(len(v) for v in mgnt.values()):,} MorphGNT)")

    def against(title, now, before, reason):
        nonlocal fails
        new = [x for x in now if x not in before]
        gone = [x for x in before if x not in now]
        print(f"  {len(now):6}  {title}" + (f"  — {reason}" if reason and not new else ""))
        for x in new[:30]:
            print("         NEW ", x)
        for x in gone[:10]:
            print("         GONE", x, "(fixed? update the baseline with --write-baseline)")
        fails += len(new) + len(gone)

    print("\nWords and verses:")
    for name in sorted(set(problems) | set(KNOWN["problems"])):
        against(name, problems.get(name, []), KNOWN["problems"].get(name, []), REASONS.get(name))
    print("\nGrammar that differs (each instance approved in the baseline):")
    print("  Most are", REASONS["*"])
    for k in sorted(set(by_kind) | set(KNOWN["kinds"]), key=lambda k: -len(by_kind.get(k, []))):
        against(k, by_kind.get(k, []), KNOWN["kinds"].get(k, []), REASONS.get(k, "judgement call (see REASONS['*'])"))
    print("\nDictionary forms that differ beyond spelling conventions:")
    against(f"{len(lem)} pairs, {sum(lem.values()):,} words", [f"{k} ×{n}" for k, n in lem.items()],
            [f"{k} ×{n}" for k, n in KNOWN["lemmas"].items()], REASONS["lemmas"])
    print(f"\n{fails} problems" if fails else "\n0 problems")
    sys.exit(1 if fails else 0)


def self_test(ours, lexicon, mgnt):
    """Plant one mistake of each kind in a copy of our data and check each is reported."""
    import copy
    base_words, base_p, base_k, base_l = run(ours, lexicon, mgnt)
    base_count = {k: len(v) for k, v in base_p.items()}
    ok = 0
    tests = []

    def plant(desc, ref, idx, fn):
        o = copy.deepcopy({ref: ours[ref]})
        fn(o[ref][idx])
        tests.append((desc, ref, o))

    plant("wrong case", ("JHN", 1, 1), 1, lambda w: w.__setitem__(4, "T-GSM"))
    plant("wrong tense", ("JHN", 1, 1), 2, lambda w: w.__setitem__(4, "V-PAI-3S"))
    plant("wrong row (all features)", ("JHN", 3, 16), 1, lambda w: w.__setitem__(4, "V-FPI-1P"))
    plant("wrong word", ("JHN", 1, 1), 3, lambda w: w.__setitem__(0, "λόγου"))
    plant("wrong accent", ("ROM", 8, 28), 0, lambda w: w.__setitem__(0, w[0].replace("ί", "ι").replace("ἴ", "ἰ") + ""))
    plant("wrong dictionary form", ("MAT", 5, 3), 0, lambda w: w.__setitem__(3, "G4160"))
    for desc, ref, o in tests:
        o2 = dict(ours)
        o2.update(o)
        _, p, k, l = run({ref: o2[ref]}, lexicon, {ref: mgnt[ref]})
        _, p0, k0, l0 = run({ref: ours[ref]}, lexicon, {ref: mgnt[ref]})
        caught = (sum(len(v) for v in p.values()) > sum(len(v) for v in p0.values())) or (sum(l.values()) > sum(l0.values()))
        print(("caught " if caught else "MISSED ") + desc)
        ok += caught
    print(f"{ok}/{len(tests)} passed")
    sys.exit(0 if ok == len(tests) else 1)


if __name__ == "__main__":
    main()
