#!/usr/bin/env python3
"""The Septuagint's spelling, as a reader of Greek would check it (19 Nov 2026):  python3 tools/check_lxx_text.py

The digital Swete (LXX-Swete-1930) came from scanned pages, and a scan misreads marks. These rules can't be broken
in printed Greek, so any word that breaks one is a slip (put right in tools/build_lxx.py, SWETE_FIXES) or one of
the few real words listed in ALLOWED below:
  • a grave accent stands only on a word's last syllable;
  • a breathing stands only on a word's first vowel or pair (ρ aside; crasis such as ταὐτά is allowed by name);
  • no capital letter inside a word (two words run together, or a misread letter);
  • no accent further back than the third syllable from the end;
  • a word starting with a vowel carries a breathing (numerals written as letters aside);
  • an accent or breathing goes on the second letter of αυ, ευ, ου, not the first (ἄυδρας was ἄνδρας);
  • a word has at most two accents (the second only before an enclitic);
  • the same word isn't printed twice in a row with different breathings (ἑμοῦ ἐμοῦ);
  • every letter is Greek (no Latin look-alikes).
Words printed in capitals at a book's start (ΕΝ ΑΡΧΗ) are left to the pronunciation check.
"""
import json
import os
import re
import sys
import unicodedata as u

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TEXT = os.path.join(ROOT, "data", "lxx", "text")
VOWELS = "αεηιουω"
PAIRS = {"αι", "ει", "οι", "αυ", "ευ", "ου", "υι", "ηυ"}
ACC = "̀́͂"
BR = "̓̔"
# Real words that look odd to the rules: crasis (τὰ αὐτά, τὸ ἐναντίον, καλὸς κἀγαθός), names written with a mark on
# the first of two vowels said apart (Ἀυάθ, Ἀταφόυτ), πρᾳΰνω (ᾳ and υ are never a pair), and Ἀβώρ printed without
# its breathing (Swete's own; the voice is the same either way)
ALLOWED = {"ταὐτά", "ταὐτὰ", "τοὐναντίον", "καλοκἀγαθίας", "καλοκἀγαθίᾳ", "καλοκἀγαθίαν", "Ἀυὰθ", "Ἀταφόυτ",
           "κατεπρᾴυνεν", "Αβώρ"}
NFC = lambda s: u.normalize("NFC", s)


def marks(w):
    out = []
    for ch in u.normalize("NFD", w):
        if u.category(ch).startswith("L"):
            out.append([ch, ""])
        elif out:
            out[-1][1] += ch
    return out


def nuclei(L):
    res, i = [], 0
    while i < len(L):
        c = L[i][0].lower()
        if c in VOWELS:
            nxt = L[i + 1] if i + 1 < len(L) else None
            if nxt and c + nxt[0].lower() in PAIRS and "̈" not in nxt[1] and not re.search(f"[{ACC}{BR}ͅ]", L[i][1]):
                res.append((i, i + 1)); i += 2; continue
            res.append((i, i))
        i += 1
    return res


def problems_of(w):
    """The rules a single word breaks (w without punctuation)."""
    L = marks(w)
    if not L or all(x[0].isupper() for x in L):
        return []
    out = []
    if any(not ("Ͱ" <= x[0] <= "Ͽ" or "ἀ" <= x[0] <= "῿") for x in L):
        out.append("a letter that isn't Greek")
    nuc = nuclei(L)
    acc = [k for k, x in enumerate(L) if re.search(f"[{ACC}]", x[1])]
    grave = [k for k, x in enumerate(L) if "̀" in x[1]]
    if grave and nuc and not nuc[-1][0] <= grave[-1] <= nuc[-1][1]:
        out.append("grave accent before the last syllable")
    for k in range(len(L) - 1):
        if (L[k][0].lower() + L[k + 1][0].lower()) in {"αυ", "ευ", "ου"} and re.search(f"[{ACC}{BR}]", L[k][1]) \
                and not re.search(f"[̈{ACC}{BR}]", L[k + 1][1]):
            out.append("mark on the first letter of αυ, ευ or ου")
            break
    if acc and nuc:
        pos = next((len(nuc) - j for j, (a, b) in enumerate(nuc) if a <= acc[0] <= b), 0)
        if pos > 3:
            out.append("accent before the third syllable from the end")
    if len(acc) > 2:
        out.append("three accents")
    if any(x[0].isupper() for x in L[1:]):
        out.append("capital letter inside a word")
    first = L[0][0].lower()
    if first in VOWELS and not re.search(f"[{BR}̈]", L[0][1]) and not (len(L) > 1 and re.search(f"[{BR}]", L[1][1])):
        out.append("word starting with a vowel has no breathing")
    br = [k for k, x in enumerate(L) if re.search(f"[{BR}]", x[1])]
    if br and br[0] > 1 and L[br[0]][0].lower() != "ρ":
        out.append("breathing inside a word")
    return out


def is_numeral(tok):
    """Swete's numbers written as letters (ιβ᾽ 12), and three where the mark was lost (EZR 2:37 α = 1,000)."""
    t = re.sub(r"[.,;:·()\[\]]", "", tok)
    return bool(re.fullmatch(r"[α-ωϛϙϡς]{1,4}[᾽’]", t))


def main():
    found = {}
    n_words = 0
    for f in sorted(os.listdir(TEXT)):
        book = json.load(open(os.path.join(TEXT, f), encoding="utf-8"))
        for c, vs in book["ch"]:
            for v, t in vs:
                ref = f"{book['id']} {c}:{v}"
                # words as the app shows them (js/audio.js lxxTokens: a mark joins its word, a space follows it)
                toks = re.sub(r"([,.;·])(?=[\u0370-\u03FF\u1F00-\u1FFF])", r"\1 ", re.sub(r"\s+([,.;·])", r"\1", t)).split()
                bare = [NFC(re.sub(r"[.,;:·()\[\]᾽’]", "", x)) for x in toks]
                for tok, w in zip(toks, bare):
                    if not w or is_numeral(tok) or w in ALLOWED:
                        continue
                    if (ref, w) in {("EZR 2:37", "α"), ("EZR 2:38", "α"), ("NEH 7:70", "α")}:
                        continue  # numerals whose mark the source lost (said as χίλιοι/χιλίους: js/audio.js)
                    n_words += 1
                    for p in problems_of(w):
                        found.setdefault(p, []).append(f"{ref}: {tok}")
                strip = lambda s: re.sub(r"[̀-ͯ]", "", u.normalize("NFD", s)).lower()
                for a, b in zip(bare, bare[1:]):
                    # (only the breathing differs: εἷς εἰς are two words, Κύριε κύριέ a capital and an enclitic's accent)
                    nobr = lambda s: re.sub(f"[{BR}]", "", u.normalize("NFD", s))
                    if a and len(strip(a)) > 2 and a != b and nobr(a) == nobr(b):
                        found.setdefault("the same word twice in a row, its breathing differing", []).append(f"{ref}: {a} {b}")
    print(f"Septuagint spelling: {n_words:,} words checked against the rules of printed Greek.")
    if not found:
        print("Every word keeps them (slips in the source are put right in tools/build_lxx.py).")
        return 0
    print(f"\n{sum(len(v) for v in found.values())} words break them:")
    for k, v in found.items():
        print(f"  {len(v)} × {k}")
        for x in v[:8]:
            print("      " + x)
    return 1


if __name__ == "__main__":
    sys.exit(main())
