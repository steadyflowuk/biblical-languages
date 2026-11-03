"""Grammar checks for the lessons (Phase 2 plan, A2). Two parts:

1. The paradigm check (automatic). Every Greek or Hebrew form in a lesson's tables and parse drills that occurs in
   the Bible must carry, somewhere in the text, the grammar the lesson claims for it: a table cell under "you (more
   than one)" must be tagged 2nd person plural, a parse drill answered "dative" must be dative, and so on. Claims are
   read from the table's row and column labels and the drills' answers (CLAIMS below); forms listed in a lesson's
   "unattested" list, or found only as a dictionary headword, are skipped.

2. The grammar cross-check record. Each written lesson names the grammar chapter it follows ("source") and carries a
   "grammarCheck": the date the lesson was compared, claim by claim, with that chapter (Schwandt or Wegner, in the
   user's Logos library), the verdict, the claims checked, and a fingerprint of the lesson's teaching (its Notice and
   Practise steps and the Read step's notes). A lesson with no record, or whose teaching changed since its record
   (the fingerprint no longer matches), fails until it is checked again.

    python3 tools/check_grammar.py                 # both checks (exit 1 on any problem)
    python3 tools/check_grammar.py status          # which lessons need a cross-check, and why
    python3 tools/check_grammar.py fingerprint ID  # the fingerprint to record after checking lesson ID
    python3 tools/check_grammar.py record ID FILE  # write FILE's record (JSON: verdict, claims, …) into lesson ID,
                                                   # with today's date and the current fingerprint
"""
import datetime, hashlib, json, os, re, sys

sys.argv, _args = sys.argv[:1], sys.argv[1:]  # check_lessons reads no arguments; keep ours for later
sys.path.insert(0, os.path.dirname(__file__))
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    import check_lessons as cl  # spelling keys and the whole Bible's words (loads once)

ROOT = cl.ROOT
LESSONS = os.path.join(ROOT, "lessons")
problems, notes = [], []

# ---------------------------------------------------------------- the words of the Bible with their grammar
greek_codes, hebrew_codes = {}, {}
for b in cl.books:
    d = cl.load(os.path.join(cl.DATA, "gnt" if b["lang"] == "grc" else "hot", f"{b['id']}.json"))
    for c, vs in d["ch"]:
        for v in vs:
            for w in v[1]:
                if len(w) < 5 or not w[4]:
                    continue
                if b["lang"] == "grc":
                    greek_codes.setdefault(cl.greek_key(w[0]), set()).add(w[4])
                else:
                    hebrew_codes.setdefault(cl.hebrew_key(w[0]), set()).add(w[4])
headwords = {cl.greek_key(e[1]) if k.startswith("G") else cl.hebrew_key(e[1]) for k, e in cl.index.items()}
lemma_of = {k: e[1] for k, e in cl.index.items()}


def greek_feats(code):
    """TAGNT code → features: V-PAI-3S, N-NSM, T-DPF, A-ASN, P-1NS …"""
    f = {"pos": code.split("-")[0]}
    parts = code.split("-")
    if f["pos"] == "V" and len(parts) > 1:
        tvm = parts[1]
        f["tense"], f["mood"] = tvm[:1], tvm[-1:]
        if len(parts) > 2:
            pn = parts[2]
            m = re.match(r"([123])([SP])$", pn)
            if m:
                f["person"], f["num"] = m.group(1), m.group(2)
            elif re.match(r"[NGDAV][SP][MFN]$", pn):  # participles
                f["case"], f["num"], f["gen"] = pn[0], pn[1], pn[2]
    else:
        for p in parts[1:]:
            m = re.match(r"([123])?([NGDAV])([SP])([MFN])?$", p)
            if m:
                f["person"] = m.group(1)
                f["case"], f["num"], f["gen"] = m.group(2), m.group(3), m.group(4)
    return f


