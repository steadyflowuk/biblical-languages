"""ESV, Septuagint and side-by-side checks (Session 6). Run with the local server on :8765:
python3 tools/test_translations.py

The ESV API is mocked here (no real key is ever used in tests); the real API is checked by hand on the live site."""
import asyncio, json, re, unicodedata
from playwright.async_api import async_playwright

BASE = "http://localhost:8765/"
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
res = []
esv_calls = []
esv_mode = {"status": 200, "offline": False}


def nfc(t):
    return unicodedata.normalize("NFC", t)


def check(name, ok, detail=""):
    res.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def esv_body(url):
    m = re.search(r"q=(\d\d)(\d\d\d)001", url)
    if not m:
        return {"passages": ["For God so loved the world, that he gave his only Son"]}
    b, c = int(m.group(1)), int(m.group(2))
    if b == 19 and c == 23:  # shaped like the real API's plain text
        return {"passages": ["A Psalm of David.\n\n[1] The LORD is my shepherd; I shall not want.\n    [2] He makes me lie down in green pastures.\n He leads me beside still waters.\n[3] He restores my soul.\n[4] Even though I walk.\n[5] You prepare a table.\n[6] Surely goodness and mercy.\n"]}
    if b == 22 and c == 1:  # Song of Songs speaker labels
        return {"passages": ["She\n\n[2] Let him kiss me with the kisses of his mouth!\n\n" + " ".join(f"[{v}] Song verse {v}." for v in range(3, 18))]}
    return {"passages": [" ".join(f"[{v}] ESV {b}:{c}:{v}." for v in range(1, 60))]}


async def esv_route(route):
    esv_calls.append(route.request.url)
    if esv_mode["offline"]:
        await route.abort()
        return
    if esv_mode["status"] != 200:
        await route.fulfill(status=esv_mode["status"], headers={"Access-Control-Allow-Origin": "*"}, body="{}")
        return
    await route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"},
                        body=json.dumps(esv_body(route.request.url)))


async def set_prefs(pg, **prefs):
    await pg.evaluate("p => { for (const [k, v] of Object.entries(p)) localStorage.setItem('ao:' + k, JSON.stringify(v)); }", prefs)


