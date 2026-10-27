"""Reader edge cases: odd links, fast switching, focus in the details card, back button, narrow phones.
Run with the local server on :8765:  python3 tools/test_reader_edges.py"""
import asyncio
from playwright.async_api import async_playwright
BASE = "http://localhost:8765/"
res = []
def check(name, ok, detail=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

async def ready(pg):
    await pg.wait_for_function("document.querySelector('main h1') && !document.querySelector('.chapter[aria-busy]')", timeout=15000)
    await pg.wait_for_timeout(150)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1243/chrome-linux64/chrome")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))

        # 1. Odd links
        for link, expect in [("read/XYZ/1", "next update|Open John 1"), ("read/JHN/0", "John 1"), ("read/JHN/999", "John 21"),
                             ("read/jhn/3", "John 3"), ("read/JHN/abc", "John 1"), ("read/JHN/3/999", "John 3"), ("read/JHN/3/abc", "John 3"),
                             ("read/PHM/2", "Philemon 1"), ("read/GEN/1", "next update")]:
            await pg.goto(f"{BASE}#/{link}"); await ready(pg)
            txt = await pg.text_content("main")
            import re
            check(f"link #/{link} handled", re.search(expect, txt) is not None, txt[:60].strip())
        check("no script errors from odd links", not errs, "; ".join(errs[:2]))

        # 2. Fast chapter switching ends on the right chapter with matching content
        await pg.goto(f"{BASE}#/read/MAT/1"); await ready(pg)
        await pg.evaluate("""async () => { for (const c of [2,3,4,5,6,7]) { location.hash = '#/read/MAT/' + c; await new Promise(r => setTimeout(r, 15)); } }""")
        await pg.wait_for_timeout(1500)
        name = await pg.text_content(".rt-name"); first = await pg.text_content(".chapter .v .wg")
        check("fast switching lands on Matthew 7 with Matthew 7's text", name.strip() == "Matthew 7" and "Μὴ" in first, f"{name} / {first}")
        check("only one chapter on screen", await pg.locator(".chapter").count() == 1)

        # 3. Sheet: keyboard open, focus inside, background not reachable, Escape returns focus to the word
        await pg.goto(f"{BASE}#/read/JHN/1"); await ready(pg)
        w = pg.locator('.v[data-vi="0"] .w').nth(1)
        await w.focus(); await pg.keyboard.press("Enter"); await pg.wait_for_selector(".sheet")
        inside = await pg.evaluate("document.activeElement.closest('.sheet') !== null")
        check("opening a word moves focus into the details", inside)
        escaped = False
        for _ in range(12):
            await pg.keyboard.press("Tab")
            if not await pg.evaluate("document.activeElement.closest('.sheet') !== null || document.activeElement === document.body"):
                escaped = True; break
        check("Tab stays inside the open details (background inert)", not escaped)
        await pg.keyboard.press("Escape")
        back = await pg.evaluate("document.activeElement?.dataset?.wi")
        check("closing returns focus to the word", back == "1", str(back))
        check("page scrolls again after closing", not await pg.evaluate("document.body.classList.contains('sheet-open')"))

        # 4. Back button with the details open closes them and changes chapter cleanly
        await pg.goto(f"{BASE}#/read/JHN/2"); await ready(pg)
        await pg.locator(".chapter .w").first.click(); await pg.wait_for_selector(".sheet")
        await pg.go_back(); await ready(pg)
        check("back button with details open: no leftover sheet", await pg.locator(".sheet").count() == 0 and not await pg.evaluate("document.body.classList.contains('sheet-open')"))

        # 5. Display change keeps the reader's place
        await pg.goto(f"{BASE}#/read/JHN/1/40"); await ready(pg)
        before = await pg.evaluate("document.querySelector('#v40').getBoundingClientRect().top")
        await pg.click("[data-display]"); await pg.check('[data-pref="showTranslit"]'); await pg.click(".sheet-close"); await pg.wait_for_timeout(300)
        top_v = await pg.evaluate("[...document.querySelectorAll('.chapter .v')].find(v => v.getBoundingClientRect().bottom > 80)?.id")
        check("changing display keeps you near the same verse", top_v in ("v38", "v39", "v40", "v41"), f"top verse now {top_v}")
        await pg.click("[data-display]"); await pg.uncheck('[data-pref="showTranslit"]'); await pg.click(".sheet-close")

        # 6. Running text: deep link highlights the verse; tapping a word shows the BSB verse
        await pg.evaluate("localStorage.setItem('ao:readLayout', JSON.stringify('text'))")
        await pg.goto(f"{BASE}#/read/ROM/8/28"); await pg.reload(); await ready(pg)
        hl = await pg.locator("#v28.focus").count()
        await pg.locator("#v28 .w").nth(3).click(); await pg.wait_for_selector(".ws-bsb")
        bsb = await pg.text_content(".ws-bsb")
        check("running text: verse 28 highlighted and its BSB shown in details", hl == 1 and "God works all things" in bsb)
        await pg.keyboard.press("Escape")
        await pg.evaluate("localStorage.setItem('ao:readLayout', JSON.stringify('words'))")

        # 7. Narrow phone (320px) and landscape, largest text: no sideways scrolling, sheet fits
        for (wd, ht, label) in [(320, 568, "320px phone"), (844, 390, "landscape phone")]:
            c2 = await b.new_context(viewport={"width": wd, "height": ht})
            await c2.add_init_script("localStorage.setItem('ao:textSize', JSON.stringify('largest'))")
            p2 = await c2.new_page()
            bad = []
            for r in ["today", "read/1TH/1", "read/REV/22", "settings"]:
                await p2.goto(f"{BASE}#/{r}"); await ready(p2)
                ov = await p2.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                if ov > 0: bad.append(f"{r} {ov}px")
            await p2.goto(f"{BASE}#/read/1TH/1"); await ready(p2)
            await p2.locator(".chapter .w").nth(2).click(); await p2.wait_for_selector(".sheet-panel")
            fits = await p2.evaluate("(() => { const r = document.querySelector('.sheet-panel').getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth + 1 && r.top >= 0; })()")
            check(f"{label}, largest text: nothing wider than the screen; details fit", not bad and fits, ", ".join(bad))
            await c2.close()

        check("no script errors overall", not errs, "; ".join(errs[:3]))
        print(f"\n{sum(res)}/{len(res)} passed")
        await b.close()

asyncio.run(main())
