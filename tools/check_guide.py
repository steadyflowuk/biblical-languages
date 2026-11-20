"""Check the Guide (Guide tab, 19 Nov 2026): its sources, the built files and everything they claim about the Bible.

    python3 tools/check_guide.py              # the guide as it is
    python3 tools/check_guide.py --self-test  # plant mistakes in a copy of the sources and show each is caught

What it checks (each a kind of problem; the summary counts them):
  build      guide/guide.json and guide/examples.json are what tools/build_guide.py makes from guide/src (never edited
             by hand), and the sources follow the format (guide/README.md)
  format     every section has an introduction and entries; every entry an id, a sentence-case title, a one-line
             summary that ends a sentence and is short, a body; known languages; no duplicate titles
  links      every [[link]], "see", lesson and app route goes somewhere real; no entry links to itself in "see"
  refs       every [BOOK c:v] is a verse of the app's Bible (Greek numbering for the New Testament, English for the Old)
  spelling   every Greek and Hebrew word is spelt as somewhere in the Bible or the dictionary (accents and vowels
             included), unless the entry lists it as "unattested"; endings and stems are written with a hyphen
  numbers    no number typed into the prose: counts come from the Bible data ({{KEY}} or "find"); the only typed
             numbers allowed are the dates in FACTS, each with where it was checked
  examples   each example's verse is the Bible's verse word for word, its English is the BSB's, its word is the one
             named, and (for picked examples) its grammar code matches the entry's pattern; every count is recounted
             here, independently of the builder
  plain      sentences of at most 40 words, no Latin abbreviations (e.g., i.e., etc.), British spelling, no
             doubled words, and every technical term another entry explains is linked the first time an entry uses it
  matches    no label phrase claimed by two entries for the same language
  claims     every Greek or Hebrew word an entry's summary gives as an example has, somewhere in the Bible, the grammar
             the entry is about (its find pattern)
  respell    every respelling written in the prose (λόγος, LO-gos; בְּרִית, be-RIT) is the app's: Greek = greekSay in
             js/sound.js, Hebrew = the word lists' and lessons' respelling of the same pointed word; Hebrew writes
             i and u (never ee, oo) and puts one stressed syllable in capitals
"""
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_guide as BG  # noqa: E402
from build_votd_pool import bsb_verses  # noqa: E402

# The only numbers typed into the guide's prose, each checked against a source (19 Nov 2026).
FACTS = {
    "1008": "Leningrad Codex: copied in 1008 (its colophon; National Library of Russia)",
    "1890": "James Strong, Exhaustive Concordance of the Bible, published 1890",
}
# entries that explain the digits inside the app's grammar codes (3ms: 3rd person)
CODE_ENTRIES = {"pgn", "abbreviations", "grammar-codes"}
AVOID = re.compile(r"drunk|sorcer|put to death|pregnant|naked|harlot|prostitut|uncovered|whore|adulter|rape|slaughter", re.I)
LATIN = re.compile(r"\b(e\.g\.|i\.e\.|etc\.|cf\.|viz\.|ibid\.|N\.B\.)", re.I)
AMERICAN = re.compile(r"\b(\w+iz(e|es|ed|ing|ation)|color(s|ed)?|center(s|ed)?|honor(s|ed)?|favor(ite|s)?|behavior|neighbor|labor|"
                      r"savior|gray|catalog|traveled|traveling|judgment|toward|fulfill|fulfillment|analyze|defense|offense|program)\b", re.I)
