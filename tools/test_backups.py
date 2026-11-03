"""Old backups restore: every sample in tools/fixtures/backups/ (one per backup format the app has had) is restored
through Settings on a fresh device, and the progress the app then shows is compared with what the sample holds.
Catches a later change that would break restoring an older backup. Run with the local server on :8765:
python3 tools/test_backups.py

When the backup format changes, add a new sample (export one from the app) with its "expect" numbers; never edit
the old ones.
"""
import asyncio, glob, json, os, re, sys, tempfile
from datetime import datetime
from playwright.async_api import async_playwright

BASE = "http://localhost:8765/"
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
HERE = os.path.dirname(os.path.abspath(__file__))
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))


async def main():
    samples = sorted(glob.glob(os.path.join(HERE, "fixtures", "backups", "*.json")))
    check("sample backups kept (at least two formats)", len(samples) >= 2, samples)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        for path in samples:
            name = os.path.basename(path)[:-5]
            sample = json.load(open(path, encoding="utf-8"))
            exp, backup = sample["expect"], sample["backup"]
            tmp = os.path.join(tempfile.mkdtemp(), f"aleph-to-omega-backup-{name}.json")
            json.dump(backup, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
            pg = await ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            await pg.clock.install(time=datetime(2026, 11, 3, 20, 0))
            await pg.goto(f"{BASE}#/settings")
            await pg.wait_for_selector("[data-action='choose']")
            await pg.set_input_files("[data-action='import']", tmp)
            await pg.wait_for_function("(document.querySelector('.restore-confirm') || {}).innerText && document.querySelector('.restore-confirm').innerText.length > 20")
            ask = await pg.locator(".restore-confirm").inner_text()
            check(f"{name}: described before restoring ({exp['lessons']} lessons, {exp['cards']} cards)",
                  f"{exp['lessons']} finished lesson" in ask and f"{exp['cards']} review card" in ask, ask)
            await pg.click("[data-restore]")
            await pg.wait_for_selector(".toast")
            got = await pg.evaluate("""() => { const g = (k) => JSON.parse(localStorage.getItem('ao:' + k) || 'null');
              return { lessons: Object.values(g('lessons') || {}).filter((x) => x && x.done).length,
                       cards: Object.keys(g('cards') || {}).length, queue: (g('reviewQueue') || []).length,
                       all: Object.fromEntries(Object.keys(localStorage).filter((k) => k.startsWith('ao:')).map((k) => [k, localStorage.getItem(k)])),
                       size: document.documentElement.getAttribute('data-size') || 'normal',
                       theme: document.documentElement.getAttribute('data-theme') || 'auto' }; }""")
            lost = [k for k, v in backup["data"].items() if k != "ao:lastBackup" and got["all"].get(k) != v]
            check(f"{name}: every saved item restored as it was", not lost, lost)
            check(f"{name}: 'last backup' becomes the backup's date", json.loads(got["all"].get("ao:lastBackup", "null") or "null") == backup["exported"], got["all"].get("ao:lastBackup"))
            check(f"{name}: lessons, cards and review list as saved",
                  (got["lessons"], got["cards"], got["queue"]) == (exp["lessons"], exp["cards"], exp["queue"]), got)
            check(f"{name}: text size and theme applied", (got["size"], got["theme"]) == (exp["textSize"], exp["theme"]), got)
            # Every screen draws from the restored progress without errors
            for route, want in (("today", ".today-plan"), ("learn", ".path"), ("progress", ".pg-big"), ("review", "main h1"),
                                ("alphabet", ".ab-tile"), ("read", ".chapter"), ("words", "main h1"), ("settings", "[data-action='choose']")):
                await pg.goto(f"{BASE}#/{route}")
                try:
                    await pg.wait_for_selector(want, timeout=15000)
                    ok = True
                except Exception:
                    ok = False
                check(f"{name}: #/{route} draws", ok)
            await pg.goto(f"{BASE}#/progress")
            await pg.wait_for_selector(".pg-big")
            await pg.wait_for_timeout(800)
            t = await pg.locator("main").inner_text()
            m = re.search(r"(\d+) of (\d+)\s+lessons finished", t)
            check(f"{name}: Progress shows {exp['lessons']} Greek lessons finished", bool(m) and int(m.group(1)) == exp["lessons"], t[:300])
            lab = await pg.locator(".pg-cal").get_attribute("aria-label")
            days = int(re.search(r"Studied on (\d+)", lab or "").group(1)) if re.search(r"Studied on (\d+)", lab or "") else -1
            check(f"{name}: calendar shows {exp['studyDays']} study days", days == exp["studyDays"], days)
            # Review takes the restored cards: a session starts and a card can be answered
            await pg.goto(f"{BASE}#/review")
            await pg.wait_for_selector("main h1")
            await pg.wait_for_timeout(600)
            start = pg.locator("main [data-start]")
            if exp["cards"] or exp["queue"]:
                ok = await start.count() > 0
                if ok:
                    await start.first.click()
                    await pg.wait_for_timeout(600)
                    ok = await pg.locator(".rv-card").count() > 0
                check(f"{name}: Review starts with the restored words", ok)
            check(f"{name}: no console errors", not errs, errs[:3])
            await ctx.close()
        await b.close()
    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
