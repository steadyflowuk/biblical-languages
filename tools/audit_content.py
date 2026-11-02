"""Content audit: the kinds of mistake that passed every functional test before and were only caught by people or a
reviewer reading the app. Each check below is named after the mistake it guards against. Run from the repo root:

    python3 tools/audit_content.py            # everything (needs the local server on :8765 for the page checks)
    python3 tools/audit_content.py --static   # file checks only (no browser)

Exit code 0 = no problems. tools/check_all.py runs this as part of the full check.
"""
import asyncio, datetime, glob, json, os, re, subprocess, sys, unicodedata
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
BASE = "http://localhost:8765/"
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
problems = defaultdict(list)   # section -> [problem]
passed = []


def check(section, name, bad):
    """bad: list of problem strings (empty = pass)."""
    if bad:
        problems[section] += [f"{name}: {b}" for b in bad[:12]] + ([f"{name}: … {len(bad) - 12} more"] if len(bad) > 12 else [])
        print(f"FAIL [{section}] {name} ({len(bad)})")
        for b in bad[:6]:
            print("     ", b)
    else:
        passed.append(name)
        print(f"PASS [{section}] {name}")


def load(p):
    return json.load(open(p, encoding="utf-8"))


def read(p):
    return open(p, encoding="utf-8").read()


def books():
    return load("data/books.json")


def greek_verses():
    for b in books():
        if b["lang"] == "grc":
            for c, vs in load(f"data/gnt/{b['id']}.json")["ch"]:
                for v in vs:
                    yield b["id"], c, v


USER_TEXT = sorted(glob.glob("js/*.js") + glob.glob("lessons/**/*.json", recursive=True) + ["index.html", "manifest.webmanifest"])
USER_TEXT = [p for p in USER_TEXT if "/vendor/" not in p]


def visible_strings(path):
    """Text a user can read: JSON string values, or JS string/template literals and HTML text (not code, not CSS)."""
    src = read(path)
    if path.endswith(".json"):
        out = []
        def walk(o):
            if isinstance(o, str):
                out.append(o)
            elif isinstance(o, dict):
                for k, v in o.items():
                    if k not in ("href", "file", "ref", "k", "id", "type", "step", "video"):
                        walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(json.loads(src))
        return out
    src = re.sub(r"^\s*//.*$|/\*[\s\S]*?\*/", "", src, flags=re.M)  # comments aren't shown
    lits = re.findall(r"`((?:[^`\\]|\\.)*)`|\"((?:[^\"\\\n]|\\.)*)\"|'((?:[^'\\\n]|\\.)*)'", src)
    out = []
    for t in ("".join(x) for x in lits):
        t = re.sub(r"<[^>]*>|\$\{[^}]*\}", " ", t)                       # tags and ${…} out
        if re.search(r"[a-z]{3,}\s+[a-z]{3,}", t, re.I):                  # looks like words, not a selector or key
            out.append(t)
    return out