def hebrew_feats(code):
    """TAHOT code → features of the main part, plus the prefixes: HVqp3ms, HNcmpa, HTd/Ncfsa, HRd/Ncbsa, HC/Vqw3ms …"""
    segs = code[1:].split("/")
    f = {"prefixes": [s for s in segs[:-1] if s], "article": any(s.startswith(("Td", "Rd")) for s in segs[:-1]),
         "conj": any(s.startswith("C") for s in segs[:-1])}
    main = segs[-1]
    f["pos"] = main[:1]
    if main.startswith("V") and len(main) >= 3:
        f["form"] = main[2]
        m = re.match(r"([123])?([mfbc])?([spd])?", main[3:])
        if m:
            f["person"], f["gen"], f["num"] = m.group(1), m.group(2), m.group(3)
    elif main[:1] in "NA" and len(main) >= 4:
        m = re.match(r"[NA][a-z]([mfbc])([spd])", main)
        if m:
            f["gen"], f["num"] = m.group(1), m.group(2)
    return f


# ---------------------------------------------------------------- what a label or an answer claims
# label (lower case, matched as whole words) → features; a list of values = any of them
GREEK_CLAIMS = [
    (r"\bi\b", {"person": "1", "num": "S"}), (r"\bwe\b", {"person": "1", "num": "P"}),
    (r"\byou \(one\)", {"person": "2", "num": "S"}), (r"\byou \(more than one\)", {"person": "2", "num": "P"}),
    (r"^you$", {"person": "2"}), (r"\bhe, she,? (or )?it\b", {"person": "3", "num": "S"}), (r"\bthey\b", {"person": "3", "num": "P"}),
    (r"^one$", {"num": "S"}), (r"^more than one$", {"num": "P"}),
    (r"subject or object", {"case": ["N", "A"]}), (r"^(nominative|subject)\b|\bnominative\b", {"case": "N"}),
    (r"genitive", {"case": "G"}), (r"dative", {"case": "D"}), (r"accusative|^object\b", {"case": "A"}),
    (r"^masculine$", {"gen": "M"}), (r"^feminine$", {"gen": "F"}), (r"^neuter$", {"gen": "N"}),
    (r"^past$", {"tense": ["I", "A", "2"]}), (r"^present$", {"tense": "P"}), (r"^future$", {"tense": "F"}),
]
HEBREW_CLAIMS = [
    (r"^i$", {"person": "1", "num": "s"}), (r"^you$", {"person": "2"}), (r"^he$", {"person": "3", "gen": "m", "num": "s"}),
    (r"^she$", {"person": "3", "gen": "f", "num": "s"}),
    (r"^one$", {"num": "s"}), (r"^more than one$", {"num": "p"}), (r"^a pair$", {"num": "d"}),
    (r"^masculine$", {"gen": ["m", "b", "c"]}), (r"^feminine$", {"gen": ["f", "b", "c"]}),
    (r"^finished$", {"form": "p"}), (r"^not yet finished$", {"form": "i"}),
]


def claims_of(label, lang, field=""):
    label = re.sub(r"<[^>]+>", "", str(label or "")).strip().lower()
    out = {}
    if lang == "he" and field.lower().startswith("has “the”"):
        return {"article": label.startswith("yes")}
    if lang == "he" and field.lower() == "first letter" and "and" in label:
        return {"conj": True}
    for pat, feats in (GREEK_CLAIMS if lang == "grc" else HEBREW_CLAIMS):
        if re.search(pat, label):
            for k, v in feats.items():
                out.setdefault(k, v)
    return out


def satisfies(f, claims):
    for k, want in claims.items():
        have = f.get(k)
        if isinstance(want, list):
            if have not in want:
                return False
        elif have != want:
            return False
    return True


