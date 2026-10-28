"""Today's plan, Progress, Videos and backup checks (Session 11). Run with the local server on :8765:
python3 tools/test_progress.py
"""
import asyncio, json, re, faulthandler
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright

faulthandler.dump_traceback_later(900, exit=True)
BASE = "http://localhost:8765/"
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
ROOT = "/home/claude/biblical-languages/"
MEDIA = json.load(open(ROOT + "lessons/media.json"))
GRC_DECK = json.load(open(ROOT + "data/decks/greek.json"))
res = []


def check(name, ok, detail=""):
    res.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def day(dt):
    """The study day (starts at 4am) of a datetime, as the app writes it."""
    return (dt - timedelta(hours=4)).strftime("%Y-%m-%d")


async def fresh(pg, extra=None):
    await pg.goto(f"{BASE}#/settings")
    await pg.evaluate("localStorage.clear()")
    for k, v in (extra or {}).items():
        await pg.evaluate(f"localStorage.setItem('ao:{k}', JSON.stringify({json.dumps(v, ensure_ascii=False)}))")


async def go(pg, route, wait):
    await pg.goto(f"{BASE}#/learn")
    await pg.goto(f"{BASE}#/{route}")
    await pg.wait_for_selector(wait, timeout=15000)


def card(key, t, n, state, stability, due_days, now):
    return {"id": f"grc:{key}", "lang": "grc", "k": key, "t": t, "en": "x", "src": "deck", "n": n,
            "f": {"state": state, "stability": stability, "difficulty": 5, "reps": 3, "lapses": 0, "elapsed_days": 1,
                  "scheduled_days": 3, "learning_steps": 0, "due": (now + timedelta(days=due_days)).isoformat() + "Z"}}


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, accept_downloads=True)
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

        # 1. Streak: days in a row, the 4am day boundary, best run kept
        now = datetime.now()
        await pg.goto(f"{BASE}#/today")
        r = await pg.evaluate("""async () => { const a = await import('./js/activity.js');
          const t = (y, m, d, h) => new Date(y, m - 1, d, h, 0);
          return { late: a.dayKey(t(2026, 10, 28, 2)), morning: a.dayKey(t(2026, 10, 28, 5)), back: a.shiftDay('2026-03-01', 1), fwd: a.shiftDay('2026-10-31', -1) }; }""")
        check("Study day starts at 4am: 2am belongs to the day before", r["late"] == "2026-10-27" and r["morning"] == "2026-10-28", str(r))
        check("Day arithmetic across month ends", r["back"] == "2026-02-28" and r["fwd"] == "2026-11-01", str(r))
        acts = {day(now - timedelta(days=d)): {"r": 5, "l": 0} for d in (1, 2, 3, 6, 7, 8, 9, 10)}
        await fresh(pg, {"activity": acts})
        s = await pg.evaluate("async () => (await import('./js/activity.js')).streak()")
        check("Streak: 3 days up to yesterday, best 5, not yet today", s == {"current": 3, "best": 5, "today": False}, str(s))
        await pg.evaluate("async () => (await import('./js/activity.js')).logActivity('l')")
        s = await pg.evaluate("async () => (await import('./js/activity.js')).streak()")
        check("A lesson step today makes it 4, studied today", s["current"] == 4 and s["today"], str(s))
        await fresh(pg, {"reviewLog": {day(now - timedelta(days=1)): {"r": 12, "n": 3}}})
        s = await pg.evaluate("async () => (await import('./js/activity.js')).streak()")
        check("Reviews from before Session 11 (review log) count for the streak", s["current"] == 1, str(s))

        # 2. Reviewing and lessons write the activity log
        q = [{"k": "G3056", "lang": "grc", "t": "λόγος", "say": "LO-gos", "en": "word", "lesson": "grc-0", "added": "2026-10-27"}]
        await fresh(pg, {"reviewQueue": q})
        await go(pg, "review", "[data-start]")
        await pg.click("[data-start]")
        await pg.click("[data-show]")
        await pg.click("[data-rate='3']")
        a = await pg.evaluate("JSON.parse(localStorage.getItem('ao:activity'))")
        check("A review answer is logged for today", (a.get(day(datetime.now())) or {}).get("r") == 1, str(a))
        await go(pg, "learn", ".path-item")
        await pg.click(".path a.path-item >> nth=0")
        await pg.wait_for_selector("[data-next]")
        await pg.click("[data-next]")
        a = await pg.evaluate("JSON.parse(localStorage.getItem('ao:activity'))")
        check("Moving on in a lesson is logged for today", (a.get(day(datetime.now())) or {}).get("l", 0) >= 1, str(a))

        # 3. Progress screen with known numbers
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cards = {
            "grc:G3588": card("G3588", "ὁ", 19769, 2, 40, 2, now),      # known well
            "grc:G2532": card("G2532", "καί", 9018, 2, 8, 1, now),       # getting there
            "grc:G1722": card("G1722", "ἐν", 2752, 1, 1, 0, now),        # still new (not known)
            "grc:abc:0": {"id": "grc:abc:0", "lang": "grc", "k": "", "t": "Α α", "src": "abc",
                          "f": card("x", "x", 0, 2, 9, 3, now)["f"]},
        }
        acts = {day(datetime.now() - timedelta(days=d)): {"r": 30, "l": 2} for d in range(0, 5)}
        await fresh(pg, {"cards": cards, "activity": acts, "bestStreak": 9,
                         "lessons": {"grc-0": {"v": 1, "done": True, "pos": 0}, "grc-1": {"v": 1, "done": True, "pos": 0}, "grc-2": {"v": 1, "pos": 4}}})
        await go(pg, "progress", ".pg-lang h2")
        t = await pg.locator(".screen").inner_text()
        check("Streak panel: 5 days in a row, studied today, best 9", "5\ndays in a row" in t.replace(" days", "\ndays") or "5 days in a row" in t, t[:200])
        check("Best run shown", "Your best is 9 days" in t, t[:300])
        check("Calendar: 12 weeks of days, today outlined, 5 days studied",
              await pg.locator(".pg-cal-grid .pg-day").count() == 84 and await pg.locator(".pg-day.today").count() == 1
              and "Studied on 5 of the last" in t, t[200:500])
        greek = await pg.locator(".pg-lang").first.inner_text()
        written = sum(1 for e in json.load(open(ROOT + "lessons/index.json"))["grc"] if e.get("file"))
        check(f"Lessons: 2 of {written} finished, 1 under way", f"2 of {written} lessons finished" in greek and "1 under way" in greek, greek[:200])
        check("Words: 3 in Review — 1 known well, 1 getting there, 1 still new",
              "3 words in Review" in greek and bool(re.search(r"Known well\s*1", greek)) and bool(re.search(r"Getting there\s*1", greek)) and bool(re.search(r"Still new\s*1", greek)), greek)
        share = round((19769 + 9018) / GRC_DECK["total"] * 100)
        check(f"Share of the NT from known words only (ὁ + καί = {share}%)", f"make up {share}% of the Greek New Testament" in greek, greek)
        check("Letters: 1 of 24 known, with a link to the guide", "1 of 24 letters known" in greek and await pg.locator(".pg-lang a[href='#/alphabet/grc']").count() == 1)
        he = await pg.locator(".pg-lang").nth(1).inner_text()
        check("Hebrew not started: a button to start", "Not started yet" in he)
        fc = await pg.locator(".pg-fc-n").all_inner_texts()
        check("Week ahead: today 1 (ἐν), tomorrow 1, day after 1, then the letter on day 3", fc[:4] == ["1", "1", "1", "1"] and len(fc) == 7, str(fc))
        await pg.click(".pg-lang [data-learn='he']")
        await pg.wait_for_selector(".path")
        check("Start the Hebrew lessons: Learn opens on Hebrew", await pg.evaluate("JSON.parse(localStorage.getItem('ao:learnLang'))") == "he")
        await pg.evaluate("localStorage.setItem('ao:learnLang', JSON.stringify('grc'))")

        # 4. Backup: saving, the date, Today's reminder, restore
        await go(pg, "progress", ".pg-backup")
        check("Backup: never saved yet", "haven't saved a backup yet" in await pg.locator(".pg-backup").inner_text())
        async with pg.expect_download() as dl:
            await pg.click("[data-backup]")
        d = await dl.value
        path = await d.path()
        backup = json.load(open(path))
        await pg.wait_for_function("document.querySelector('.pg-backup-last').textContent.includes('today')")
        check("Save a backup: a file is saved and the date shows 'today'", backup["app"] == "aleph-to-omega" and "ao:cards" in backup["data"] and "ao:activity" in backup["data"])
        check("The backup holds lessons, cards, activity and settings", all(k in backup["data"] for k in ("ao:lessons", "ao:cards", "ao:activity", "ao:bestStreak")), str(list(backup["data"])))
        many = {f"grc:G{1000 + i}": card(f"G{1000 + i}", "λ", 50, 2, 5, 3, now) for i in range(25)}
        await fresh(pg, {"cards": many})
        await go(pg, "today", ".today-plan")
        check("Today: a reminder to save a backup once there's real progress and no backup", await pg.locator(".today-backup").count() == 1)
        async with pg.expect_download():
            await pg.click(".today-backup [data-backup]")
        await pg.wait_for_selector(".today-backup", state="detached")
        check("Saving from Today removes the reminder", True)
        await pg.evaluate(f"localStorage.setItem('ao:lastBackup', JSON.stringify('{(datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=40)).isoformat()}Z'))")
        await go(pg, "today", ".today-plan")
        check("The reminder comes back after a month", await pg.locator(".today-backup").count() == 1)
        # restore into an empty profile: the numbers come back
        await fresh(pg)
        await go(pg, "settings", "[data-action='export']")
        await pg.set_input_files("[data-action='import']", path)
        await pg.wait_for_selector(".toast")
        await go(pg, "progress", ".pg-lang h2")
        t = await pg.locator(".screen").inner_text()
        last = await pg.evaluate("JSON.parse(localStorage.getItem('ao:lastBackup'))")
        check("Restore: progress comes back and counts as backed up on the backup's date", "3 words in Review" in t and last == backup["exported"], f"{last} {t[:120]}")

        # 5. Today's plan
        await fresh(pg, {"activity": {day(datetime.now() - timedelta(days=1)): {"r": 3, "l": 0}}, "lessons": {"grc-0": {"v": 1, "done": True, "pos": 0}}})
        await go(pg, "today", ".today-plan")
        check("Today: streak line, inviting today's study", "1 day in a row · keep it going today" in await pg.locator(".today-streak").inner_text())
        await pg.wait_for_function("document.querySelector('.today-video a').getAttribute('href').startsWith('https://')", timeout=8000)
        href = await pg.get_attribute(".today-video a", "href")
        check("Today: the video for the next lesson (grc-1: Angela's alphabet lesson)", href == MEDIA["grc"]["lessons"]["grc-1"][0]["href"], href)
        check("…opens outside the app", await pg.get_attribute(".today-video a", "target") == "_blank")
        check("Today: link to Progress", await pg.locator(".today-progress a[href='#/progress']").count() == 1)

        # 6. Videos screen
        await fresh(pg, {"lessons": {"grc-0": {"v": 1, "done": True, "pos": 0}}})
        await go(pg, "media", ".md-lesson")
        opened = await pg.locator(".md-lesson[open] summary").inner_text()
        check("Videos: the next lesson's videos are open, marked Next", "The alphabet, part 1" in opened and "Next" in opened, opened)
        check("Videos: a finished lesson is marked Done", "Done" in await pg.locator(".md-lesson").first.inner_text())
        links = await pg.evaluate("[...document.querySelectorAll('.md-body a.row')].map((a) => [a.href, a.target, a.rel])")
        check("Every video link opens in a new page, safely", all(t == "_blank" and "noopener" in r for _, t, r in links) and len(links) > 15, str(links[:2]))
        await pg.click("[data-lang='he']")
        await pg.wait_for_function("document.querySelector('.md-body').textContent.includes('Aleph with Beth')")
        hlinks = await pg.evaluate("[...document.querySelectorAll('.md-body a.row')].map((a) => a.href)")
        expect = [v["href"] for v in MEDIA["he"]["lessons"]["he-1"]]
        check("Hebrew: alphabet videos for lessons 1 and 2, plus readings and songs", all(h in hlinks for h in expect) and any("mechon-mamre" in h for h in hlinks), str(len(hlinks)))
        # the lesson's own video isn't listed twice in its Hear step
        await go(pg, "learn", ".path-item")
        await pg.goto(f"{BASE}#/lesson/grc/grc-1")
        await pg.wait_for_selector("[data-next]")
        for _ in range(20):
            if await pg.locator(".ls-alongside").count():
                break
            await pg.click("[data-next]")
            await pg.wait_for_timeout(200)
        n_along = await pg.locator(".ls-alongside li").count()
        check("Lesson 1's Hear step: the alphabet song alongside (its own Angela video not repeated)", n_along == len(MEDIA["grc"]["lessons"]["grc-1"]) - 1, str(n_along))

        # 7. iPad: Progress in the side rail
        await pg.set_viewport_size({"width": 1180, "height": 820})
        await go(pg, "progress", ".pg-streak")
        check("iPad: Progress in the side rail, current", await pg.get_attribute(".tabs a[data-tab='progress']", "aria-current") == "page")
        check("iPad: no sideways scroll", not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"))

        # 8. 320px, largest text, dark; and offline
        await ctx.close()
        ctx = await b.new_context(viewport={"width": 320, "height": 640}, color_scheme="dark")
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_INTERNET_DISCONNECTED" not in m.text else None)
        await fresh(pg, {"textSize": "largest", "cards": cards, "activity": acts, "lessons": {"grc-0": {"v": 1, "done": True, "pos": 0}}})
        for route, sel in (("today", ".today-plan"), ("progress", ".pg-lang h2"), ("media", ".md-lesson")):
            await go(pg, route, sel)
            await pg.wait_for_timeout(400)
            over = await pg.evaluate("[...document.querySelectorAll('.screen *')].filter((e) => e.getBoundingClientRect().right > innerWidth + 1).map((e) => e.className || e.tagName).slice(0, 4)")
            check(f"320px, largest text, dark: {route} fits", not over and not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"), str(over))
        await pg.evaluate("navigator.serviceWorker.ready")
        await pg.wait_for_timeout(1500)
        await go(pg, "today", ".today-plan")
        await ctx.set_offline(True)
        await pg.reload()
        await go(pg, "media", ".md-lesson")
        check("Offline: Videos opens (the list is saved with the app)", await pg.locator(".md-section").count() >= 4)
        await go(pg, "progress", ".pg-lang h2")
        check("Offline: Progress adds up (word lists saved with the app)", "make up" in await pg.locator(".pg-lang").first.inner_text())
        await ctx.set_offline(False)

        check("No console errors", not errs, str(errs[:5]))
        await b.close()
    print(f"\n{sum(res)}/{len(res)} passed")
    raise SystemExit(0 if all(res) else 1)


asyncio.run(main())
