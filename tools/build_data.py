"""Convert the open source data into the app's data files.

Usage:
    tools/fetch_sources.sh /path/to/sources
    python3 tools/build_data.py /path/to/sources

Writes into data/ (relative to the repo root):
    books.json                      book list, chapters and verse counts
    gnt/<BOOK>.json                 Greek NT (SBL Greek New Testament), word by word, with that book's lexicon subset
    hot/<BOOK>.json                 Hebrew/Aramaic OT (Leningrad), word by word, with lexicon subset
    bsb/<BOOK>.json                 Berean Standard Bible with headings, paragraphs, poetry and notes
    lex/greek-index.json            every Greek lexicon entry: key, lemma, transliteration, gloss, NT count
    lex/hebrew-index.json           the same for Hebrew/Aramaic with OT counts
    lex/G/<nn>.json, lex/H/<nn>.json full lexicon entries, chunked by Strong's number, with every occurrence
                                    and form (added by tools/build_dictionary.py)
    morph/greek.json, morph/hebrew.json   plain-English explanations of every grammar code used
    votd.json                       verses for the Today screen, fully glossed and parsed
    stats.json                      counts used by the checks

Word formats (arrays, trailing empty fields dropped):
    Greek:  [text, translit, english, strong, morph, after, before, cont]
        cont "+" = second half of a word SBL writes as two (Μαράνα θά, Ἄρειος Πάγος): not counted again
        "after" ending in ¶ marks a paragraph break after the word (not shown as a character)
        compound (crasis) words join two keys and codes with "+", e.g. "G2532+G1565", "CONJ+D-NSM"
    Hebrew: [text, translit, english, strongs, morph, after, flag, note]
        text/english/strongs/morph keep the source's "/" between joined parts (prefix/word/suffix)
        strongs marks the main word in {braces}; morph segments after the first omit the H/A prefix
        flag: "q" read as qere (note = ketiv as written), "k" written but not read (ketiv without qere),
              "x" not in the Leningrad Codex (from other manuscripts)
        Hebrew keeps the source's order of vowel and accent marks (it is not Unicode-normalised).
Data: SBL Greek New Testament CC BY 4.0 (Society of Biblical Literature, Logos Bible Software); STEPBible Data
CC BY 4.0 (Tyndale House Cambridge, STEPBible.org); BSB public domain.
"""
import glob, json, os, re, sys, unicodedata
from difflib import SequenceMatcher
from collections import Counter, OrderedDict, defaultdict

SRC = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SOURCES", "")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data")
STEP = os.path.join(SRC, "step")

# USFM id, STEP code, name comes from the BSB index
STEP_CODES = ("Gen Exo Lev Num Deu Jos Jdg Rut 1Sa 2Sa 1Ki 2Ki 1Ch 2Ch Ezr Neh Est Job Psa Pro Ecc Sng Isa Jer Lam "
              "Ezk Dan Hos Jol Amo Oba Jon Mic Nam Hab Zep Hag Zec Mal Mat Mrk Luk Jhn Act Rom 1Co 2Co Gal Eph Php "
              "Col 1Th 2Th 1Ti 2Ti Tit Phm Heb Jas 1Pe 2Pe 1Jn 2Jn 3Jn Jud Rev").split()
USFM = {s: s.upper() for s in STEP_CODES}

# Main reference = NA28 / Leningrad numbering as used by STEPBible. Optional extras:
#   (32.1) Hebrew numbering (TAHOT)   [13.14] English numbering for part of a verse   {14.24} where other editions put it
WORD_RE = re.compile(r"^([1-3]?[A-Za-z]{2,3})\.(\d+)\.(\d+)(?:\((\d+)\.(\d+)\))?(?:\[(?P<en>[^\]]*)\])?(?:\{[^}]*\})?#(?P<word>\d+)=(?P<kind>\S+)\t")


def nfc(s):
    return unicodedata.normalize("NFC", s)


def dump(path, obj):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def trim(arr):
    while arr and arr[-1] in ("", None):
        arr.pop()
    return arr


# ---------------------------------------------------------------- lexicons

def read_lexicon(pattern):
    entries = OrderedDict()
    path = glob.glob(os.path.join(STEP, "Lexicons", pattern))[0]
    for line in open(path, encoding="utf-8-sig"):
        c = line.rstrip("\n").split("\t")
        if len(c) < 7 or not re.match(r"^[GH]\d{4}[A-Za-z]?$", c[0]):
            continue
        key = c[1].split(" ")[0].strip()
        entries[key] = {
            "estrong": c[0], "rel": c[1].split("=", 1)[1].strip() if "=" in c[1] else "",
            "ustrong": c[2].strip(), "lemma": nfc(c[3].strip()) if key[0] == "G" else c[3].strip(),
            "translit": c[4].strip(),
            "morph": c[5].strip(), "gloss": c[6].strip(), "def": c[7].strip() if len(c) > 7 else "",
        }
    return entries


