"""Review trainer and audio checks (Session 9). Run with the local server on :8765:  python3 tools/test_review.py

The phone's voices are replaced by a stand-in that records what it was asked to say (no real voices here).
"""
import asyncio, json, re, faulthandler
from playwright.async_api import async_playwright

faulthandler.dump_traceback_later(900, exit=True)
BASE = "http://localhost:8765/"
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
ROOT = "/home/claude/biblical-languages/"
res = []

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


def lesson_words(lang, n):
    L = json.load(open(f"{ROOT}lessons/{lang}/{n}.json"))
    return [dict(it, lang=lang, lesson=L["id"], added="2026-10-27") for s in L["steps"] for c in s["cards"] if c["type"] == "words" for it in c["items"]]


async def fresh(pg, queue=None, extra=None):
    await pg.goto(f"{BASE}#/settings")
    await pg.evaluate("localStorage.clear()")
    if queue is not None:
        await pg.evaluate(f"localStorage.setItem('ao:reviewQueue', JSON.stringify({json.dumps(queue, ensure_ascii=False)}))")
    for k, v in (extra or {}).items():
        await pg.evaluate(f"localStorage.setItem('ao:{k}', JSON.stringify({json.dumps(v, ensure_ascii=False)}))")


async def open_review(pg):
    await pg.goto(f"{BASE}#/today")
    await pg.goto(f"{BASE}#/review")
    await pg.wait_for_selector(".rv-summary")


