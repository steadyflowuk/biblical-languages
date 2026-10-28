"""Alphabet and sounds checks (Session 10c). Run with the local server on :8765:  python3 tools/test_alphabet.py

The phone's voices are replaced by a stand-in that records what it was asked to say (no real voices here).
"""
import asyncio, json, re, faulthandler
from playwright.async_api import async_playwright

faulthandler.dump_traceback_later(600, exit=True)
BASE = "http://localhost:8765/"
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
ROOT = "/home/claude/biblical-languages/"
GRC = json.load(open(ROOT + "lessons/alphabet/grc.json"))
HE = json.load(open(ROOT + "lessons/alphabet/he.json"))
res = []
cons = lambda t: re.sub(r"[\u0591-\u05C7]", "", t)

VOICES = """
window.__spoken = [];
window.__voices = [{name: 'Melina', lang: 'el-GR', localService: true}, {name: 'Carmit', lang: 'he-IL', localService: true}];
window.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; } };
Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
  getVoices() { return window.__voices; },
  speak(u) { window.__spoken.push({ text: u.text, lang: u.lang, rate: u.rate }); setTimeout(() => u.onend && u.onend(), 30); },
  cancel() {}, addEventListener() {} } });
"""


def check(name, ok, detail=""):
    res.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


async def fresh(pg, extra=None):
    await pg.goto(f"{BASE}#/settings")
    await pg.evaluate("localStorage.clear()")
    for k, v in (extra or {}).items():
        await pg.evaluate(f"localStorage.setItem('ao:{k}', JSON.stringify({json.dumps(v, ensure_ascii=False)}))")


