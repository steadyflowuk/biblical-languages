"""End-to-end checks for the app shell.

Run from the repo root:
    python3 -m http.server 8765 &   (then)   python3 tools/test_app.py
Uses the Chromium that ships with Playwright in this workspace.
"""
import asyncio, json, os, sys, tempfile
from playwright.async_api import async_playwright

BASE = os.environ.get("APP_URL", "http://localhost:8765/")
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
ROUTES = ["today", "learn", "alphabet", "read", "words", "review", "progress", "media", "settings"]
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

        # 7c. Reader
        ctx, page = await new_page(b)
        await page.goto(f"{BASE}#/read/JHN/1"); await page.wait_for_selector(".chapter .v")
        nv = await page.locator(".chapter .v").count()
        check("Reader: John 1 shows all 51 verses", nv == 51, str(nv))
        title = await page.title()
        check("Reader: page title names the chapter", title.startswith("John 1"), title)
        await page.locator('.v[data-vi="0"] .w').nth(4).click()
        await page.wait_for_selector(".sheet .ws-word")
        word = await page.text_content(".sheet .ws-word")
        await page.wait_for_function("!document.querySelector('.ws-count')?.hidden")
        count = await page.text_content(".ws-count dd")
        facts = await page.locator(".ws-facts dd").all_inner_texts()
        check("Reader: tapping λόγος opens its details", word.strip() == "λόγος" and "G3056" in facts[0] and "word" in facts[1], f"{word} {facts[:2]}")
        check("Reader: shows how common the word is", "330" in count, count)
        await page.click('.sheet [data-step="1"]')
        nxt = await page.text_content(".sheet .ws-word")
        check("Reader: next word button moves along the verse", nxt.strip() == "καὶ", nxt)
        await page.keyboard.press("Escape")
        check("Reader: Escape closes the details", await page.locator(".sheet").count() == 0)
        # every word in a long chapter opens a sheet with a meaning
        await page.goto(f"{BASE}#/read/PHM/1"); await page.wait_for_selector(".chapter .v")
        total = await page.locator(".chapter .w").count()
        bad = await page.evaluate("""async () => {
          const ws = [...document.querySelectorAll('.chapter .w')]; const out = [];
          for (const w of ws) { w.click(); const dd = document.querySelectorAll('.sheet .ws-facts dd');
            if (!dd.length || !dd[0].textContent.trim() || !dd[1].textContent.trim() || dd[1].textContent.trim() === '—') out.push(w.textContent.slice(0, 20));
            document.querySelector('.sheet [data-close]')?.click(); }
          return out; }""")
        check(f"Reader: all {total} words in Philemon open with a dictionary form and meaning", total > 300 and not bad, "; ".join(bad[:5]))
        # chapter navigation, remembering the place, book picker
        await page.goto(f"{BASE}#/read/JHN/21"); await page.wait_for_selector(".chapter .v")
        nexts = await page.locator(".chapter-nav a").all_inner_texts()
        check("Reader: last chapter of John leads on to Acts 1", "Acts 1" in nexts, str(nexts))
        await page.goto(f"{BASE}#/today"); await page.click('.tabs a[data-tab="read"]'); await page.wait_for_selector(".chapter .v")
        check("Reader: the Read tab reopens the last chapter", "John 21" in (await page.text_content(".rt-name")))
        await page.click("[data-pick]"); await page.click('[data-book="ROM"]'); await page.click('.pick-ch:text-is("8")')
        await page.wait_for_selector(".chapter .v"); await page.wait_for_timeout(200)
        check("Reader: picker opens Romans 8", "Romans 8" in (await page.text_content(".rt-name")) and await page.locator(".sheet").count() == 0)
        # textual and numbering notes
        await page.goto(f"{BASE}#/read/MAT/17/20"); await page.wait_for_selector(".v-gap")
        gap = await page.text_content(".v-gap")
        check("Reader: explains the missing Matthew 17:21", "Verse 21" in gap, gap[:60])
        await page.goto(f"{BASE}#/read/2CO/13"); await page.wait_for_selector(".chapter .v")
        b13 = await page.text_content("#v13 .bsb")
        check("Reader: 2 Corinthians 13:13 (NA28) shows BSB verse 14", "grace of the Lord Jesus" in b13, b13[:50])
        # display options persist, no paragraph marks shown, largest text fits
        await page.goto(f"{BASE}#/read/JHN/1"); await page.wait_for_selector(".chapter .v")
        await page.click("[data-display]"); await page.check('[data-pref="showTranslit"]'); await page.check('[data-pref="showGrammar"]')
        await page.click(".sheet-close"); await page.reload(); await page.wait_for_selector(".chapter .v")
        has_t = await page.locator(".wt").count(); has_m = await page.locator(".wm").count()
        check("Reader: pronunciation and grammar options stay on after reopening", has_t > 100 and has_m > 100)
        await page.click("[data-display]"); await page.check('input[name="readLayout"][value="text"]'); await page.click(".sheet-close")
        paras = await page.locator(".layout-text .para").count()
        check("Reader: running text shows paragraphs", paras >= 3, str(paras))
        body_text = await page.text_content(".chapter")
        check("Reader: no ¶ or ¬ marks shown", "\u00b6" not in body_text and "\u00ac" not in body_text)
        await page.evaluate("localStorage.setItem('ao:textSize', JSON.stringify('largest')); localStorage.setItem('ao:readLayout', JSON.stringify('words'))")
        await page.goto(f"{BASE}#/read/MAT/1"); await page.reload(); await page.wait_for_selector(".chapter .v")
        check("Reader: largest text still fits the screen", await overflow(page) <= 0, str(await overflow(page)))
        # Hebrew and Aramaic Old Testament
        await page.evaluate("localStorage.setItem('ao:textSize', JSON.stringify('default'))")
        await page.goto(f"{BASE}#/read/GEN/1"); await page.reload(); await page.wait_for_selector(".chapter .v")
        nv = await page.locator(".chapter .v").count()
        rtl = await page.evaluate("getComputedStyle(document.querySelector('.chapter .v .words')).direction")
        check("Reader: Genesis 1 shows 31 verses, right to left", nv == 31 and rtl == "rtl", f"{nv} {rtl}")
        b1 = await page.text_content("#v1 .bsb")
        check("Reader: Genesis 1:1 has the BSB in English, left to right", "In the beginning God created" in b1
              and await page.evaluate("getComputedStyle(document.querySelector('#v1 .bsb')).direction") == "ltr")
        await page.locator('#v1 .w').first.click(); await page.wait_for_selector(".sheet .ws-word")
        await page.wait_for_function("!document.querySelector('.ws-count')?.hidden")
        sheet = await page.text_content(".sheet")
        check("Reader: tapping בְּרֵאשִׁית shows its parts, dictionary form and Strong's",
              "Word parts" in sheet and "H7225" in sheet and "beginning" in sheet and "be·re·Shit" in sheet, sheet[:120])
        check("Reader: Hebrew word shows how common it is", "times in the Old Testament" in sheet)
        await page.keyboard.press("Escape")
        await page.goto(f"{BASE}#/read/PSA/3"); await page.wait_for_selector(".chapter .v")
        t0 = await page.text_content("#v0"); v1 = await page.text_content("#v1 .vn")
        check("Reader: Psalm 3 title shown with its BSB, and Hebrew verse numbers", "A Psalm of David" in t0 and "3:2" in v1, f"{t0[:40]} / {v1}")
        check("Reader: chapter called Psalm 3, not Psalms 3", (await page.text_content(".rt-name")).strip() == "Psalm 3")
        await page.goto(f"{BASE}#/read/DAN/2"); await page.wait_for_selector(".chapter .v")
        notes = " ".join(await page.locator(".v-note").all_inner_texts())
        check("Reader: Daniel 2 explains the Aramaic (verses 4 to 49) and the ° reading marks", "Verses 4 to 49 are in Aramaic" in notes and "°" in notes, notes[:90])
        await page.locator("#v4 .w-q").first.click(); await page.wait_for_selector(".sheet .ws-word")
        sheet = await page.text_content(".sheet")
        check("Reader: a ° word shows how it is written and that it is Aramaic", "Written" in sheet and "Aramaic" in sheet, sheet[:100])
        await page.keyboard.press("Escape")
        await page.goto(f"{BASE}#/read/RUT/1"); await page.wait_for_selector(".chapter .v")
        total = await page.locator(".chapter .w").count()
        bad = await page.evaluate("""async () => {
          const ws = [...document.querySelectorAll('.chapter .w')]; const out = [];
          for (const w of ws) { w.click(); const dl = document.querySelector('.sheet .ws-facts'); const t = dl ? dl.innerText : '';
            if (!/Dictionary form\\s*\\S/.test(t) || !/Meaning\\s*[^—\\s]/.test(t) || !/Grammar\\s*\\S/.test(t)) out.push(w.textContent.slice(0, 20));
            document.querySelector('.sheet [data-close]')?.click(); }
          return out; }""")
        check(f"Reader: all {total} words in Ruth 1 open with a dictionary form, meaning and grammar", total > 250 and not bad, "; ".join(bad[:5]))
        # Session 4 deep check: compounds, written-not-read words, lettered senses, labels
        await page.goto(f"{BASE}#/read/EXO/4/2"); await page.wait_for_selector(".chapter .v")
        await page.locator("#v2 .w").nth(3).click(); await page.wait_for_selector(".ws-facts")
        forms = await page.locator(".ws-facts div:has(dt:text-is('Dictionary form')) .ws-lemma").count()
        check("Reader: a two-word compound (מַה־זֶּה) shows both dictionary forms", forms == 2, str(forms))
        await page.keyboard.press("Escape")
        await page.goto(f"{BASE}#/read/1SA/24/8"); await page.wait_for_selector(".chapter .v")
        under = (await page.locator("#v8 .w-k .we").first.text_content()).strip()
        check("Reader: a written-not-read word shows a plain gloss", under == "from", under)
        await page.goto(f"{BASE}#/read/GEN/31/30"); await page.wait_for_selector(".chapter .v")
        await page.locator("#v30 .w").nth(11).click(); await page.wait_for_selector(".ws-facts")
        await page.wait_for_function("!document.querySelector('.ws-count')?.hidden", timeout=5000)
        check("Reader: words with a lettered sense (H0430J) still show how common they are", True)
        await page.keyboard.press("Escape")
        await page.evaluate("localStorage.setItem('ao:showGrammar', 'true')")
        await page.goto(f"{BASE}#/read/GEN/1"); await page.reload(); await page.wait_for_selector(".chapter .wm")
        labels = " ".join(await page.locator(".chapter .wm").all_inner_texts())
        check("Reader: grammar labels read naturally (no 'and (narrative)' before wayyiqtol, no 'numerical')",
              "wayyiqtol" in labels and "(narrative) + Qal wayyiqtol" not in labels and "numerical" not in labels and "number" in labels)
        await page.evaluate("localStorage.setItem('ao:showGrammar', 'false')")
        await page.goto(f"{BASE}#/read/MAL/4"); await page.wait_for_selector(".chapter .v")
        nexts = await page.locator(".chapter-nav a").all_inner_texts()
        check("Reader: Malachi 4 leads on to Matthew 1", "Matthew 1" in nexts, str(nexts))
        await page.click("[data-pick]"); await page.wait_for_selector(".pick-switch")
        ot_first = await page.locator('[data-testament="OT"][aria-pressed="true"]').count()
        await page.click('[data-testament="NT"]'); has_mat = await page.locator('[data-book="MAT"]').count()
        await page.click('[data-testament="OT"]'); await page.click('[data-book="PSA"]')
        chs = await page.locator(".pick-ch").count(); await page.click('.pick-ch:text-is("23")')
        await page.wait_for_selector(".chapter .v"); await page.wait_for_timeout(200)
        check("Reader: picker switches Testament and opens Psalm 23", ot_first == 1 and has_mat == 1 and chs == 150
              and "Psalm 23" in (await page.text_content(".rt-name")))
        await page.evaluate("localStorage.setItem('ao:readLayout', JSON.stringify('text'))")
        await page.goto(f"{BASE}#/read/GEN/1"); await page.reload(); await page.wait_for_selector(".chapter .para")
        paras = await page.locator(".layout-text .para").count()
        txt = await page.text_content(".chapter")
        check("Reader: Hebrew running text breaks into paragraphs without showing פ or ס marks", paras >= 6 and " ס " not in txt and " פ " not in txt, str(paras))
        await page.evaluate("localStorage.setItem('ao:readLayout', JSON.stringify('words'))")
        await page.goto(f"{BASE}#/today"); await page.wait_for_selector(".verse-original")
        await page.click('.switch button:nth-child(2)'); await page.wait_for_selector('.verse-original[lang="he"]')
        href = await page.get_attribute(".verse-link:not(.verse-dict)", "href") or ""
        heb = await page.text_content(".verse-original")
        check("Today: Hebrew verse links into the Reader and shows no paragraph letters", href.startswith("#/read/")
              and not any(t in ("\u05e1", "\u05e4") for t in heb.split()), href)
        check("Reader: no console errors", not page.errors, "; ".join(page.errors[:3]))
        await ctx.close()

        # 8. Tap targets on phone (minimum 44px tall, tab bar items)
        ctx, page = await new_page(b)
        small = []
        for r in ["today", "settings", "media", "read/JHN/3"]:
            await page.goto(f"{BASE}#/{r}"); await page.wait_for_selector("main h1")
            small += await page.evaluate("""() => [...document.querySelectorAll('a, button, label, [role=button]')]
              .filter(e => e.offsetParent && !e.closest('.verse-original') && !e.closest('.chapter') && !e.classList.contains('skip'))
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