# ================================================================ 1. Copyright and licences
def audit_copyright():
    S = "copyright"
    # 1a. No Nestle-Aland or Online Bible wording shown to the user
    bad = []
    for p in USER_TEXT:
        for t in visible_strings(p):
            for m in re.finditer(r"NA28|NA27|Nestle|Aland|Online ?Bible|Larry Pierce|LSB|Legacy Standard|NASB|NIV\b|\bNKJV|Logos text", t):
                bad.append(f"{p}: …{t[max(0, m.start() - 40):m.end() + 40]}…")
    check(S, "no Nestle-Aland / Online Bible / copyrighted-translation names in app text", bad)

    # 1b. Hebrew definitions must be Strong's (public domain), never STEPBible's Online Bible "Meaning" outlines
    bad = []
    for p in glob.glob("data/lex/H/*.json"):
        for k, e in load(p).items():
            d = e[4] if len(e) > 4 else ""
            if re.search(r"(^|<br />)\s*1[a-z]?\)|\b2[a-z]\)", d) or "Also means" in d:
                bad.append(f"{k}: {re.sub('<[^>]+>', '', d)[:80]}")
    check(S, "Hebrew definitions are Strong's, not Online Bible's outline", bad)

    # 1c. Every source fetched by tools/fetch_sources.sh is credited in Settings › About and the README
    about = read("js/screens.js")
    readme = read("README.md")
    credit = {"STEPBible-Data": "STEPBible", "LXX-Swete-1930": "Swete", "HebrewLexicon": "Open Scriptures",
              "SBLGNT": "SBL Greek New Testament", "communityofbrothers": "Berean Standard Bible"}
    bad = []
    for url in re.findall(r"https://github.com/\S+", read("tools/fetch_sources.sh")):
        name = url.rstrip("/").split("/")[-1]
        if name == "morphhb":
            continue  # used only by tools/check_data.py, not shipped
        want = credit.get(name) or credit.get(url.split("/")[3])
        if not want:
            bad.append(f"{url}: no expected credit known — add it to audit_content.py and to the credits")
            continue
        for where, text in (("Settings › About", about), ("README", readme)):
            if want not in text:
                bad.append(f"{name}: '{want}' missing from {where}")
    for phrase in ("copyright 2010 Society of Biblical Literature and Logos Bible Software", "creativecommons.org/licenses/by/4.0"):
        if phrase not in about:
            bad.append(f"Settings › About lacks '{phrase}'")
    check(S, "every shipped source credited (About + README), SBL copyright line, licence links", bad)

    # 1d. GPL Septuagint folder keeps its licence and notice; fonts and FSRS keep theirs
    bad = [p for p in ("data/lxx/LICENSE", "data/lxx/README.md", "assets/fonts/LICENSES.txt", "js/vendor/ts-fsrs.LICENSE")
           if not os.path.exists(p)]
    check(S, "licence files kept beside GPL/OFL/MIT material", bad)

    # 1e. No ESV API key (or any 40-hex token) committed
    bad = []
    for p in subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split():
        if p.startswith(("data/", "assets/")) or p.endswith((".png", ".woff")):
            continue
        try:
            t = read(p)
        except Exception:
            continue
        if re.search(r"Token\s+[0-9a-f]{40}|\b[0-9a-f]{40}\b(?!.*sha)", t) and "ts-fsrs" not in p:
            bad.append(p)
    check(S, "no API key or token committed", bad)

    # 1f. ESV text only from the API: no ESV verse text stored in the repo
    bad = [p for p in glob.glob("data/**/*.json", recursive=True) if "esv" in p.lower()]
    check(S, "no ESV text in data/", bad)


