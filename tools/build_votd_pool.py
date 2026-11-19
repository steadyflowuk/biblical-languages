#!/usr/bin/env python3
"""Today's verse pool (19 Nov 2026): every verse that reads well on its own, for a day-seeded random pick.

    python3 tools/build_votd_pool.py            # writes data/votd-pool.json from data/ (run by build_data.py too)
    python3 tools/build_votd_pool.py --stats    # counts per rule, nothing written

The app (js/votd.js) picks one verse a day from this list for each language, the same on every device on that day,
and builds it from the Bible data like the Reader does. A verse is in the pool when:
  • it is a whole sentence in the BSB: starts with a capital (or an opening quote) and ends with . ! ? or a closing
    quote after one of them; its quotation marks (“ ” and ‘ ’) and brackets open and close inside it; no
    translator's brackets left over;
  • it has 5–24 Greek words, or 3–14 Hebrew words (Hebrew words carry their prefixes, so fewer);
  • names make up no more than a third of its words (genealogies and lists of places stay out);
  • nothing unusual: no Aramaic (the Hebrew track is Hebrew), no psalm titles (verse 0), no written-not-read or
    other-manuscript words (flags k and x), not inside the double brackets ⟦ ⟧ (later additions), no verse whose
    English the Reader has to borrow or split (3 John 15, Rev 12:18, Rom 16:25-27, Acts 19:41 …);
  • nothing a beginner would find jarring met alone, with no context (UNSETTLING: graphic violence, sexual or bodily
    detail); well-known verses (ALWAYS) are let in whatever their length.
Format: {"grc": {"MAT": "5.3 5.4 …", …}, "he": {…}, "count": {"grc": N, "he": N}}; refs in Reader (English) numbering.
"""
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data")
GREEK_WORDS = (5, 24)
HEBREW_WORDS = (3, 14)
NAME_SHARE = 1 / 3


def bsb_verses(book, ch):
    """{verse: text} as the Reader's bsbChapter builds it (headings, cross-references and blank lines skipped)."""
    out, v = {}, 0
    chapter = book["chapters"][ch - 1] if ch - 1 < len(book["chapters"]) else None
    if not chapter:
        return out
    for kind, items in chapter[0]:
        if kind in ("s", "qa", "r", "b"):
            continue
        for x in items:
            if isinstance(x, int):
                v = x
                out.setdefault(v, "")
            elif isinstance(x, str):
                out[v] = re.sub(r"\s+", " ", (out.get(v, "") + " " + x)).strip()
    return {k: re.sub(r"\u0001\d+\u0001", "", t).strip() for k, t in out.items()}


def paired(en):
    """Quotation marks and brackets open and close inside the verse: “ ”, ‘ ’ (a ’ after a letter and before a space or
    a mark that ends a word is an apostrophe or a plural possessive, “the brothers’ sacks”, unless a mark comes first)."""
    if en.count("“") != en.count("”") or en.count("(") != en.count(")"):
        return False
    closing = len(re.findall(r"[.,!?;:—–]’", en)) + len(re.findall(r"’(?=[”\s]*$)", en)) - len(re.findall(r"[.,!?;:—–]’(?=[”\s]*$)", en))
    return en.count("‘") == closing


# Verses that read badly as a "verse for today" for a beginner met with no context (graphic violence, sexual or bodily
# detail): kept in the Bible, left out of the daily pick (19 Nov 2026, after the review). Matched in the BSB English.
UNSETTLING = [r"\bdash(es|ed)?\b.*\b(infants|little ones|children)\b", r"\bripped open\b", r"\bpregnant women\b.*\b(ripped|torn)\b",
              r"\b(boiled|cooked|ate)\b.*\b(sons|daughters|children)\b", r"\bblood of the wicked\b", r"\bravished\b",
              r"\braped?\b", r"\bsemen\b", r"\bemission\b", r"\bgenitals?\b", r"\btesticles\b", r"\bcrushed or severed\b",
              r"\bbreasts?\b", r"\bnipples?\b", r"\bdung\b", r"\bexcrement\b", r"\bfeces\b", r"\bintestines\b", r"\bentrails\b",
              r"\bemasculate\b", r"\bcastrat", r"\bforeskins?\b", r"\bmenstrua", r"\bdischarge\b", r"\bbodily\b",
              r"\bnakedness\b", r"\buncover\b", r"\bprostitut", r"\bharlot\b", r"\bwhor", r"\badulter", r"\blust(s|ed|ful)?\b",
              r"\bslept with\b", r"\bsleeps with\b", r"\blies? with\b", r"\blay with\b", r"\bgo in to\b", r"\bwent in to\b",
              r"\banimal\b.*\b(lie|lies|mates?)\b", r"\bmates? with\b", r"\bincest", r"\bvomit", r"\bmaggots?\b", r"\brotting\b",
              r"\bcorpses?\b", r"\bdisembowel", r"\bimpaled?\b", r"\bhanged\b", r"\bbeheaded\b", r"\bmutilat", r"\bscalp",
              r"\bkill(ed)? (every|all the) (male|men|women)\b", r"\bburned their sons\b", r"\bsacrificed their sons\b",
              r"\bthrough the fire\b", r"\bcut (him|them|her) (in|into) pieces\b", r"\bcut off (his|her|their) (hands|thumbs|noses?|ears?)\b"]