def check_form(where, word, claims, lang, unattested):
    if not claims or not re.search(cl.GREEK if lang == "grc" else cl.HEBREW, word):
        return
    key = cl.greek_key(word) if lang == "grc" else cl.hebrew_key(word)
    codes = (greek_codes if lang == "grc" else hebrew_codes).get(key)
    if not codes:
        if word in unattested or key in headwords:
            return  # textbook form not in the Bible, or a dictionary form (λύω)
        problems.append(f"{where}: {word} doesn't occur in the Bible (spelling?) — or list it under \"unattested\"")
        return
    feats = [greek_feats(c) if lang == "grc" else hebrew_feats(c) for c in codes]
    if not any(satisfies(f, claims) for f in feats):
        problems.append(f"{where}: {word} is taught as {claims}, but the text tags it only as {sorted(codes)[:6]}")


def forms_in(cell, lang):
    """The words of a table cell that are forms (not endings like -ομεν or stem + ending sums)."""
    text = re.sub(r"<[^>]+>", "", str(cell))
    if "+" in text or re.search(r"(^|\s)-|-($|\s)", text) or "/" in text:
        return []
    pat = cl.GREEK if lang == "grc" else cl.HEBREW
    return [w.strip(".,;:·()“”") for w in text.split() if pat.search(w)]


def paradigm_check(lid, L):
    lang, unattested = L["lang"], set(L.get("unattested", []))
    n = 0
    for s in L["steps"]:
        for i, c in enumerate(s["cards"]):
            where = f"{lid} {s['step']} card {i + 1}"
            t = c.get("table")
            if t and not c.get("letters"):
                head = t.get("head") or []
                for r, row in enumerate(t.get("rows", [])):
                    rowc = claims_of(row[0], lang)
                    for j, cell in enumerate(row[1:], start=1):
                        h = head[j] if j < len(head) else ""
                        # a heading that is itself a word ("λύω, I loose") claims nothing; the column wins a clash,
                        # except that a row "a pair" refines "more than one" to the dual (he-6: עַיִן / עֵינַיִם)
                        headc = {} if re.search(cl.GREEK if lang == "grc" else cl.HEBREW, h) else claims_of(h, lang)
                        claims = {**rowc, **headc}
                        if rowc.get("num") == "d" and headc.get("num") == "p":
                            claims["num"] = "d"
                        for w in forms_in(cell, lang):
                            check_form(f"{where} table row {r + 1}", w, claims, lang, unattested)
                            n += 1 if claims else 0
            if c.get("type") == "parse" and c.get("word"):
                claims = {}
                for fld in c.get("fields", []):
                    claims.update(claims_of(fld.get("answer"), lang, fld.get("label", "")))
                words = c["word"].split()
                for w in words:
                    wc = dict(claims)
                    if len(words) > 1 and lang == "grc":
                        wc.pop("person", None)  # an article + noun pair: both carry case, number and gender
                    check_form(f"{where} (parse {c['word']})", w, wc, lang, unattested)
                    n += 1 if wc else 0
    return n


# ---------------------------------------------------------------- the cross-check record
def teaching(L):
    """What the fingerprint covers: the Notice and Practise steps in full, and the Read step's notes."""
    parts = []
    for s in L["steps"]:
        if s["step"] in ("notice", "practise"):
            parts.append(s["cards"])
        elif s["step"] == "read":
            parts.append([c.get("note", "") for c in s["cards"]])
    return parts


