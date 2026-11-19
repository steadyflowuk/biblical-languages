#!/usr/bin/env python3
"""Today's verse pool (19 Nov 2026): every verse that reads well on its own, for a day-seeded random pick.

    python3 tools/build_votd_pool.py            # writes data/votd-pool.json from data/ (run by build_data.py too)
    python3 tools/build_votd_pool.py --stats    # counts per rule, nothing written

The app (js/today.js) picks one verse a day from this list for each language, the same on every device on that day,
and builds it from the Bible data like the Reader does. A verse is in the pool when:
  • it is a whole sentence in the BSB: starts with a capital (or an opening quote) and ends with . ! ? or a closing
    quote after one of them; its quotation marks open and close inside it; no translator's brackets left over;
  • it has 5–24 Greek words, or 3–14 Hebrew words (Hebrew words carry their prefixes, so fewer);
  • names make up no more than a third of its words (genealogies and lists of places stay out);
  • nothing unusual: no Aramaic (the Hebrew track is Hebrew), no psalm titles (verse 0), no written-not-read or
    other-manuscript words (flags k and x), not inside the double brackets ⟦ ⟧ (later additions), no verse whose
    English the Reader has to borrow or split (3 John 15, Rev 12:18, Rom 16:25-27, Acts 19:41 …);
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
                if not lo <= n <= hi:
                    no(lang, "too short" if n < lo else "too long"); continue
                if sum(1 for w in words if is_name(lang, w)) > n * NAME_SHARE:
                    no(lang, "mostly names"); continue
                en = english.get(v, "")
                if not en:
                    no(lang, "no BSB text"); continue
                if not SENTENCE.match(en) or re.search(r"[\[\]]", en) or en.count("“") != en.count("”"):
                    no(lang, "not a whole sentence in English"); continue
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