# Well-known verses let in whatever their length or names (data/votd.json's 24 and a few more); every other rule holds
ALWAYS = {"JHN 3:16", "JHN 1:1", "JHN 14:6", "ROM 5:8", "ROM 8:28", "EPH 2:8", "PHP 4:13", "HEB 11:1", "1JN 4:8", "MAT 5:3",
          "MRK 1:15", "GAL 2:20", "GEN 1:1", "DEU 6:4", "PSA 23:1", "PSA 119:105", "PRO 3:5", "ISA 40:8", "MIC 6:8", "NUM 6:24",
          "JOS 1:9", "PSA 46:10", "ISA 53:5", "LAM 3:23", "ROM 6:23", "ROM 12:2", "JHN 11:35", "1CO 13:4", "MAT 11:28",
          "PSA 27:1", "ISA 41:10", "JER 29:11", "PSA 46:1", "PRO 3:6"}


SENTENCE = re.compile(r"^[“‘\"'(]?[A-Z].*[.!?][”’\"')]*$")


def is_name(lang, w):
    code = w[4] if len(w) > 4 else ""
    if lang == "grc":
        return bool(re.search(r"-(P|L|G|LG|PG)$", code)) or code.startswith("N-PRI")
    # people, places and peoples (Npm, Npf, Npl, Npg …); not Npt, the title-names Yahweh and Adonai
    return any(re.match(r"^[HA]?Np[^t]", c) for c in code.split("/"))


def main():
    stats = "--stats" in sys.argv
    books = json.load(open(os.path.join(DATA, "books.json"), encoding="utf-8"))
    books = books if isinstance(books, list) else books.get("books", books)
    pool = {"grc": {}, "he": {}}
    why = {"grc": {}, "he": {}}

    def no(lang, reason):
        why[lang][reason] = why[lang].get(reason, 0) + 1

    for b in books:
        uid = b["id"]
        lang = "grc" if b.get("lang") == "grc" else "he"
        src = os.path.join(DATA, "gnt" if lang == "grc" else "hot", uid + ".json")
        if not os.path.exists(src):
            continue
        orig = json.load(open(src, encoding="utf-8"))
        bsb = json.load(open(os.path.join(DATA, "bsb", uid + ".json"), encoding="utf-8"))
        refs = []
        bracket = False  # inside ⟦ ⟧
        for ch, verses in orig["ch"]:
            english = bsb_verses(bsb, ch)
            for item in verses:
                v, words = item[0], item[1]
                extra = item[2] if len(item) > 2 else None
                text = "".join((w[6] if len(w) > 6 else "") + w[0] + (w[5] if len(w) > 5 else "") for w in words)
                opens, closes = "⟦" in text, "⟧" in text
                inside = bracket or opens
                if opens:
                    bracket = True
                if closes:
                    bracket = False
                if inside:
                    no(lang, "inside ⟦ ⟧"); continue
                if v == 0:
                    no(lang, "psalm title"); continue
                if extra and lang == "grc":  # its words belong to other English verses too (MAT 17:15)
                    no(lang, "English verse split"); continue
                if lang == "he" and any(len(w) > 6 and w[6] in ("k", "x") for w in words):
                    no(lang, "written-not-read or other-manuscript word"); continue
                if lang == "he" and any(str(w[4]).startswith("A") for w in words if len(w) > 4):
                    no(lang, "Aramaic"); continue
                n = len([w for w in words if not (len(w) > 7 and w[7] == "+")])
                lo, hi = GREEK_WORDS if lang == "grc" else HEBREW_WORDS
                known = f"{uid} {ch}:{v}" in ALWAYS  # well known: in whatever its length or names
                if not lo <= n <= hi and not known:
                    no(lang, "too short" if n < lo else "too long"); continue
                if sum(1 for w in words if is_name(lang, w)) > n * NAME_SHARE and not known:
                    no(lang, "mostly names"); continue
                en = english.get(v, "")
                if not en:
                    no(lang, "no BSB text"); continue
                if not SENTENCE.match(en) or re.search(r"[\[\]]", en) or not paired(en):
                    no(lang, "not a whole sentence in English"); continue
                if any(re.search(p, en, re.I) for p in UNSETTLING):
                    no(lang, "not one to meet on its own"); continue
                refs.append(f"{ch}.{v}")
        if refs:
            pool[lang][uid] = " ".join(refs)
    count = {lang: sum(len(s.split()) for s in pool[lang].values()) for lang in pool}
    if stats:
        for lang in ("grc", "he"):
            print(lang, "in the pool:", count[lang])
            for k, n in sorted(why[lang].items(), key=lambda x: -x[1]):
                print(f"   {n:6} {k}")
        return
    out = {"grc": pool["grc"], "he": pool["he"], "count": count}
    path = os.path.join(DATA, "votd-pool.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"votd-pool.json: {count['grc']} Greek and {count['he']} Hebrew verses ({os.path.getsize(path) // 1024} KB)")


if __name__ == "__main__":
    main()
