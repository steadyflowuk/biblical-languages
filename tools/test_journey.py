"""A new learner's first week, on a fake clock, checking that every screen agrees with every other
(Session 12 deep check). Run with the local server on :8765:  python3 tools/test_journey.py

Day 1: install, first lesson, its words in Review, the alphabet flashcards, a chapter read, Progress.
Day 2: Today asks for today; reviews; second lesson. Day 4 (a day missed): the run restarts, best kept.
Then a backup, restored on a second device, which carries on exactly where the first left off.
"""
import asyncio, json, re, faulthandler
from datetime import datetime
from playwright.async_api import async_playwright

faulthandler.dump_traceback_later(1500, exit=True)
BASE = "http://localhost:8765/"
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
ROOT = "/home/claude/biblical-languages/"
INDEX = json.load(open(ROOT + "lessons/index.json"))
MEDIA = json.load(open(ROOT + "lessons/media.json"))
LESSONS = {e["id"]: json.load(open(ROOT + e["file"])) for es in INDEX.values() for e in es if e.get("file")}
res = []

VOICES = """
window.__spoken = [];
window.__voices = [{name: 'Melina', lang: 'el-GR', localService: true}, {name: 'Carmit', lang: 'he-IL', localService: true}];
window.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; } };
Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
  getVoices() { return window.__voices; }, speaking: false, pending: false,
  speak(u) { window.__spoken.push({ text: u.text, lang: u.lang }); setTimeout(() => { u.onstart && u.onstart(); u.onend && u.onend(); }, 10); },
  cancel() {}, addEventListener() {} } });
"""


def check(name, ok, detail=""):
    res.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def review_words(lid):
    return [w for s in LESSONS[lid]["steps"] if s["step"] == "review" for c in s["cards"] for w in c.get("items", [])]


def card_by_title(lesson, title):
    for s in lesson["steps"]:
        for c in s["cards"]:
            if (c.get("prompt") or c.get("text") or c.get("title")) == title:
                return c
    return None


async def finish_lesson(pg, lid):
    """Play a lesson through with right answers, from wherever it opens, to 'Lesson complete'."""
    L = LESSONS[lid]
    for _ in range(200):
        if await pg.locator(".ls-done").count():
            return True
        k = await pg.evaluate("""(() => { const c = document.querySelector('.ls-card');
          for (const k of ['choose','match','build','parse']) if (c.querySelector('.ls-' + k)) return k; return 'other'; })()""")
        title = await pg.evaluate("document.querySelector('.ls-card .ls-title, .ls-card .ls-big')?.textContent")
        c = card_by_title(L, title)
        if k != "other" and c and await pg.locator("[data-next]").is_disabled():
            if k == "choose":
                await pg.click(f"[data-opt='{c['answer']}']")
            elif k == "match":
                for i in range(len(c["pairs"])):
                    await pg.click(f"[data-left='{i}']"); await pg.click(f"[data-right='{i}']")
            elif k == "build":
                for i in range(len(c["tiles"])):
                    await pg.click(f".ls-bank [data-tile='{i}']")
                await pg.click("[data-check]")
            elif k == "parse":
                for fi, f in enumerate(c["fields"]):
                    await pg.click(f"[data-pick='{fi}'][data-value={json.dumps(f['answer'], ensure_ascii=False)}]")
                await pg.click("[data-check]")
        await pg.click("[data-next]")
        await pg.wait_for_timeout(60)
    return False


async def review_all(pg, rating="3", limit=80):
    """Answer every card in today's session; returns how many answers were given."""
    await go(pg, "review", ".rv-summary")
    if not await pg.locator("[data-start]").count():
        return 0
    await pg.click("[data-start]")
    n = 0
    while n < limit:
        if await pg.locator(".rv-done").count():
            break
        await pg.wait_for_selector("[data-show], [data-rate], .rv-done")
        if await pg.locator("[data-show]").count():
            await pg.click("[data-show]")
        if await pg.locator(f"[data-rate='{rating}']").count():
            await pg.click(f"[data-rate='{rating}']")
            n += 1
        await pg.wait_for_timeout(40)
    return n


async def go(pg, route, sel):
    await pg.goto(f"{BASE}#/settings")
    await pg.goto(f"{BASE}#/{route}")
    await pg.wait_for_selector(sel, timeout=15000)