def fingerprint(L):
    raw = json.dumps(teaching(L), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def written():
    idx = cl.load(os.path.join(LESSONS, "index.json"))
    for lang in ("grc", "he"):
        for e in idx[lang]:
            if e.get("file"):
                yield e["id"], os.path.join(ROOT, e["file"])


def record_problems(lid, L):
    out = []
    if not L.get("source"):
        out.append("no \"source\" (the grammar chapter it follows)")
    g = L.get("grammarCheck")
    if not g:
        out.append("not yet cross-checked against its grammar chapter")
    else:
        for k in ("date", "fingerprint", "verdict", "claims"):
            if not g.get(k):
                out.append(f"grammarCheck has no {k}")
        if g.get("fingerprint") and g["fingerprint"] != fingerprint(L):
            out.append(f"its teaching changed since the cross-check of {g.get('date')}: check it again")
        for c in g.get("claims", []):
            if c.get("result") not in ("agrees", "differs on purpose", "fixed"):
                out.append(f"claim {c.get('claim', '?')[:40]!r} has result {c.get('result')!r}")
    return out


def main():
    cmd = _args[0] if _args else "check"
    if cmd == "fingerprint":
        path = dict(written())[_args[1]]
        print(fingerprint(cl.load(path)))
        return
    if cmd == "record":
        lid, src = _args[1], _args[2]
        path = dict(written())[lid]
        L = json.load(open(path, encoding="utf-8"))
        rec = json.load(open(src, encoding="utf-8"))
        if "source" in rec:
            L["source"] = rec.pop("source")
        rec = {"date": datetime.date.today().isoformat(), **rec, "fingerprint": fingerprint(L)}
        L["grammarCheck"] = rec
        # Written as two lines at the end of the file, so the lesson's own hand layout is kept
        text = open(path, encoding="utf-8").read()
        text = re.sub(r',\n  "source": .*\Z', "\n}\n", text, flags=re.S).rstrip()
        assert text.endswith("}"), path
        tail = (',\n  "source": ' + json.dumps(L["source"], ensure_ascii=False) +
                ',\n  "grammarCheck": ' + json.dumps(rec, ensure_ascii=False) + "\n}\n")
        text = text[:-1].rstrip() + tail
        json.loads(text)
        open(path, "w", encoding="utf-8").write(text)
        print(f"{lid}: recorded ({rec['verdict']}, {len(rec.get('claims', []))} claims, fingerprint {rec['fingerprint']})")
        return
    # known answers first: a table with two rows swapped and a drill answered wrongly must both be caught
    fake = {"lang": "grc", "steps": [{"step": "notice", "cards": [{"type": "explain", "table": {"head": ["who", "form"],
            "rows": [["I", "λέγω"], ["he, she, it", "λέγετε"], ["you (more than one)", "λέγει"]]}}]},
            {"step": "practise", "cards": [{"type": "parse", "word": "τοῖς ἀδελφοῖς", "fields": [
             {"label": "Case", "answer": "genitive: of"}, {"label": "How many?", "answer": "more than one"}]}]}]}
    paradigm_check("self-test", fake)
    caught = len(problems)
    problems.clear()
    if caught != 4:  # λέγετε, λέγει, and both words of τοῖς ἀδελφοῖς
        problems.append(f"self-test: the paradigm check caught {caught} of 4 planted mistakes")
    # and a lesson whose teaching changes after its record must need checking again (its fingerprint changes)
    probe = json.loads(json.dumps(cl.load(dict(written())["grc-4"])))
    before = record_problems("grc-4", probe)
    probe["steps"][1]["cards"][0]["body"][0] += " (changed)"
    if before or not any("teaching changed" in p for p in record_problems("grc-4", probe)):
        problems.append("self-test: a changed lesson didn't lose its cross-check")
    checked = 0
    waiting = []
    for lid, path in written():
        L = cl.load(path)
        checked += paradigm_check(lid, L)
        for p in record_problems(lid, L):
            waiting.append(f"{lid}: {p}")
    if cmd == "status":
        print("\n".join(waiting) if waiting else "Every lesson's cross-check is up to date.")
        return
    print(f"Paradigm check: {checked} forms compared with the grammar of the text")
    for p in problems:
        print("FAIL " + p)
    print(f"Grammar cross-check records: {len(list(written())) - len({w.split(':')[0] for w in waiting})} of {len(list(written()))} lessons up to date")
    for w in waiting:
        print("FAIL " + w)
    bad = len(problems) + len(waiting)
    print(f"\n{'All checks passed' if not bad else f'{bad} problems'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