def strongs_hebrew_definitions(hlex):
    """Replace STEPBible's Hebrew definitions (Online Bible's Abridged BDB: not ours to use) with Strong's Hebrew
    dictionary (1890, public domain; Open Scriptures Hebrew Bible Project's edition, CC BY 4.0). Glosses stay
    STEPBible's (written by Tyndale House scholars, CC BY 4.0)."""
    path = os.path.join(SRC, "HebrewLexicon", "HebrewStrong.xml")
    xml = open(path, encoding="utf-8").read()
    ns = lambda t: re.sub(r"<w src=\"H(\d+)\"[^>]*>[^<]*</w>", lambda m: f"H{int(m.group(1)):04d}", t)
    strong = {}
    for m in re.finditer(r'<entry id="H(\d+)">(.*?)</entry>', xml, re.S):
        body = re.sub(r"<note>.*?</note>", "", m.group(2), flags=re.S)  # the editors' notes ("corrected to …")
        part = lambda tag: (re.search(f"<{tag}>(.*?)</{tag}>", body, re.S) or [None, ""])[1]
        meaning = re.sub(r"<def>(.*?)</def>", r"<b>\1</b>", ns(part("meaning")))
        meaning = re.sub(r"</?(?!b>|/b>)[^>]+>", "", meaning)
        source = re.sub(r"<[^>]+>", "", ns(part("source"))).strip().rstrip(";")
        usage = re.sub(r"\(\s*\)\s*", "", re.sub(r"<[^>]+>", "", ns(part("usage")))).strip()  # "( ) arrow": lost signs
        lines = [x for x in (meaning.strip(), source and f"<i>Origin:</i> {source}", usage and f"<i>Translated in the KJV:</i> {usage}") if x]
        tidy_line = lambda x: re.sub(r";\s*,", ",", re.sub(r"\s+([,;.:)])", r"\1", re.sub(r"\s+", " ", x)))
        strong[int(m.group(1))] = " <br /> ".join(tidy_line(x) for x in lines)
    n = 0
    STOPS = {"the", "and", "for", "with", "from", "his", "her", "who", "one", "not", "that", "this", "place"}
    # STEPBible numbers without a lower-case letter (H1980, H5769) split one word into senses or people: Strong's
    # entry is about them all. Numbers with a letter (H6211a "moth", H6211b "grass") are different words sharing a
    # Strong's number: Strong's entry shows only under the one it describes. A few are decided by hand (checked):
    SHOW, HIDE = {"H5178a", "H5387a", "H5608b"}, {"H6211b", "H5178b", "H7189a"}
    stem = lambda w: re.sub(r"(ings?|ed|es|s|ness|ers?|ly|eous|ous)$", "", w) if len(w) > 4 else w
    loose = lambda w: re.sub(r"(.)\1", r"\1", w.replace("ch", "h").replace("j", "y").replace("ts", "z").replace("k", "c").replace("ph", "f"))
    for e in hlex.values():
        num = int(re.sub(r"\D", "", e["estrong"]) or 0)
        d = strong.get(num, "") if num < 9000 else ""
        homonym = bool(re.search(r"[a-z]$", e["estrong"]))
        if d and homonym and e["estrong"] not in SHOW:
            text = re.sub(r"<[^>]+>|[()\[\]]", " ", d).lower()
            tokens = re.findall(r"[a-z]+", text.replace("-", " ")) + re.findall(r"[a-z]+", text.replace("-", ""))  # he-goat: "goat", "hegoat"
            have = {stem(w) for w in tokens} | {loose(w) for w in tokens}
            words = [w for w in re.findall(r"[a-z]+", e["gloss"].lower().replace("-", "")) if len(w) > 1 and w not in STOPS]
            names = [w for w in re.findall(r"[A-Z][a-z]+", e["gloss"]) if len(w) > 3]  # spelt differently: Elioenai / Eljoenai
            close = lambda w: any(SequenceMatcher(None, loose(w.lower()), x).ratio() >= 0.75 for x in have if len(x) > 3)
            if e["estrong"] in HIDE or (words and not any(stem(w) in have or loose(w) in have for w in words)
                                        and not any(close(w) for w in names)):
                d = ""
        e["def"] = d
        n += bool(e["def"])
        # Aramaic words STEPBible marks "in Aramaic of" but codes as Hebrew (אֱלָהּ H0426)
        if "in Aramaic of" in e.get("rel", "") and e["morph"].startswith("H:"):
            e["morph"] = "A:" + e["morph"][2:]
    return n


def lookup(lex, key):
    """Find a lexicon entry for a word's Strong's key, allowing for sub-sense letters."""
    if key in lex:
        return key
    base = re.match(r"^([GH])0*(\d+)", key)
    if not base:
        return None
    num = f"{base.group(1)}{int(base.group(2)):04d}"
    if num in lex:
        return num
    for suffix in "GHIJKLMNOPQRSTUVWXYZABCDEF":
        if num + suffix in lex:
            return num + suffix
    return None


# ---------------------------------------------------------------- morphology

def tidy(text):
    """Calm the source's emphasis capitals and odd punctuation: 'an ACTION OR ACTIVITY' -> 'an action or activity'."""
    text = text.replace("\u201a", ",").replace('"', "").strip()
    return re.sub(r"\b[A-Z]{2,}\b", lambda m: m.group(0).lower(), text)


def tidy_desc(desc):
    """'Verb : Qal (Simple, Active) Perfect ...' -> 'Verb: Qal (simple, active) perfect ...' (keeps stem names)."""
    desc = tidy(desc).replace(" :", ":")
    if not desc:
        return desc
    words = desc.split(" ")
    keep = {"Qal", "Niphal", "Piel", "Pual", "Hiphil", "Hophal", "Hithpael", "Peal", "Peil", "Pael", "Haphel",
            "Aphel", "Hithpeel", "Hithpaal", "Ithpeel", "Ithpaal", "Shaphel", "Polel", "Pilpel", "Hebrew", "Aramaic",
            "Attic", "Greek"}
    out = [words[0]] + [w if w.strip("(),:;") in keep else w.lower() for w in words[1:]]
    return " ".join(out)


def read_morph(pattern, codes_used, lang_prefix_ok=True):
    path = glob.glob(os.path.join(STEP, "Morphology codes", pattern))[0]
    table, block = {}, []

    def flush():
        if not block:
            return
        head = block[0].split("\t")
        code = head[0].strip()
        if code and code in codes_used and code not in table:
            lines = [b.strip().strip('"').strip() for b in block[1:] if b.strip() and b.strip() != "$"]
            desc = lines[0] if lines else head[1] if len(head) > 1 else ""
            expl = lines[1] if len(lines) > 1 else ""
            ex = lines[2] if len(lines) > 2 else ""
            ex = re.sub(r"^Example:\s*", "", ex).replace("_", "").strip(' "')
            table[code] = trim([tidy_desc(desc), tidy(expl), tidy(ex.split('": "')[-1])])
    for line in open(path, encoding="utf-8-sig"):
        line = line.rstrip("\n")
        if line.strip() == "$":
            flush(); block = []
        elif re.match(r"^[A-Z][\w\-]*\t", line) and not block:
            block = [line]
        elif block:
            block.append(line)
    flush()
    return table


# ---------------------------------------------------------------- Greek NT

PUNCT = "··,.;:!?;—–’ʼ[]()⸀-ⸯ"
PUNCT_RE_POST = re.compile(r"([··,.;:!?;—–\]\)⸀-ⸯ¶¬]+)$")  # ¶ = paragraph break after the word; ¬ appears once (Mat 11:17)
PUNCT_RE_PRE = re.compile(r"^([\[\(—–⸀-ⸯ]+)")


def split_punct(text):
    pre = post = ""
    m = PUNCT_RE_PRE.match(text)
    if m:
        pre, text = m.group(1), text[m.end():]
    m = PUNCT_RE_POST.search(text)
    if m:
        post, text = m.group(1), text[:m.start()]
    return text, post, pre


# The Greek text is the SBL Greek New Testament (CC BY 4.0, Society of Biblical Literature and Logos Bible Software):
# its words, spelling, punctuation, paragraphs and verse numbers. TAGNT (STEPBible, CC BY 4.0) supplies the tagging
# for each word (Strong's number, grammar code, transliteration, English in context), matched word by word to the
# rows TAGNT marks as SBL readings. No Nestle-Aland text, punctuation or paragraphing is used.
SBL_DIR = os.path.join(SRC, "sblgnt", "data", "sblgnt", "xml")
SBL_FILES = {"MAT": "Matt", "MRK": "Mark", "LUK": "Luke", "JHN": "John", "ACT": "Acts", "ROM": "Rom", "1CO": "1Cor",
             "2CO": "2Cor", "GAL": "Gal", "EPH": "Eph", "PHP": "Phil", "COL": "Col", "1TH": "1Thess", "2TH": "2Thess",
             "1TI": "1Tim", "2TI": "2Tim", "TIT": "Titus", "PHM": "Phlm", "HEB": "Heb", "JAS": "Jas", "1PE": "1Pet",
             "2PE": "2Pet", "1JN": "1John", "2JN": "2John", "3JN": "3John", "JUD": "Jude", "REV": "Rev"}