AMERICAN_OK = {"size", "sizes", "seize", "seized", "prize"}
# Words that are both everyday English and a grammar term: an entry may use them without a link (their own entries
# exist and are linked where the grammar meaning matters). Everything else another entry explains must be linked.
COMMON = {"word", "words", "case", "cases", "number", "numbers", "person", "persons", "voice", "voices", "mood", "subject",
          "object", "stem", "stems", "root", "roots", "gender", "sentence", "sentences", "clause", "phrase", "letter",
          "letters", "verse", "verses", "name", "names", "time", "past", "future", "present", "title", "meaning", "count",
          "times", "form", "forms", "ending", "endings", "prefix", "suffix", "translation", "translations", "english",
          "greek", "hebrew", "aramaic", "grammar", "label", "labels", "help", "say", "first", "second", "third",
          "command", "commands", "wish", "location", "individual", "particle", "particles", "point", "points", "mark",
          "marks", "dot", "dots", "sign", "signs", "article", "statement", "question", "pronunciation", "reading",
          "readings", "paragraph", "chapter", "chapters", "edition", "text", "today", "review", "streak", "backup",
          "offline", "listen", "active", "passive", "middle", "masculine", "feminine", "neuter", "singular", "plural",
          "common", "consonant", "consonants", "vowel", "vowels", "syllable", "syllables", "noun", "nouns", "verb",
          "verbs", "adjective", "adjectives", "pronoun", "pronouns", "preposition", "prepositions", "conjunction",
          "adverb", "interjection", "names", "like", "the like", "rest", "the rest", "verb stems", "stress",
          "accent", "accents", "using this guide", "gloss", "lemma", "transliteration", "manuscripts", "agreement",
          "perfect", "stepbible"}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Checker:
    def __init__(self, src=BG.SRC, built=None):
        self.problems = []
        self.src = src
        self.built = built

    def bad(self, kind, where, msg):
        self.problems.append((kind, f"{where}: {msg}"))

    # ------------------------------------------------------------ Bible spellings and verses
    _bible = None

    def bible(self):
        if Checker._bible:  # the Bible data is the same for every run (the self-test runs many)
            self.__dict__.update(Checker._bible)
            return
        books = load(os.path.join(DATA, "books.json"))
        self.books = {b["id"]: b for b in books}
        self.greek_forms, self.hebrew_forms, self.verses, self.form_codes = set(), set(), {}, {}
        self.codes = {"grc": [], "he": [], "arc": []}
        for b in books:
            d = load(os.path.join(DATA, "gnt" if b["lang"] == "grc" else "hot", f"{b['id']}.json"))
            for c, vs in d["ch"]:
                for v in vs:
                    self.verses[(b["id"], c, v[0])] = v[1]
                    for wi, w in enumerate(v[1]):
                        if b["lang"] == "grc":
                            self.greek_forms.add(BG.greek_key(w[0]))
                            self.form_codes.setdefault(("grc", BG.greek_key(w[0])), set()).add((w[4], w[3]))
                            self.codes["grc"].append((w[4], (b["id"], c, v[0], wi), w[3]))
                        else:
                            self.hebrew_forms.add(BG.hebrew_key(w[0].replace("/", "")))
                            self.form_codes.setdefault(("he", BG.hebrew_key(w[0].replace("/", ""))), set()).add((w[4], w[3]))
                            for part in w[0].split("/"):
                                self.hebrew_forms.add(BG.hebrew_key(part))
                            lang = "arc" if w[4].startswith("A") else "he"
                            self.codes[lang].append((w[4], (b["id"], c, v[0], wi), w[3]))
        self.by_name = {b["name"]: b["id"] for b in books}
        self.by_name["Psalm"] = "PSA"
        names = "|".join(sorted((re.escape(n) for n in self.by_name), key=len, reverse=True))
        self.ref_rx = re.compile(r"\b(" + names + r") (\d+):(\d+)(?:[–-](\d+(?::\d+)?))?")
        Checker._bible = {k: getattr(self, k) for k in ("books", "greek_forms", "hebrew_forms", "verses", "codes", "by_name", "ref_rx", "form_codes")}
        for lang, f in (("grc", "greek-index.json"), ("he", "hebrew-index.json")):
            for e in load(os.path.join(DATA, "lex", f)):
                if len(e) > 1:
                    (self.greek_forms if lang == "grc" else self.hebrew_forms).add(
                        BG.greek_key(e[1]) if lang == "grc" else BG.hebrew_key(e[1].replace("/", "")))

    # ------------------------------------------------------------ the checks
    def run(self):
        try:
            sections, entries = BG.read_sources(self.src)
            guide, ex = BG.build(self.src)
        except BG.SourceError as err:
            self.bad("build", "sources", str(err))
            return self.problems
        if self.src == BG.SRC:
            for name, obj in (("guide.json", guide), ("examples.json", ex)):
                path = os.path.join(ROOT, "guide", name)
                if not os.path.exists(path) or open(path, encoding="utf-8").read() != BG.dump(obj):
                    self.bad("build", f"guide/{name}", "out of date or edited by hand: run python3 tools/build_guide.py")
        self.bible()
        byid = {e["id"]: e for e in guide["entries"]}
        src_entry = {e["id"]: e for e in entries}
        lessons = {x["id"] for lang in ("grc", "he") for x in load(os.path.join(ROOT, "lessons", "index.json"))[lang] if x.get("file")}
        self.check_format(guide, src_entry)
        for sec in guide["sections"]:  # the introductions are prose too: spelling, numbers, plain English
            src_entry[f"section-{sec['id']}"] = {"file": "section intro", "unattested": [], "find": [], "examples": [], "counts": {}}
        self.intros = [{"id": f"section-{sec['id']}", "body": [{"p": p} for p in sec["intro"]], "short": "", "title": sec["title"]} for sec in guide["sections"]]
        self.check_links(guide, byid, lessons)
        self.check_text(guide, byid, src_entry)
        self.check_examples(guide, ex, src_entry)
        self.check_claims(guide, src_entry)
        self.check_matches(guide)
        self.check_respellings(guide, src_entry)
        return self.problems

    def texts(self, e):
        """(where, text) for every piece of an entry's prose, in reading order."""
        yield "short", e.get("short", "")
        for i, b in enumerate(e.get("body", [])):
            if "p" in b:
                yield f"paragraph {i + 1}", b["p"]
            elif "h" in b:
                yield f"heading {i + 1}", b["h"]
            elif "ul" in b:
                for j, x in enumerate(b["ul"]):
                    yield f"list {i + 1}.{j + 1}", x
            elif "table" in b:
                t = b["table"]
                yield f"table {i + 1} caption", t["caption"]
                for x in t["head"] + [c for r in t["rows"] for c in r]:
                    yield f"table {i + 1}", x

    def check_format(self, guide, src_entry):
        titles = {}
        for s in guide["sections"]:
            if not s["intro"]:
                self.bad("format", f"section {s['id']}", "no introduction")
            if not s["entries"]:
                self.bad("format", f"section {s['id']}", "no entries")
        for e in guide["entries"]:
            w = f"{src_entry[e['id']]['file']}: {e['id']}"
            if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", e["id"]):
                self.bad("format", w, "id: lower case words joined by hyphens")
            t = e["title"]
            if not t or not (t[0].isupper() or t[0].isdigit() or not t[0].isalpha() or re.match("[\u0370-\u03ff\u1f00-\u1fff\u05d0-\u05ea]", t)):
                self.bad("format", w, f"title should start with a capital: {t}")
            caps = [x for x in re.findall(r"[A-Za-z]+", t)[1:] if x[0].isupper()]
            if len(caps) >= 2 and len(caps) >= len(re.findall(r"[A-Za-z]+", t)) - 1:
                self.bad("format", w, f"title in Title Case, not sentence case: {t}")
            if t.lower() in titles:
                self.bad("format", w, f"same title as {titles[t.lower()]}")
            titles[t.lower()] = e["id"]
            short = BG_plain(e.get("short", ""))
            if not short:
                self.bad("format", w, "no one-line summary (short:)")
            elif not re.search(r"[.!?”’)]$", short):
                self.bad("format", w, "the summary should end a sentence")
            elif len(short.split()) > 45:
                self.bad("format", w, f"the summary is {len(short.split())} words: keep it to one short line or two")
            if not e.get("body"):
                self.bad("format", w, "no explanation after the summary")
            if e.get("lang", "") not in BG.LANGS:
                self.bad("format", w, f"unknown lang {e.get('lang')}")

    def check_links(self, guide, byid, lessons):
        routes = re.compile(r"^#/(today|learn|read(/[1-3]?[A-Z]{2,3}(/\d+){0,3})?|words(/[GH]\d+[A-Za-z]?)?|review|alphabet(/(grc|he))?|"
                            r"progress|media|settings|check|guide(/[a-z0-9-]+)?|lesson/(grc|he)/(grc|he)-\d+)$")
        for e in guide["entries"]:
            w = e["id"]
            for _, t in self.texts(e):
                for m in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", t):
                    target = m.group(1)
                    if target.startswith("#/"):
                        if not routes.match(target):
                            self.bad("links", w, f"no such screen {target}")
                    elif target not in byid:
                        self.bad("links", w, f"[[{target}]] links to no entry")
                    elif target == w:
                        self.bad("links", w, f"links to itself")
                for m in re.finditer(r"\[([1-3]?[A-Z]{2,3}) (\d+):(\d+)(?:\|[^\]]+)?\]", t):
                    if (m.group(1), int(m.group(2)), int(m.group(3))) not in self.verses:
                        self.bad("refs", w, f"no verse {m.group(1)} {m.group(2)}:{m.group(3)} in the app's Bible")
                if re.search(r"\[\[|\]\]", re.sub(r"\[\[[^\]]+\]\]", "", t)):
                    self.bad("links", w, "an unclosed [[ ]]")
            for s in e.get("see", []):
                if s not in byid:
                    self.bad("links", w, f"see: {s} is no entry")
                if s == w:
                    self.bad("links", w, "see: lists itself")
            if len(set(e.get("see", []))) != len(e.get("see", [])):
                self.bad("links", w, "see: lists an entry twice")
            for l in e.get("lessons", []):
                if l not in lessons:
                    self.bad("links", w, f"lessons: {l} is not a written lesson")

    def check_text(self, guide, byid, src_entry):
        terms = []  # (regex, ids, name) for every technical term an entry explains: the parts of its title
        for e in guide["entries"]:
            # the name before a colon, and any name in brackets: “Diaeresis: two dots” → diaeresis
            title = e["title"]
            names = [title.split(":")[0]] + re.findall(r"\(([^)]*)\)", title)
            for name in [x for n in names for x in re.split(r",| and |\(", re.sub(r"\(.*?\)", "", n))] + re.findall(r"\(([^)]*)\)", title):
                n = re.sub(r"^(the|a|an) ", "", name.strip().lower()).strip()
                if len(n) < 4 or n in COMMON or not re.search(r"[a-z]", n) or re.search(r"[^\w\s'-]", n) or len(n.split()) > 3:
                    continue
                terms.append((n, e["id"]))
        by_name = {}
        for n, tid in terms:
            by_name.setdefault(n, []).append(tid)
        lang_of = {e["id"]: e.get("lang", "") for e in guide["entries"]}
        terms = [(re.compile(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", re.I), ids, n) for n, ids in by_name.items()]
        for e in guide["entries"] + self.intros:
            w = f"{src_entry[e['id']]['file']}: {e['id']}"
            allowed = set(src_entry[e["id"]].get("unattested", []))
            seen_links = {e["id"]}  # an entry may name its own subject
            first_unlinked = {}
            for where, t in self.texts(e):
                plain = BG_plain(t)
                in_table = where.startswith("table")
                # spelling
                for lang, word, part in original_words(t):
                    if part or word in allowed:
                        continue
                    if lang == "grc" and BG.greek_key(word) not in self.greek_forms:
                        self.bad("spelling", w, f"Greek {word} is not written so anywhere in the Bible or dictionary")
                    if lang == "he" and BG.hebrew_key(word) not in self.hebrew_forms:
                        self.bad("spelling", w, f"Hebrew {word} is not written so anywhere in the Bible or dictionary")
                # numbers typed into the prose
                bare = re.sub(r"\[[1-3]?[A-Z]{2,3} \d+:\d+(\|[^\]]*)?\]|\{\{[a-z0-9-]+\}\}|\[\[[^\]]*\]\]", " ", t)
                # a reference written out (Mark 16:9–20) is allowed, if every verse it names exists
                def ref_ok(m):
                    bk = self.by_name[m.group(1)]
                    c, v = int(m.group(2)), int(m.group(3))
                    end = m.group(4)
                    ends = [(c, int(end))] if end and ":" not in end else [tuple(map(int, end.split(":")))] if end else []
                    for cc, vv in [(c, v)] + ends:
                        if (bk, cc, vv) not in self.verses:
                            self.bad("refs", w, f"no verse {m.group(1)} {cc}:{vv} in the app's Bible ({where})")
                    return " "
                bare = self.ref_rx.sub(ref_ok, bare)
                for m in re.finditer(r"(?<![\w-])\d[\d,.]*(?![\w])", bare):
                    tok = m.group(0).rstrip(".,")
                    if tok in FACTS or (e["id"] in CODE_ENTRIES and tok in ("1", "2", "3")):
                        continue
                    self.bad("numbers", w, f"a typed number “{tok}” in {where}: count it from the data ({{{{KEY}}}}) or add it to FACTS with its source")
                # plain English
                for m in LATIN.finditer(plain):
                    self.bad("plain", w, f"Latin abbreviation “{m.group(0)}”: write it out")
                for m in AMERICAN.finditer(plain):
                    if m.group(0).lower() not in AMERICAN_OK:
                        self.bad("plain", w, f"American spelling “{m.group(0)}”")
                for m in re.finditer(r"\b([A-Za-z]+) \1\b", plain, re.I):
                    if m.group(1).lower() not in ("that", "had"):
                        self.bad("plain", w, f"doubled word “{m.group(0)}”")
                for sent in re.split(r"(?<=[.!?:;])\s+", plain):
                    n = len(re.findall(r"[A-Za-zͰ-Ͽἀ-῿א-ת]+", sent))
                    if n > 40:
                        self.bad("plain", w, f"a sentence of {n} words in {where}: split it: {sent[:60]}…")
                # technical terms: linked the first time this entry uses them
                links = [(m.start(), m.end(), m.group(1)) for m in re.finditer(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", t)]
                own = t
                for part in re.split(r":|,| and |\(|\)", e.get("title", "")):  # the entry naming its own subject
                    if len(part.strip()) > 3:
                        own = re.sub(re.escape(part.strip()), lambda m: " " * len(m.group(0)), own, flags=re.I)
                for rx, ids, name in ([] if in_table or e["id"].startswith("section-") else terms):
                    if seen_links & set(ids) or name in first_unlinked:
                        continue
                    for m in rx.finditer(own):
                        inside = [l for l in links if l[0] <= m.start() < l[1]]
                        if inside:
                            break
                        if any(l[2] in ids and l[0] < m.start() for l in links):
                            break
                        # Greek or Hebrew word lists, names of tables, quotations of labels in quotation marks are fine
                        if re.search(r"“[^”]*$", t[:m.start()]):
                            continue
                        # the entry for this term in the entry's own language, if there is one
                        mine = [i for i in ids if lang_of[i] == e.get("lang", "")] or ids
                        first_unlinked[name] = (mine[0], where)
                        break
                for l in links:
                    seen_links.add(l[2])
            for name, (tid, where) in first_unlinked.items():
                self.bad("plain", w, f"uses “{name}” ({where}) before linking it: write [[{tid}|{name}]] the first time")

    def check_claims(self, guide, src_entry):
        """A word an entry's summary gives as an example of what it explains must, somewhere in the Bible, have the
        grammar the entry's find pattern describes (הִנֵּה was once given as a “demonstrative particle”; STEPBible
        labels it an interjection)."""
        for e in guide["entries"]:
            pats = src_entry[e["id"]]["find"]
            if not pats:
                continue
            short = e.get("short", "")
            # each run of Greek or Hebrew (a word, or words side by side such as μὴ γένοιτο) is one example; a word
            # after “from” is the dictionary form it comes from, not an example
            runs = re.findall(r"(?<!from )(?<![\u0370-\u03ff\u1f00-\u1fff\u05d0-\u05ea\u0591-\u05c7\u0300-\u036f])((?:[\u0370-\u03ff\u1f00-\u1fff\u05d0-\u05ea][^\sA-Za-z,“”;:()]*[\s\u05be]*)+)", short)
            for run in runs:
                words = [w for w in original_words(run) if not w[2]]
                checked = [self.claim_ok(lang, word, pats) for lang, word, _ in words]
                if checked and all(c is not None for c in checked) and not any(c[0] for c in checked):
                    self.bad("claims", e["id"], f"the summary gives {run.strip()} as an example, but in the Bible it never has this grammar "
                             f"({', '.join(sorted({x for c in checked for x in c[1]})[:4])})")

    def claim_ok(self, lang, word, pats):
        """(True/False, codes found) for one word, or None if the word isn't in the text as written."""
        if True:
            if True:
                key = (lang, BG.greek_key(word) if lang == "grc" else BG.hebrew_key(word))
                found = self.form_codes.get(key)
                if not found:
                    return None  # a dictionary form or a textbook form: nothing in the text to compare
                ok = False
                for code, keys in found:
                    for p in pats:
                        if p["pattern"].startswith("flag="):
                            ok = True
                        elif p["pattern"].startswith("key="):
                            ks = re.findall(r"\{([GH]\d{4,5}[A-Za-z]?)\}", keys) if lang != "grc" else keys.split("+")
                            ok = ok or any(re.search(p["pattern"][4:], k) for k in ks)
                        elif (p["lang"] == "grc") == (lang == "grc"):
                            parts = code.split("+") if lang == "grc" else [code[1:]]
                            ok = ok or any(re.search(p["pattern"], c) for c in parts)
                return ok, {c for c, _ in found}

    def check_examples(self, guide, ex, src_entry):
        bsb_cache = {}
        for e in guide["entries"]:
            w = e["id"]
            pats = src_entry[w]["find"]
            for x in ex["examples"].get(w, []):
                key = (x["book"], x["ch"], x["v"])
                words = self.verses.get(key)
                if words is None:
                    self.bad("examples", w, f"{x['ref']}: no such verse")
                    continue
                if words != x["words"]:
                    self.bad("examples", w, f"{x['ref']}: the verse's words differ from the Bible data")
                if not 0 <= x["wi"] < len(words):
                    self.bad("examples", w, f"{x['ref']}: no word {x['wi']}")
                    continue
                if (x["book"], x["ch"]) not in bsb_cache:
                    bsb_cache[(x["book"], x["ch"])] = bsb_verses(load(os.path.join(DATA, "bsb", f"{x['book']}.json")), x["ch"])
                if bsb_cache[(x["book"], x["ch"])].get(x["v"], "") != x["english"]:
                    self.bad("examples", w, f"{x['ref']}: the English is not the BSB's verse")
                named = [s for s in src_entry[w]["examples"] if (s["book"], s["ch"], s["v"]) == key]
                if not named and pats:
                    code = words[x["wi"]][4]
                    lang = "grc" if x["lang"] == "grc" else ("arc" if code.startswith("A") else "he")
                    ok = False
                    for p in pats:
                        if p["pattern"].startswith("key="):
                            raw = words[x["wi"]][3]
                            ks = re.findall(r"\{([GH]\d{4,5}[A-Za-z]?)\}", raw) if lang != "grc" else raw.split("+")
                            ok = ok or any(re.search(p["pattern"][4:], k) for k in ks)
                        elif p["lang"] == lang:
                            parts = code.split("+") if lang == "grc" else [code[1:]]
                            ok = ok or any(re.search(p["pattern"], c) for c in parts)
                    raw = words[x["wi"]][3]
                    ks = re.findall(r"\{([GH]\d{4,5}[A-Za-z]?)\}", raw) if x["lang"] != "grc" else raw.split("+")
                    for p in pats:
                        if p.get("key") and not any(re.search(p["key"], k) for k in ks) and len(pats) == 1:
                            ok = False
                        if p.get("nokey") and any(re.search(p["nokey"], k) for k in ks) and len(pats) == 1:
                            ok = False
                    if not ok:
                        self.bad("examples", w, f"{x['ref']} {words[x['wi']][0]}: its grammar {code} or entry doesn't match the entry's find")
                    # a picked example's word must make sense on its own (checked here independently of the builder)
                    gl = str(words[x["wi"]][2] if len(words[x["wi"]]) > 2 else "").strip()
                    if not gl or re.fullmatch(r"(\[[^\]]*\]\s*)?<[^>]*>(\s*\[[^\]]*\])?", gl):
                        self.bad("examples", w, f"{x['ref']} {words[x['wi']][0]}: its English “{gl}” isn't translated, so it explains nothing on its own")
                    prev = words[x["wi"] - 1] if x["wi"] else None
                    if prev and w not in ("negative", "prohibition"):
                        pc = prev[4] if len(prev) > 4 else ""
                        if (x["lang"] == "grc" and "PRT-N" in pc.split("+")) or (x["lang"] != "grc" and pc.endswith("Tn")):
                            self.bad("examples", w, f"{x['ref']} {words[x['wi']][0]}: comes straight after “not”, so its English on its own says the opposite")
                    if any(f"{x['book']}{x['ch']}:{x['v']}" in p.get("avoid", []) for p in pats):
                        self.bad("examples", w, f"{x['ref']}: picked although the entry says to avoid it")
                    if AVOID.search(x["english"]):
                        self.bad("examples", w, f"{x['ref']}: a verse a beginner shouldn't meet as a grammar example ({AVOID.search(x['english']).group(0)})")
                if len(words[x["wi"]]) > 6 and words[x["wi"]][6] in ("k", "x"):
                    self.bad("examples", w, f"{x['ref']}: the example word is not read aloud or not in Leningrad")
            # counts, recounted here
            for c, p in zip(e.get("count", []), pats):
                n = self.recount(p["lang"], p["pattern"], p.get("key"), p.get("nokey"))
                if n != c["n"]:
                    self.bad("examples", w, f"count for {p['lang']} {p['pattern']} says {c['n']}, recounted {n}")
            for key, val in (e.get("counts") or {}).items():
                spec = src_entry[w]["counts"][key]
                n = self.recount(spec["lang"], spec["pattern"])
                if val != f"{n:,}":
                    self.bad("examples", w, f"{{{{{key}}}}} says {val}, recounted {n:,}")
            if pats and not ex["examples"].get(w):
                self.bad("examples", w, "has a find pattern but no examples were picked")
            used = set(re.findall(r"\{\{([a-z0-9-]+)\}\}", json.dumps([e.get("short"), e.get("body")], ensure_ascii=False)))
            for key in used - set(e.get("counts") or {}):
                self.bad("numbers", w, f"{{{{{key}}}}} has no count: line")

    # ------------------------------------------------------------ respellings written in the prose
    RESPELL = re.compile(r"(?:, “[^”]*”,? is said |, | is said | is | \()((?:[a-zA-Z']+-)*[a-zA-Z']+(?: (?:[a-zA-Z']+-)*[a-zA-Z']+)?)(?=, “|,? “|\)|[,;.:]|$)")

    def known_says(self):
        """What the app already says for a written Hebrew word: the word lists and every lesson and Letters card."""
        if getattr(Checker, "_says", None) is not None:
            return Checker._says
        says = {}
        for r in load(os.path.join(DATA, "decks", "hebrew.json"))["words"]:
            if r[4]:
                says.setdefault(BG.hebrew_key(r[1]), set()).add(r[4])

        def walk(x):
            if isinstance(x, dict):
                t, say = x.get("t") or x.get("he"), x.get("say")
                if isinstance(t, str) and isinstance(say, str) and HEBREW_WORD.fullmatch(t.strip()):
                    says.setdefault(BG.hebrew_key(t.strip()), set()).add(say)
                for y in x.values():
                    walk(y)
            elif isinstance(x, list):
                for y in x:
                    walk(y)
        for d, _, files in os.walk(os.path.join(ROOT, "lessons", "he")):
            for f in files:
                if f.endswith(".json"):
                    walk(load(os.path.join(d, f)))
        walk(load(os.path.join(ROOT, "lessons", "alphabet", "he.json")))
        Checker._says = says
        return says

    def respellings(self, text):
        """(lang, word, respelling) wherever the prose gives a word's sound: “בְּרִית, be-RIT, …”, “שָׁמְרוּ is sha-me-RU”."""
        s = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text).replace("*", "")
        out = []
        for rx, lang in ((GREEK_WORD, "grc"), (HEBREW_WORD, "he")):
            for m in rx.finditer(s):
                word = m.group(0)
                if s[m.start() - 1:m.start()] == "\u05be":  # the second word of a maqqef phrase: read with the first
                    continue
                if lang == "he":  # a maqqef phrase: כָּל־הָאָרֶץ, kol ha-A-rets
                    j = m.end()
                    while j < len(s) and s[j] == "\u05be":
                        n = rx.match(s, j + 1)
                        if not n:
                            break
                        j = n.end()
                    word = s[m.start():j]
                r = self.RESPELL.match(s, m.start() + len(word))
                if not r:
                    continue
                say = r.group(1)
                after = s[r.end():r.end() + 3]
                # a respelling has syllables joined by hyphens (not letters spelt out, Y-H-W-H), or is one short
                # lower-case syllable followed by the word's meaning in quotes (καί, kai, “and”)
                parts = re.split("[- ]", say)
                if "-" in say:
                    if all(len(x) == 1 and x.isupper() for x in parts):
                        continue
                elif not (say.islower() and len(say) <= 5 and after.startswith((", “", " “")) and say not in {"and", "or", "is", "the", "a", "see", "not", "in", "for", "to", "of"}):
                    continue
                out.append((lang, word, say))
        return out

    def check_respellings(self, guide, src_entry):
        """Every respelling in the prose is the one the app gives: Greek = greekSay (js/sound.js), Hebrew = the word
        lists' and lessons' respelling of the same pointed word; Hebrew writes i and u (never ee, oo) and marks the
        stressed syllable of a longer word in capitals."""
        import subprocess
        found = []
        for e in guide["entries"] + self.intros:
            w = f"{src_entry[e['id']]['file']}: {e['id']}"
            for where, t in self.texts(e):
                for lang, word, say in self.respellings(t):
                    found.append((w, lang, word, say))
        greek = [x for x in found if x[1] == "grc"]
        if greek:
            out = subprocess.run(["node", os.path.join(ROOT, "tools", "greek_say.mjs")], input="\n".join(x[2] for x in greek),
                                 capture_output=True, text=True)
            if out.returncode:
                self.bad("respell", "tools/greek_say.mjs", out.stderr.strip()[:300])
            else:
                for (w, _, word, say), want in zip(greek, out.stdout.split("\n")):
                    if say != want:
                        self.bad("respell", w, f"{word} is respelt {say}, but the app says {want}")
        says = self.known_says()
        for w, lang, word, say in found:
            if lang != "he":
                continue
            if re.search(r"ee|oo", say, re.I):
                self.bad("respell", w, f"{word} is respelt {say}: Hebrew respellings write i and u, not ee and oo")
            for part in say.split():
                if part.count("-") and sum(1 for x in part.split("-") if x.isupper()) != 1 and not re.search(r"[A-Z]", say.replace(part, "")):
                    self.bad("respell", w, f"{word} is respelt {say}: mark the stressed syllable in capitals, once")
            want = says.get(BG.hebrew_key(word.replace("\u05be", "")))

            def single(x):  # a doubled letter may be shown across the hyphen (hash-sha) or not (ha-sha)
                return re.sub(r"(sh|ch|kh|ts|[a-z])-(?=\1)", "-", x, flags=re.I)
            if want and single(say) not in {single(x) for x in want}:
                self.bad("respell", w, f"{word} is respelt {say}, but the word lists or lessons say {' or '.join(sorted(want))}")
        self.respell_count = len(found)

    def recount(self, lang, pattern, key=None, nokey=None):
        if key or nokey:  # word by word: the dictionary entry decides as well as the grammar
            krx, nrx = re.compile(key) if key else None, re.compile(nokey) if nokey else None
            n = 0
            for code, _, raw in self.codes[lang]:
                ks = re.findall(r"\{([GH]\d{4,5}[A-Za-z]?)\}", raw) if lang != "grc" else raw.split("+")
                if krx and not any(krx.search(k) for k in ks):
                    continue
                if nrx and any(nrx.search(k) for k in ks):
                    continue
                if pattern.startswith("key="):
                    n += any(re.search(pattern[4:], k) for k in ks)
                else:
                    parts = code.split("+") if lang == "grc" else [code[1:]]
                    n += any(re.search(pattern, c) for c in parts)
            return n
        n = 0
        if pattern.startswith("flag="):
            for code, (bk, c, v, wi), _ in self.codes[lang]:
                w = self.verses[(bk, c, v)][wi]
                n += len(w) > 6 and w[6] == pattern[5:]
            return n
        if pattern.startswith("key="):
            rx = re.compile(pattern[4:])
            for code, _, keys in self.codes[lang]:
                ks = re.findall(r"\{([GH]\d{4,5}[A-Za-z]?)\}", keys) if lang != "grc" else keys.split("+")
                n += any(rx.search(k) for k in ks)
            return n
        rx = re.compile(pattern)
        if not hasattr(self, "_code_counts"):
            self._code_counts = {}
        if lang not in self._code_counts:
            cc = {}
            for code, _, _ in self.codes[lang]:
                cc[code] = cc.get(code, 0) + 1
            self._code_counts[lang] = cc
        for code, k in self._code_counts[lang].items():
            parts = code.split("+") if lang == "grc" else [code[1:]]
            n += k if any(rx.search(p) for p in parts) else 0
        return n

    def check_matches(self, guide):
        seen = {}
        for e in guide["entries"]:
            for m in e.get("match", []):
                phrase = re.sub(r"[(),:]", " ", m.split("=")[0].lower())
                phrase = " ".join(phrase.split())
                lang = e.get("lang") or "both"
                key = (phrase, lang)
                if key in seen and seen[key] != e["id"]:
                    self.bad("matches", e["id"], f"“{phrase}” is also matched by {seen[key]} for the same language")
                seen[key] = e["id"]


GREEK_WORD = re.compile("[Ͱ-Ͽἀ-῿][Ͱ-Ͽἀ-῿̀-ͯ’᾽]*")
HEBREW_WORD = re.compile("[א-ת][֑-ֽֿ-ׇא-ת]*")


def is_letters(lang, word):
    """Letters or a pair of letters named in the text (η, ει, σα, ח), not a word: no accent, breathing or vowel point."""
    if lang == "grc":
        return len(word) <= 1 or (len(word) <= 3 and not re.search("[\u0300-\u036f]", unicodedata.normalize("NFD", word)))
    return not re.search("[\u05b0-\u05bb\u05c7]", word)  # a root (קדשׁ): letters with no vowels


def original_words(text):
    """(lang, word, part) for every Greek and Hebrew word in a text, as js/guide-text.js finds them; part is true for
    an ending or stem written with a hyphen, and for letters named on their own."""
    s = re.sub(r"\[\[([^\]|]+)\|", "[[", text)  # link targets are ids, not words
    out = []
    for m in GREEK_WORD.finditer(s):
        word = re.sub("[;·]+$", "", m.group(0))
        before, after = s[m.start() - 1:m.start()], s[m.end():m.end() + 1]
        if word:
            out.append(("grc", word, before == "-" or after == "-" or is_letters("grc", word)))
    for m in HEBREW_WORD.finditer(s):
        before = re.sub("[\u0591-\u05c7]+$", "", s[:m.start()])[-1:]  # -ַיִם: the hyphen comes before the first vowel
        after = s[m.end():m.end() + 1]
        out.append(("he", m.group(0), before == "-" or after == "-" or is_letters("he", m.group(0))))
    return out


def BG_plain(text):
    s = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", str(text or ""))
    s = re.sub(r"\[\[([^\]]+)\]\]", lambda m: m.group(1).replace("-", " "), s)
    s = re.sub(r"\[([1-3]?[A-Z]{2,3}) (\d+):(\d+)\|([^\]]+)\]", r"\4", s)
    s = re.sub(r"\[([1-3]?[A-Z]{2,3}) (\d+):(\d+)\]", r"\1 \2:\3", s)
    return s.replace("*", "")


def report(problems, title="Guide check"):
    kinds = {}
    for k, msg in problems:
        kinds.setdefault(k, []).append(msg)
    for k, msgs in sorted(kinds.items()):
        print(f"\n{k}: {len(msgs)}")
        for m in msgs[:60]:
            print("  ", m)
        if len(msgs) > 60:
            print(f"   … and {len(msgs) - 60} more")
    print(f"\n{title}: {len(problems)} problems")


# ---------------------------------------------------------------- self-test
PLANTS = [
    ("links", "[[aorist]]", "[[aorists-nowhere]]"),
    ("spelling", "λόγος", "λογός"),
    ("numbers", "Most of them never change their ending", "Most of them, 37 in all, never change their ending"),
    ("refs", "[JHN 1:1]", "[JHN 1:99]"),
    ("plain", "Greek has five cases:", "Greek has five cases, e.g. these:"),
    ("plain", "for each set of verb forms", "for each set of verb forms, which we analyze"),
    ("format", "## nominative | Nominative", "## nominative | Nominative Case Ending"),
    ("matches", "match: genitive=the “of” case", "match: genitive=the “of” case; nominative"),
    ("build", "> ACT 13:38 ἠδυνήθητε", "> ACT 13:39 ἠδυνήθητε"),
    ("plain", "In the [[indicative]] the aorist has an", "In the indicative the aorist has an"),
    ("claims", "nd: נֵלְכָה, “let us go”.", "nd: נַעֲשֶׂה, “let us make”."),
    ("respell", "אֶרֶץ, E-rets", "אֶרֶץ, e-RETS"),
    ("respell", "οὐρανός, oo-ra-NOS", "οὐρανός, oo-RA-nos"),
    ("respell", "בְּרִית, be-RIT, “covenant”", "בְּרִית, be-REET, “covenant”"),
]


def self_test():
    ok = 0
    for kind, old, new in PLANTS:
        tmp = tempfile.mkdtemp()
        try:
            for name in os.listdir(BG.SRC):
                shutil.copy(os.path.join(BG.SRC, name), tmp)
            hit = None
            for name in sorted(os.listdir(tmp)):
                p = os.path.join(tmp, name)
                s = open(p, encoding="utf-8").read()
                if old in s:
                    open(p, "w", encoding="utf-8").write(s.replace(old, new, 1))
                    hit = name
                    break
            if not hit:
                print(f"  ?    plant not placed (text moved?): {old[:40]}")
                continue
            found = [p for p in Checker(tmp).run() if p[0] == kind]
            base = [p for p in BASE if p[0] == kind]
            caught = len(found) > len(base) or (kind == "build" and found)
            ok += bool(caught)
            print(f"  {'pass' if caught else 'FAIL'} {kind}: {new[:50]}")
        finally:
            shutil.rmtree(tmp)
    print(f"{ok}/{len(PLANTS)} passed")
    return ok == len(PLANTS)


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        BASE = Checker(BG.SRC).run()
        BASE = [p for p in BASE if p[0] != "build"]
        sys.exit(0 if self_test() else 1)
    probs = Checker().run()
    report(probs)
    sys.exit(1 if probs else 0)
