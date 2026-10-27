"""Dictionary (Words tab) checks. Run with the local server on :8765:  python3 tools/test_dictionary.py"""
import asyncio, re, time
from playwright.async_api import async_playwright

BASE = "http://localhost:8765/"
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
res = []


def check(name, ok, detail=""):
    res.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


async def rows(pg):
    return [r.replace("\n", " | ") for r in await pg.locator(".dict-results .dict-row").all_inner_texts()]


async def search(pg, q):
    await pg.fill("#dict-q", q)
    await pg.wait_for_function("document.querySelector('.dict-count')", timeout=10000)
    await pg.wait_for_timeout(250)
    return await rows(pg)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

        # 1. The Words tab
        await pg.goto(f"{BASE}#/words")
        await pg.wait_for_selector('.dict-common[data-letter="H"] .dict-row')
        g = await pg.locator('.dict-common[data-letter="G"] .dict-row').all_inner_texts()
        h = await pg.locator('.dict-common[data-letter="H"] .dict-row').all_inner_texts()
        check("Words: most common Greek and Hebrew words listed, ὁ and καί first", len(g) == 25 and len(h) == 25 and g[0].startswith("ὁ") and g[1].startswith("καί"), g[:2])
        await pg.click('[data-more-common="G"]')
        check("Words: 'Show the top 100' lists 100", await pg.locator('.dict-common[data-letter="G"] .dict-row').count() == 100)

        # 2. Searching every way
        cases = [
            ("shepherd", lambda r: any(x.startswith("ποιμήν") for x in r) and any("רָעָה" in x for x in r), "English finds ποιμήν and רָעָה (from its definition)"),
            ("λογος", lambda r: r and r[0].startswith("λόγος"), "Greek without accents finds λόγος first"),
            ("logos", lambda r: r and r[0].startswith("λόγος"), "pronunciation finds λόγος first"),
            ("G3056", lambda r: len(r) == 1 and r[0].startswith("λόγος"), "Strong's G3056 finds λόγος"),
            ("3056", lambda r: len(r) == 2, "a bare number finds both languages"),
            ("H430", lambda r: r and "אֱלֹהִים" in r[0] and "God" in r[0], "Strong's H430 finds אֱלֹהִים, God first"),
            ("elohim", lambda r: r and "אֱלֹהִים" in r[0], "pronunciation finds אֱלֹהִים"),
            ("דבר", lambda r: any("H1697" in x for x in r) and any("H1696" in x for x in r), "Hebrew without vowels finds דָּבָר and דָבַר"),
            ("ἀγάπη", lambda r: r and r[0].startswith("ἀγάπη"), "Greek with accents finds ἀγάπη"),
            ("love", lambda r: any(x.startswith("ἀγαπάω") for x in r[:4]) and any("H157" in x for x in r[:4]), "English 'love' finds ἀγαπάω and אָהֵב (H157) at the top"),
        ]
        for q, ok, label in cases:
            r = await search(pg, q)
            check(f"Search: {label}", ok(r), f"{q}: {r[:3]}")
        await pg.fill("#dict-q", "xqzv")
        await pg.wait_for_function("document.querySelector('.dict-results').textContent.includes('No matches')", timeout=5000)
        check("Search: no matches explains what to try", "No matches" in await pg.text_content(".dict-results"))
        # speed
        await pg.fill("#dict-q", "")
        t = time.time()
        await pg.fill("#dict-q", "a")
        await pg.wait_for_function("document.querySelector('.dict-count')?.textContent.includes('match')")
        dt = time.time() - t
        check("Search: a one-letter search answers quickly", dt < 1.0, f"{dt:.2f}s")

        # 3. Language filter, remembered
        await pg.click('[data-lang="H"]')
        r = await search(pg, "word")
        check("Filter: Hebrew only shows no Greek", r and not any(re.search(r"[α-ωἀ-ῼ]", x) for x in r), r[:3])
        await pg.reload()
        await pg.wait_for_selector('.dict-switch [data-lang="H"][aria-pressed="true"]')
        check("Filter: choice remembered after reopening", True)
        await pg.click('[data-lang="both"]')

        # 4. An entry: λόγος
        await pg.goto(f"{BASE}#/words/G3056")
        await pg.wait_for_selector(".occ-books")
        count = await pg.text_content(".entry-count")
        first_form = (await pg.locator(".forms tbody tr").first.inner_text()).split("\t")
        nbooks = await pg.locator(".occ-book").count()
        link = await pg.get_attribute(".entry-def a[href='#/read/MAT/8/8']", "href")
        check("Entry λόγος: 330 times in 24 books", "330 times" in count and nbooks == 24, f"{count} {nbooks}")
        check("Entry λόγος: forms table starts with λόγον 130", first_form[0].strip() == "λόγον" and first_form[1].strip() == "130", first_form)
        check("Entry λόγος: definition links Matthew 8:8 into the Reader", link == "#/read/MAT/8/8")
        await pg.click('.occ-book[data-book="JHN"] summary')
        await pg.wait_for_selector('.occ-book[data-book="JHN"] .occ')
        lines = await pg.locator('.occ-book[data-book="JHN"] .occ').count()
        marked = await pg.locator('.occ-book[data-book="JHN"] .occ').first.locator("mark").inner_text()
        check("Entry λόγος: John lists all 40 places, the word highlighted", lines == 40 and "λόγος" in marked, f"{lines} {marked}")
        await pg.locator('.occ-book[data-book="JHN"] .occ').first.click()
        await pg.wait_for_selector(".chapter .w.on")
        on = await pg.text_content(".chapter .w.on .wg")
        chip = await pg.text_content(".return-chip")
        check("Verse link: opens John 1:1 with λόγος highlighted and a way back", "λόγος" in on and "λόγος" in chip and "John 1" in await pg.text_content(".rt-name"), f"{on} / {chip}")
        await pg.click(".return-chip")
        await pg.wait_for_selector('.occ-book[data-book="JHN"][open] .occ')
        check("Back: returns to λόγος with John still open", await pg.locator('.occ-book[data-book="JHN"][open]').count() == 1)

        # 5. A Hebrew entry with an outline definition and other senses
        await pg.goto(f"{BASE}#/words/H1254A")
        await pg.wait_for_selector(".entry-def")
        outline = await pg.locator(".def-line").count()
        sib = await pg.locator(".entry-sec .rows .dict-row").all_inner_texts()
        gen = await pg.text_content('.occ-book[data-book="GEN"] .occ-n')
        check("Entry בָּרָא: numbered definition, 'to fatten' as another meaning, 11 in Genesis",
              outline >= 10 and any("fatten" in s for s in sib) and gen.strip() == "11", f"{outline} {sib} {gen}")
        forms = [r.split("\t")[0].strip() for r in await pg.locator(".forms tbody tr").all_inner_texts()]
        check("Entry בָּרָא: forms differing only by a dagesh are one row", len(forms) == len(set(f.replace("ּ", "") for f in forms)), forms)

        await pg.goto(f"{BASE}#/words/H0157G")
        await pg.wait_for_selector(".entry-def")
        check("Definition: a mention of another entry (H0157H) links to it", await pg.locator(".entry-def a[href='#/words/H0157H']").count() >= 1)

        # 6. Entries that are not ordinary words
        await pg.goto(f"{BASE}#/words/H9002")
        await pg.wait_for_selector(".entry-count")
        check("Entry for a prefix (וְ 'and') explains it is joined to words", "joined to the front" in await pg.text_content(".entry-count"))
        await pg.goto(f"{BASE}#/words/G99999")
        await pg.wait_for_selector(".dict-entry .note")
        check("Unknown entry shows a message, not an error", "isn't in the dictionary" in await pg.text_content(".dict-entry"))
        await pg.goto(f"{BASE}#/words/G20447")
        await pg.wait_for_selector(".entry-count")
        check("Words without a Strong's number (ἐπίστασις G20447) have entries", "2 times" in await pg.text_content(".entry-count"))

        # 7. Recently looked up
        await pg.goto(f"{BASE}#/words")
        await pg.fill("#dict-q", "")
        await pg.wait_for_selector(".dict-section h2")
        recent = await pg.locator(".dict-section").first.inner_text()
        hrefs = await pg.locator(".dict-section").first.locator("a").evaluate_all("as => as.map(a => a.getAttribute('href'))")
        check("Recently looked up lists the entries opened", recent.startswith("Recently looked up") and "#/words/G3056" in hrefs and "#/words/H1254A" in hrefs, hrefs)
        await pg.click("[data-clear]")
        await pg.wait_for_timeout(300)
        check("Clearing the recent list works", "Recently looked up" not in await pg.text_content(".dict-results"))

        # 8. From the Reader to the dictionary and back to the same word
        await pg.goto(f"{BASE}#/read/GEN/1")
        await pg.wait_for_selector(".chapter .w")
        await pg.locator("#v27 .w").nth(1).click()
        await pg.click(".ws-dict a")
        await pg.wait_for_selector(".entry-lemma")
        lemma = await pg.text_content(".entry-lemma")
        await pg.click("[data-back]")
        await pg.wait_for_selector(".chapter .w.on")
        where = await pg.evaluate("document.querySelector('.chapter .w.on').closest('.v').id")
        check("Reader word → dictionary → back lands on the same word", "אֱלֹהִים" in lemma and where == "v27", f"{lemma} {where}")
        await pg.goto(f"{BASE}#/read/EXO/4/2")
        await pg.wait_for_selector(".chapter .w")
        await pg.locator("#v2 .w").nth(3).click()
        check("Reader: a compound word offers each dictionary word", await pg.locator(".ws-dict a").count() == 2)
        await pg.keyboard.press("Escape")

        # 9. Today's verse words lead to the dictionary
        await pg.goto(f"{BASE}#/today")
        await pg.wait_for_selector(".verse-original .w")
        await pg.locator(".verse-original .w").nth(1).click()
        href = await pg.get_attribute(".verse-dict", "href") or ""
        check("Today: a tapped word links to its dictionary entry", href.startswith("#/words/"), href)

        # 10. The longest list pages rather than drawing 2,800 lines at once
        await pg.goto(f"{BASE}#/words/G3588")
        await pg.wait_for_selector(".occ-books")
        await pg.click('.occ-book[data-book="MAT"] summary')
        await pg.wait_for_selector('.occ-book[data-book="MAT"] [data-occ-more]')
        n = await pg.locator('.occ-book[data-book="MAT"] .occ').count()
        await pg.click('.occ-book[data-book="MAT"] [data-occ-more]')
        await pg.wait_for_timeout(200)
        n2 = await pg.locator('.occ-book[data-book="MAT"] .occ').count()
        check("ὁ in Matthew: 50 places at a time, 'Show more' adds 50", n == 50 and n2 == 100, f"{n} {n2}")

        # 11. Offline: an entry opened once still opens
        await pg.goto(f"{BASE}#/today")
        await pg.evaluate("navigator.serviceWorker.ready")
        await pg.goto(f"{BASE}#/words/G0025")
        await pg.wait_for_selector(".occ-books")
        await pg.wait_for_timeout(800)
        await ctx.set_offline(True)
        await pg.reload()
        await pg.wait_for_selector(".entry-lemma", timeout=15000)
        check("Offline: ἀγαπάω opens after being opened once", "ἀγαπάω" in await pg.text_content(".entry-lemma"))
        await ctx.set_offline(False)
        check("No script errors", not errs, "; ".join(errs[:3]))

        # 12. Small phone, largest text: nothing wider than the screen
        c2 = await b.new_context(viewport={"width": 320, "height": 568})
        await c2.add_init_script("localStorage.setItem('ao:textSize', JSON.stringify('largest'))")
        p2 = await c2.new_page()
        bad = []
        for r, sel in [("words", ".dict-common .dict-row"), ("words/G3588", ".occ-books"), ("words/H0430G", ".occ-books"), ("words/G3056", ".entry-def")]:
            await p2.goto(f"{BASE}#/{r}")
            await p2.wait_for_selector(sel)
            for det in (await p2.locator(".occ-book").all())[:1]:
                await det.locator("summary").click()
                await p2.wait_for_timeout(600)
            ov = await p2.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if ov > 0:
                bad.append(f"{r} {ov}px")
        await p2.goto(f"{BASE}#/words")
        await p2.wait_for_selector(".dict-common .dict-row")
        await p2.fill("#dict-q", "shepherd")
        await p2.wait_for_timeout(500)
        ov = await p2.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        if ov > 0:
            bad.append(f"search {ov}px")
        check("320px, largest text: Words, results and entries fit the screen", not bad, ", ".join(bad))
        await c2.close()

        print(f"\n{sum(res)}/{len(res)} passed")
        await b.close()

asyncio.run(main())