APPARATUS = re.compile("[\u2e00-\u2e0f]")  # SBLGNT's apparatus signs ⸀ ⸁ ⸂ ⸃ ⸄ ⸅: notes we don't carry


def greek_match_key(s):
    """Letters only, no accents or breathings, lower case, final sigma folded: for matching words between editions."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower().replace("ς", "σ")
    return re.sub(r"[^α-ω]", "", s)


def read_sblgnt(uid):
    """[(ch, vs, text, before, after)] in reading order; after ends in ¶ before a new paragraph."""
    xml = open(os.path.join(SBL_DIR, SBL_FILES[uid] + ".xml"), encoding="utf-8-sig").read()
    out, ch, vs, pending_pre = [], 0, 0, ""
    for m in re.finditer(r"<p>|<verse-number id=\"[^\"]*? (\d+):(\d+)\">|<prefix>(.*?)</prefix>|<w>(.*?)</w>|<suffix>(.*?)</suffix>", xml, re.S):
        if m.group(0) == "<p>":
            if out and not out[-1][4].endswith("\u00b6"):
                out[-1] = out[-1][:4] + (out[-1][4] + "\u00b6",)
        elif m.group(1):
            ch, vs = int(m.group(1)), int(m.group(2))
        elif m.group(3) is not None:
            pending_pre += APPARATUS.sub("", m.group(3)).strip()
        elif m.group(4) is not None:
            out.append((ch, vs, nfc(m.group(4)), pending_pre, ""))
            pending_pre = ""
        else:
            out[-1] = out[-1][:4] + (APPARATUS.sub("", m.group(5)).strip(),)
    return out


def parse_variants(text):
    """TAGNT's variant column: [(form, translit, gloss, strong, morph, editions)] for every alternative reading."""
    out = []
    for part in re.split(r"[;\u00a6]", text or ""):
        m = re.match(r"\s*(\S+)\s+\((?:[A-Za-z])=([^)]*)\)\s+(.*?)\s+-\s+(G\d+[A-Za-z]?=[^\s+]+(?:\s*\+\s*G\d+[A-Za-z]?=[^\s+]+)*)\s+in:\s*(\S+)", part)
        if m:
            out.append((m.group(1), m.group(2), m.group(3), m.group(4), m.group(5).split("+")))
            continue
        # several words: 'τὰ ἴδια (T=ta idia) <the> own - G3588=T-APN + G2398=A-APN in: Tyn+SBL+…' → one per word
        m = re.match(r"\s*(.+?)\s+\((?:[A-Za-z])=([^)]*)\)\s+(.*?)\s+-\s+(G\d+.*?)\s+in:\s*(\S+)", part)
        if m:
            forms, trs, pairs = m.group(1).split(), m.group(2).split(), [x.strip() for x in m.group(4).split(" + ")]
            if len(forms) == len(pairs):
                for i, (f, pr) in enumerate(zip(forms, pairs)):
                    head = re.sub(r"<[^>]*>", "", m.group(3)).strip() if i == len(forms) - 1 else ""
                    out.append((f, trs[i] if len(trs) == len(forms) else "", head, pr, m.group(5).split("+")))
    return out


# TAGNT verse (Nestle-Aland numbering) -> BSB verse(s), where the BSB departs from the KJV numbering TAGNT records.
# Rev 12:18 "the dragon stood on the shore": KJV 13:1, but the BSB ends 12:17 with it.
BSB_REF_OVERRIDES = {("REV", 12, 18): ["12.17"]}


# Where SBLGNT prints a different word or tense from the reading TAGNT marks as SBL's, the word gets its own
# tagging here (our analysis of the SBL word): (book, ch, verse, SBL form) -> (Strong's, grammar code, English).
SBL_TAGS = {
    ("MRK", 3, 4, "ἀγαθοποιῆσαι"): ("G0015", "V-AAN", "to do good"),
    ("LUK", 8, 29, "παρήγγελλεν"): ("G3853", "V-IAI-3S", "he was commanding"),
    ("LUK", 22, 34, "φωνήσει"): ("G5455", "V-FAI-3S", "will crow"),
    ("JHN", 8, 4, "κατελήφθη"): ("G2638", "V-API-3S", "has been caught"),
    ("ACT", 7, 31, "ἐθαύμασεν"): ("G2296", "V-AAI-3S", "marvelled at"),
    ("ACT", 15, 4, "Ἱεροσόλυμα"): ("G2414", "N-APN-L", "Jerusalem"),
    ("1CO", 2, 4, "πειθοῖ"): ("G3981", "N-DSF", "persuasiveness"),
    ("REV", 18, 3, "πέπτωκαν"): ("G4098", "V-RAI-3P", "have fallen"),
    ("REV", 22, 11, "ῥυπαρευθήτω"): ("G4510", "V-APM-3S", "let him be made filthy"),
    ("MRK", 16, 18, "βλάψῃ"): ("G0984", "V-AAS-3S", "will harm"),
    ("JHN", 8, 3, "καταλήφθεισαν"): ("G2638", "V-APP-ASF", "caught"),
    ("JHN", 8, 7, "πρῶτον"): ("G4412", "ADV", "first"),
    ("JHN", 8, 9, "οὖσα"): ("G1510", "V-PAP-NSF", "being"),
    ("JHN", 8, 11, "κρίνω"): ("G2919", "V-PAI-1S", "judge"),
    ("1CO", 16, 22, "Μαράνα"): ("G3134", "N-NSM-ARAM", "Our Lord"),
    ("1CO", 16, 22, "θά"): ("G3134", "N-NSM-ARAM", "come!", True),  # True: second half of one word (counted once)
}

GREEK_LATIN = {"α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "ē", "θ": "th", "ι": "i", "κ": "k",
               "λ": "l", "μ": "m", "ν": "n", "ξ": "x", "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t",
               "υ": "u", "φ": "ph", "χ": "ch", "ψ": "ps", "ω": "ō"}


def greek_translit(word):
    """A transliteration in TAGNT's style (Archē, hōmologēsen), for the few SBL spellings TAGNT doesn't have."""
    d = unicodedata.normalize("NFD", word)
    out, cap = [], False
    letters = [ch for ch in d]
    rough = "\u0314" in d
    for i, ch in enumerate(letters):
        low = ch.lower()
        if low in GREEK_LATIN:
            if not out and ch != low:
                cap = True
            nxt = next((x.lower() for x in letters[i + 1:] if not unicodedata.combining(x)), "")
            t = GREEK_LATIN[low]
            if low == "γ" and nxt in "γκξχ":
                t = "n"
            if low == "ρ" and not out and rough:
                t, rough = "rh", False
            out.append(t)
        elif ch in "\u1fbd\u2019\u02bc\u1fbf'":
            out.append("\u1fbd")
    s = "".join(out)
    if rough and s:
        s = "h" + s
    return s[:1].upper() + s[1:] if cap else s


