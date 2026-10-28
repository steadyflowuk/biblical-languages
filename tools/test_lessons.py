"""Lesson engine checks (Session 7). Run with the local server on :8765:  python3 tools/test_lessons.py"""
import asyncio, json, re, unicodedata, faulthandler
from playwright.async_api import async_playwright

faulthandler.dump_traceback_later(900, exit=True)
BASE = "http://localhost:8765/"
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
GRC = json.load(open("/home/claude/biblical-languages/lessons/grc/0.json"))
HE = json.load(open("/home/claude/biblical-languages/lessons/he/0.json"))
res = []


def check(name, ok, detail=""):
    res.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def card_by_title(lesson, title):
    for s in lesson["steps"]:
        for c in s["cards"]:
            if (c.get("prompt") or c.get("text") or c.get("title")) == title:
                return c
    return None


async def kind(pg):
    return await pg.evaluate("""(() => { const c = document.querySelector('.ls-card');
      for (const k of ['choose','match','build','parse','scene','verse','words','video','explain']) if (c.querySelector('.ls-' + k)) return k;
      return c.querySelector('.ls-done') ? 'done' : 'other'; })()""")


async def title(pg):
    return await pg.evaluate("document.querySelector('.ls-card .ls-title, .ls-card .ls-big')?.textContent")


async def answer(pg, lesson, right=True):
    """Answer the current drill (rightly or wrongly); returns the card kind."""
    k = await kind(pg)
    c = card_by_title(lesson, await title(pg))
    if k == "choose":
        i = c["answer"] if right else (c["answer"] + 1) % len(c["options"])
        await pg.click(f"[data-opt='{i}']")
    elif k == "match":
        if not right:
            await pg.click("[data-left='0']"); await pg.click("[data-right='1']")
        for i in range(len(c["pairs"])):
            await pg.click(f"[data-left='{i}']"); await pg.click(f"[data-right='{i}']")
    elif k == "build":
        order = list(range(len(c["tiles"])))
        if not right:
            order = order[::-1]
        for i in order:
            await pg.click(f".ls-bank [data-tile='{i}']")
        await pg.click("[data-check]")
    elif k == "parse":
        for fi, f in enumerate(c["fields"]):
            v = f["answer"] if right or fi else next(o for o in f["options"] if o != f["answer"])
            await pg.click(f"[data-pick='{fi}'][data-value='{v}']")
        await pg.click("[data-check]")
    return k