# ================================================================ 2. The Bible data (beyond tools/check_data.py)
def audit_data():
    S = "data"
    # 2a. Greek words: transliteration present, its capital follows the Greek, no TAGNT "ēa" for ῃ, English present
    bad_case, bad_sub, bad_en, bad_tr = [], [], [], []
    for bk, c, v in greek_verses():
        for w in v[1]:
            ref = f"{bk} {c}:{v[0]} {w[0]}"
            tr = w[1] if len(w) > 1 else ""
            first = next((x for x in w[0] if x.isalpha()), "")
            if not tr:
                bad_tr.append(ref)
            elif first and tr[0].isalpha() and tr[0].isupper() != first.isupper():
                bad_case.append(f"{ref} → {tr}")
            if re.search("[ηω]ͅ", unicodedata.normalize("NFD", w[0])) and re.search("[ēō]a$", tr):
                bad_sub.append(f"{ref} → {tr}")
            if len(w) < 3 or not w[2].strip():
                bad_en.append(ref)
    check(S, "Greek: every word has a transliteration", bad_tr)
    check(S, "Greek: transliteration capitals follow the Greek", bad_case)
    check(S, "Greek: iota under η/ω not transliterated as 'a' (τῇ ≠ tēa)", bad_sub)
    check(S, "Greek: every word has English for this verse", bad_en)

    # 2b. Today's verses: each word complete, text identical to the Reader's, joined words carry both parts
    gtext = {}
    for bk, c, v in greek_verses():
        gtext[(bk, c, v[0])] = [w[0] for w in v[1]]
    bad = []
    for x in load("data/votd.json"):
        bk, c, vs = x["id"].split("-")
        for w in x["words"]:
            for f in ("t", "lemma", "gloss", "parse", "en", "k"):
                if not str(w.get(f, "")).strip():
                    bad.append(f"{x['ref']} {w.get('t')}: no {f}")
        if x["lang"] == "grc":
            if [w["t"] for w in x["words"]] != gtext.get((bk, int(c), int(vs))):
                bad.append(f"{x['ref']}: words differ from data/gnt")
            words = next(v[1] for b2, c2, v in greek_verses() if b2 == bk and c2 == int(c) and v[0] == int(vs))
            for w, src in zip(x["words"], words):
                if "+" in str(src[3]) and not w.get("parts"):
                    bad.append(f"{x['ref']} {w['t']}: joined word without its parts")
    check(S, "Today's verses complete and identical to the Bible text", bad)

    # 2c. Built-in fallback verses (js/verses.js) match the data word for word
    src = read("js/verses.js")
    bad = []
    for vid, ref in (("john-1-1", ("JHN", 1, 1)), ("gen-1-1", ("GEN", 1, 1))):
        block = src[src.index(f'id: "{vid}"'):]
        block = block[:block.index("focus:")]
        ts = re.findall(r'\{ t: "([^"]+)"', block)
        folder = "gnt" if ref[0] == "JHN" else "hot"
        d = load(f"data/{folder}/{ref[0]}.json")
        data_words = [w[0].replace("/", "") for ch in d["ch"] if ch[0] == ref[1] for v in ch[1] if v[0] == ref[2] for w in v[1]]
        if ts != data_words:
            bad.append(f"{vid}: {' '.join(ts)} ≠ {' '.join(data_words)}")
    check(S, "built-in verses (js/verses.js) match the data", bad)

    # 2d. Hebrew definitions: clean markup, spacing, links only to entries that exist
    keys = {r[0] for r in load("data/lex/hebrew-index.json")}
    nums = {re.sub(r"[A-Z]$", "", k) for k in keys}
    bad_markup, bad_link = [], []
    for p in glob.glob("data/lex/H/*.json"):
        for k, e in load(p).items():
            d = e[4] if len(e) > 4 else ""
            if re.search(r"<(?!/?(b|i)>|br />)[^>]*>|\s[,;.]|\(\s*\)|&[a-z]+;", d):
                bad_markup.append(f"{k}: {d[:90]}")
            for ref in re.findall(r"\bH\d{4}\b", d):
                if ref not in nums and ref not in keys:
                    bad_link.append(f"{k} → {ref}")
    check(S, "Hebrew definitions: no stray markup or spacing", bad_markup)
    check(S, "Hebrew definitions: every mentioned entry exists", bad_link)

    # 2e. Search keywords free of labels and boilerplate
    bad = []
    for name in ("greek", "hebrew"):
        for r in load(f"data/lex/{name}-index.json"):
            if len(r) > 5 and re.search(r"\b(kjv|origin|translated|primitive|figurative|compare)\b", str(r[5])):
                bad.append(f"{r[0]}: {r[5]}")
    check(S, "dictionary search keywords hold no labels or boilerplate", bad)

    # 2f. Numbers quoted in the app's text agree with the data
    deck = {l: load(f"data/decks/{n}.json") for l, n in (("grc", "greek"), ("he", "hebrew"))}
    bad = []
    for p in glob.glob("js/*.js") + glob.glob("tools/test_*.py"):
        for m in re.finditer(r"(\d{3}) (?:most common Greek words|words appear 50 times)", read(p)):
            if int(m.group(1)) != len(deck["grc"]["words"]):
                bad.append(f"{p}: says {m.group(1)}, the Greek list has {len(deck['grc']['words'])}")
        for m in re.finditer(r"(\d{3}) most common Hebrew words", read(p)):
            if int(m.group(1)) != len(deck["he"]["words"]):
                bad.append(f"{p}: says {m.group(1)}, the Hebrew list has {len(deck['he']['words'])}")
    check(S, "word-list sizes quoted in the app match the lists", bad)

    # 2g. Lesson review words still in the dictionary, with the meaning the lesson gives sensible (not empty)
    idx = {r[0] for n in ("greek", "hebrew") for r in load(f"data/lex/{n}-index.json")}
    bad = []
    for p in glob.glob("lessons/*/*.json"):
        L = load(p)
        for st in L.get("steps", []):
            for c in st["cards"]:
                for w in c.get("items", []) if c.get("type") == "words" else []:
                    if w.get("k") and w["k"] not in idx:
                        bad.append(f"{L['id']}: {w.get('t')} key {w['k']} not in the dictionary")
                    if not str(w.get("en", "")).strip():
                        bad.append(f"{L['id']}: {w.get('t')} has no meaning")
    check(S, "lesson review words exist in the dictionary and have meanings", bad)