SPELLING_LOG = []  # (ref, SBL form, TAGNT form, strong, morph) where the spelling differs: reviewed by hand


def build_greek(glex):
    from difflib import SequenceMatcher
    stats = Counter()
    counts = Counter()
    fallback = {}
    # 1. TAGNT tagging, chapter by chapter: rows marked as SBL readings first, then every other reading as a reserve
    tag = defaultdict(list)       # (uid, ch) -> [record] that SBL reads, in TAGNT order
    rows = defaultdict(list)      # (uid, ch) -> [(record, SBL reads it, an alternative reading)]
    sbl_verses = set()
    reserve = defaultdict(list)   # (uid, ch, vs) -> [record] any reading at all
    for path in sorted(glob.glob(os.path.join(STEP, "Translators Amalgamated OT+NT", "TAGNT*.txt")),
                       key=lambda p: 0 if "Mat-Jhn" in p else 1):
        for line in open(path, encoding="utf-8-sig"):
            m = WORD_RE.match(line)
            if not m:
                continue
            c = line.rstrip("\n").split("\t")
            uid, ch, vs = USFM[m.group(1)], int(m.group(2)), int(m.group(3))
            en = m.group("en") or f"{ch}.{vs}"
            m2 = re.match(r"^(.*?)\s+\(([^)]*)\)\s*$", c[1])
            form, translit = (m2.group(1), m2.group(2)) if m2 else (c[1], "")
            pairs = [(p.split("=", 1) + [""])[:2] for p in c[3].split(" + ")]
            rec = {"form": nfc(split_punct(form.strip())[0]), "tr": translit, "en": c[2].strip(),
                   "strong": "+".join(k.strip() for k, _ in pairs), "morph": "+".join(x.strip() for _, x in pairs),
                   "vs": vs, "enref": en}
            for part in c[4].split(" + "):  # a lemma the brief lexicon lacks
                if "=" in part and rec["strong"] and not lookup(glex, rec["strong"].split("+")[0]):
                    lem, gl = part.split("=", 1)
                    fallback.setdefault(rec["strong"].split("+")[0], [nfc(lem.strip()), "", gl.strip()])
            is_sbl = any(e.startswith("SBL") for e in c[5].split("+"))
            rows[(uid, ch)].append((rec, is_sbl, False))
            if is_sbl:
                sbl_verses.add((uid, ch, vs))
            reserve[(uid, ch, vs)].append(rec)
            for form2, tr2, gl2, pairs2, eds in parse_variants(c[6]):
                pp = [x.strip().split("=", 1) for x in pairs2.split("+")]
                alt = dict(rec, form=nfc(split_punct(form2)[0]), tr=tr2, en=gl2,
                           strong="+".join(k for k, _ in pp), morph="+".join(v for _, v in pp))
                alt_sbl = any(e.startswith("SBL") for e in eds)
                rows[(uid, ch)].append((alt, alt_sbl, True))
                if alt_sbl:
                    sbl_verses.add((uid, ch, vs))
                reserve[(uid, ch, vs)].append(alt)
    # TAGNT marks no SBL reading in a few passages SBL prints in ⟦ ⟧ (Mark 16:9-20, John 7:53-8:11): use its main text there
    for (uid, ch), rs in rows.items():
        tag[(uid, ch)] = [r for r, is_sbl, is_alt in rs if is_sbl or ((uid, ch, r["vs"]) not in sbl_verses and not is_alt)]
    for r in [r for rs in list(tag.values()) + list(reserve.values()) for r in rs]:
        r["key"] = greek_match_key(r["form"])

    # 2. The SBLGNT text, each word given its TAGNT record
    books = OrderedDict()
    en_refs = {}
    unmatched = []
    for uid in SBL_FILES:
        words = read_sblgnt(uid)
        by_ch = OrderedDict()
        for w in words:
            by_ch.setdefault(w[0], []).append(w)
        for ch, ws in by_ch.items():
            cands = tag.get((uid, ch), [])
            a = [greek_match_key(w[2]) for w in ws]
            b = [r["key"] for r in cands]
            match = {}
            used = set()
            for op, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
                if op == "equal":
                    for k in range(i2 - i1):
                        match[i1 + k] = j1 + k
                        used.add(j1 + k)
            # words SBL orders differently: the same word, unused, in the same verse
            for i, w in enumerate(ws):
                if i in match:
                    continue
                pick = next((j for j, r in enumerate(cands) if j not in used and r["vs"] == w[1] and b[j] == a[i]), None)
                if pick is not None:
                    match[i] = pick
                    used.add(pick)
                    stats["matched_out_of_order"] += 1
            # the editions divide a few words differently: SBL μήγε = μή + γε; SBL καὶ ἐγώ = κἀγώ; Μαράνα θά
            for i, w in enumerate(ws):
                if i in match:
                    continue
                pool = [j for j, r in enumerate(cands) if j not in used and r["vs"] == w[1]]
                two = next(((j, k) for j in pool for k in pool if k == j + 1 and b[j] + b[k] == a[i]), None)
                if two:
                    r1, r2 = cands[two[0]], cands[two[1]]
                    match[i] = dict(r1, form=w[2], key=a[i], tr=r1["tr"] + r2["tr"], en=(r1["en"] + " " + r2["en"]).strip(),
                                    strong=r1["strong"] + "+" + r2["strong"], morph=r1["morph"] + "+" + r2["morph"])
                    used.update(two)
                    stats["joined_from_two_records"] += 1
                    continue
                if i + 1 < len(ws) and i + 1 not in match:
                    both = a[i] + a[i + 1]
                    # one record that matches the two words together far better than either alone
                    fits = lambda k: (SequenceMatcher(None, both, k).ratio() >= 0.8 and len(k) >= len(both) - 2
                                      and max(SequenceMatcher(None, a[i], k).ratio(), SequenceMatcher(None, a[i + 1], k).ratio()) < 0.75)
                    one = next((j for j in pool if fits(b[j])), None)
                    r = cands[one] if one is not None else next(
                        (x for x in reserve.get((uid, ch, w[1]), []) if fits(x["key"])), None)
                    if r is not None:
                        ks, ms = r["strong"].split("+"), r["morph"].split("+")
                        if len(ks) == 2:  # κἀγώ = ἐγώ + καί: give each word the part whose dictionary form it resembles
                            lem = [greek_match_key((glex.get(lookup(glex, k) or "", {}) or {}).get("lemma", "")) for k in ks]
                            first = 0 if SequenceMatcher(None, a[i], lem[0]).ratio() >= SequenceMatcher(None, a[i], lem[1]).ratio() else 1
                            parts = [(ks[first], ms[first]), (ks[1 - first], ms[1 - first])]
                        else:
                            parts = [(r["strong"], r["morph"])] * 2
                        if len(ks) == 2:
                            match[i] = dict(r, form=ws[i][2], key=a[i], tr="", en="", strong=parts[0][0], morph=parts[0][1])
                            match[i + 1] = dict(r, form=ws[i + 1][2], key=a[i + 1], tr="", en="", strong=parts[1][0], morph=parts[1][1])
                        else:  # Ἄρειος Πάγος: one word in TAGNT, two in SBL; the English and the count go with the first
                            match[i] = dict(r, form=ws[i][2], key=a[i], tr="")
                            match[i + 1] = dict(r, form=ws[i + 1][2], key=a[i + 1], tr="", en="(with the word before)", cont=True)
                        if one is not None:
                            used.add(one)
                        stats["split_from_one_record"] += 2
            # spelt a little differently (movable ν, ἀλλά / ἀλλ᾽): same verse, nearest unused record
            for i, w in enumerate(ws):
                if i in match:
                    continue
                pool = [j for j, r in enumerate(cands) if j not in used and r["vs"] == w[1]]
                pick = next((j for j in pool if b[j] == a[i]), None)
                if pick is None:
                    near = [(SequenceMatcher(None, a[i], b[j]).ratio(), j) for j in pool]
                    near = [x for x in near if x[0] >= 0.75]
                    pick = max(near)[1] if near else None
                if pick is not None:
                    match[i] = pick
                    used.add(pick)
                    stats["matched_by_spelling"] += 1
            # one word left between two matched neighbours, one record left between theirs: the same word, spelt
            # differently (SBL μετά / μεθ᾽, εἰπόν / εἰπέ)
            for i, w in enumerate(ws):
                if i in match or not isinstance(match.get(i - 1), int) or not isinstance(match.get(i + 1), int):
                    continue
                gap = [j for j in range(match[i - 1] + 1, match[i + 1]) if j not in used]
                if len(gap) == 1 and cands[gap[0]]["vs"] == w[1]:
                    match[i] = gap[0]
                    used.add(gap[0])
                    stats["matched_by_position"] += 1
            for i, w in enumerate(ws):
                _, vs, text, pre, post = w
                if i in match:
                    r = match[i] if isinstance(match[i], dict) else cands[match[i]]
                else:
                    pool = reserve.get((uid, ch, vs), [])
                    r = next((x for x in pool if x["key"] == a[i]), None)
                    if r is None:
                        near = sorted(((SequenceMatcher(None, a[i], x["key"]).ratio(), k) for k, x in enumerate(pool)), reverse=True)
                        r = pool[near[0][1]] if near and near[0][0] >= 0.75 else None
                    if r is None:
                        if (uid, ch, vs, text) not in SBL_TAGS:
                            unmatched.append(f"{uid} {ch}:{vs} {text}")
                        r = {"tr": "", "en": "", "strong": "", "morph": "", "enref": f"{ch}.{vs}", "key": a[i], "form": ""}
                    else:
                        stats["matched_from_other_readings"] += 1
                if (uid, ch, vs, text) in SBL_TAGS:
                    st, mo, gl = SBL_TAGS[(uid, ch, vs, text)][:3]
                    r = dict(r, strong=st, morph=mo, en=gl, form=text, key=a[i], tr="", cont=len(SBL_TAGS[(uid, ch, vs, text)]) > 3)
                    stats["tagged_here"] += 1
                if r["key"] != a[i]:
                    stats["spelling_differs_from_tagnt"] += 1
                    SPELLING_LOG.append((f"{uid} {ch}:{vs}", text, r["form"], r["strong"], r["morph"]))
                tr = r["tr"] if r["key"] == a[i] and r["tr"] else greek_translit(text)
                if re.search("[ηω][\u0300-\u036f]*\u0345", unicodedata.normalize("NFD", text)) and re.search("[ēō]a$", tr):
                    tr = tr[:-1]  # TAGNT writes τῇ as "tēa": the iota under η/ω isn't sounded
                first = next((x for x in text if x.isalpha()), "")
                if tr and first:  # capitals as in the SBL text (SBL capitalises quotations, TAGNT doesn't)
                    tr = (tr[0].upper() if first.isupper() else tr[0].lower()) + tr[1:]
                if not r["en"].strip() and r["strong"] and not r.get("cont"):  # half of a split word: its own short gloss
                    gl = (glex.get(lookup(glex, r["strong"].split("+")[0]) or "", {}) or {}).get("gloss", "")
                    r = dict(r, en=re.split(r"[/,;]", gl.split(": ")[-1])[0].strip())
                    stats["english_from_dictionary"] += 1
                item = trim([text, tr, r["en"], r["strong"], r["morph"], post, pre, "+" if r.get("cont") else ""])
                books.setdefault(uid, OrderedDict()).setdefault(ch, OrderedDict()).setdefault(vs, []).append(item)
                refs = en_refs.setdefault((uid, ch, vs), [])
                if r["enref"] not in refs:
                    refs.append(r["enref"])
                stats["words"] += 1
                prev = books[uid][ch][vs][-2] if len(books[uid][ch][vs]) > 1 else None
                same_name = (prev is not None and "+" not in r["strong"] and prev[3:4] == [r["strong"]]
                             and prev[4:5] == [r["morph"]] and greek_match_key(prev[0]) != a[i]
                             and r["morph"].endswith(("-P", "-L", "-T")))
                for k in ([] if r.get("cont") or same_name else r["strong"].split("+")):
                    if k:
                        counts[lookup(glex, k) or k] += 1
    stats["unmatched"] = len(unmatched)
    stats["fallback_lexicon_entries"] = len(fallback)
    if unmatched:
        print("Greek words with no TAGNT tagging:", len(unmatched), "; ".join(unmatched[:40]))
    en_refs.update(BSB_REF_OVERRIDES)
    en_refs = {k: v for k, v in en_refs.items() if v != [f"{k[1]}.{k[2]}"]}
    stats["verses_with_english_numbering"] = len(en_refs)
    return books, stats, counts, fallback, en_refs


