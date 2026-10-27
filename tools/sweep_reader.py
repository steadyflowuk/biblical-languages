"""Opens every chapter at 360px with all display options and reports anything odd.
Run with the local server on :8765:  python3 tools/sweep_reader.py [nt|ot|all]
NT (260 chapters) takes about 10 minutes, OT (929 chapters) about 35."""
import asyncio, json, collections, sys
from playwright.async_api import async_playwright
BASE = "http://localhost:8765/"
books = json.load(open("/home/claude/biblical-languages/data/books.json"))
which = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
nt = [b for b in books if (b["lang"] == "grc" and which in ("nt", "all")) or (b["lang"] == "he" and which in ("ot", "all"))]
issues = collections.defaultdict(list)

CHECK = r"""
() => {
  const ch = document.querySelector('.chapter');
  const text = ch.innerText;
  const verses = [...ch.querySelectorAll('.v:not(.v-bsb-only)')];
  const noBsb = verses.filter(v => !v.querySelector('.bsb')).map(v => v.id);
  const emptyBsb = verses.filter(v => { const b = v.querySelector('.bsb'); return b && !b.textContent.trim(); }).map(v => v.id);
  const noteBsb = verses.filter(v => v.querySelector('.bsb.muted')).map(v => v.id);
  const emptyEng = [...ch.querySelectorAll('.we')].filter(e => !e.textContent.replace(/ /g,'').trim()).length;
  const words = ch.querySelectorAll('.w').length;
  const bad = (text.match(/\bundefined\b|\bNaN\b|\bnull\b|\[object|¶|¬|\u0001|&lt;|&gt;|&amp;/g) || []);
  const engLeft = [...ch.querySelectorAll('.we')].map(e => e.textContent).filter(t => /[{}<>]|\[\d|\(\d/.test(t)).slice(0, 3);
  const ov = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  const wide = [...ch.querySelectorAll('.w')].filter(w => { const r = w.getBoundingClientRect(); return r.right > window.innerWidth + 1 || r.left < -1; }).length;
  return { verses: verses.length, words, noBsb, emptyBsb, noteBsb, emptyEng, bad: [...new Set(bad)], engLeft, ov, wide,
           gaps: [...ch.querySelectorAll('.v-gap')].map(g => g.textContent.slice(0, 40)), extra: ch.querySelectorAll('.v-bsb-only').length };
}"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1243/chrome-linux64/chrome")
        ctx = await b.new_context(viewport={"width": 360, "height": 740})
        await ctx.add_init_script("localStorage.setItem('ao:showTranslit','true');localStorage.setItem('ao:showGrammar','true')")
        page = await ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        total_words = 0; chapters = 0; notes = []
        for bk in nt:
            data = json.load(open(f"/home/claude/biblical-languages/data/{'hot' if bk['lang'] == 'he' else 'gnt'}/{bk['id']}.json"))
            expect = {c: len(vs) for c, vs in data["ch"]}
            for c in range(1, bk["ch"] + 1):
                n0 = len(errs)
                await page.goto(f"{BASE}#/read/{bk['id']}/{c}")
                await page.wait_for_function("document.querySelector('.chapter:not([aria-busy])')?.querySelector('.v, .note')", timeout=15000)
                r = await page.evaluate(CHECK)
                ref = f"{bk['id']} {c}"
                chapters += 1; total_words += r["words"]
                if r["verses"] != expect.get(c, -1): issues["verse count differs from data"].append(f"{ref}: {r['verses']} vs {expect.get(c)}")
                if r["noBsb"] and True: issues["verse without BSB line"].append(f"{ref}: {r['noBsb'][:4]}")
                if r["emptyBsb"]: issues["empty BSB line"].append(f"{ref}: {r['emptyBsb'][:4]}")
                if r["noteBsb"]: notes.append(f"{ref}: {r['noteBsb']}")
                if r["emptyEng"]: issues["word with empty English"].append(f"{ref}: {r['emptyEng']}")
                if r["bad"]: issues["bad text on screen"].append(f"{ref}: {r['bad']}")
                if r["engLeft"]: issues["leftover markup in English"].append(f"{ref}: {r['engLeft']}")
                if r["ov"] > 0 or r["wide"]: issues["wider than the screen"].append(f"{ref}: overflow {r['ov']}px, {r['wide']} words")
                if r["extra"]: issues["BSB-only verses appended"].append(ref)
                if len(errs) > n0: issues["console errors"].append(f"{ref}: {errs[n0:][:2]}")
        print(f"{chapters} chapters, {total_words:,} words rendered at 360px with pronunciation and grammar on")
        print("BSB 'part of a neighbouring verse' notes:", notes)
        for k, v in issues.items():
            print(f"\n{len(v):4d} {k}"); [print("      ", x) for x in v[:8]]
        print("\nissue types:", len(issues))
        await b.close()

asyncio.run(main())