# ================================================================ 3. Wording
AMERICAN = r"\b(\w+iz(e|es|ed|ing|ation)|colou?r(?<!colour)s?|center(s|ed)?|honor(s|ed)?|favor(ite|s)?|behavior|neighbor|labor|savior|gray|catalog|traveled|traveling|judgment|toward|fulfill|fulfillment|analyze|license(?=d? (to|by))|defense|offense|program(?!me))\b"
ALLOWED_AMERICAN = {"organize", "Organize"}  # none needed so far


def audit_wording():
    S = "wording"
    bad_us, bad_double, bad_case = [], [], []
    for p in USER_TEXT:
        for t in visible_strings(p):
            for m in re.finditer(AMERICAN, t, re.I):
                w = m.group(0)
                if w in ALLOWED_AMERICAN or w.lower() in ("color", "center", "size") and re.search(w + r"\s*:", t):
                    continue
                if w.lower() in ("authorization", "normalize", "autocapitalize", "license"):
                    continue
                if w[0].isupper() and re.search(r"[A-Z][a-z]+\s+$", t[:m.start()]):
                    continue  # part of a name (Biblical Language Center)
                bad_us.append(f"{p}: '{w}' in …{t[max(0, m.start() - 30):m.end() + 30]}…")
            if re.fullmatch(r"[\w\s-]+", t) and not re.search(r"[A-Z.,]", t):
                continue  # a class list such as "toast toast-warn", not words
            for m in re.finditer(r"\b(\w{2,})\s+\1\b", t):
                if m.group(1).lower() not in ("ha", "no", "that", "had", "amen", "ἀμὴν", "very"):
                    bad_double.append(f"{p}: '{m.group(0)}'")
    check(S, "British spelling in app text", bad_us)
    check(S, "no doubled words in app text", bad_double)

    # Headings and button labels in sentence case (no Title Case Like This)
    bad = []
    for p in glob.glob("js/*.js"):
        for m in re.finditer(r"<(h1|h2|h3|button)[^>]*>([^<${]{6,})<", read(p)):
            words = [w for w in m.group(2).split() if w[:1].isalpha()]
            caps = [w for w in words[1:] if w[0].isupper() and w not in ("Greek", "Hebrew", "Aramaic", "Bible", "BSB", "ESV",
                    "SBL", "Septuagint", "Strong's", "Erasmian", "Koine", "Restored", "English", "Old", "New", "Testament", "I")]
            if len(caps) >= 2 and not re.search(r"English Standard Version|Berean Standard Bible|Septuagint", m.group(2)):
                bad.append(f"{p}: {m.group(2).strip()}")
    check(S, "headings and buttons in sentence case", bad)