# ---------------------------------------------------------------- Hebrew OT

def build_hebrew(hlex):
    books = OrderedDict()
    stats = Counter()
    counts = Counter()
    heb_refs = {}
    order = ["Gen-Deu", "Jos-Est", "Job-Sng", "Isa-Mal"]
    files = sorted(glob.glob(os.path.join(STEP, "Translators Amalgamated OT+NT", "TAHOT*.txt")),
                   key=lambda p: next(i for i, o in enumerate(order) if o in p))
    for path in files:
        for line in open(path, encoding="utf-8-sig"):
            m = WORD_RE.match(line)
            if not m:
                continue
            c = line.rstrip("\n").split("\t")
            book, ch, vs = m.group(1), int(m.group(2)), int(m.group(3))
            kind = m.group("kind")
            stats["records"] += 1
            # "\\" separates punctuation (maqaf ־, sof pasuq ׃, paragraph marks פ ס);
            # a part holding letters is the rest of a hyphenated word, e.g. כְּדָרְ\\־לָעֹ֔מֶר
            parts = c[1].split("\\")
            text = parts[0]
            tail = []
            for part in parts[1:]:
                if len(re.findall(r"[\u05d0-\u05ea]", part)) >= 2 and not tail:
                    text += part
                else:
                    tail.append(part)
            # Hebrew is NOT normalised: NFC reorders vowel/dagesh marks in ~47% of words (OSHB advises against it)
            after = re.sub(r"\s+", " ", "".join(tail)).strip()
            strongs = c[4].strip()
            morph = c[5].strip()
            flag = note = ""
            if kind.startswith("Q") and not text.strip():
                # written in the Leningrad Codex but not read aloud: K= ki (כִּי) "for" (H3588A=HR)
                km = re.search(r'K=\s*(\S+)\s+\(([^)]*)\)\s+"([^"]*)"\s+\(([^=]+)=([^)]+)\)', c[6])
                if km:
                    tr, form, gloss, strong, mcode = km.groups()
                    w = trim([form.split("\\")[0], tr, f"({gloss}: written, not read)", "{" + strong + "}", mcode,
                              after, "k"])
                    uid = USFM[book]
                    books.setdefault(uid, OrderedDict()).setdefault(ch, OrderedDict()).setdefault(vs, []).append(w)
                    stats["written_not_read"] += 1
                    stats["words"] += 1
                    counts[lookup(hlex, strong) or strong] += 1
                    continue
                stats["empty_word_skipped"] += 1
                continue
            if kind.startswith("Q"):
                flag = "q"
                # ketiv (as written): "K= translit (כְּתִיב) ..." in meaning variants, or "K= כְּתִיב" in spelling variants
                km = re.search(r"K=\s*[^()¦;]*?\(([^)]*)\)", c[6]) or re.search(r"K=\s*([^\s¦;]+)", c[7])
                note = km.group(1).split("\\")[0].replace("/", "").strip() if km else ""
                if not note:
                    stats["qere_without_ketiv"] += 1
                stats["qere"] += 1
            elif kind == "X":  # words from other manuscripts (e.g. Gen 4:8 "Let us go out to the field")
                flag = "x"
                stats["not_leningrad"] += 1
            w = trim([text, c[2].strip(), c[3].strip(), strongs, morph, after, flag, note])
            uid = USFM[book]
            books.setdefault(uid, OrderedDict()).setdefault(ch, OrderedDict()).setdefault(vs, []).append(w)
            if m.group(4):
                heb_refs[(uid, ch, vs)] = f"{m.group(4)}.{m.group(5)}"
            stats["words"] += 1
            if morph[:1] == "A":
                stats["aramaic_words"] += 1
            mains = re.findall(r"\{([^}]+)\}", strongs)
            for k in mains or [strongs]:
                counts[lookup(hlex, k) or k] += 1
    return books, stats, counts, heb_refs


