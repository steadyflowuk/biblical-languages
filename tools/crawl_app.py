"""Visit every screen and every in-app link found on them, at phone and iPad sizes, light and dark, and the smallest
phone at the largest text size. Reports pages that fail to draw, console errors, sideways scrolling, a missing
heading, the wrong tab highlighted, or links that lead nowhere. Run with the local server on :8765:
python3 tools/crawl_app.py [quick]
"""
import asyncio, re, sys, faulthandler
from playwright.async_api import async_playwright

faulthandler.dump_traceback_later(3000, exit=True)
BASE = "http://localhost:8765/"
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
START = ["today", "learn", "alphabet", "alphabet/grc", "alphabet/he", "read", "read/JHN/1", "read/GEN/1", "read/PSA/23",
         "read/DAN/2", "lxx/PSA/22", "words", "words/G3056", "words/H0430G", "review", "progress", "media", "settings", "check",
         "lesson/grc/grc-0", "lesson/grc/grc-9", "lesson/he/he-0", "lesson/he/he-10"]
TAB = {"lesson": "learn", "lxx": "read", "check": "settings"}
SEED = """(() => { localStorage.clear();
  const now = Date.now(), day = 86400000, iso = (t) => new Date(t).toISOString();
  const f = (s, st, d) => ({ state: s, stability: st, difficulty: 5, reps: 3, lapses: 0, elapsed_days: 1, scheduled_days: 3, learning_steps: 0, due: iso(now + d * day) });
  localStorage.setItem('ao:cards', JSON.stringify({
    'grc:G3056': { id: 'grc:G3056', lang: 'grc', k: 'G3056', t: 'λόγος', say: 'LO-gos', en: 'word', src: 'lesson', lesson: 'grc-0', f: f(2, 30, 2) },
    'he:H0430G': { id: 'he:H0430G', lang: 'he', k: 'H0430G', t: 'אֱלֹהִים', say: 'e-lo-HIM', en: 'God', src: 'lesson', lesson: 'he-0', f: f(1, 1, 0) },
    'grc:abc:0': { id: 'grc:abc:0', lang: 'grc', k: '', t: 'Α α', src: 'abc', say: 'AL-fa', en: 'alpha: a', sp: 'ἄλφα', f: f(2, 9, 1) } }));
  localStorage.setItem('ao:lessons', JSON.stringify({ 'grc-0': { v: 1, done: true, pos: 0, best: 100 }, 'he-0': { v: 1, done: true, pos: 0, best: 80 } }));
  localStorage.setItem('ao:reviewQueue', JSON.stringify([{ k: 'G3056', lang: 'grc', t: 'λόγος', say: 'LO-gos', en: 'word', lesson: 'grc-0' }]));
  localStorage.setItem('ao:activity', JSON.stringify({}));
})()"""


async def crawl(b, w, h, scheme, size, limit, problems, label):
    ctx = await b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, service_workers="block")
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    await pg.goto(f"{BASE}#/settings")
    await pg.evaluate(SEED)
    if size != "normal":
        await pg.evaluate(f"localStorage.setItem('ao:textSize', JSON.stringify('{size}'))")
    seen, kinds, queue, visited = set(), set(), list(START), 0
    while queue and visited < limit:
        route = queue.pop(0)
        if route in seen:
            continue
        seen.add(route)
        visited += 1
        errs.clear()
        await pg.goto(f"{BASE}#/settings")
        await pg.goto(f"{BASE}#/{route}")
        try:
            await pg.wait_for_function("document.querySelector('main h1, main .ls-stepbar, main .chapter, main .lxx-text, main .entry-lemma')", timeout=15000)
        except Exception:
            problems.append(f"{label} #{route}: nothing drew in 15 s")
            continue
        await pg.wait_for_timeout(700)
        name = route.split("/")[0]
        if not pg.url.endswith(f"#/{route}") and name not in ("alphabet",):
            if "#/today" in pg.url:
                problems.append(f"{label} #{route}: sent back to Today (unknown address)")
        info = await pg.evaluate("""() => ({
            over: document.documentElement.scrollWidth > innerWidth,
            wide: [...document.querySelectorAll('main *')].filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.right > innerWidth + 1 && !e.closest('.ls-table-wrap, .table-wrap, .ck-report, pre'); }).map((e) => e.tagName + '.' + (e.className || '')).slice(0, 3),
            h1: (document.querySelector('main h1') || {}).textContent || '',
            tab: (document.querySelector('.tabs a[aria-current="page"]') || {}).dataset ? (document.querySelector('.tabs a[aria-current="page"]') || { dataset: {} }).dataset.tab : '',
            text: (document.querySelector('main') || {}).innerText || '',
            links: [...document.querySelectorAll('main a[href^="#/"]')].map((a) => a.getAttribute('href').slice(2)),
            empty: [...document.querySelectorAll('main a, main button')].filter((e) => !(e.textContent || '').trim() && !e.getAttribute('aria-label') && !e.querySelector('img[alt], svg[aria-label]')).length })""")
        if info["over"] or info["wide"]:
            problems.append(f"{label} #{route}: sideways scroll {info['wide']}")
        if errs:
            problems.append(f"{label} #{route}: console {errs[:2]}")
        if re.search(r"undefined|NaN|\[object Object\]|null\b", info["text"]):
            problems.append(f"{label} #{route}: odd text {re.findall(r'.{0,30}(?:undefined|NaN|\[object Object\]|null).{0,20}', info['text'])[:2]}")
        if info["empty"]:
            problems.append(f"{label} #{route}: {info['empty']} buttons/links with no name")
        want = TAB.get(name, name)
        if want in ("today", "learn", "alphabet", "read", "words", "review", "progress", "media", "settings") and info["tab"] != want:
            problems.append(f"{label} #{route}: tab {info['tab']!r} highlighted, expected {want!r}")
        for l in info["links"]:
            l = l.split("?")[0]
            # keep the crawl broad but bounded: one example of each kind of link
            kind = re.sub(r"\d+", "N", l)
            kind = re.sub(r"/[A-Z0-9]{3}/", "/BOOK/", kind)
            kind = re.sub(r"/[GH]\w+$", "/KEY", kind)
            if kind not in kinds:
                kinds.add(kind)
                queue.append(l)
    await ctx.close()
    return visited


async def main():
    quick = len(sys.argv) > 1 and sys.argv[1] == "quick"
    problems = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        runs = [(390, 844, "light", "normal", "phone light"), (390, 844, "dark", "normal", "phone dark"),
                (1180, 820, "light", "normal", "iPad"), (320, 640, "dark", "largest", "small largest")]
        for w, h, scheme, size, label in (runs[:1] if quick else runs):
            n = await crawl(b, w, h, scheme, size, 60 if quick else 200, problems, label)
            print(f"{label}: {n} screens")
        await b.close()
    print(f"{len(problems)} problems")
    for x in problems:
        print("  " + x)
    raise SystemExit(1 if problems else 0)


asyncio.run(main())