# ================================================================ 4. The app shell and code
def audit_shell():
    S = "shell"
    sw = read("sw.js")
    files = re.findall(r'^\s*"([^"]+)",?$', sw[sw.index("SHELL_FILES"):sw.index("];", sw.index("SHELL_FILES"))], re.M)
    bad = [f for f in files if f != "./" and not os.path.exists(f)]
    for p in glob.glob("lessons/**/*.json", recursive=True) + glob.glob("js/*.js") + glob.glob("js/vendor/*.js") + glob.glob("css/*.css"):
        if p not in files:
            bad.append(f"{p} not in SHELL_FILES")
    check(S, "SHELL_FILES complete and every listed file exists", bad)

    # Data cache name used the same way everywhere
    m = re.search(r'const DATA = "([^"]+)"', sw)
    name = m.group(1) if m else "?"
    bad = []
    for p in glob.glob("js/*.js") + glob.glob("tools/*.py"):
        for other in set(re.findall(r"['\"](data-v\d+)['\"]", read(p))):
            if other != name:
                bad.append(f"{p} uses {other}, sw.js uses {name}")
    if "k.startsWith(\"data-\") && k !== DATA" not in sw:
        bad.append("sw.js activate doesn't delete old data caches")
    check(S, "one data cache name everywhere; old ones deleted on update", bad)

    # VERSION changed whenever shipped files changed since the live version (origin/main)
    bad = []
    try:
        live = subprocess.run(["git", "show", "origin/main:sw.js"], capture_output=True, text=True).stdout
        live_v = re.search(r'VERSION = "([^"]+)"', live).group(1)
        here_v = re.search(r'VERSION = "([^"]+)"', sw).group(1)
        changed = subprocess.run(["git", "diff", "--name-only", "origin/main", "--", "js", "css", "lessons", "data", "index.html", "sw.js"],
                                 capture_output=True, text=True).stdout.split()
        if changed and live_v == here_v:
            bad.append(f"{len(changed)} shipped files changed but VERSION is still {here_v}")
    except Exception as e:  # no origin/main (fresh clone without fetch)
        bad.append(f"couldn't compare with origin/main: {e}")
    check(S, "VERSION bumped when shipped files change", bad)

    # data/files.json ("Save it all") lists every data file with its real size
    fl = load("data/files.json")
    listed = {p: n for p, n in fl["files"]}
    bad = [f"{p}: listed {n}, actual {os.path.getsize(p) if os.path.exists(p) else 'missing'}"
           for p, n in listed.items() if not os.path.exists(p) or os.path.getsize(p) != n]
    actual = {p for p in glob.glob("data/**/*.json", recursive=True)} - {"data/files.json", "data/stats.json"}
    bad += [f"{p} not in files.json" for p in sorted(actual - set(listed))]
    check(S, "data/files.json matches the data folder", bad)

    # Old-iPhone JavaScript: nothing newer than Safari 13.4 (needs esbuild)
    esb = "/opt/npm-tools/node_modules/.bin/esbuild"
    bad = []
    if os.path.exists(esb):
        for p in glob.glob("js/*.js"):
            r = subprocess.run([esb, p, "--target=safari13.4", "--supported:destructuring=true", "--log-level=error"],
                               capture_output=True, text=True)
            if r.returncode:
                bad.append(f"{p}: {r.stderr.strip().splitlines()[0] if r.stderr.strip() else 'error'}")
    else:
        bad.append("esbuild not found: syntax baseline not checked")
    check(S, "JavaScript runs on iOS 13.4 (esbuild)", bad)

    # Media links: https, plain YouTube links
    bad = []
    for m in re.finditer(r'"href":\s*"([^"]+)"', read("lessons/media.json")):
        u = m.group(1)
        if not u.startswith("https://"):
            bad.append(u)
    check(S, "video and audio links use https", bad)