async def open_guide(pg, lang):
    await pg.goto(f"{BASE}#/today")
    await pg.goto(f"{BASE}#/alphabet/{lang}")
    await pg.wait_for_selector(".ab-grid")
    await pg.wait_for_selector(".ab-verse", timeout=15000)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        await ctx.add_init_script(VOICES)
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

        # 1. Learn links to the guide for the language shown
        await fresh(pg)
        await pg.goto(f"{BASE}#/learn")
        await pg.wait_for_selector(".learn-abc a")
        check("Learn: Alphabet and sounds row (Greek)", await pg.get_attribute(".learn-abc a", "href") == "#/alphabet/grc")
        await pg.click(".screen [data-lang='he']")
        await pg.wait_for_function("document.querySelector('.learn-abc a').getAttribute('href') === '#/alphabet/he'", timeout=3000)
        check("Learn: the row follows the Hebrew switch", True)
        await pg.click(".screen [data-lang='grc']")
        await pg.wait_for_function("document.querySelector('.learn-abc a').getAttribute('href') === '#/alphabet/grc'", timeout=3000)
        await pg.click(".learn-abc a")
        await pg.wait_for_selector(".ab-grid")
        check("Learn row opens the guide; Learn tab stays current",
              await pg.evaluate("!!document.querySelector('[href=\"#/learn\"][aria-current=\"page\"]')"))

        # 2. Greek page
        await open_guide(pg, "grc")
        n = await pg.locator(".ab-tile").count()
        check("Greek: 24 letter tiles", n == 24, str(n))
        secs = await pg.locator(".ab-section h2").all_inner_texts()
        check("Greek: every section plus Read aloud", [s["title"] for s in GRC["sections"]] + ["Read aloud"] == secs, str(secs))
        t = await pg.locator(".ab-section").nth(len(GRC["sections"])).inner_text()
        check("Read aloud: John 1:1 from the Bible text, with its pronunciation", "Ἐν ἀρχῇ ἦν ὁ λόγος" in t and "en ar-KHAY ayn ho LO-gos" in t, t[:200])
        # Every example respelling matches the app's own Erasmian respelling (greekSay)
        exs = [L["example"] for L in GRC["letters"]] + [e for s in GRC["sections"] for e in s.get("examples", [])]
        got = await pg.evaluate("async (ws) => { const s = await import('./js/sound.js'); return ws.map((w) => s.greekSay(w)); }", [e["t"] for e in exs])
        bad = [(e["t"], e["say"], g) for e, g in zip(exs, got) if e["say"] != g]
        check(f"All {len(exs)} Greek examples respelt as the app says them", not bad, str(bad[:5]))

        # 3. Letter sheet: forms, name, Erasmian + Koine, previous / next, Listen
        await pg.click("[data-letter='1']")
        await pg.wait_for_selector(".sheet .ab-big")
        s = await pg.locator(".sheet-body").inner_text()
        check("Beta sheet: Β β, βῆτα BAY-ta, b (used in the app), Restored Koine v",
              "Β β" in s and "βῆτα" in s and "BAY-ta" in s and "used in the app" in s and "Restored Koine" in s and "βασιλεία" in s, s[:300])
        check("Sheet: focus inside, page behind inert", await pg.evaluate("document.querySelector('.sheet').contains(document.activeElement) && [...document.body.children].filter((e) => !e.classList.contains('sheet')).every((e) => e.hasAttribute('inert') || e.tagName === 'SCRIPT')"))
        await pg.evaluate("window.__spoken = []")
        await pg.click(".ab-sheet-name [data-say]")
        await pg.wait_for_timeout(120)
        sp = await pg.evaluate("window.__spoken")
        check("Listen to the name: Greek voice, Erasmian respelt (μπέιτα)", sp and sp[-1]["lang"] == "el-GR" and sp[-1]["text"] == "μπέιτα", str(sp))
        await pg.click("[data-step='1']")
        await pg.wait_for_function("document.querySelector('.ab-big').textContent.includes('γ')")
        check("Next: gamma", "gamma" in (await pg.locator(".ab-sheet-name").inner_text()))
        await pg.click("[data-step='-1']")
        await pg.click("[data-step='-1']")
        await pg.wait_for_function("document.querySelector('.ab-big').textContent.includes('α')")
        check("First letter: Previous is off", await pg.locator("[data-step='-1']").is_disabled())
        await pg.keyboard.press("Escape")
        await pg.wait_for_selector(".sheet", state="detached")
        check("Escape closes; focus back on the tile", await pg.evaluate("document.activeElement.dataset.letter === '0'"))

        # Restored Koine chosen in Settings: the tag moves
        await pg.evaluate("localStorage.setItem('ao:greekVoice', JSON.stringify('koine'))")
        await pg.click("[data-letter='1']")
        await pg.wait_for_selector(".sheet .ab-big")
        tags = await pg.evaluate("[...document.querySelectorAll('.sheet .ws-facts div')].map((d) => d.querySelector('dt').textContent + '|' + !!d.querySelector('.tag'))")
        check("Koine voice chosen: 'used in the app' sits beside Restored Koine", "Sound (Erasmian)|false" in tags and "Restored Koine|true" in tags, str(tags))
        await pg.keyboard.press("Escape")
        await pg.evaluate("localStorage.removeItem('ao:greekVoice')")

        # 4. Hebrew page: right to left, finals, the vowel table, practice say
        await pg.click(".switch-link[href='#/alphabet/he']")
        await pg.wait_for_function("document.querySelectorAll('.ab-tile').length === 22")
        await pg.wait_for_selector(".ab-verse", timeout=15000)
        check("Hebrew: 22 tiles, the grid right to left", await pg.get_attribute(".ab-grid", "dir") == "rtl")
        check("Switch: Hebrew current", await pg.get_attribute(".switch-link[href='#/alphabet/he']", "aria-current") == "page")
        vt = await pg.locator(".ab-section").first.inner_text()
        check("Vowel table: qamets, patah, shewa, holam", all(w in vt for w in ("qamets", "patah", "shewa", "holam")), vt[:200])
        rt = await pg.locator(".ab-section").last.inner_text()
        check("Read aloud: Genesis 1:1 and Deuteronomy 6:4 in Hebrew", "בראשית" in cons(rt) and "שמע" in cons(rt) and "Deuteronomy 6:4" in rt, rt[:200])
        check("Hebrew verse text has no cantillation", await pg.evaluate(r"![...document.querySelectorAll('.ab-verse-t')].some((p) => /[֑-֯]/.test(p.textContent))"))
        await pg.click("[data-letter='10']")  # kaf: three forms
        await pg.wait_for_selector(".sheet .ab-big")
        kb = await pg.locator(".ab-big").inner_text()
        check("Kaf sheet: כּ כ ך", all(f in kb for f in HE["letters"][10]["forms"]), kb)
        await pg.evaluate("window.__spoken = []")
        await pg.click(".sheet .ls-examples [data-say]")
        await pg.wait_for_timeout(120)
        sp = await pg.evaluate("window.__spoken")
        check("Listen to a Hebrew example: Israeli voice", sp and sp[-1]["lang"] == "he-IL", str(sp))
        await pg.keyboard.press("Escape")
        await pg.evaluate("window.__spoken = []")
        await pg.click(".ab-verse [data-say]")
        await pg.wait_for_timeout(120)
        sp = await pg.evaluate("window.__spoken")
        check("Listen to the verse: Genesis 1:1, divine name and accents handled", sp and sp[-1]["lang"] == "he-IL" and cons(sp[-1]["text"]).startswith("בראשית ברא אלהים"), str(sp))
        await pg.click(".ab-verse-ref a")
        await pg.wait_for_selector(".verse, .chapter", timeout=15000)
        check("Verse link opens the Reader at Genesis 1:1", "#/read/GEN/1/1" in pg.url, pg.url)

        # 5. Review: alphabet flashcards first, then lesson words
        q = [{"k": "G3056", "lang": "grc", "t": "λόγος", "say": "LO-gos", "en": "word", "lesson": "grc-0", "added": "2026-10-27"}]
        await fresh(pg, {"reviewQueue": q, "newPerDay": 30})
        await pg.goto(f"{BASE}#/today")
        await pg.goto(f"{BASE}#/review")
        await pg.wait_for_selector(".rv-summary")
        check("Review: alphabet switches for both languages, off to start",
              await pg.locator("[data-deck='grcLetters']").count() == 1 and not await pg.locator("[data-deck='grcLetters']").is_checked()
              and await pg.locator("[data-deck='heLetters']").count() == 1)
        await pg.check("[data-deck='grcLetters']")
        await pg.wait_for_function("document.querySelector('.rv-summary').textContent.includes('25 new')", timeout=5000)
        check("Greek alphabet on: 24 letters + 1 lesson word", True)
        await pg.click("[data-start]")
        first = await pg.locator(".rv-word").inner_text()
        check("Letters come first, in alphabet order: Α α", first == "Α α", first)
        meta = await pg.locator(".rv-meta").inner_text()
        await pg.evaluate("window.__spoken = []")
        await pg.click(".rv-listen [data-say]")
        await pg.wait_for_timeout(120)
        sp = await pg.evaluate("window.__spoken")
        check("Letter card: marked 'alphabet'; Listen says the letter's name", "alphabet" in meta and sp and sp[-1]["text"] == "άλφα", f"{meta} {sp}")
        await pg.click("[data-show]")
        a = await pg.locator(".rv-answer").inner_text()
        check("Answer: name, sound, an example and a link to the guide",
              "AL-fa" in a and "alpha" in a and GRC["letters"][0]["example"]["t"] in a and "Alphabet guide" in a, a)
        await pg.click("[data-rate='3']")
        cards = await pg.evaluate("JSON.parse(localStorage.getItem('ao:cards'))")
        check("Card saved as grc:abc:0", "grc:abc:0" in cards and cards["grc:abc:0"]["src"] == "abc", str(list(cards)))
        await pg.click("[data-stop]")
        await pg.wait_for_selector(".rv-summary")
        # Word list links an alphabet card to the guide
        await pg.evaluate("document.querySelectorAll('details.rv-words').forEach((d) => d.open = true)")
        href = await pg.locator("details.rv-words a.row").first.get_attribute("href")
        check("Your words: a letter links to the guide", href == "#/alphabet/grc", href)
        # Guide notes the letters are in Review
        await open_guide(pg, "grc")
        check("Guide: 'The letters are in your review list.'", "in your review list" in await pg.locator(".ab-practise").inner_text())
        # Hebrew letters
        await fresh(pg, {"reviewDecks": {"heLetters": True}})
        await pg.goto(f"{BASE}#/today")
        await pg.goto(f"{BASE}#/review")
        await pg.wait_for_selector("[data-start]")
        await pg.click("[data-start]")
        w = pg.locator(".rv-word")
        check("Hebrew alphabet cards: alef first, right to left", (await w.inner_text()).strip() == "א" and await w.get_attribute("dir") == "rtl", await w.inner_text())

        # 6. Desktop: side rail, no overflow
        await pg.set_viewport_size({"width": 1180, "height": 820})
        await open_guide(pg, "grc")
        check("iPad width: no sideways scroll", not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"))

        # 7. 320px, largest text, dark; and offline after one visit
        await ctx.close()
        ctx = await b.new_context(viewport={"width": 320, "height": 640}, color_scheme="dark")
        await ctx.add_init_script(VOICES)
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_INTERNET_DISCONNECTED" not in m.text else None)
        await fresh(pg, {"textSize": "largest"})
        for lang in ("grc", "he"):
            await open_guide(pg, lang)
            wide = await pg.evaluate("[...document.querySelectorAll('.screen *')].filter((e) => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('.ls-table-wrap, .table-wrap')).map((e) => e.className || e.tagName).slice(0, 5)")
            over = await pg.evaluate("document.documentElement.scrollWidth > innerWidth")
            check(f"320px, largest, dark ({lang}): nothing off the side", not wide and not over, str(wide))
            await pg.click("[data-letter='3']")
            await pg.wait_for_selector(".sheet .ab-big")
            sw = await pg.evaluate("document.querySelector('.sheet-panel').scrollWidth <= document.querySelector('.sheet-panel').clientWidth + 1")
            check(f"320px letter sheet fits ({lang})", sw)
            await pg.keyboard.press("Escape")
        await pg.evaluate("navigator.serviceWorker.ready")
        await pg.wait_for_timeout(1500)
        await pg.goto(f"{BASE}#/today")
        await pg.goto(f"{BASE}#/alphabet/he")  # also caches the verse books
        await pg.wait_for_selector(".ab-verse", timeout=15000)
        await pg.goto(f"{BASE}#/today")
        await ctx.set_offline(True)
        await pg.reload()
        await pg.goto(f"{BASE}#/alphabet/grc")
        await pg.wait_for_selector(".ab-grid", timeout=10000)
        await pg.wait_for_selector(".ab-verse", timeout=15000)
        check("Offline: the guide opens (saved with the app)", await pg.locator(".ab-tile").count() == 24)
        await ctx.set_offline(False)

        check("No console errors", not errs, str(errs[:5]))
        await b.close()
    print(f"\n{sum(res)}/{len(res)} passed")
    raise SystemExit(0 if all(res) else 1)


asyncio.run(main())
