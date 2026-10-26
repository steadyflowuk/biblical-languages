"""End-to-end checks for the app shell.

Run from the repo root:
    python3 -m http.server 8765 &   (then)   python3 tools/test_app.py
Uses the Chromium that ships with Playwright in this workspace.
"""
import asyncio, json, os, sys, tempfile
from playwright.async_api import async_playwright

BASE = os.environ.get("APP_URL", "http://localhost:8765/")
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
ROUTES = ["today", "learn", "read", "words", "review", "media", "settings"]
IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")

results = []
def check(name, ok, detail=""):
    results.append((bool(ok), name, detail))

async def new_page(browser, w=390, h=844, scheme="light", ua=None, **kw):
    ctx = await browser.new_context(viewport={"width": w, "height": h}, color_scheme=scheme,
                                    has_touch=w < 900, user_agent=ua, accept_downloads=True, **kw)
    page = await ctx.new_page()
    page.errors = []
    page.on("console", lambda m: page.errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    return ctx, page

async def overflow(page):
    return await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)

        # 1. Every screen, phone + iPad, light + dark: renders, no errors, no sideways scroll, nav state
        for (w, h, label) in [(390, 844, "phone"), (1180, 820, "iPad")]:
            for scheme in ["light", "dark"]:
                ctx, page = await new_page(b, w, h, scheme)
                for r in ROUTES:
                    await page.goto(f"{BASE}#/{r}")
                    await page.wait_for_selector("main h1")
                    h1 = await page.text_content("main h1")
                    cur = await page.get_attribute(f'.tabs a[data-tab="{r}"]', "aria-current")
                    ov = await overflow(page)
                    check(f"{label} {scheme}: {r} renders", h1 and ov <= 0 and cur == "page",
                          f"h1={h1!r} overflow={ov} current={cur}")
                check(f"{label} {scheme}: no console errors", not page.errors, "; ".join(page.errors[:3]))
                await ctx.close()

        ctx, page = await new_page(b)
        # 2. Unknown route and back button
        await page.goto(f"{BASE}#/nonsense"); await page.wait_for_timeout(300)
        check("unknown address goes to Today", page.url.endswith("#/today"), page.url)
        await page.goto(f"{BASE}#/today"); await page.click('.tabs a[data-tab="learn"]'); await page.wait_for_timeout(200)
        await page.go_back(); await page.wait_for_timeout(300)
        check("back button returns to previous screen", (await page.text_content("main h1")) == "Today")

        # 3. Verse: today's verse comes from the data; every word tappable with a gloss; keyboard; switch
        await page.goto(f"{BASE}#/today")
        votd = json.loads(await page.evaluate("fetch('data/votd.json').then(r => r.text())"))
        ids = {v["id"] for v in votd}
        await page.wait_for_function("document.querySelector('.verse-slot')?.dataset.verse?.includes('-')")
        shown = await page.get_attribute(".verse-slot", "data-verse")
        check("Today shows a verse from the Bible data", shown in ids, shown)
        for lang in ["grc", "he"]:
            await page.click(f'[data-lang="{lang}"]')
            vid = await page.get_attribute(".verse-slot", "data-verse")
            n = await page.locator(".verse-original .w").count()
            bad = []
            for i in range(n):
                await page.locator(".verse-original .w").nth(i).click()
                g = (await page.text_content(".verse-gloss .meaning")) or ""
                lem = (await page.text_content(".verse-gloss .lemma")) or ""
                pressed = await page.locator('.verse-original .w[aria-pressed="true"]').count()
                if not g.strip() or not lem.strip() or pressed != 1: bad.append(i)
            dir_ = await page.get_attribute(".verse-original", "dir")
            check(f"{vid}: all {n} words show a meaning and dictionary form", n > 0 and not bad, f"failed words {bad}")
            check(f"{vid}: text direction", dir_ == ("rtl" if lang == "he" else "ltr"), dir_)
        # every curated verse renders a complete gloss
        empty = [f"{v['id']} word {i}" for v in votd for i, w in enumerate(v["words"]) if not w.get("gloss") or not w.get("lemma") or not w.get("parse")]
        check("all 24 curated verses have a meaning, form and grammar for every word", len(votd) == 24 and not empty, "; ".join(empty[:5]))
        check("all curated verses have their English", all(v["english"] for v in votd))
        await page.click('[data-lang="grc"]')
        await page.locator(".verse-original .w").nth(1).focus()
        await page.keyboard.press("Enter")
        k = await page.get_attribute('.verse-original .w[data-i="1"]', "aria-pressed")
        await page.locator(".verse-original .w").nth(2).focus()
        await page.keyboard.press(" ")
        k2 = await page.get_attribute('.verse-original .w[data-i="2"]', "aria-pressed")
        check("words work with the keyboard (Enter and Space)", k == "true" and k2 == "true")

        # 4. Settings persist and apply
        await page.goto(f"{BASE}#/settings")
        await page.check('input[name="textSize"][value="largest"]')
        await page.check('input[name="theme"][value="dark"]')
        await page.check('input[name="greekVoice"][value="koine"]')
        await page.reload(); await page.wait_for_selector("main h1")
        size = await page.get_attribute("html", "data-size")
        theme = await page.get_attribute("html", "data-theme")
        voice = await page.is_checked('input[name="greekVoice"][value="koine"]')
        tc = await page.get_attribute('meta[name="theme-color"]', "content")
        check("settings survive a reload", size == "largest" and theme == "dark" and voice, f"{size} {theme} {voice}")
        check("status bar colour follows dark theme", tc == "#0C1322", tc)
        for r in ROUTES:
            await page.goto(f"{BASE}#/{r}"); await page.wait_for_timeout(150)
            ov = await overflow(page)
            check(f"largest text: {r} fits the screen", ov <= 0, f"overflow {ov}px")
        bg = await page.evaluate("getComputedStyle(document.body).backgroundColor")
        check("dark theme applied", bg == "rgb(17, 24, 39)", bg)

        # 5. Backup and restore round trip
        await page.goto(f"{BASE}#/settings")
        async with page.expect_download() as dl:
            await page.click('[data-action="export"]')
        d = await dl.value
        path = await d.path()
        data = json.load(open(path))
        check("backup file is valid", data.get("app") == "aleph-to-omega" and data["data"].get("ao:textSize") == '"largest"',
              d.suggested_filename)
        await page.evaluate("localStorage.clear()")
        await page.reload(); await page.wait_for_selector("main h1")
        await page.set_input_files('[data-action="import"]', path)
        await page.wait_for_timeout(400)
        toast = await page.text_content(".toast")
        restored = await page.get_attribute("html", "data-size")
        check("restore brings settings back", restored == "largest" and "restored" in (toast or ""), f"{toast} {restored}")
        bad_file = os.path.join(tempfile.mkdtemp(), "notes.json")
        open(bad_file, "w").write("this is not json")
        await page.set_input_files('[data-action="import"]', bad_file)
        await page.wait_for_timeout(300)
        t2 = await page.text_content(".toast")
        check("a wrong file gives a clear message", "couldn't be read" in (t2 or ""), t2)
        wrong_app = os.path.join(tempfile.mkdtemp(), "other.json")
        json.dump({"hello": 1}, open(wrong_app, "w"))
        await page.set_input_files('[data-action="import"]', wrong_app)
        await page.wait_for_timeout(300)
        t3 = await page.text_content(".toast")
        check("another app's file is refused", "isn't an Aleph to Omega backup" in (t3 or ""), t3)
        await ctx.close()

        # 6. Install tip: dismiss sticks; iPhone wording; hidden install button without prompt
        ctx, page = await new_page(b)
        await page.goto(f"{BASE}#/today"); await page.wait_for_selector(".install-tip")
        hidden_btn = await page.locator("[data-install]").is_hidden()
        check("install button hidden until the browser offers install", hidden_btn)
        await page.click("[data-dismiss-install]"); await page.reload(); await page.wait_for_selector("main h1")
        check("dismissed install tip stays away", await page.locator(".install-tip").count() == 0)
        await ctx.close()
        ctx, page = await new_page(b, ua=IPHONE_UA)
        await page.goto(f"{BASE}#/today"); await page.wait_for_selector(".install-tip")
        tip = await page.text_content(".install-tip")
        check("iPhone sees Share → Add to Home Screen steps", "Add to Home Screen" in tip and await page.locator("[data-install]").count() == 0)
        await ctx.close()

        # 7. Offline: load once, cut the network, reload every screen
        ctx, page = await new_page(b)
        await page.goto(f"{BASE}#/today"); await page.wait_for_selector("main h1")
        await page.evaluate("navigator.serviceWorker.ready")
        await page.reload(); await page.wait_for_timeout(800)
        await ctx.set_offline(True)
        ok_all = True; detail = []
        for r in ROUTES:
            await page.goto(f"{BASE}#/{r}"); await page.wait_for_selector("main h1", timeout=5000)
            if (await page.text_content("main h1")) is None: ok_all = False; detail.append(r)
        await page.goto(BASE); await page.wait_for_selector("main h1", timeout=5000)
        await page.reload(); await page.wait_for_selector("main h1", timeout=5000)
        fonts = await page.evaluate("document.fonts.ready.then(() => [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family))")
        check("works offline (all screens, after reload)", ok_all, ",".join(detail))
        check("fonts available offline", {"Atkinson", "Gentium"} <= set(fonts), str(fonts))
        await page.click('[data-lang="he"]'); await page.wait_for_timeout(400)
        vid = await page.get_attribute(".verse-slot", "data-verse")
        check("today's verse (from data) shows offline", vid and "-" in vid and vid != "gen-1-1", vid)
        hf = await page.evaluate("document.fonts.ready.then(() => [...document.fonts].some(f => f.family === 'Hebrew Serif' && f.status === 'loaded'))")
        check("Hebrew font available offline", hf)
        await ctx.close()

        # 7b. Bible data offline: a book opened once stays available; one never opened fails cleanly
        ctx, page = await new_page(b)
        await page.goto(f"{BASE}#/today"); await page.wait_for_selector("main h1")
        await page.evaluate("navigator.serviceWorker.ready"); await page.reload(); await page.wait_for_timeout(600)
        first = await page.evaluate("fetch('data/gnt/JHN.json').then(r => r.json()).then(d => d.ch.length)")
        await page.wait_for_timeout(300)
        await ctx.set_offline(True)
        again = await page.evaluate("fetch('data/gnt/JHN.json').then(r => r.json()).then(d => d.ch.length).catch(e => 'failed')")
        never = await page.evaluate("fetch('data/hot/OBA.json').then(r => r.ok ? 'ok' : 'not ok').catch(e => 'failed cleanly')")
        check("a book opened once is readable offline", first == 21 and again == 21, f"{first} / {again}")
        check("a book never opened fails cleanly offline", never == "failed cleanly", never)
        await ctx.close()

        # 8. Tap targets on phone (minimum 44px tall, tab bar items)
        ctx, page = await new_page(b)
        small = []
        for r in ["today", "settings", "media"]:
            await page.goto(f"{BASE}#/{r}"); await page.wait_for_selector("main h1")
            small += await page.evaluate("""() => [...document.querySelectorAll('a, button, label, [role=button]')]
              .filter(e => e.offsetParent && !e.closest('.verse-original') && !e.classList.contains('skip'))
              .map(e => ({t: (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 30), h: e.getBoundingClientRect().height, w: e.getBoundingClientRect().width}))
              .filter(x => x.h < 44 || x.w < 44).map(x => `${x.t} ${Math.round(x.w)}x${Math.round(x.h)}`)""")
        check("tap targets at least 44px", not small, "; ".join(sorted(set(small))[:8]))
        words = await page.goto(f"{BASE}#/today") or True
        await page.wait_for_selector(".verse-original .w")
        wh = await page.evaluate("Math.min(...[...document.querySelectorAll('.verse-original .w')].map(e => e.getBoundingClientRect().height))")
        check("verse words are big enough to tap", wh >= 30, f"smallest {wh:.0f}px")
        await ctx.close()
        await b.close()

    for ok, name, detail in results:
        print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    fails = sum(1 for r in results if not r[0])
    print(f"\n{len(results) - fails}/{len(results)} passed")
    sys.exit(1 if fails else 0)

asyncio.run(main())