# ================================================================ 5. In the browser: what a learner actually sees
PAGE_JS = r"""async () => {
  const data = await import('./js/data.js'); const R = await import('./js/reader.js'); const H = await import('./js/hebrew.js');
  await data.loadMeanings('grc'); await data.loadMeanings('he');
  const out = [];
  const odd = (s) => /[\/:\[\]<>]|undefined|null|NaN|^\s*$/.test(s);
  const index = await data.getJSON('lessons/index.json');
  for (const lang of ['grc', 'he']) {
    const he = lang === 'he'; const morph = await data.morph(lang);
    for (const L of index[lang].filter((x) => x.file)) {
      const lesson = await data.getJSON(L.file);
      for (const st of lesson.steps) for (const c of st.cards) if (c.type === 'verse') {
        const [bookId, cv] = c.ref.split(' '); const [ch, vn] = cv.split(':').map(Number);
        const orig = await data.original(bookId);
        const words = ((orig.ch.find(([x]) => x === ch) || [0, []])[1].find(([n]) => n === vn) || [0, []])[1];
        if (!words.length) out.push(`${L.id} ${c.ref}: verse not found`);
        words.forEach((w) => {
          const keys = he ? [H.heMainKey(w)] : String(w[3] || '').split('+');
          const codes = he ? [(H.heParts(w).find((p) => p.main) || {}).code] : String(w[4] || '').split('+');
          const form = he ? H.heText(w) : w[0];
          keys.forEach((k) => { if (!orig.lex[k]) out.push(`${L.id} ${c.ref} ${form}: no dictionary form for ${k}`);
            else if (odd(data.meaningOf(lang, k, orig.lex[k][2]))) out.push(`${L.id} ${c.ref} ${form}: meaning "${data.meaningOf(lang, k, orig.lex[k][2])}"`); });
          codes.forEach((cd) => { if (!morph[cd]) out.push(`${L.id} ${c.ref} ${form}: no grammar for ${cd}`); });
          if (!R.englishHTML(he ? H.heEnglish(w[2]) : w[2]).replace(/<[^>]+>/g, '').trim()) out.push(`${L.id} ${c.ref} ${form}: no English for this verse`);
        });
      }
    }
  }
  return out;
}"""

SPECIAL = ["ROM/16", "MRK/16", "JHN/7", "JHN/8", "ACT/19", "2CO/13", "3JN/1", "REV/12", "MAT/17", "1CO/16", "LUK/22"]