# ---------------------------------------------------------------- output helpers

def lex_subset(keys, lex, fallback=None):
    sub = {}
    for k in sorted(keys):
        hit = lookup(lex, k)
        if hit:
            e = lex[hit]
            sub[k] = [e["lemma"], e["translit"], e["gloss"]]
        elif fallback and k in fallback:
            sub[k] = fallback[k]
    return sub


def greek_keys(book):
    return {k for ch in book.values() for v in ch.values() for w in v if len(w) > 3 for k in w[3].split("+") if k}


def hebrew_keys(book):
    keys = set()
    for ch in book.values():
        for v in ch.values():
            for w in v:
                if len(w) > 3:
                    keys.update(k.strip("{} +") for k in re.split(r"[/\\]", w[3]) if k.strip("{} +"))
    return keys


def chapters_out(book, heb_refs=None, uid=None, en_refs=None):
    """[[chapter, [[verse, words, ref?], ...]], ...]
    Hebrew: ref = "c.v" in Hebrew numbering when it differs from the English numbering used for the verse.
    Greek:  ref = ["c.v", ...] English (BSB) verses this NA28 verse's words belong to, when not just its own number."""
    out = []
    for ch, verses in book.items():
        vs_out = []
        for vs, words in verses.items():
            item = [vs, words]
            if heb_refs and (uid, ch, vs) in heb_refs:
                item.append(heb_refs[(uid, ch, vs)])
            if en_refs and (uid, ch, vs) in en_refs:
                item.append(en_refs[(uid, ch, vs)])
            vs_out.append(item)
        out.append([ch, vs_out])
    return out


# ---------------------------------------------------------------- BSB

USFM_KIND = {"m": "p", "p": "p", "pmo": "pi", "li1": "li", "li2": "li2", "s1": "s", "s2": "s", "ms1": "s", "mr": "r",
             "r": "r", "b": "b", "q1": "q1", "q2": "q2", "qr": "qr", "d": "d", "qa": "qa", "pc": "pc"}
# Slips in the official file, put right (each checked against the BSB's printed wording and the chapter's sense)
BSB_FIXES = [("PSA", "A Psalms of David, when he fled", "A Psalm of David, when he fled"),
             ("1CH", "David’s Psalms of Thanksgiving", "David’s Psalm of Thanksgiving")]
BSB_NAMES = {"SNG": "Song of Songs"}  # the file's short title is "Song"
USFM_SKIP = {"id", "h", "toc1", "toc2", "toc3", "mt1", "mt2", "ide", "rem"}


def usfm_inline(text, notes):
    """One line's text: word markup removed, footnotes replaced by \u0001n\u0001 (n = index into the chapter's notes)."""
    def note(m):
        body = re.sub(r"\\fr [^\\]*", "", m.group(1))
        body = re.sub(r"\\f[a-z]+\*?\s?", "", body).strip()
        notes.append(re.sub(r"\s+", " ", body))
        return f"\u0001{len(notes) - 1}\u0001"
    text = re.sub(r"\\f \+ (.*?)\\f\*", note, text)
    text = re.sub(r"\\\+?w ([^|\\]*)(\|[^\\]*)?\\\+?w\*", r"\1", text)
    text = re.sub(r"\\\+?(it|bk|add|nd|sc|em|bd|wj)\*? ?", "", text)
    if "\\" in text:
        raise ValueError(f"BSB: markup left in {text[:80]!r}")
    return text


