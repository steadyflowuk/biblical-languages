"""Convert the open source data into the app's data files.

Usage:
    tools/fetch_sources.sh /path/to/sources
    python3 tools/build_data.py /path/to/sources

Writes into data/ (relative to the repo root):
    books.json                      book list, chapters and verse counts
    gnt/<BOOK>.json                 Greek NT (NA28 text), word by word, with that book's lexicon subset
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
    Greek:  [text, translit, english, strong, morph, after, before]
        "after" ending in ¶ marks a paragraph break after the word (not shown as a character)
        compound (crasis) words join two keys and codes with "+", e.g. "G2532+G1565", "CONJ+D-NSM"
    Hebrew: [text, translit, english, strongs, morph, after, flag, note]
        text/english/strongs/morph keep the source's "/" between joined parts (prefix/word/suffix)
        strongs marks the main word in {braces}; morph segments after the first omit the H/A prefix
        flag: "q" read as qere (note = ketiv as written), "k" written but not read (ketiv without qere),
              "x" not in the Leningrad Codex (from other manuscripts)
        Hebrew keeps the source's order of vowel and accent marks (it is not Unicode-normalised).
Data: STEPBible Data CC BY 4.0 (Tyndale House Cambridge, STEPBible.org); BSB public domain.
"""
import glob, json, os, re, sys, unicodedata
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


def parse_greek_variant(mv):
    """'ἐσθῆτι (t=esthēti) garment - G2066=N-DSF in: NA28+TR+Byz' → the NA28 alternative, if any."""
    for part in re.split(r"[;\u00a6]", mv):
        m = re.match(r"\s*(\S+)\s+\((?:[A-Za-z])=([^)]*)\)\s+(.*?)\s+-\s+(G\d+[A-Za-z]?)=(\S+)\s+in:\s*(\S+)", part)
        if m and "NA28" in m.group(6).split("+"):
            return m.groups()
    return None


# NA28 verse -> BSB verse(s), where the BSB departs from the KJV numbering TAGNT records.
# Rev 12:18 "the dragon stood on the shore": KJV 13:1, but the BSB ends 12:17 with it.
BSB_REF_OVERRIDES = {("REV", 12, 18): ["12.17"]}


def build_greek(glex):
    books = OrderedDict()
    stats = Counter()
    counts = Counter()
    substituted = []
    fallback = {}
    en_refs = {}  # (book, ch, vs) -> English verse refs its words belong to, in order
    for path in sorted(glob.glob(os.path.join(STEP, "Translators Amalgamated OT+NT", "TAGNT*.txt")),
                       key=lambda p: 0 if "Mat-Jhn" in p else 1):
        for line in open(path, encoding="utf-8-sig"):
            m = WORD_RE.match(line)
            if not m:
                continue
            c = line.rstrip("\n").split("\t")
            stats["records"] += 1
            book, ch, vs = m.group(1), int(m.group(2)), int(m.group(3))
            editions = c[5].split("+")
            word_form = c[1]
            english = c[2]
            pairs = [(p.split("=", 1) + [""])[:2] for p in c[3].split(" + ")]
            strong = "+".join(k.strip() for k, _ in pairs)
            morph = "+".join(m_.strip() for _, m_ in pairs)
            if "NA28" not in editions:
                alt = parse_greek_variant(c[6])
                if not alt:
                    continue
                form, tr, gloss, strong, morph, _ = alt
                word_form, english = f"{form} ({tr})", gloss
                substituted.append(f"{book}.{ch}.{vs}")
            m2 = re.match(r"^(.*?)\s+\(([^)]*)\)\s*$", word_form)
            text, translit = (m2.group(1), m2.group(2)) if m2 else (word_form, "")
            sv = c[7]
            msv = re.search(r"([\w+»]*NA28[\w+»]*):\s*([^;]+?)\s*;", sv)
            if msv:
                text = msv.group(2).strip()
                stats["spelling_na28"] += 1
            text, post, pre = split_punct(nfc(text.strip()))
            for part in c[4].split(" + "):
                if "=" in part and strong and not lookup(glex, strong.split("+")[0]):
                    lem, gl = part.split("=", 1)
                    fallback.setdefault(strong.split("+")[0], [nfc(lem.strip()), "", gl.strip()])
            w = trim([text, translit, english.strip(), strong, morph, post, pre])
            uid = USFM[book]
            books.setdefault(uid, OrderedDict()).setdefault(ch, OrderedDict()).setdefault(vs, []).append(w)
            en = m.group("en") or f"{ch}.{vs}"
            refs = en_refs.setdefault((uid, ch, vs), [])
            if en not in refs:
                refs.append(en)
            stats["words"] += 1
            for k in strong.split("+"):
                counts[lookup(glex, k) or k] += 1
    stats["substituted_na28"] = len(substituted)
    stats["fallback_lexicon_entries"] = len(fallback)
    # TAGNT's [x.y] refs follow KJV numbering; where the BSB differs from the KJV, use the BSB's verse
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

def clean_note(n):
    return n.replace(" a a ", " a ").strip()


def build_bsb():
    d = json.load(open(os.path.join(SRC, "bsb", "bsb.json"), encoding="utf-8"))
    out, verse_sets = {}, {}
    for uid, b in d["books"].items():
        chapters = []
        vset = set()
        for ci, c in enumerate(b["c"], start=1):
            blocks = []
            for blk in c["b"]:
                items = []
                for x in blk.get("c", []):
                    if isinstance(x, dict) and "v" in x:
                        v = x["v"]
                        items.append(int(v) if str(v).isdigit() else v)
                        vset.add((ci, int(v) if str(v).isdigit() else v))
                    else:
                        items.append(x)
                blocks.append([blk["k"], items])
            chapters.append(trim([blocks, [clean_note(n) for n in c.get("n", [])]]))
        out[uid] = {"name": b["n"], "t": b["t"], "chapters": chapters}
        verse_sets[uid] = vset
    return d["index"], out, verse_sets


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
        if kind in ("s", "r", "b"):
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

    # Session 6: the Septuagint (Swete), lined up with the Hebrew/English verse numbers
    if os.path.isdir(os.path.join(SRC, "lxx-swete")):
        import build_lxx
        build_lxx.build(SRC)


if __name__ == "__main__":
    main()