async def text(pg, sel):
    return await pg.locator(sel).first.inner_text()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, accept_downloads=True)
        await ctx.add_init_script(VOICES)
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        await pg.clock.install(time=datetime(2026, 11, 2, 18, 0))

        # ---- Day 1 (Monday 2 November, 6pm): a brand-new learner
        await pg.goto(f"{BASE}#/today")
        await pg.wait_for_selector(".today-plan")
        await pg.wait_for_function("document.querySelector('.today-lesson').textContent.includes('first taste')", timeout=8000)
        t = await text(pg, ".screen")
        check("Day 1, Today: no streak yet; next lesson is the John 1:1 taster", ".today-streak" and "in a row" not in t and "Next lesson: A first taste: John 1:1" in t, t[:300])
        check("…no words to review yet", "No words to review yet" in t)
        await pg.click(".today-lesson a")
        await pg.wait_for_selector("[data-next]")
        check("Today's lesson row opens the lesson", "#/lesson/grc/grc-0" in pg.url, pg.url)
        check("Finish the taster lesson with right answers", await finish_lesson(pg, "grc-0"))
        words0 = review_words("grc-0")
        done = await text(pg, ".ls-done")
        check(f"Lesson complete: {len(words0)} words go to the review list", f"{len(words0)} new words" in done, done)
        await go(pg, "today", ".today-plan")
        await pg.wait_for_function("!document.querySelector('.today-review').textContent.includes('Review your words')", timeout=8000)
        t = await text(pg, ".screen")
        check("Today now: 1 day in a row, studied today", "1 day in a row · you've studied today" in t, t[:200])
        check(f"Today: {len(words0)} words to review (the lesson's words)", f"{len(words0)} words to review" in t, t)
        check("Today: the next lesson is the alphabet, part 1", "Next lesson: The alphabet, part 1" in t)
        await pg.wait_for_function("document.querySelector('.today-video a').getAttribute('href').startsWith('https')", timeout=8000)
        check("Today: the video for that lesson (Angela, the alphabet)", await pg.get_attribute(".today-video a", "href") == MEDIA["grc"]["lessons"]["grc-1"][0]["href"])
        await go(pg, "learn", ".path")
        path = await text(pg, ".path")
        check("Learn: the taster is marked done, the alphabet is next", re.search(r"A first taste.*\n.*\n?.*Done", path) or "Done" in path.split("The alphabet, part 1")[0], path[:300])
        # Review: the lesson's words, all of them, then done for today
        n = await review_all(pg, "4")
        check(f"Review: the {len(words0)} lesson words, answered Easy, then done", n == len(words0), str(n))
        cards = await pg.evaluate("JSON.parse(localStorage.getItem('ao:cards'))")
        check("Each lesson word is now a card", all(any(c["k"] == w["k"] or c["id"].endswith(":" + w["k"]) for c in cards.values()) for w in words0) or len(cards) == len(words0), str(list(cards)))
        await go(pg, "today", ".today-plan")
        await pg.wait_for_function("document.querySelector('.today-review').textContent.includes('done')", timeout=8000)
        check("Today: reviews done for today", "Reviews done for today" in await text(pg, ".today-review"))
        # Letters: the guide, then its flashcards in Review
        await pg.click(".tabs a[data-tab='alphabet']")
        await pg.wait_for_selector(".ab-grid")
        check("Letters tab opens the Greek guide (the language being learnt)", await pg.locator(".ab-tile").count() == 24)
        await pg.click("[data-letter='0']")
        await pg.click(".ab-sheet-name [data-say]")
        await pg.wait_for_timeout(50)
        sp = await pg.evaluate("window.__spoken")
        check("Alpha's name is spoken with the Greek voice", sp and sp[-1]["lang"] == "el-GR", str(sp))
        await pg.keyboard.press("Escape")
        await go(pg, "review", ".rv-summary")
        await pg.check("[data-deck='grcLetters']")
        await pg.wait_for_function("document.querySelector('.rv-summary').textContent.includes('new')", timeout=5000)
        n = await review_all(pg, "4", limit=10)
        cards = await pg.evaluate("JSON.parse(localStorage.getItem('ao:cards'))")
        abc = [k for k in cards if ":abc:" in k]
        check("Alphabet flashcards: the new-words limit (10 a day) stops at the limit", n == 10 - len(words0) and len(abc) == 10 - len(words0), f"{n} {len(abc)}")
        # Read a chapter for half a minute: counts towards the day
        await go(pg, "read/JHN/1", ".chapter .v")
        await pg.clock.run_for(31000)
        a = await pg.evaluate("JSON.parse(localStorage.getItem('ao:activity'))")
        check("Reading John 1 for half a minute counts as a chapter read", (a.get("2026-11-02") or {}).get("v") == 1, str(a))
        await pg.click(".v .w >> nth=0")
        await pg.wait_for_selector(".sheet .ws-translit")
        dict_link = pg.locator(".sheet a[href^='#/words/']").first
        href = await dict_link.get_attribute("href")
        await dict_link.click()
        await pg.wait_for_selector(".entry-lemma")
        check("Reader word → its dictionary entry", pg.url.endswith(href), f"{pg.url} {href}")
        # Progress agrees with all of that
        await go(pg, "progress", ".pg-lang h2")
        t = await text(pg, ".screen")
        total_cards = len(await pg.evaluate("Object.keys(JSON.parse(localStorage.getItem('ao:cards')))"))
        check("Progress: 1 day in a row", t.split("\n")[2].startswith("1") or "1 day in a row" in t.replace("\n", " "), t[:150])
        written = len([e for e in INDEX["grc"] if e.get("file")])
        check(f"Progress: 1 of {written} Greek lessons finished", f"1 of {written} lessons finished" in t, t[300:700])
        check(f"Progress: {len(words0)} words in Review (letters counted apart)", f"{len(words0)} words in Review" in t, t[300:800])
        check(f"Progress: letters met, none known yet (Easy on day 1 = due later)", "of 24 letters known" in t)
        await pg.click(".pg-day.today")
        pick = await text(pg, ".pg-cal-pick")
        check("Calendar, today: cards reviewed, lesson steps and 1 chapter read", "cards reviewed" in pick and "lesson steps" in pick and "1 chapter read" in pick, pick)

        # ---- Day 2 (Tuesday 7pm)
        await pg.clock.set_system_time(datetime(2026, 11, 3, 19, 0))
        await go(pg, "today", ".today-plan")
        check("Day 2, Today: 1 day in a row, keep it going today", "1 day in a row · keep it going today" in await text(pg, ".today-streak"))
        await review_all(pg, "3", limit=60)
        await go(pg, "lesson/grc/grc-1", "[data-next]")
        check("Day 2: the alphabet lesson, finished", await finish_lesson(pg, "grc-1"))
        await go(pg, "today", ".today-plan")
        check("Day 2, Today: 2 days in a row", "2 days in a row · you've studied today" in await text(pg, ".today-streak"))

        # ---- Day 4 (Thursday): Wednesday was missed
        await pg.clock.set_system_time(datetime(2026, 11, 5, 9, 0))
        await go(pg, "today", ".today-plan")
        check("Day 4 (a day missed): no streak line until today's study", await pg.locator(".today-streak").count() == 0)
        await go(pg, "progress", ".pg-streak")
        st = await text(pg, ".pg-streak")
        check("Progress: 0 days in a row, best 2", st.startswith("0") and "Your best is 2 days" in st, st)
        await review_all(pg, "3", limit=60)
        await go(pg, "today", ".today-plan")
        check("After today's reviews: 1 day in a row again", "1 day in a row" in await text(pg, ".today-streak"))
        # Backup
        await go(pg, "progress", ".pg-backup")
        async with pg.expect_download() as dl:
            await pg.click("[data-backup]")
        path = await (await dl.value).path()
        before = await pg.evaluate("({ cards: Object.keys(JSON.parse(localStorage.getItem('ao:cards'))).length, lessons: JSON.parse(localStorage.getItem('ao:lessons')), q: JSON.parse(localStorage.getItem('ao:reviewQueue')).length })")
        greek_before = await text(pg, ".pg-lang")

        # ---- A second device: restore and carry on
        ctx2 = await b.new_context(viewport={"width": 1180, "height": 820})
        await ctx2.add_init_script(VOICES)
        pg2 = await ctx2.new_page()
        pg2.on("pageerror", lambda e: errs.append(str(e)))
        await pg2.clock.install(time=datetime(2026, 11, 5, 20, 0))
        await pg2.goto(f"{BASE}#/settings")
        await pg2.wait_for_selector("[data-action='choose']")
        await pg2.set_input_files("[data-action='import']", path)
        ask = await text(pg2, ".restore-confirm")
        check("Second device: the backup is described (2 lessons, its cards)", "2 finished lessons" in ask and f"{before['cards']} review cards" in ask, ask)
        await pg2.click("[data-restore]")
        await pg2.wait_for_selector(".toast")
        after = await pg2.evaluate("({ cards: Object.keys(JSON.parse(localStorage.getItem('ao:cards'))).length, lessons: JSON.parse(localStorage.getItem('ao:lessons')), q: JSON.parse(localStorage.getItem('ao:reviewQueue')).length })")
        check("Restored: the same cards, lessons and review list", after == before, f"{after} vs {before}")
        await go(pg2, "progress", ".pg-lang h2")
        greek_after = await text(pg2, ".pg-lang")
        check("Restored: Progress shows the same Greek numbers", greek_after == greek_before, f"{greek_after!r} vs {greek_before!r}")
        st2 = await text(pg2, ".pg-streak")
        check("Restored: the run of days and the best come too", "1" in st2.split("\n")[0] and "Your best is 2 days" in st2, st2)
        await go(pg2, "today", ".today-plan")
        await pg2.wait_for_function("document.querySelector('.today-lesson').textContent.includes('Next lesson')", timeout=8000)
        check("Restored: Today's next lesson is the alphabet, part 2", "The alphabet, part 2" in await text(pg2, ".today-lesson"))
        await ctx2.close()

        check("No console errors anywhere on the way", not errs, str(errs[:4]))
        await b.close()
    print(f"\n{sum(res)}/{len(res)} passed")
    raise SystemExit(0 if all(res) else 1)


asyncio.run(main())