def usfm_book(path):
    """A USFM book → chapters [[blocks, notes]] in the app's format: blocks [kind, items], items = verse numbers and text."""
    chapters, blocks, notes = [], None, None
    cur = None
    for raw in open(path, encoding="utf-8-sig"):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"\\(\w+)\s?(.*)$", line)
        if not m:
            raise ValueError(f"BSB: unexpected line {line[:60]!r} in {path}")
        mk, rest = m.group(1), m.group(2)
        if mk in USFM_SKIP:
            continue
        if mk == "c":
            blocks, notes = [], []
            chapters.append([blocks, notes])
            cur = None
            continue
        if mk == "v":  # a verse line inside the current paragraph
            if cur is None:
                cur = ["p", []]
                blocks.append(cur)
            rest = line
        elif mk in USFM_KIND:
            cur = [USFM_KIND[mk], []]
            blocks.append(cur)
        else:
            raise ValueError(f"BSB: unknown marker \\{mk} in {path}")
        parts = re.split(r"\\v (\S+) ?", rest)
        if parts[0].strip():
            cur[1].append(parts[0])
        for i in range(1, len(parts), 2):
            v = parts[i]
            cur[1].append(int(v) if v.isdigit() else v)
            if parts[i + 1].strip():
                cur[1].append(parts[i + 1])
        cur[1] = [usfm_inline(x, notes) if isinstance(x, str) else x for x in cur[1]]
        cur[1] = [re.sub(r"\s+(\u0001\d+\u0001)", r"\1", re.sub(r"\s+", " ", x)).strip() if isinstance(x, str) else x
                  for x in cur[1]]
        # a note that ends straight before the next word (JDG 16:14 "web.\\f*\\w Then") still needs the space
        cur[1] = [re.sub(r"(\u0001\d+\u0001)(?=[A-Za-z“‘(])", r"\1 ", x) if isinstance(x, str) else x for x in cur[1]]
        cur[1] = [x for x in cur[1] if x != ""]
        # a heading line that is only a bracketed reference is a cross-reference (HEB 11 "(Joshua–Malachi)")
        if mk in ("s1", "s2") and re.fullmatch(r"\(.*\)", cur[1][0] if cur[1] and isinstance(cur[1][0], str) else ""):
            cur[0] = "r"
        if mk in ("b", "s1", "s2", "ms1", "mr", "r", "d", "qa"):
            cur = None  # a verse line after a heading or blank line starts a paragraph of its own
    # blocks that hold nothing (\b, an empty \m before its verse line) are kept only as the "b" marker the Reader skips
    for blocks, _ in chapters:
        blocks[:] = [b for b in blocks if b[1] or b[0] == "b"]
    return chapters


def build_bsb():
    """The Berean Standard Bible (public domain) from eBible.org's official USFM files (engbsb_usfm.zip)."""
    folder = os.path.join(SRC, "bsb", "usfm")
    files = sorted(f for f in os.listdir(folder) if re.match(r"\d\d-\w{3}engbsb\.usfm$", f))
    out, verse_sets, index = {}, {}, []
    for f in files:
        uid, testament = f[3:6], ("NT" if int(f[:2]) >= 70 else "OT")
        name = re.search(r"^\\h (.+?)\s*$", open(os.path.join(folder, f), encoding="utf-8-sig").read(), re.M).group(1)
        name = BSB_NAMES.get(uid, name)
        chapters = usfm_book(os.path.join(folder, f))
        if uid == "PSA":  # Psalm 119's stanza names, with the Hebrew letter each stanza's lines begin with
            stanzas = [blk for blk in chapters[118][0] if blk[0] == "qa"]
            if len(stanzas) != 22:
                raise ValueError(f"Psalm 119: {len(stanzas)} stanza headings, expected 22")
            for letter, blk in zip("אבגדהוזחטיכלמנסעפצקרשת", stanzas):
                blk[1] = [f"{letter} {blk[1][0]}"]
        for book, wrong, right in BSB_FIXES:
            if book == uid:
                hits = 0
                for blocks, _ in chapters:
                    for blk in blocks:
                        for i, x in enumerate(blk[1]):
                            if isinstance(x, str) and wrong in x:
                                blk[1][i] = x.replace(wrong, right)
                                hits += 1
                if hits != 1:
                    raise ValueError(f"BSB fix {wrong!r} found {hits} times in {uid}")
        vset = set()
        for ci, (blocks, _) in enumerate(chapters, start=1):
            for _, items in blocks:
                vset.update((ci, x) for x in items if not isinstance(x, str))
        out[uid] = {"name": name, "t": testament, "chapters": [trim(c) for c in chapters]}
        verse_sets[uid] = vset
        index.append({"a": uid, "n": name, "t": testament, "c": len(chapters)})
    return index, out, verse_sets


# ---------------------------------------------------------------- verse of the day

VOTD = {
    "grc": [("JHN", 1, 1, "G3056"), ("JHN", 3, 16, "G0025"), ("JHN", 14, 6, "G3598"), ("ROM", 5, 8, "G0026"),
            ("ROM", 8, 28, "G0018"), ("EPH", 2, 8, "G5485"), ("PHP", 4, 13, "G2480"), ("HEB", 11, 1, "G4102"),
            ("1JN", 4, 8, "G0026"), ("MAT", 5, 3, "G3107"), ("MRK", 1, 15, "G3340"), ("GAL", 2, 20, "G5547")],
    "he": [("GEN", 1, 1, "H0430"), ("DEU", 6, 4, "H8085"), ("PSA", 23, 1, "H7462"), ("PSA", 119, 105, "H5216"),
           ("PRO", 3, 5, "H0982"), ("ISA", 40, 8, "H1697"), ("MIC", 6, 8, "H2617"), ("NUM", 6, 24, "H1288"),
           ("JOS", 1, 9, "H2388"), ("PSA", 46, 10, "H3045"), ("ISA", 53, 5, "H7495"), ("LAM", 3, 23, "H0530")],
}


def bsb_verse_text(bsb_book, ch, vs):
    out, on = [], False
    for kind, items in bsb_book["chapters"][ch - 1][0]:
        if kind in ("s", "r", "b", "qa"):
            continue  # section headings, cross-references and blank lines belong to no verse
        for x in items:
            if isinstance(x, int):
                on = (x == vs)
            elif on and isinstance(x, str):
                out.append(re.sub(r"\u0001\d+\u0001", "", x).strip())
    return re.sub(r"\s+", " ", " ".join(out)).strip()


def short_parse(code, table):
    e = table.get(code)
    return e[0] if e else code


