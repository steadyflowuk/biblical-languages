"""Opens every dictionary entry at 360px and reports anything odd (about 25 minutes for all ~21,000).
Run with the local server on :8765:  python3 tools/sweep_dictionary.py [G|H|all] [every-nth]"""
import asyncio, collections, json, sys, time
from playwright.async_api import async_playwright

BASE = "http://localhost:8765/"
ROOT = "/home/claude/biblical-languages/data/lex/"
which = (sys.argv[1] if len(sys.argv) > 1 else "all").upper()
step = int(sys.argv[2]) if len(sys.argv) > 2 else 1
keys = []
for letter, name in (("G", "greek"), ("H", "hebrew")):
    if which in (letter, "ALL"):
        keys += [e[0] for e in json.load(open(f"{ROOT}{name}-index.json"))]
keys = keys[::step]

CHECK = r"""
() => {
  const main = document.querySelector('main');
  const text = main.innerText;
  const ov = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  const wide = [...main.querySelectorAll('.entry-lemma, .forms, .entry-def, .tag, .rows')].filter(e => e.getBoundingClientRect().right > innerWidth + 1).map(e => e.className).slice(0, 3);
  return {
    h1: !!main.querySelector('h1.entry-lemma') && main.querySelector('h1.entry-lemma').textContent.trim().length > 0,
    note: !!main.querySelector('.dict-entry .note'),
    count: (main.querySelector('.entry-count') || {}).textContent || '',
    gloss: ((main.querySelector('.entry-gloss') || {}).textContent || '').trim(),
    bad: [...new Set(text.match(/\bundefined\b|\bNaN\b|\[object|&lt;|&gt;|&amp;|__|�/g) || [])],
    ov, wide,
    forms: main.querySelectorAll('.forms tbody tr').length,
    books: main.querySelectorAll('.occ-book').length,
  };
}"""


async def main():
    issues = collections.defaultdict(list)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1243/chrome-linux64/chrome")
        ctx = await b.new_context(viewport={"width": 360, "height": 740})
        page = await ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        await page.goto(f"{BASE}#/words")
        await page.wait_for_selector(".dict-common .dict-row")
        t0 = time.time()
        for i, key in enumerate(keys):
            n0 = len(errs)
            await page.evaluate(f"location.hash = '#/words/{key}'")
            try:
                await page.wait_for_function(f"location.hash === '#/words/{key}' && (document.querySelector('h1.entry-lemma') || document.querySelector('.dict-entry .note'))", timeout=15000)
            except Exception:
                issues["did not open"].append(key)
                continue
            r = await page.evaluate(CHECK)
            if r["note"] or not r["h1"]:
                issues["no entry shown"].append(key)
            if not r["gloss"] or r["gloss"] == "—":
                issues["no meaning"].append(key)
            if not r["count"].strip():
                issues["no count line"].append(key)
            if r["bad"]:
                issues["odd text"].append(f"{key} {r['bad']}")
            if r["ov"] > 0 or r["wide"]:
                issues["wider than the screen"].append(f"{key} {r['ov']}px {r['wide']}")
            if len(errs) > n0:
                issues["script errors"].append(f"{key}: {errs[n0:][:1]}")
            if i and i % 2000 == 0:
                print(f"  {i:,} entries, {time.time() - t0:.0f}s", flush=True)
        print(f"{len(keys):,} entries opened at 360px in {time.time() - t0:.0f}s")
        for k, v in issues.items():
            print(f"\n{len(v):5d} {k}")
            for x in v[:10]:
                print("       ", x)
        print("\nissue types:", len(issues))
        await b.close()

asyncio.run(main())