async def open_chapter(pg, ref, wait=".v"):
    await pg.goto(f"{BASE}#/today")
    await pg.goto(f"{BASE}#/read/{ref}")
    await pg.wait_for_selector(f".chapter {wait}", timeout=15000)
    await pg.wait_for_timeout(900)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        await ctx.route("https://api.esv.org/**", esv_route)
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "api.esv.org" not in m.text and "Failed to load resource" not in m.text else None)

        # 1. Without a key: the option says what's needed and the Reader points to Settings
        await pg.goto(f"{BASE}#/today")
        await pg.evaluate("localStorage.clear()")
        await set_prefs(pg, showESV=True, readLayout="words")
        await open_chapter(pg, "JHN/3")
        note = await pg.locator(".chapter .v-note").first.inner_text()
        check("no key: Reader says to add the key in Settings", "Settings" in note and await pg.locator(".esv").count() == 0, note)
        check("no key: no ESV requests", not esv_calls, str(esv_calls[:2]))

        # 2. Settings: save a key (pasted with its header), not in backups
        await pg.goto(f"{BASE}#/settings")
        await pg.fill("[data-esv-key]", "Authorization: Token TESTKEY123")
        await pg.click("[data-esv-save]")
        await pg.wait_for_selector("[data-esv-remove]", timeout=5000)
        key = await pg.evaluate("localStorage.getItem('esv:key')")
        check("Settings saves the key without 'Authorization: Token'", key == "TESTKEY123", key)
        auth = await pg.evaluate("""async () => { const s = await import('./js/store.js'); return JSON.stringify(s.exportBackup()); }""")
        check("backup leaves the ESV key out", "TESTKEY123" not in auth and "esv:" not in auth, auth[:200])
        notice = await pg.locator(".esv-notice").inner_text()
        check("Settings shows the ESV copyright notice and www.esv.org link",
              "Crossway" in notice and await pg.locator('.esv-notice a[href="https://www.esv.org"], a[href="https://www.esv.org"]').count() > 0, notice[:80])

        # 3. Wrong key
        esv_mode["status"] = 401
        await pg.click("[data-esv-remove]")
        await pg.fill("[data-esv-key]", "WRONG")
        await pg.click("[data-esv-save]")
        await pg.wait_for_function("document.querySelector('[data-esv-msg]').textContent.includes('accepted')", timeout=5000)
        check("a refused key isn't saved", await pg.evaluate("localStorage.getItem('esv:key')") is None)
        esv_mode["status"] = 200
        await pg.fill("[data-esv-key]", "TESTKEY123")
        await pg.click("[data-esv-save]")
        await pg.wait_for_selector("[data-esv-remove]", timeout=5000)

        # 4. Word by word, Psalm 23: BSB, ESV and Septuagint under each verse, labelled
        await set_prefs(pg, showESV=True, showLXX=True, showBSB=True, readLayout="words")
        esv_calls.clear()
        await open_chapter(pg, "PSA/23")
        await pg.wait_for_function("!document.querySelector('.esv .muted') && !document.querySelector('.lxx .muted:not(:empty)') || document.querySelectorAll('.lxx-ref').length", timeout=8000)
        await pg.wait_for_timeout(500)
        tags = await pg.locator("#v1 .tr-tag").all_inner_texts()
        check("Psalm 23:1 has BSB, ESV and LXX labels", tags == ["BSB", "ESV", "LXX"], str(tags))
        e1 = await pg.locator("#v1 .esv").inner_text()
        check("ESV 23:1 text, verse number markers removed", "The LORD is my shepherd; I shall not want." in e1 and "[" not in e1, e1)
        e2 = await pg.locator("#v2 .esv").inner_text()
        check("ESV line breaks inside a verse are joined", "pastures. He leads me" in e2, e2)
        e0 = await pg.locator("#v0 .esv").inner_text()
        check("ESV psalm title goes with the title (verse 0)", "A Psalm of David." in e0, e0)
        l0 = await pg.locator("#v0 .lxx").inner_text()
        check("Septuagint psalm title note", "part of the first verse" in l0, l0)
        l1 = nfc(await pg.locator("#v1 .lxx").inner_text())
        check("Psalm 23:1 Septuagint is Psalm 22:1 (labelled)", "22:1" in l1 and "Κύριος ποιμαίνει" in l1, l1)
        n = await pg.locator(".chapter .v-note").first.inner_text()
        check("note: in the Septuagint this is Psalm 22", "Psalm 22" in n and await pg.locator('.v-note a[href="#/lxx/PSA/22"]').count() == 1, n)
        check("one ESV request per chapter, whole chapter range",
              len(esv_calls) == 1 and "q=19023001-19023999" in esv_calls[0], str(esv_calls))
        check("ESV credit with www.esv.org link under the chapter",
              await pg.locator('.esv-credit a[href="https://www.esv.org"]').count() == 1)

        # 5. Song of Songs: speaker labels aren't verses or text
        await open_chapter(pg, "SNG/1")
        await pg.wait_for_function("document.querySelector('#v2 .esv') && !document.querySelector('#v2 .esv .muted')", timeout=8000)
        s2 = await pg.locator("#v2 .esv").inner_text()
        check("Song of Songs speaker label left out of the ESV", "She" not in s2 and "Let him kiss" in s2, s2)

        # 6. Weak chapter: note, no line-by-line Septuagint
        await open_chapter(pg, "EXO/37")
        await pg.wait_for_timeout(800)
        weak = await pg.locator(".chapter .v-note").first.inner_text()
        check("weak chapter: note and link instead of verse lines",
              "can't be lined up" in weak and await pg.locator(".lxx").count() == 0, weak)

        # 7. Renumbered chapters
        await open_chapter(pg, "JER/31")
        await pg.wait_for_selector("#v31 .lxx-ref")
        j = nfc(await pg.locator("#v31 .lxx").inner_text())
        check("Jeremiah 31:31 = Septuagint 38:31", "38:31" in j and "διαθήκην καινήν" in j, j)
        await open_chapter(pg, "MAL/4")
        await pg.wait_for_selector("#v5 .lxx-ref")
        m5 = nfc(await pg.locator("#v5 .lxx").inner_text())
        check("Malachi 4:5 (Elijah) = Septuagint 4:4", "4:4" in m5 and "Ἠλίαν" in m5, m5)
        await open_chapter(pg, "DAN/4")
        await pg.wait_for_selector("#v1 .lxx-ref")
        d1 = await pg.locator("#v1 .lxx").inner_text()
        check("Daniel 4:1 = Septuagint (Theodotion) 3:98", "3:98" in d1, d1)

        # 8. New Testament: no Septuagint, ESV still there
        await open_chapter(pg, "JHN/3")
        await pg.wait_for_function("document.querySelector('#v16 .esv') && !document.querySelector('#v16 .esv .muted')", timeout=8000)
        check("NT: ESV shown, no Septuagint", await pg.locator(".lxx").count() == 0 and "ESV 43:3:16." in await pg.locator("#v16 .esv").inner_text())

        # 9. Running text: translations off, options disabled
        await set_prefs(pg, readLayout="text")
        await open_chapter(pg, "PSA/23", ".para")
        check("running text: no translation lines", await pg.locator(".esv, .lxx, .bsb").count() == 0)
        await pg.click("[data-display]")
        check("running text: Translations options disabled", await pg.evaluate("document.querySelector('fieldset.tr-opts').disabled"))
        await pg.check("input[value=parallel]")
        await pg.wait_for_selector(".chapter.layout-parallel .pv")
        check("switching to side by side redraws", not await pg.evaluate("document.querySelector('fieldset.tr-opts').disabled"))
        await pg.keyboard.press("Escape")

        # 10. Side by side on a phone: stacked, labelled
        await open_chapter(pg, "PSA/23", ".pv")
        await pg.wait_for_timeout(800)
        cls = await pg.locator("#v1 .cols").get_attribute("class")
        labels = await pg.locator("#v1 .col-label").all_text_contents()
        cols_css = await pg.evaluate("getComputedStyle(document.querySelector('#v1 .cols')).gridTemplateColumns.split(' ').length")
        check("side by side: 4 columns (Hebrew, BSB, ESV, Septuagint)", cls == "cols n4" and labels == ["BSB", "ESV", "Septuagint"], f"{cls} {labels}")
        check("side by side: stacked on a phone", cols_css == 1, str(cols_css))
        sw = await pg.evaluate("document.documentElement.scrollWidth")
        check("side by side: no sideways scrolling at 390px", sw <= 390, str(sw))
        await pg.click("#v1 .col-orig .w >> nth=0")
        await pg.wait_for_selector(".sheet .ws-word")
        check("side by side: Hebrew words still open the word sheet", await pg.locator(".sheet .ws-word.he").count() == 1)
        await pg.keyboard.press("Escape")

        # 11. Side by side on iPad: real columns, header, wider page
        await pg.set_viewport_size({"width": 1180, "height": 820})
        await pg.wait_for_timeout(400)
        cols_css = await pg.evaluate("getComputedStyle(document.querySelector('#v1 .cols')).gridTemplateColumns.split(' ').length")
        head = await pg.locator(".pv-head").is_visible()
        wide = await pg.evaluate("document.querySelector('.screen.reader').classList.contains('wide')")
        check("iPad side by side: 4 columns with a header row", cols_css == 4 and head and wide, f"{cols_css} {head} {wide}")
        await open_chapter(pg, "JHN/1", ".pv")
        check("iPad NT side by side: Greek, BSB, ESV", await pg.locator(".pv-head .col").all_text_contents() == ["Greek", "BSB", "ESV"])
        await pg.set_viewport_size({"width": 390, "height": 844})

        # 12. ESV problems
        esv_mode["status"] = 401
        await pg.evaluate("localStorage.removeItem('esv:chapters')")
        await set_prefs(pg, readLayout="words")
        await open_chapter(pg, "GEN/2")
        await pg.wait_for_selector(".esv-msg:not([hidden])", timeout=8000)
        msg = await pg.locator(".esv-msg").inner_text()
        check("refused key: a clear message, page still readable", "Settings" in msg and await pg.locator(".bsb").count() > 0, msg)
        esv_mode["status"] = 200
        await open_chapter(pg, "GEN/3")
        await pg.wait_for_function("document.querySelector('#v1 .esv') && !document.querySelector('#v1 .esv .muted')", timeout=8000)
        esv_mode["offline"] = True
        await pg.evaluate("async () => { const e = await import('./js/esv.js'); e.setKey(e.getKey()); }")  # clears this session's memory
        await open_chapter(pg, "GEN/3")
        await pg.wait_for_function("document.querySelector('#v1 .esv') && !document.querySelector('#v1 .esv .muted')", timeout=8000)
        check("offline: a recently read ESV chapter still shows", "ESV 1:3:1." in await pg.locator("#v1 .esv").inner_text())
        await open_chapter(pg, "GEN/4")
        await pg.wait_for_selector(".esv-msg:not([hidden])", timeout=8000)
        check("offline: unread ESV chapter explains it needs a connection", "internet" in await pg.locator(".esv-msg").inner_text())
        esv_mode["offline"] = False

        # 13. The offline ESV store stays within Crossway's limit
        await pg.evaluate("""async () => { const e = await import('./js/esv.js');
          for (let c = 1; c <= 25; c++) { try { await e.chapter(1, c); } catch (x) {} } }""")
        stored = await pg.evaluate("JSON.parse(localStorage.getItem('esv:chapters')||'[]').reduce((n, x) => n + Object.keys(x[1]).length, 0)")
        check("ESV offline store holds no more than 450 verses", 0 < stored <= 450, str(stored))

        # 14. Septuagint screen
        await pg.goto(f"{BASE}#/lxx/PSA/22/4")
        await pg.wait_for_selector(".lxx-text .lv")
        await pg.wait_for_timeout(400)
        check("Septuagint screen: title and page title",
              (await pg.locator(".rt-name").inner_text()) == "Psalm 22" and "Septuagint" in await pg.title())
        check("Septuagint screen: verse from the link is highlighted", await pg.locator("#v4.focus").count() == 1)
        cmp_ = await pg.locator(".lxx-compare a").get_attribute("href")
        check("Septuagint screen: compare with Hebrew Psalm 23", cmp_ == "#/read/PSA/23", cmp_)
        check("Read tab is current on the Septuagint screen", await pg.locator('.tabs a[data-tab="read"][aria-current="page"]').count() >= 1)
        await pg.locator(".lxx-text .lw", has_text="Κύριος").first.click()
        await pg.wait_for_selector(".lxx-look .rows li, .lxx-look .dict-row", timeout=10000)
        look = nfc(await pg.locator(".lxx-look").inner_text())
        check("tapping a Septuagint word finds κύριος", "κύριος" in look, look[:120])
        await pg.click("[data-lxx-search]")
        await pg.wait_for_selector("#dict-q")
        check("'Search the dictionary' fills the Words search", (await pg.input_value("#dict-q")) == "Κύριος")
        await pg.goto(f"{BASE}#/lxx/GEN/50")
        await pg.wait_for_selector(".lxx-text .lv")
        nxt = await pg.locator(".chapter-nav a").last.get_attribute("href")
        check("Septuagint next chapter runs on to the next book", nxt == "#/lxx/EXO/1", nxt)
        await pg.goto(f"{BASE}#/lxx/SIR/1")
        await pg.wait_for_selector(".lxx-text .lv")
        check("a book found only in Greek (Sirach) opens, no Hebrew link",
              await pg.locator(".lxx-compare").count() == 0 and await pg.locator(".lv").count() > 10)
        await pg.goto(f"{BASE}#/lxx/XYZ/1")
        await pg.wait_for_selector(".note")
        check("unknown Septuagint book: friendly message", "isn't in the Septuagint" in await pg.locator(".note").inner_text())
        await pg.goto(f"{BASE}#/lxx")
        await pg.wait_for_selector(".lxx-text .lv")
        check("#/lxx reopens the last Septuagint chapter", (await pg.locator(".rt-name").inner_text()) == "Sirach 1")

        # 15. Picker: Septuagint tab
        await open_chapter(pg, "PSA/23")
        await pg.click("[data-pick]")
        await pg.click('[data-testament="LXX"]')
        await pg.wait_for_selector("[data-lxx-book]")
        n_books = await pg.locator("[data-lxx-book]").count()
        check("picker: Septuagint tab lists 60 books in groups", n_books == 60, str(n_books))
        await pg.click('[data-lxx-book="TOB"]')
        await pg.click('.pick-ch[href="#/lxx/TOB/3"]')
        await pg.wait_for_selector(".lxx-text .lv")
        check("picker: choosing Tobit 3 opens it", (await pg.locator(".rt-name").inner_text()) == "Tobit 3")
        sw = await pg.evaluate("document.documentElement.scrollWidth")
        check("Septuagint screen: no sideways scrolling", sw <= 390, str(sw))

        # 16. 320px: side by side and Septuagint
        await pg.set_viewport_size({"width": 320, "height": 640})
        await set_prefs(pg, readLayout="parallel")
        for ref in ["PSA/119", "ROM/16", "EST/1"]:
            await open_chapter(pg, ref, ".pv")
            sw = await pg.evaluate("document.documentElement.scrollWidth")
            check(f"320px side by side {ref}: no sideways scrolling", sw <= 320, str(sw))
        await pg.goto(f"{BASE}#/lxx/ESG/1")
        await pg.wait_for_selector(".lxx-text .lv")
        sw = await pg.evaluate("document.documentElement.scrollWidth")
        check("320px Septuagint Esther (Greek): no sideways scrolling", sw <= 320, str(sw))

        check("no console errors", not errs, "; ".join(errs[:4]))
        await b.close()
    print(f"\n{sum(res)}/{len(res)} passed")


asyncio.run(main())
