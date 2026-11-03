"""Slow-phone check: the main screens timed on Chromium slowed six times with a slow 4G connection, roughly an older
iPad or a budget Android phone. Each screen has a time limit; going over fails. Run with the local server on :8765:
python3 tools/test_slow.py

Two situations: the very first visit (nothing saved yet, everything over slow 4G) and everyday use (the app opened
from the home screen, its files saved by the service worker). An emulation, not Safari: the devices remain the judge.
"""
import asyncio, sys, time
from playwright.async_api import async_playwright

BASE = "http://localhost:8765/"
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
SLOW4G = {"offline": False, "latency": 150, "downloadThroughput": 1.6 * 1024 * 1024 / 8, "uploadThroughput": 750 * 1024 / 8}
READY = "document.querySelector('main h1, main .ls-stepbar, main .chapter .w, main .entry-lemma')"
# (what, route, ready when, limit in seconds): everyday use
SCREENS = [
    ("Today", "today", "document.querySelector('.verse-original button, .verse-original [data-i], .verse-original span') && document.querySelector('.today-plan')", 3),
    ("Learn", "learn", READY, 2),
    ("Reader: Genesis 1 (Hebrew, word by word)", "read/GEN/1", "document.querySelectorAll('.chapter .w').length > 400", 5),
    ("Reader: Psalm 119 (the longest chapter)", "read/PSA/119", "document.querySelectorAll('.chapter .w').length > 1000", 9),
    ("Reader: John 1 (Greek)", "read/JHN/1", "document.querySelectorAll('.chapter .w').length > 500", 4),
    ("Septuagint: Psalm 22", "lxx/PSA/22", "document.querySelector('main .lxx-text, main .chapter')", 4),
    ("Words: an entry (λόγος)", "words/G3056", "document.querySelector('main .entry-lemma')", 3),
    ("Review", "review", READY, 3),
    ("Progress", "progress", READY, 3),
    ("A lesson (grc-4)", "lesson/grc/grc-4", "document.querySelector('main .ls-stepbar')", 3),
    ("Letters (Greek)", "alphabet/grc", "document.querySelector('main .ab-tile')", 3),
]
FIRST_VISIT_LIMIT = 12  # Today, from nothing, over slow 4G


async def slow(pg, cpu=6, net=True):
    cdp = await pg.context.new_cdp_session(pg)
    await cdp.send("Emulation.setCPUThrottlingRate", {"rate": cpu})
    if net:
        await cdp.send("Network.enable")
        await cdp.send("Network.emulateNetworkConditions", SLOW4G)
    return cdp


async def timed(pg, route, ready, limit):
    await pg.goto(f"{BASE}#/settings")
    await pg.wait_for_function(READY, timeout=30000)
    t0 = time.time()
    await pg.evaluate(f"location.hash = '#/{route}'")
    try:
        await pg.wait_for_function(ready, timeout=(limit * 3 + 10) * 1000, polling=50)
    except Exception:
        return None
    return time.time() - t0


async def main():
    fails, lines = [], []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        # 1. First visit: nothing saved, everything over slow 4G
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page()
        await slow(pg)
        t0 = time.time()
        await pg.goto(f"{BASE}#/today")
        await pg.wait_for_function(SCREENS[0][2], timeout=90000)
        t = time.time() - t0
        lines.append(f"First visit, Today: {t:.1f} s (limit {FIRST_VISIT_LIMIT})")
        if t > FIRST_VISIT_LIMIT:
            fails.append(lines[-1])
        await ctx.close()

        # 2. Everyday use: the app's files saved, then the phone slowed down
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page()
        await pg.goto(f"{BASE}#/today")
        await pg.evaluate("navigator.serviceWorker.ready")
        await pg.reload()
        for _, route, ready, _ in SCREENS:  # visit each once so its data is saved, as on a phone in use
            await pg.goto(f"{BASE}#/{route}")
            await pg.wait_for_function(ready, timeout=30000)
        await pg.wait_for_timeout(1500)
        await pg.reload()
        await slow(pg)
        for name, route, ready, limit in SCREENS:
            t = await timed(pg, route, ready, limit)
            lines.append(f"{name}: {'did not finish' if t is None else f'{t:.1f} s'} (limit {limit})")
            if t is None or t > limit:
                fails.append(lines[-1])
        await ctx.close()
        await b.close()
    for l in lines:
        print(("FAIL " if l in fails else "  ok ") + l)
    total = len(SCREENS) + 1
    print(f"\n{total - len(fails)}/{total} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    asyncio.run(main())