async def go_next(pg):
    await pg.click("[data-next]")
    await pg.wait_for_timeout(150)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

        # 1. Learn
        await pg.goto(f"{BASE}#/learn")
        await pg.evaluate("localStorage.clear()")
        await pg.reload()
        await pg.wait_for_selector(".path li")
        IX = json.load(open("/home/claude/biblical-languages/lessons/index.json"))
        n_all, n_soon = len(IX["grc"]), sum(1 for e in IX["grc"] if not e.get("file"))
        items = await pg.locator(".path li").count()
        check("Learn: Greek path from the lesson index, first one ready", items == n_all
              and await pg.locator('.path li.next a[href="#/lesson/grc/grc-0"]').count() == 1, f"{items} vs {n_all}")
        check("Learn: lessons not written yet say 'Coming soon' and aren't links",
              await pg.locator(".path li.soon").count() == n_soon and await pg.locator(".path li.soon a").count() == 0)
        await pg.click("[data-lang=he]")
        await pg.wait_for_selector('a[href="#/lesson/he/he-0"]')
        await pg.reload()
        await pg.wait_for_selector(".path li")
        check("Learn: the chosen language is remembered", await pg.locator('[data-lang=he][aria-pressed="true"]').count() == 1
              and await pg.locator('a[href="#/lesson/he/he-0"]').count() == 1)
        await pg.click("[data-lang=grc]")

        # 2. Start, leave, come back to the same card
        await pg.click('a[href="#/lesson/grc/grc-0"]')
        await pg.wait_for_selector(".ls-card .ls-title")
        check("Lesson: opens on step 1 (Hear and see), Back hidden", "Hear and see" in await pg.locator('.ls-steps li[aria-current="step"] .ls-step-full').text_content()
              and await pg.locator("[data-back]").is_hidden())
        check("Read/Learn tab: Learn is current inside a lesson", await pg.locator('.tabs a[data-tab="learn"][aria-current="page"]').count() >= 1)
        for _ in range(3):
            await go_next(pg)
        t3 = await title(pg)
        await pg.click(".ls-close")
        await pg.wait_for_selector(".path li")
        check("Leaving mid-lesson: Learn says 'Carry on where you left off'",
              "Carry on" in await pg.locator('.path li a[href="#/lesson/grc/grc-0"]').inner_text())
        await pg.click('a[href="#/lesson/grc/grc-0"]')
        await pg.wait_for_selector(".ls-card .ls-big, .ls-card .ls-title")
        check("Coming back opens the same card", await title(pg) == t3, f"{await title(pg)} vs {t3}")
        await pg.click("[data-reveal]")
        check("Scene: 'Show the English' reveals the translation", await pg.locator(".ls-en").is_visible()
              and await pg.locator("[data-reveal]").get_attribute("aria-expanded") == "true")

        # 3. Through the notes to the drills; Continue is locked until a drill is answered
        while await kind(pg) not in ("choose",):
            await go_next(pg)
        check("Practise: Continue is disabled until the drill is answered", await pg.locator("[data-next]").is_disabled())
        options = await pg.locator("[data-opt]").evaluate_all("els => els.map(e => +e.dataset.opt)")
        check("Choose: answers are shuffled (not in the written order)", options != sorted(options), str(options))
        await answer(pg, GRC, right=False)
        fb = await pg.locator(".ls-feedback").inner_text()
        check("Wrong answer: 'Not quite', the right answer is marked, another go promised",
              "Not quite" in fb and "another go" in fb and await pg.locator(".ls-option.right").count() == 1 and await pg.locator(".ls-option.wrong").count() == 1, fb)
        check("Wrong answer: Continue unlocks", await pg.locator("[data-next]").is_enabled())
        check("After answering, focus moves to Continue", await pg.evaluate("document.activeElement.hasAttribute('data-next')"))
        await go_next(pg)
        await pg.click("[data-back]")
        await pg.wait_for_timeout(150)
        check("Going Back to an answered drill doesn't lock Continue", await pg.locator("[data-next]").is_enabled())
        await go_next(pg)
        await answer(pg, GRC)  # second choose, right
        check("Right answer: 'Right.' with the explanation", "Right." in await pg.locator(".ls-feedback").inner_text())
        await go_next(pg)

        # match: one wrong pairing
        check("Match drill is next", await kind(pg) == "match")
        await pg.click("[data-left='0']")
        await pg.click("[data-right='1']")
        check("Match: a wrong pair says 'Not a pair' and stays open", "Not a pair" in await pg.locator(".ls-feedback").inner_text()
              and await pg.locator(".ls-tile.matched").count() == 0)
        for i in range(len(GRC["steps"][2]["cards"][2]["pairs"])):
            await pg.click(f"[data-left='{i}']"); await pg.click(f"[data-right='{i}']")
        check("Match: all matched (after a mistake) counts as not first time", "All matched now" in await pg.locator(".ls-feedback").inner_text())
        await go_next(pg)

        # build: take a word back, then answer
        check("Build drill is next", await kind(pg) == "build")
        await pg.click(".ls-bank [data-tile='1']")
        await pg.click(".ls-line [data-placed='1']")
        check("Build: a placed word can be taken back", await pg.locator(".ls-line .ls-tile").count() == 0 and await pg.locator("[data-check]").is_disabled())
        await answer(pg, GRC)
        check("Build: the right order is accepted", "Right." in await pg.locator(".ls-feedback").inner_text())
        await go_next(pg)

        # parse
        check("Parse drill is next; Check waits for every answer", await kind(pg) == "parse" and await pg.locator("[data-check]").is_disabled())
        await answer(pg, GRC)
        await go_next(pg)

        # retries come before the reading
        again = await pg.locator(".ls-again").count()
        check("Practice questions missed first time come back ('Have another go')", again == 1 and await kind(pg) == "choose")
        await answer(pg, GRC)
        await go_next(pg)
        check("…then the match again", await kind(pg) == "match" and await pg.locator(".ls-again").count() == 1)
        await answer(pg, GRC)
        await go_next(pg)

        # 4. Read real verses
        await pg.wait_for_selector(".ls-vw")
        check("Read step: John 1:1 word by word, every word known", "You know 17 of these 17 words" in await pg.locator(".ls-known").inner_text(),
              await pg.locator(".ls-known").inner_text())
        check("Read step: the BSB is shown", "In the beginning was the Word" in await pg.locator(".ls-verse-en").inner_text())
        await pg.click(".ls-vw >> nth=4")
        g = unicodedata.normalize("NFC", await pg.locator(".ls-gloss").inner_text())
        check("Tapping a word shows its dictionary form, meaning and grammar", "λόγος" in g and "word" in g and "Noun" in g, g)
        check("…with a link to the dictionary and to the Reader", await pg.locator('.ls-gloss a[href="#/words/G3056"]').count() == 1
              and await pg.locator('.ls-verse a[href="#/read/JHN/1/1"]').count() == 1)
        await go_next(pg)
        await pg.wait_for_selector(".ls-vw")
        check("John 1:2: the note is shown and known words are underlined", await pg.locator(".ls-note").count() == 1 and await pg.locator(".ls-vw.known").count() >= 6)
        await go_next(pg)

        # 5. Review and finish
        check("Last card lists the words and the button says 'Finish the lesson'", await kind(pg) == "words"
              and (await pg.locator("[data-next]").inner_text()) == "Finish the lesson" and await pg.locator(".ls-wordlist li").count() == 8)
        await go_next(pg)
        await pg.wait_for_selector(".ls-done")
        done = await pg.locator(".ls-done").inner_text()
        check("Finished: score counts first tries only (3 of 5) and 8 words added", "3 of 5" in done and "8 new words" in done, done)
        q = await pg.evaluate("JSON.parse(localStorage.getItem('ao:reviewQueue'))")
        check("Review list: 8 Greek words with lesson and date", len(q) == 8 and all(w["lang"] == "grc" and w["lesson"] == "grc-0" and w["added"] for w in q))
        prog = await pg.evaluate("JSON.parse(localStorage.getItem('ao:lessons'))['grc-0']")
        check("Progress: done, best 60%", prog.get("done") is True and prog.get("best") == 60, str(prog))
        backup = await pg.evaluate("async () => { const s = await import('./js/store.js'); return Object.keys(s.exportBackup().data); }")
        check("Backup includes lesson progress and the review list", "ao:lessons" in backup and "ao:reviewQueue" in backup)

        # 6. Doing it again (from Learn): no duplicates; best score kept or raised
        await pg.goto(f"{BASE}#/learn")
        await pg.wait_for_selector(".path li")
        check("Learn: the finished lesson is ticked, with its score", "Done · 60%" in await pg.locator('.path li.done').inner_text())
        await pg.click('a[href="#/lesson/grc/grc-0"]')
        await pg.wait_for_selector(".ls-card .ls-title")
        check("A finished lesson starts again from the beginning", await pg.locator("[data-back]").is_hidden())
        for _ in range(40):
            k = await kind(pg)
            if k in ("choose", "match", "build", "parse"):
                await answer(pg, GRC)
            if k == "verse":
                await pg.wait_for_selector(".ls-vw")
            label = await pg.locator("[data-next]").inner_text()
            await go_next(pg)
            if label.startswith("Finish"):
                break
        await pg.wait_for_selector(".ls-done")
        done = await pg.locator(".ls-done").inner_text()
        q = await pg.evaluate("JSON.parse(localStorage.getItem('ao:reviewQueue'))")
        prog = await pg.evaluate("JSON.parse(localStorage.getItem('ao:lessons'))['grc-0']")
        check("Second time: 5 of 5, no duplicate words, best now 100%", "5 of 5" in done and "already in your review list" in done
              and len(q) == 8 and prog["best"] == 100, f"{done} {len(q)} {prog}")

        # 7. Today and Review
        await pg.goto(f"{BASE}#/today")
        await pg.wait_for_function("document.querySelector('.today-lesson a[href=\"#/lesson/grc/grc-1\"]')", timeout=5000)
        await pg.wait_for_function("document.querySelector('.today-review').textContent.includes('to review')", timeout=5000)
        check("Today: the next Greek lesson is the alphabet; 8 words to review",
              "alphabet" in await pg.locator(".today-lesson").inner_text()
              and "8 words to review" in await pg.locator(".today-review").inner_text())
        await pg.goto(f"{BASE}#/review")
        await pg.wait_for_selector(".rv-summary")
        check("Review: the 8 lesson words are waiting as new words",
              "8 words" in await pg.locator(".rv-summary").inner_text() and "8 so far" in await pg.locator(".rv-lists").inner_text())
        await pg.evaluate("localStorage.setItem('ao:learnLang', JSON.stringify('he'))")
        await pg.goto(f"{BASE}#/today")
        await pg.wait_for_function("document.querySelector('.today-lesson a[href=\"#/lesson/he/he-0\"]')", timeout=5000)
        check("Today: points to the next lesson in the language being learnt (Hebrew)", "Genesis 1:1" in await pg.locator(".today-lesson").inner_text())

        # 8. Hebrew: right to left, build order, verse
        await pg.click(".today-lesson a")
        await pg.wait_for_selector(".ls-card .ls-title")
        while await kind(pg) != "build":
            if await kind(pg) in ("choose", "match"):
                await answer(pg, HE)
            await go_next(pg)
        check("Hebrew build: answer line and word bank run right to left",
              await pg.locator(".ls-line").get_attribute("dir") == "rtl" and await pg.locator(".ls-bank").get_attribute("dir") == "rtl")
        await answer(pg, HE)
        check("Hebrew build: in the right order", "Right." in await pg.locator(".ls-feedback").inner_text())
        await go_next(pg)
        await answer(pg, HE)
        await go_next(pg)
        await pg.wait_for_selector(".ls-vw")
        check("Hebrew verse: right to left, 7 of 7 words known, no raw <obj.> markers",
              await pg.locator(".ls-verse-words").get_attribute("dir") == "rtl" and "7 of these 7" in await pg.locator(".ls-known").inner_text()
              and "<" not in await pg.locator(".ls-verse-words").inner_text())

        # 9. Keyboard
        await pg.goto(f"{BASE}#/lesson/grc/grc-0")
        await pg.wait_for_selector(".ls-card .ls-title")
        await pg.focus("[data-next]")
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(200)
        focused = await pg.evaluate("document.activeElement.className + '|' + document.activeElement.tagName")
        check("Keyboard: Continue moves focus to the new card's heading", "ls-big" in focused or "ls-title" in focused, focused)

        # 9b. A lesson file that changes while someone is part-way through restarts cleanly
        await pg.goto(f"{BASE}#/learn")
        await pg.wait_for_selector(".path li")
        await pg.click("[data-lang=grc]")
        await pg.evaluate("""() => { const a = JSON.parse(localStorage.getItem('ao:lessons')); a['grc-0'].pos = 7; a['grc-0'].sig = 'old'; localStorage.setItem('ao:lessons', JSON.stringify(a)); }""")
        await pg.click('a[href="#/lesson/grc/grc-0"]')
        await pg.wait_for_selector(".ls-card .ls-title")
        check("A changed lesson file restarts at the first card", await pg.locator("[data-back]").is_hidden()
              and await pg.locator('.ls-steps li[aria-current="step"] .ls-step-full').inner_text() == "Hear and see")

        # 10. Odd links
        await pg.goto(f"{BASE}#/lesson/grc/grc-10")
        await pg.wait_for_selector(".note")
        check("A lesson that isn't written yet: friendly message", "isn't ready yet" in await pg.locator(".note").inner_text())
        await pg.goto(f"{BASE}#/lesson/xx/yy")
        await pg.wait_for_selector(".note")
        check("A nonsense lesson link: friendly message", "isn't ready yet" in await pg.locator(".note").inner_text())

        # 11. Narrow phone: every card fits
        await pg.set_viewport_size({"width": 320, "height": 640})
        await pg.goto(f"{BASE}#/lesson/he/he-0")
        await pg.wait_for_selector(".ls-card .ls-title")
        await pg.evaluate("localStorage.setItem('ao:lessons', '{}')")
        await pg.reload()
        await pg.wait_for_selector(".ls-card .ls-title")
        wide = []
        for _ in range(30):
            k = await kind(pg)
            if k == "verse":
                await pg.wait_for_selector(".ls-vw")
            sw = await pg.evaluate("document.documentElement.scrollWidth")
            if sw > 320:
                wide.append(f"{k}:{sw}")
            if k in ("choose", "match", "build", "parse"):
                await answer(pg, HE)
            label = await pg.locator("[data-next]").inner_text()
            await go_next(pg)
            if label.startswith("Finish"):
                break
        check("320px: every Hebrew card fits without sideways scrolling", not wide, str(wide))
        await pg.set_viewport_size({"width": 390, "height": 844})

        # 12. Offline: lessons are saved with the app
        ctx2 = await b.new_context(viewport={"width": 390, "height": 844})
        pg2 = await ctx2.new_page()
        await pg2.goto(f"{BASE}#/today")
        await pg2.evaluate("navigator.serviceWorker.ready")
        await pg2.wait_for_timeout(1500)
        await ctx2.set_offline(True)
        await pg2.goto(f"{BASE}#/lesson/he/he-0")
        await pg2.wait_for_selector(".ls-card .ls-title", timeout=10000)
        check("Offline: a lesson never opened before still opens (saved with the app)", await pg2.locator(".ls-card .ls-title").count() == 1)
        await ctx2.close()

        # 13. Every written lesson can be finished with the right answers, fits a 320px phone, and has no errors
        index = json.load(open("/home/claude/biblical-languages/lessons/index.json"))
        await pg.set_viewport_size({"width": 320, "height": 640})
        for lang, entries in index.items():
            for e in entries:
                if not e.get("file"):
                    continue
                L = json.load(open("/home/claude/biblical-languages/" + e["file"]))
                await pg.goto(f"{BASE}#/learn")
                await pg.wait_for_selector(".path li")
                await pg.evaluate(f"localStorage.setItem('ao:learnLang', JSON.stringify('{lang}'))")
                await pg.reload()
                await pg.wait_for_selector(f'a[href="#/lesson/{lang}/{e["id"]}"]')
                await pg.click(f'a[href="#/lesson/{lang}/{e["id"]}"]')
                await pg.wait_for_selector(".ls-card .ls-title, .ls-card .ls-big")
                wide, stuck = [], False
                for _ in range(80):
                    k = await kind(pg)
                    if k == "verse":
                        await pg.wait_for_selector(".ls-vw, .ls-verse .note, .ls-card .note", timeout=10000)
                    if await pg.evaluate("document.documentElement.scrollWidth") > 320:
                        wide.append(k)
                    if k in ("choose", "match", "build", "parse"):
                        await answer(pg, L)
                        if "Right." not in await pg.locator(".ls-feedback").inner_text():
                            stuck = f"{k}: {await title(pg)}"
                            break
                    label = await pg.locator("[data-next]").inner_text()
                    await go_next(pg)
                    if label.startswith("Finish"):
                        break
                done = await pg.locator(".ls-done").count() == 1 and "right first time" in await pg.locator(".ls-done").inner_text()
                check(f"{e['id']}: finished with every answer right, fits 320px", done and not wide and not stuck, f"{stuck} {wide}")
        await pg.set_viewport_size({"width": 390, "height": 844})

        # 14. Largest text on a 320px phone (8b): step labels readable, Continue inside the screen, tables fully in view
        await pg.set_viewport_size({"width": 320, "height": 640})
        await pg.evaluate("localStorage.setItem('ao:textSize', JSON.stringify('largest'))")
        cut, wide_at, scrolls = set(), [], []
        for e in index["grc"]:
            if not e.get("file"):
                continue
            L = json.load(open("/home/claude/biblical-languages/" + e["file"]))
            sig = ",".join(f"{st['step']}:{len(st['cards'])}" for st in L["steps"])
            cards = [c for st in L["steps"] for c in st["cards"]]
            for pos in sorted({0, 1} | {i for i, c in enumerate(cards) if c.get("table") or c["type"] in ("build", "verse", "words")}):
                await pg.evaluate(f"localStorage.setItem('ao:lessons', JSON.stringify({{'{e['id']}': {{v: 1, sig: '{sig}', pos: {pos}, retries: [], first: {{}}}}}}))")
                await pg.goto(f"{BASE}#/learn")
                await pg.goto(f"{BASE}#/lesson/grc/{e['id']}")
                await pg.wait_for_selector(".ls-card .ls-title, .ls-card .ls-big")
                r = await pg.evaluate("""() => ({
                  cut: [...document.querySelectorAll('.ls-steps li span')].filter((s) => getComputedStyle(s).display !== 'none' && getComputedStyle(s).position !== 'absolute' && s.scrollWidth > s.clientWidth).map((s) => s.textContent),
                  wide: document.documentElement.scrollWidth > innerWidth,
                  scrolls: [...document.querySelectorAll('.ls-table-wrap')].some((w) => w.scrollWidth > w.clientWidth) })""")
                cut |= set(r["cut"])
                if r["wide"]:
                    wide_at.append(f"{e['id']}@{pos}")
                if r["scrolls"]:
                    scrolls.append(f"{e['id']}@{pos}")
        check("largest text, 320px: every step label fits", not cut, str(sorted(cut)))
        check("largest text, 320px: lesson screens never scroll sideways (Continue inside)", not wide_at, str(wide_at[:5]))
        check("largest text, 320px: every lesson table fits without scrolling", not scrolls, str(scrolls[:5]))
        await pg.evaluate("localStorage.setItem('ao:textSize', JSON.stringify('normal')); localStorage.setItem('ao:lessons', '{}')")
        await pg.set_viewport_size({"width": 390, "height": 844})

        # 15. Joined builds say "pieces"; Settings shows Greek in the Greek font (8b)
        L4 = json.load(open("/home/claude/biblical-languages/lessons/grc/4.json"))
        sig4 = ",".join(f"{st['step']}:{len(st['cards'])}" for st in L4["steps"])
        pos4 = [i for i, c in enumerate([c for st in L4["steps"] for c in st["cards"]]) if c.get("join") == ""][0]
        await pg.evaluate(f"localStorage.setItem('ao:lessons', JSON.stringify({{'grc-4': {{v: 1, sig: '{sig4}', pos: {pos4}, retries: [], first: {{}}}}}}))")
        await pg.goto(f"{BASE}#/learn")
        await pg.goto(f"{BASE}#/lesson/grc/grc-4")
        await pg.wait_for_selector(".ls-build")
        how = await pg.locator(".ls-how").inner_text()
        await pg.click(".ls-bank [data-tile='1']"); await pg.click(".ls-bank [data-tile='0']"); await pg.click("[data-check]")
        fb = await pg.locator(".ls-feedback").inner_text()
        check("joined build: asks for pieces, and a wrong try shows the whole word", "pieces" in how and "The word is πιστεύομεν" in fb, f"{how} | {fb}")
        await pg.evaluate("localStorage.setItem('ao:lessons', '{}')")
        await pg.goto(f"{BASE}#/settings")
        await pg.wait_for_selector(".field-help")
        n = await pg.locator(".field-help .t-grc").count()
        check("Settings: pronunciation help shows Greek letters in the Greek font", n >= 4, str(n))

        check("no console errors", not errs, "; ".join(errs[:4]))
        await b.close()
    print(f"\n{sum(res)}/{len(res)} passed")


asyncio.run(main())
