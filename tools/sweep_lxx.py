"""Opens every Old Testament chapter side by side with the Septuagint, and every Septuagint chapter on its own screen,
at 360px, and reports anything odd. Run with the local server on :8765:  python3 tools/sweep_lxx.py [ot|lxx|all]
Takes about 40 minutes for both."""
import asyncio, json, collections, sys
from playwright.async_api import async_playwright

BASE = "http://localhost:8765/"
ROOT = "/home/claude/biblical-languages/data"
which = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
books = [b for b in json.load(open(f"{ROOT}/books.json")) if b["lang"] == "he"]
lxx_books = json.load(open(f"{ROOT}/lxx/books.json"))
issues = collections.defaultdict(list)

CHECK = r"""
() => {
  const ch = document.querySelector('.chapter');
  const text = ch.innerText;
  const bad = (text.match(/\bundefined\b|\bNaN\b|\bnull\b|\[object|&lt;|&gt;|&amp;|⸂|⸃|⸆/g) || []);
  const ov = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  const cols = [...ch.querySelectorAll('.v.pv .col-lxx')];
  return { verses: ch.querySelectorAll('.v.pv, .lv').length, lxx: cols.length,
           none: cols.filter(c => /No matching verse/.test(c.textContent)).length,
           loading: (text.match(/Loading/g) || []).length, bad: [...new Set(bad)], ov,
           weak: /can't be lined up/.test(text), lw: ch.querySelectorAll('.lw').length };
}"""


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1243/chrome-linux64/chrome")
        ctx = await b.new_context(viewport={"width": 360, "height": 740})
        await ctx.add_init_script("localStorage.setItem('ao:showLXX','true');localStorage.setItem('ao:readLayout','\"parallel\"')")
        page = await ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        n_ch = n_none = n_lw = 0
        if which in ("ot", "all"):
            for bk in books:
                ot = json.load(open(f"{ROOT}/lxx/ot/{bk['id']}.json"))
                info = {c: x for c, x in ot["ch"]}
                for c in range(1, bk["ch"] + 1):
                    n0 = len(errs)
                    await page.goto(f"{BASE}#/read/{bk['id']}/{c}")
                    await page.wait_for_function("document.querySelector('.chapter:not([aria-busy]) .pv') && !/Loading the Septuagint|Loading…/.test(document.querySelector('.chapter').innerText)", timeout=20000)
                    r = await page.evaluate(CHECK)
                    ref = f"{bk['id']} {c}"
                    n_ch += 1
                    x = info.get(c)
                    if not x:
                        issues["chapter missing from lxx/ot"].append(ref)
                    elif x["weak"]:
                        if r["lxx"] or not r["weak"]: issues["weak chapter shows verse lines"].append(ref)
                    else:
                        if r["lxx"] != r["verses"]: issues["Septuagint column count differs"].append(f"{ref}: {r['lxx']} vs {r['verses']}")
                        first = {e[0]: e for e in x["v"]}
                        # a psalm title inside Septuagint verse 1 gets its own note, not "no matching verse"
                        nulls = sum(1 for e in x["v"] if not e[1] and not (e[0] == 0 and first.get(1, [0, None])[1]))
                        if r["none"] != nulls: issues["'no matching verse' count differs from data"].append(f"{ref}: {r['none']} vs {nulls}")
                        n_none += r["none"]
                    if r["bad"]: issues["bad text on screen"].append(f"{ref}: {r['bad']}")
                    if r["ov"] > 0: issues["wider than the screen"].append(f"{ref}: {r['ov']}px")
                    if len(errs) > n0: issues["console errors"].append(f"{ref}: {errs[n0:][:2]}")
            print(f"{n_ch} OT chapters side by side; {n_none} verses with no Septuagint match shown")
        if which in ("lxx", "all"):
            n = 0
            for bk in lxx_books:
                text = json.load(open(f"{ROOT}/lxx/text/{bk['id']}.json"))
                expect = {c: len(vs) for c, vs in text["ch"]}
                for c in bk["chapters"]:
                    n0 = len(errs)
                    await page.goto(f"{BASE}#/lxx/{bk['id']}/{c}")
                    await page.wait_for_function(f"document.querySelector('.rt-name')?.textContent.endsWith(' {c}') && document.querySelector('.lxx-chapter:not([aria-busy]) .lv')", timeout=20000)
                    r = await page.evaluate(CHECK)
                    ref = f"LXX {bk['id']} {c}"
                    n += 1; n_lw += r["lw"]
                    if r["verses"] != expect.get(c): issues["Septuagint verse count differs"].append(f"{ref}: {r['verses']} vs {expect.get(c)}")
                    if r["bad"]: issues["bad text on screen"].append(f"{ref}: {r['bad']}")
                    if r["ov"] > 0: issues["wider than the screen"].append(f"{ref}: {r['ov']}px")
                    if len(errs) > n0: issues["console errors"].append(f"{ref}: {errs[n0:][:2]}")
            print(f"{n} Septuagint chapters, {n_lw:,} words shown")
        await b.close()
    if not issues:
        print("0 issues")
    for k, v in issues.items():
        print(f"{k}: {len(v)}")
        for x in v[:12]:
            print("   ", x)


asyncio.run(main())