async def audit_pages():
    from playwright.async_api import async_playwright
    S = "pages"
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

        # 5a. Every word of every lesson verse: dictionary form, meaning, grammar, English
        await pg.goto(f"{BASE}#/settings")
        await pg.wait_for_selector("main h1")
        check(S, "lesson Read steps: every word has its dictionary form, meaning, grammar and English", await pg.evaluate(PAGE_JS))

        # 5b. Today: every word of every verse shows itself first, then where it comes from
        bad = []
        votd = load("data/votd.json")
        await pg.clock.install(time=datetime.datetime(2030, 1, 1, 12))
        await pg.goto(f"{BASE}#/settings")
        for v in votd:
            # Today picks its verse by the date: set the clock to a day that shows this one
            same = [x for x in votd if x["lang"] == v["lang"]]
            i = same.index(v)
            day = next(datetime.date(2030, 1, 1) + datetime.timedelta(k) for k in range(400)
                       if ((datetime.date(2030, 1, 1) + datetime.timedelta(k)) - datetime.date(1970, 1, 1)).days % len(same) == i)
            await pg.clock.set_fixed_time(datetime.datetime(day.year, day.month, day.day, 12))
            await pg.goto(f"{BASE}#/settings")
            await pg.reload()
            await pg.goto(f"{BASE}#/today")
            await pg.click(f'[data-lang="{v["lang"]}"]')
            try:
                await pg.wait_for_function(f"document.querySelector('.verse-slot')?.dataset.verse === {json.dumps(v['id'])}", timeout=8000)
            except Exception:
                bad.append(f"{v['ref']}: not shown on its day")
                continue
            ws = pg.locator(".verse-original .w")
            for k in range(await ws.count()):
                await ws.nth(k).click()
                tapped = (await ws.nth(k).text_content()) or ""
                g = await pg.locator(".verse-gloss").inner_text()
                form = (await pg.locator(".verse-gloss .form").text_content()) or ""
                if form != tapped:
                    bad.append(f"{v['ref']} {tapped}: panel leads with {form!r}")
                if "Dictionary form:" not in g and "Joined from two words:" not in g:
                    bad.append(f"{v['ref']} {tapped}: no dictionary form line")
                if re.search(r"undefined|null|NaN|\[object", g):
                    bad.append(f"{v['ref']} {tapped}: odd text {g[:60]!r}")
        check(S, "Today: every tapped word shows itself, its meaning here and its dictionary form", bad)

        # 5c. Reader notes for the chapters with special cases, in all three layouts: the same notes, true ones
        bad = []
        notes_by = {}
        for layout in ("words", "text", "parallel"):
            await pg.goto(f"{BASE}#/settings")
            await pg.evaluate(f"localStorage.setItem('ao:readLayout', JSON.stringify({json.dumps(layout)}))")
            for r in SPECIAL:
                await pg.goto(f"{BASE}#/settings")
                await pg.goto(f"{BASE}#/read/{r}")
                await pg.wait_for_selector(".chapter .v, .chapter .para")
                await pg.wait_for_timeout(250)
                notes = [n.strip() for n in await pg.locator(".chapter .v-gap").all_inner_texts()]
                notes_by[(r, layout)] = notes
                if len(notes) != len(set(notes)):
                    bad.append(f"{r} ({layout}): a note appears twice")
                for n in notes:
                    m = re.search(r"doesn't have verses? (\d+)", n)
                    if m and r != "ROM/16":
                        bad.append(f"{r} ({layout}): says verse {m.group(1)} is missing: {n[:80]}")
                    if "NA28" in n or "Nestle" in n:
                        bad.append(f"{r} ({layout}): {n[:80]}")
                has_brackets = r in ("MRK/16", "JHN/7", "JHN/8")
                if has_brackets != any("double brackets" in n for n in notes):
                    bad.append(f"{r} ({layout}): double-bracket note {'missing' if has_brackets else 'unexpected'}")
                if r == "ROM/16" and not any("25 to 27" in n for n in notes):
                    bad.append(f"ROM/16 ({layout}): no note about verses 25 to 27")
        for r in SPECIAL:
            kinds = {lay: sorted(re.sub(r"\d+", "N", n.split(".")[0]) for n in notes_by[(r, lay)] if "ESV" not in n)
                     for lay in ("words", "text", "parallel")}
            if kinds["words"] != kinds["parallel"]:
                bad.append(f"{r}: word-by-word and side-by-side notes differ: {kinds['words']} vs {kinds['parallel']}")
        await pg.evaluate("localStorage.setItem('ao:readLayout', JSON.stringify('words'))")
        check(S, "Reader notes true and the same in every layout (Romans 16, Mark 16, John 7–8, Acts 19 …)", bad)

        # 5d. Dictionary entries whose Strong's number is shared: the definition is about the word shown
        bad = []
        h = {}
        for f in glob.glob("data/lex/H/*.json"):
            h.update(load(f))
        stop = {"the", "and", "for", "with", "from", "his", "her", "who", "one", "not", "that", "this", "son", "place"}
        by_num = defaultdict(list)
        for k in h:
            by_num[re.sub(r"[A-Z]$", "", k)].append(k)
        for num, ks in by_num.items():
            if len(ks) < 2:
                continue
            for k in ks:
                e = h[k]
                d = re.sub(r"<[^>]+>", " ", e[4] if len(e) > 4 else "").lower()
                words = {w for w in re.findall(r"[a-z]{3,}", str(e[3]).lower()) if w not in stop}
                if d and words and not any(re.search(r"\b" + re.escape(w[:max(4, len(w) - 2)]), d) for w in words):
                    bad.append(f"{k} '{e[3]}': definition is about something else: {d[:60]}")
        check(S, "dictionary: a shared Strong's number never shows another word's definition", bad)

        # 5e. Settings › About shows every credit
        await pg.goto(f"{BASE}#/settings")
        about = await pg.locator("main").inner_text()
        bad = [x for x in ("SBL Greek New Testament", "Society of Biblical Literature", "STEPBible", "Open Scriptures",
                           "Berean Standard Bible", "Swete", "Abbott-Smith", "Perseus", "ESV") if x not in about]
        check(S, "Settings › About credits every source", bad)
        check(S, "no console errors during the page checks", errs[:10])
        await b.close()


def main():
    static_only = "--static" in sys.argv
    audit_copyright()
    audit_data()
    audit_wording()
    audit_shell()
    if not static_only:
        asyncio.run(audit_pages())
    n = sum(len(v) for v in problems.values())
    print(f"\n{len(passed)} checks passed, {len(problems)} sections with problems ({n} findings)")
    for s, items in problems.items():
        print(f"\n[{s}]")
        for it in items:
            print("  -", it)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