def build_votd(gnt, hot, bsb, glex, hlex, gmorph, hmorph, books_meta):
    names = {b["id"]: b["name"] for b in books_meta}
    out = []
    for lang in ("grc", "he"):
        for uid, ch, vs, focus in VOTD[lang]:
            words = (gnt if lang == "grc" else hot)[uid][ch][vs]
            items, focus_i = [], 0
            for i, w in enumerate(words):
                w = w + [""] * (8 - len(w))
                if lang == "grc":
                    keys, codes = w[3].split("+"), w[4].split("+")
                    main = keys[0]
                    lex = glex.get(lookup(glex, main) or "", {})
                    parse = " + ".join(short_parse(c, gmorph) for c in codes)
                    item = {"t": w[0], "p": re.sub("[\u00b6\u00ac]", "", w[5]), "pre": w[6]}
                else:
                    segs = w[4].split("/")
                    lang_letter = segs[0][:1]
                    codes = [segs[0]] + [lang_letter + x for x in segs[1:]]
                    keys = [k for k in re.split(r"[/\\]", w[3]) if k.strip("{} +")]
                    mains = re.findall(r"\{([^}]+)\}", w[3])
                    main = mains[0] if mains else keys[0].strip("{}")
                    lex = hlex.get(lookup(hlex, main) or "", {})
                    parts = []
                    for k, c in zip(keys, codes):
                        k = k.strip("{} ")
                        d = short_parse(c, hmorph)
                        if k != main:
                            e = hlex.get(lookup(hlex, k) or "", {})
                            form = e.get("lemma", "").replace("/", "")
                            d = f"{d} {form} \u201c{e.get('gloss', '').split(': ')[-1]}\u201d".strip()
                        parts.append(d)
                    parse = " + ".join(parts)
                    # drop the paragraph letters פ ס; keep maqaf, sof pasuq, paseq (see js/hebrew.js heAfter)
                    after = re.sub(r"(^|\s)[\u05e4\u05e1](?=\s|$)", "", w[5]).strip()
                    after = re.sub(r"\s+(?![\u05c0\u05c6])", "", re.sub(r"\s*([\u05c0\u05c6])", r" \1", after))
                    item = {"t": w[0].replace("/", ""), "p": after}
                gloss = (lex.get("gloss", "") or w[2]).split(": ")[-1]
                item.update({"lemma": lex.get("lemma", ""), "gloss": gloss,
                             "parse": parse, "en": w[2],
                             "k": lookup(glex if lang == "grc" else hlex, main) or ""})  # dictionary entry
                if lang == "grc" and len(keys) > 1:  # a word joined from two (κἀγώ, οὐκέτι): every part
                    item["parts"] = [[glex.get(lookup(glex, k) or "", {}).get("lemma", ""),
                                      (glex.get(lookup(glex, k) or "", {}).get("gloss", "")).split(": ")[-1],
                                      lookup(glex, k) or ""] for k in keys]
                if any(k.strip("{}").startswith(focus) for k in keys) and not focus_i:
                    focus_i = i
                items.append({k: v for k, v in item.items() if v})
            name = "Psalm" if uid == "PSA" else names[uid]
            out.append({"id": f"{uid}-{ch}-{vs}", "lang": lang, "ref": f"{name} {ch}:{vs}",
                        "english": bsb_verse_text(bsb[uid], ch, vs), "words": items, "focus": focus_i})
    return out


# ---------------------------------------------------------------- main

def main():
    if not os.path.isdir(STEP):
        sys.exit("Give the sources folder made by tools/fetch_sources.sh")
    glex = read_lexicon("TBESG*.txt")
    hlex = read_lexicon("TBESH*.txt")
    print("Hebrew definitions from Strong's:", strongs_hebrew_definitions(hlex), "of", len(hlex))
    gnt, gstats, gcounts, gfallback, gen_refs = build_greek(glex)
    hot, hstats, hcounts, heb_refs = build_hebrew(hlex)
    index, bsb, bsb_verses = build_bsb()

    # grammar codes actually used
    gcodes = {m for b in gnt.values() for ch in b.values() for v in ch.values() for w in v if len(w) > 4
              for m in w[4].split("+")}
    hcodes = set()
    for b in hot.values():
        for ch in b.values():
            for v in ch.values():
                for w in v:
                    if len(w) > 4 and w[4]:
                        segs = w[4].split("/")
                        lang = segs[0][:1]
                        hcodes.add(segs[0])
                        hcodes.update(lang + s for s in segs[1:] if s)
    gmorph = read_morph("TEGMC*.txt", gcodes)
    hmorph = read_morph("TEHMC*.txt", hcodes)

    # write
    for d in ("gnt", "hot", "bsb", "lex", "morph"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    books = []
    for i, entry in enumerate(index):
        uid = entry["a"]
        step = next(s for s, u in USFM.items() if u == uid)
        src = gnt if uid in gnt else hot
        lang = "grc" if uid in gnt else "he"
        chapters = [len([v for (c, v) in bsb_verses[uid] if c == ch]) for ch in range(1, entry["c"] + 1)]
        books.append({"id": uid, "step": step, "name": entry["n"], "t": entry["t"], "lang": lang,
                      "ch": entry["c"], "v": chapters})
        if lang == "grc":
            dump(f"gnt/{uid}.json", {"id": uid, "lex": lex_subset(greek_keys(src[uid]), glex, gfallback),
                                     "ch": chapters_out(src[uid], en_refs=gen_refs, uid=uid)})
        else:
            dump(f"hot/{uid}.json", {"id": uid, "lex": lex_subset(hebrew_keys(src[uid]), hlex),
                                     "ch": chapters_out(src[uid], heb_refs, uid)})
        dump(f"bsb/{uid}.json", {"id": uid, **bsb[uid]})
    dump("books.json", books)
    dump("votd.json", build_votd(gnt, hot, bsb, glex, hlex, gmorph, hmorph, books))

    for name, lex, counts, letter in (("greek", glex, gcounts, "G"), ("hebrew", hlex, hcounts, "H")):
        dump(f"lex/{name}-index.json",
             [trim([k, e["lemma"], e["translit"], e["gloss"], counts.get(k, 0)]) for k, e in lex.items()])
        chunks = defaultdict(dict)
        for k, e in lex.items():
            chunks[k[1:3]][k] = trim([e["lemma"], e["translit"], e["morph"], e["gloss"], e["def"], e["rel"]])
        for nn, entries in chunks.items():
            dump(f"lex/{letter}/{nn}.json", entries)
    dump("morph/greek.json", gmorph)
    dump("morph/hebrew.json", hmorph)

    stats = {
        "greek": {**gstats, "books": len(gnt), "verses": sum(len(ch) for b in gnt.values() for ch in b.values()),
                  "codes_used": len(gcodes), "codes_explained": len(gmorph)},
        "hebrew": {**hstats, "books": len(hot), "verses": sum(len(ch) for b in hot.values() for ch in b.values()),
                   "verses_with_hebrew_numbering": len(heb_refs),
                   "codes_used": len(hcodes), "codes_explained": len(hmorph)},
        "bsb": {"books": len(bsb), "verses": sum(len(v) for v in bsb_verses.values())},
        "lexicon": {"greek_entries": len(glex), "hebrew_entries": len(hlex)},
    }
    dump("stats.json", stats)
    print(json.dumps(stats, indent=1))

    # Session 5: every occurrence and form for each dictionary entry (rewrites data/lex/G|H chunks)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import build_dictionary
    build_dictionary.build()
    import build_decks
    build_decks.main()

    # Session 6: the Septuagint (Swete), lined up with the Hebrew/English verse numbers
    if os.path.isdir(os.path.join(SRC, "lxx-swete")):
        import build_lxx
        build_lxx.build(SRC)

    # Session 12: the list of data files for Settings › "Save it all for offline use"
    import list_data
    list_data.main()


if __name__ == "__main__":
    main()