async def spoken(pg):
    return await pg.evaluate("window.__spoken")


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        await ctx.add_init_script(VOICES)
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

        # 1. Respelling and voice text (the functions the buttons use)
        await pg.goto(f"{BASE}#/today")
        r = await pg.evaluate("""async () => { const s = await import('./js/sound.js'); return {
          say: ['λόγος', 'ἀγάπη', 'ἄγγελος', 'υἱός', 'δόξα', 'Πέτρος', 'ὄχλος'].map((w) => s.greekSay(w)),
          eras: ['λόγος', 'ἀγάπη', 'ἄγγελος', 'βασιλεία', 'δόξα'].map((w) => s.erasmianSpeech(w)),
          koine: s.koineSpeech('ὁ λόγος τοῦ θεοῦ·'),
          he: ['יְהוָה', 'לַיהוָה', 'אֲדֹנָי יְהוִה', 'בְּ/רֵאשִׁ֖ית', 'כָּל־הָאָ֫רֶץ׃ פ'].map((w) => s.hebrewSpeech(w)) }; }""")
        check("Erasmian respelling: LO-gos, a-GA-pay, ANG-ge-los, hwee-OS, DOK-sa, PE-tros, OKH-los",
              r["say"] == ["LO-gos", "a-GA-pay", "ANG-ge-los", "hwee-OS", "DOK-sa", "PE-tros", "OKH-los"], str(r["say"]))
        check("Erasmian for the Greek voice: λόγκος, αγκάπεϊ, άγγελος, μπασιλέια, ντόκσα",
              r["eras"] == ["λόγκος", "αγκάπεϊ", "άγγελος", "μπασιλέια", "ντόκσα"], str(r["eras"]))
        check("Restored Koine: modern accents, no breathings, raised dot read as a comma", r["koine"] == "ο λόγος τού θεού,", r["koine"])
        r2 = await pg.evaluate("""async () => { const s = await import('./js/sound.js'); return {
          he: ['סוּס', 'כָּעַס', 'וַיְהִי פ', 'כִּי [אם]'].map((w) => s.hebrewSpeech(w)),
          el: [s.erasmianSpeech('δ᾽ ἂν'), s.erasmianSpeech('δ᾽'), s.greekSay('δ᾽ ἂν'), s.koineSpeech('ἁμάρτανε.]]')] }; }""")
        check("Hebrew voice: a word's last ס stays (סוּס, כָּעַס); a lone paragraph ס/פ and brackets go",
              r2["he"] == ["סוּס", "כָּעַס", "וַיְהִי", "כִּי אם"], str(r2["he"]))
        check("Greek elision: δ᾽ ἂν said as one word (ντάν, dan); δ᾽ alone said ντέ; Koine drops ]]",
              r2["el"] == ["ντάν", "ντέ", "dan", "αμάρτανε."], str(r2["el"]))
        check("Hebrew voice: the divine name read Adonai (with prefixes) or Elohim after Adonai; no accents or sof pasuq",
              r["he"] == ["אֲדֹנָי", "לַאֲדֹנָי", "אֲדֹנָי אֱלֹהִים", "בְּרֵאשִׁית", "כָּל הָאָרֶץ"], str(r["he"]))

        # 2. Nothing yet
        await fresh(pg)
        await open_review(pg)
        t = await pg.locator(".rv-summary").inner_text()
        check("Review, nothing yet: says so and offers a lesson", "Nothing to review yet" in t and await pg.locator('.rv-summary a[href="#/learn"]').count() == 1, t)
        await pg.goto(f"{BASE}#/today")
        await pg.wait_for_function("document.querySelector('.today-review').textContent.includes('No words to review yet')", timeout=5000)
        check("Today, nothing yet: 'No words to review yet'", True)

        # 3. Lesson words are waiting; Today counts them
        q = lesson_words("grc", 0)  # 8 words
        await fresh(pg, q)
        await pg.goto(f"{BASE}#/today")
        await pg.wait_for_function("document.querySelector('.today-review').textContent.includes('to review')", timeout=5000)
        check("Today: 8 words to review, with a time estimate", "8 words to review" in await pg.locator(".today-review").inner_text()
              and "minute" in await pg.locator(".today-review").inner_text())
        await open_review(pg)
        check("Review: 8 new words, Start button", "8 words" in await pg.locator(".rv-summary").inner_text() and "8 new" in await pg.locator(".rv-summary").inner_text())

        # 4. A session: show the answer, rate, words due soon come back, finish
        await pg.click("[data-start]")
        await pg.wait_for_selector(".rv-card")
        focus = await pg.evaluate("document.activeElement.hasAttribute('data-show')")
        check("Card: the word, a Listen button, focus on Show the answer", focus and await pg.locator(".rv-listen [data-say]").count() == 1
              and await pg.locator("[data-rate]").count() == 0)
        await pg.keyboard.press("Space")
        await pg.wait_for_selector("[data-rate]")
        labels = await pg.locator("[data-rate]").all_inner_texts()
        good_focus = await pg.evaluate("document.activeElement.dataset.rate")
        check("Space shows the answer: meaning, pronunciation and four choices with when each comes back; focus on Good",
              len(labels) == 4 and all(any(u in x for u in ("min", "hour", "day")) for x in labels) and good_focus == "3"
              and await pg.locator(".rv-say").inner_text() != "" and await pg.locator(".rv-en").inner_text() != "", str(labels))
        await pg.keyboard.press("1")  # Again: back in a minute, so it comes back in this session
        await pg.wait_for_selector(".rv-card")
        cards = await pg.evaluate("JSON.parse(localStorage.getItem('ao:cards'))")
        first = next(iter(cards.values()))
        check("Key 1 (Again) saves the card with its FSRS state", len(cards) == 1 and first["f"]["state"] == 1 and first["f"]["reps"] == 1 and first["src"] == "lesson", str(first))
        count_text = await pg.locator(".rv-count").inner_text()
        check("The count stays at 8 when a word comes back", count_text.endswith("of 8"), count_text)
        seen, n = [], 0
        while await pg.locator(".rv-card").count() and n < 60:
            seen.append(await pg.locator(".rv-word").inner_text())
            if await pg.locator("[data-show]").count():
                await pg.click("[data-show]")
            await pg.click(f"[data-rate='3']")
            n += 1
        check("Again-ed word comes back within a few cards; every word is seen until done", seen.count(first["t"]) >= 2 and len(set(seen)) == 8, str(seen))
        done = await pg.locator(".rv-done").inner_text()
        check("Finish: 'Done for now' with the number of answers", "Done for now" in done and "answers saved" in done, done)
        cards = await pg.evaluate("JSON.parse(localStorage.getItem('ao:cards'))")
        log = await pg.evaluate("JSON.parse(localStorage.getItem('ao:reviewLog'))")
        day = list(log.values())[0]
        check("All 8 words are cards now, due in days; the log counts 8 new and every answer", len(cards) == 8
              and all(c["f"]["state"] == 2 for c in cards.values()) and day["n"] == 8 and day["r"] == n + 1, f"{day} {n}")
        await pg.click("[data-back]")
        await pg.wait_for_selector(".rv-summary")
        t = await pg.locator(".rv-summary").inner_text()
        check("Afterwards: 'All done for today' and when words come back", "All done for today" in t and "come back" in t, t)
        await pg.click(".rv-words summary")
        wl = await pg.locator(".rv-words").inner_text()
        check("Your words: each with its pronunciation, meaning and when it's due, linking to the dictionary",
              await pg.locator(".rv-words .row").count() == 8 and await pg.locator('.rv-words a[href="#/words/G3056"]').count() == 1
              and any(x in wl for x in ("in 2 days", "in 3 days", "tomorrow")), wl[:200])

        # 5. Due today (before 4am tomorrow) vs later; overdue first
        await pg.evaluate("""() => { const c = JSON.parse(localStorage.getItem('ao:cards')); const ks = Object.keys(c);
          const end = new Date(); end.setHours(4, 0, 0, 0); if (end <= new Date()) end.setDate(end.getDate() + 1);
          c[ks[0]].f.due = new Date(Date.now() - 3 * 86400000).toISOString();
          c[ks[1]].f.due = new Date(end.getTime() - 60000).toISOString();
          c[ks[2]].f.due = new Date(end.getTime() + 60000).toISOString();
          localStorage.setItem('ao:cards', JSON.stringify(c)); }""")
        await pg.goto(f"{BASE}#/today")
        await open_review(pg)
        t = await pg.locator(".rv-summary").inner_text()
        check("Due today: an overdue word and one due before 4am; not one due after", "2 to review" in t and "new" not in t, t)

        # 6. New words a day; the frequency lists
        await fresh(pg, q, {"newPerDay": 5})
        await open_review(pg)
        check("New words a day: 5 of the 8 lesson words today", "5 new" in await pg.locator(".rv-summary").inner_text())
        await pg.select_option("[data-per-day]", "20")
        await pg.wait_for_function("document.querySelector('.rv-summary').textContent.includes('8 new')", timeout=5000)
        check("Changing it to 20 shows all 8", True)
        await pg.check("[data-deck='grc']")
        await pg.wait_for_function("document.querySelector('.rv-summary').textContent.includes('20 new')", timeout=5000)
        check("Greek list on: lesson words first, then the commonest words, up to 20", "316 most common Greek words" in await pg.locator(".rv-lists").inner_text())
        await pg.click("[data-start]")
        order = []
        for _ in range(10):
            order.append(await pg.locator(".rv-word").inner_text())
            await pg.click("[data-show]")
            await pg.click("[data-rate='4']")  # Easy: straight to days, no repeats
        lesson_t = [w["t"] for w in q]
        check("Order: the 8 lesson words, then the commonest list words not already met (αὐτός, σύ: ὁ and καί were in the lesson)", order[:8] == lesson_t and order[8:10] == ["αὐτός", "σύ"], str(order))
        cards = await pg.evaluate("JSON.parse(localStorage.getItem('ao:cards'))")
        check("A word in a lesson and a list is one card (by dictionary key)", "grc:G3588" in cards and sum(1 for k in cards if k == "grc:G2532") == 1)

        # alias: a lesson key for a split sense joins the list's card; lesson wording replaces the list's
        await fresh(pg, None, {"reviewDecks": {"grc": True, "he": False}, "newPerDay": 30})
        await pg.evaluate("""() => { localStorage.setItem('ao:cards', JSON.stringify({ 'grc:G2962G': { id: 'grc:G2962G', lang: 'grc', k: 'G2962G', t: 'κύριος', say: '', en: 'lord', src: 'deck',
            f: { due: new Date(Date.now() + 5 * 86400000).toISOString(), stability: 5, difficulty: 5, elapsed_days: 0, scheduled_days: 5, reps: 1, lapses: 0, learning_steps: 0, state: 2 } } }));
          localStorage.setItem('ao:reviewQueue', JSON.stringify([{ k: 'G2962H', lang: 'grc', t: 'κύριος', say: 'KÜ-ree-os', en: 'lord, Lord; master', lesson: 'grc-6' }])); }""")
        await open_review(pg)
        cards = await pg.evaluate("JSON.parse(localStorage.getItem('ao:cards'))")
        fresh_words = await pg.locator(".rv-summary").inner_text()
        check("A lesson word for another sense (G2962H) joins the list's card, taking the lesson's wording",
              list(cards) == ["grc:G2962G"] and cards["grc:G2962G"]["en"] == "lord, Lord; master" and cards["grc:G2962G"]["src"] == "lesson", str(cards))

        # 7. Both languages: a switch; Hebrew cards right to left with the Israeli voice
        await fresh(pg, lesson_words("grc", 0) + lesson_words("he", 0))
        await open_review(pg)
        check("Both languages: Both / Greek / Hebrew switch", await pg.locator("[data-rv-lang]").count() == 3)
        await pg.click("[data-rv-lang='he']")
        await pg.wait_for_selector("[data-start]")
        n_he = len(lesson_words("he", 0))
        check(f"Hebrew only: {n_he} words", f"{n_he} new" in await pg.locator(".rv-summary").inner_text(), await pg.locator(".rv-summary").inner_text())
        await pg.click("[data-start]")
        await pg.wait_for_selector(".rv-word")
        check("Hebrew card: right to left", await pg.locator(".rv-word").get_attribute("dir") == "rtl" and await pg.locator(".rv-word").get_attribute("lang") == "he")
        await pg.evaluate("window.__spoken = []")
        await pg.click(".rv-listen [data-say]")
        await pg.wait_for_timeout(150)
        sp = await spoken(pg)
        check("Listen on a Hebrew card: the Israeli voice, slow by default", sp and sp[-1]["lang"] == "he-IL" and sp[-1]["rate"] == 0.75, str(sp))
        await pg.click("[data-stop]")
        await pg.wait_for_selector(".rv-summary")
        await pg.click("[data-rv-lang='all']")

        # 8. Audio settings: Erasmian vs Koine, speed, say each word aloud
        await fresh(pg, q, {"reviewAutoPlay": True, "speechRate": "normal"})
        await open_review(pg)
        await pg.evaluate("window.__spoken = []")
        await pg.click("[data-start]")
        await pg.wait_for_timeout(200)
        sp = await spoken(pg)
        check("Say each word aloud: the first card plays by itself, at normal speed", sp and sp[0]["lang"] == "el-GR" and sp[0]["rate"] == 1, str(sp))
        await pg.goto(f"{BASE}#/settings")
        await pg.wait_for_selector(".say-test")
        await pg.evaluate("window.__spoken = []")
        await pg.click(".say-test [data-say-lang='grc']")
        await pg.click("input[name=greekVoice][value=koine]")
        await pg.click(".say-test [data-say-lang='grc']")
        await pg.wait_for_timeout(150)
        sp = await spoken(pg)
        check("Settings: Try Greek follows the pronunciation choice (Erasmian respelt, then Koine as written)",
              len(sp) == 2 and sp[0]["text"] == "έν αρχέι έιν ό λόγκος" and sp[1]["text"] == "εν αρχή ήν ο λόγος", str(sp))

        # 9. No voice on the phone: plain help; no speech at all: says so
        await pg.evaluate("window.__voices = [{name: 'Daniel', lang: 'en-GB', localService: true}]")
        await pg.click(".say-test [data-say-lang='he']")
        await pg.wait_for_selector(".toast")
        tip = await pg.locator(".toast").inner_text()
        check("No Hebrew voice: explains how to add one", "Hebrew voice" in tip and "Listen again" in tip, tip)
        await pg.evaluate("window.__voices = [{name: 'Melina', lang: 'el-GR', localService: true}, {name: 'Carmit', lang: 'he-IL', localService: true}]")

        # 9b. (10b) Speech starts inside the tap: no waiting, even before the phone has listed its voices
        await pg.evaluate("window.__voices = []; window.__spoken = []")
        await pg.click(".say-test [data-say-lang='he']")
        sp = await spoken(pg)  # read straight away: nothing async may come before speak()
        check("Voices not listed yet: speaks at once, asking for Hebrew (he-IL) by language", sp and sp[-1]["lang"] == "he-IL", str(sp))
        await pg.evaluate("""() => { window.__silent = true; const s = window.speechSynthesis; s.speak = (u) => { window.__spoken.push({ text: u.text, lang: u.lang }); }; }""")
        await pg.evaluate("document.querySelectorAll('.toast').forEach((t) => t.remove())")
        await pg.click(".say-test [data-say-lang='grc']")
        await pg.wait_for_function("document.querySelector('.toast') && document.querySelector('.toast').textContent.includes('Greek voice')", timeout=6000)
        tip = await pg.locator(".toast").inner_text()
        check("Nothing starts within a few seconds (no voice installed): the help appears", "Greek voice" in tip, tip)
        await pg.reload()
        await pg.evaluate("window.__voices = [{name: 'Melina', lang: 'el-GR', localService: true}, {name: 'Carmit', lang: 'he-IL', localService: true}]")

        # 10. Listen buttons around the app (a button inside a link doesn't follow the link)
        L1 = json.load(open(f"{ROOT}lessons/grc/1.json"))
        sig = ",".join(f"{s['step']}:{len(s['cards'])}" for s in L1["steps"])
        await fresh(pg, None, {"lessons": {"grc-1": {"v": 1, "sig": sig, "pos": 1, "retries": [], "first": {}}}})
        await pg.goto(f"{BASE}#/learn")
        await pg.goto(f"{BASE}#/lesson/grc/grc-1")
        await pg.wait_for_selector(".ls-scene")
        check("Lesson scene: Listen", await pg.locator(".ls-scene [data-say]").count() == 1)
        last = sum(len(s["cards"]) for s in L1["steps"]) - 1
        await pg.evaluate(f"localStorage.setItem('ao:lessons', JSON.stringify({{'grc-1': {{v: 1, sig: '{sig}', pos: {last}, retries: [], first: {{}}}}}}))")
        await pg.goto(f"{BASE}#/learn")
        await pg.goto(f"{BASE}#/lesson/grc/grc-1")
        await pg.wait_for_selector(".ls-wordlist")
        before = pg.url
        await pg.evaluate("window.__spoken = []")
        await pg.locator(".ls-wordlist [data-say]").first.click()
        await pg.wait_for_timeout(150)
        check("Lesson word list: a Listen button per word; it plays without leaving the lesson",
              await pg.locator(".ls-wordlist [data-say]").count() == len(L1["steps"][4]["cards"][0]["items"]) and pg.url == before and len(await spoken(pg)) == 1)
        await pg.goto(f"{BASE}#/words/G3056")
        await pg.wait_for_selector(".entry-listen [data-say]")
        check("Dictionary entry: Listen", await pg.locator(".entry-listen [data-say]").get_attribute("data-say") == "λόγος")
        await pg.goto(f"{BASE}#/read/JHN/1")
        await pg.wait_for_selector(".w")
        await pg.locator(".w").first.click()
        await pg.wait_for_selector(".sheet [data-say]")
        check("Reader word (Greek): Listen in the word sheet", True)
        await pg.keyboard.press("Escape")
        await pg.goto(f"{BASE}#/read/GEN/1")
        await pg.wait_for_selector(".lang-he .w")
        await pg.locator(".w").first.click()
        await pg.wait_for_selector(".sheet [data-say]")
        check("Reader word (Hebrew): Listen in the word sheet", await pg.locator(".sheet [data-say]").get_attribute("data-say-lang") == "he")
        await pg.keyboard.press("Escape")
        await pg.goto(f"{BASE}#/today")
        await pg.wait_for_selector(".verse-gloss [data-say]")
        check("Today's verse: Listen next to the tapped word", True)

        # 11. Small phone, largest text, dark: the card fits, choices in two rows
        await ctx.close()
        ctx = await b.new_context(viewport={"width": 320, "height": 640}, color_scheme="dark")
        await ctx.add_init_script(VOICES)
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        await fresh(pg, lesson_words("he", 0), {"textSize": "largest", "reviewDecks": {"grc": True, "he": True}})
        await open_review(pg)
        wide = await pg.evaluate("document.documentElement.scrollWidth > innerWidth")
        await pg.click("[data-start]")
        await pg.click("[data-show]")
        await pg.wait_for_selector("[data-rate]")
        cols = await pg.evaluate("getComputedStyle(document.querySelector('.rv-rate')).gridTemplateColumns.split(' ').length")
        wide2 = await pg.evaluate("document.documentElement.scrollWidth > innerWidth")
        check("320px, largest text: review page and card fit; choices two by two", not wide and not wide2 and cols == 2, f"{wide} {wide2} {cols}")
        await pg.click("[data-rate='3']")

        # 11b. Offline after the app has been opened once: the word lists come from the phone's copy
        await pg.evaluate("navigator.serviceWorker.ready")
        await pg.wait_for_timeout(1500)
        await ctx.set_offline(True)
        await pg.evaluate("localStorage.setItem('ao:newPerDay', JSON.stringify(30))")
        await pg.reload()
        await pg.goto(f"{BASE}#/today")
        await pg.goto(f"{BASE}#/review")
        await pg.wait_for_selector(".rv-summary")
        t = await pg.locator(".screen").inner_text()
        check("Offline: both word lists still load (saved with the app)", "need a connection" not in t and "316 most common" in t and bool(re.search(r"7\d\d most common Hebrew", t)), t[:200])
        await ctx.set_offline(False)

        # 12. Lists can't load (offline, first time): the page still works
        await pg.route("**/data/decks/**", lambda r: r.abort())
        await pg.evaluate("localStorage.setItem('ao:textSize', JSON.stringify('normal'))")
        ctx2 = await b.new_context(viewport={"width": 390, "height": 844}, service_workers="block")  # first visit, nothing saved yet
        await ctx2.add_init_script(VOICES)
        pg2 = await ctx2.new_page()
        await pg2.route("**/data/decks/**", lambda r: r.abort())
        await pg2.goto(f"{BASE}#/settings")
        await pg2.evaluate(f"localStorage.clear(); localStorage.setItem('ao:reviewQueue', JSON.stringify({json.dumps(q, ensure_ascii=False)})); localStorage.setItem('ao:reviewDecks', JSON.stringify({{grc: true, he: false}}))")
        await pg2.goto(f"{BASE}#/today")
        await pg2.goto(f"{BASE}#/review")
        await pg2.wait_for_selector(".rv-summary")
        t = await pg2.locator(".screen").inner_text()
        check("Lists unavailable: lesson words still reviewable, with a note about the connection", "8 new" in t and "need a connection" in t, t[:300])
        await ctx2.close()

        # 12b. (10b) A list card follows corrections to the list; a week on a fake clock keeps to 10 new words a day
        await fresh(pg, None, {"reviewDecks": {"grc": True, "he": False}})
        await pg.evaluate("""() => localStorage.setItem('ao:cards', JSON.stringify({ 'grc:G0846': { id: 'grc:G0846', lang: 'grc', k: 'G0846', t: 'αὐτός', say: '', en: 'it/s/he', n: 1, src: 'deck',
            f: { due: new Date(Date.now() + 5 * 86400000).toISOString(), stability: 5, difficulty: 5, elapsed_days: 0, scheduled_days: 5, reps: 1, lapses: 0, learning_steps: 0, state: 2 } } }))""")
        await open_review(pg)
        c = await pg.evaluate("JSON.parse(localStorage.getItem('ao:cards'))['grc:G0846']")
        check("A list card picks up the list's corrected meaning and count", c["en"] == "he, she, it; self, same" and c["n"] > 1000, str(c))
        import datetime
        ctx3 = await b.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
        pg3 = await ctx3.new_page()
        t0 = datetime.datetime(2026, 11, 2, 19, 0)
        await pg3.clock.install(time=t0)
        await pg3.goto(f"{BASE}#/settings")
        await pg3.evaluate("localStorage.clear(); localStorage.setItem('ao:reviewDecks', JSON.stringify({grc: true, he: false}))")
        per_day, ok_days = [], True
        for day, hour in enumerate([0, 1, 2, 8.5, 2, 3, 0]):  # day 3 at 03:30 the next morning still counts as day 3
            await pg3.clock.set_system_time(t0 + datetime.timedelta(days=day, hours=hour))
            await pg3.goto(f"{BASE}#/today")
            await pg3.goto(f"{BASE}#/review")
            await pg3.wait_for_selector(".rv-summary")
            n = 0
            if await pg3.locator("[data-start]").count():
                await pg3.click("[data-start]")
                while await pg3.locator(".rv-card").count() and n < 300:
                    if await pg3.locator("[data-show]").count():
                        await pg3.click("[data-show]")
                    await pg3.click("[data-rate='3']")
                    await pg3.clock.run_for(5000)
                    n += 1
            ok_days = ok_days and await pg3.locator(".rv-done").count() == 1
        log = await pg3.evaluate("JSON.parse(localStorage.getItem('ao:reviewLog'))")
        cards = await pg3.evaluate("JSON.parse(localStorage.getItem('ao:cards'))")
        check("A week of reviews on a fake clock: 10 new words a day (03:30 counts as the day before), every session finishes",
              ok_days and [v["n"] for _, v in sorted(log.items())] == [10] * 7 and len(cards) == 70 and "2026-11-05" in log and "2026-11-09" not in log, f"{log} {len(cards)}")
        await ctx3.close()

        # 13. Backup includes the cards
        await pg.click("[data-start]")
        await pg.click("[data-show]")
        await pg.click("[data-rate='3']")
        await pg.goto(f"{BASE}#/settings")
        keys = await pg.evaluate("""async () => { const s = await import('./js/store.js'); return Object.keys(s.exportBackup().data); }""")
        check("Backup includes cards and the review log", "ao:cards" in keys and "ao:reviewLog" in keys, str(keys))

        check("no console errors", not [e for e in errs if "net::ERR_FAILED" not in e and "Failed to load resource" not in e], "; ".join(errs[:4]))
        await b.close()
    print(f"\n{sum(res)}/{len(res)} passed")


asyncio.run(main())
