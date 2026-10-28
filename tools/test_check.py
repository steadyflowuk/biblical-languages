"""Check this device (Session 12). Run with the local server on :8765:  python3 tools/test_check.py"""
import asyncio, faulthandler
from playwright.async_api import async_playwright

faulthandler.dump_traceback_later(600, exit=True)
BASE = "http://localhost:8765/"
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
res = []
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 Mobile/15E148 Safari/604.1"

VOICES = """
window.__spoken = [];
window.__voices = %s;
window.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; } };
Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
  getVoices() { return window.__voices; }, speaking: false, pending: false,
  speak(u) { window.__spoken.push({ text: u.text, lang: u.lang }); if (window.__voices.length) setTimeout(() => { u.onstart && u.onstart(); setTimeout(() => u.onend && u.onend(), 30); }, 20); },
  cancel() {}, addEventListener() {} } });
"""
BOTH = "[{name: 'Melina', lang: 'el-GR', localService: true}, {name: 'Carmit', lang: 'he-IL', localService: true}]"


def check(name, ok, detail=""):
    res.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


async def open_check(pg):
    await pg.goto(f"{BASE}#/settings")
    await pg.click("a[href='#/check']")
    await pg.wait_for_selector(".ck-report")


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        errs = []

        # 1. Reading the device from the browser's description
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page()
        await pg.goto(f"{BASE}#/today")
        r = await pg.evaluate("""async () => { const c = await import('./js/check.js'); return [
          c.describeDevice('Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1', 5),
          c.describeDevice('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15', 5),
          c.describeDevice('Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36', 5),
          c.describeDevice('Mozilla/5.0 (Linux; Android 13; SM-T220) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.0.0 Safari/537.36', 5),
          c.describeDevice('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15', 0),
        ].map((d) => [d.device, d.system, d.browser].join(' | ')); }""")
        check("iPhone: iOS 17.1, Safari", r[0] == "iPhone | iOS 17.1 | Safari", r[0])
        check("iPad (asks for desktop sites): iPadOS 16.5", r[1] == "iPad | iPadOS 16.5 | Safari", r[1])
        check("Android phone with Chrome", r[2] == "Android phone | Android 14 | Chrome 126", r[2])
        check("Samsung tablet with Samsung Internet", r[3] == "Android tablet | Android 13 | Samsung Internet 25", r[3])
        check("A Mac (no touch) is a computer", r[4].startswith("Computer | macOS | Safari"), r[4])
        await ctx.close()

        # 2. The screen with voices, as an iPhone
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, user_agent=IPHONE)
        await ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        await ctx.add_init_script(VOICES % BOTH)
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        await pg.goto(f"{BASE}#/today")
        await pg.evaluate("navigator.serviceWorker.ready")
        await pg.wait_for_timeout(1500)
        await open_check(pg)
        t = await pg.locator(".ck-body").inner_text()
        check("Settings › Check this device opens it", True)
        check("Shows the device: iPhone · iOS 15.6, Safari", "iPhone · iOS 15.6" in t, t[:200])
        check("Offline: the app is saved (version and files)", "The app is saved on this device" in t and "Version 2026-" in t, t[200:600])
        check("Voices listed: Melina for Greek, Carmit for Hebrew", "Melina (el-GR)" in t and "Carmit (he-IL)" in t)
        check("Fonts in use", "The app's fonts are in use" in t)
        await pg.click("[data-test='he']")
        await pg.wait_for_timeout(150)
        sp = await pg.evaluate("window.__spoken")
        check("Hebrew test plays with the Israeli voice, sample without accents", sp and sp[-1]["lang"] == "he-IL" and "בְּרֵאשִׁית" in sp[-1]["text"], str(sp))
        await pg.click("[data-heard='he'][data-v='no']")
        tip = await pg.locator(".ck-voice[data-lang='he'] .ck-tip").inner_text()
        check("Heard it? No → advice mentions the ringer switch (iPhone)", "ringer switch" in tip, tip)
        rep = await pg.locator(".ck-report").inner_text()
        check("Report: Hebrew test started, heard: no; Greek not played", "Hebrew test: started · heard: no" in rep and "Greek test: not played" in rep, rep)
        check("Report holds the app version and the browser's description", "App version: 2026-" in rep and "iPhone OS 15_6" in rep)
        await pg.click("[data-copy]")
        clip = await pg.evaluate("navigator.clipboard.readText()")
        check("Copy the report → on the clipboard", clip.startswith("Aleph to Omega device check"), clip[:60])
        check("Settings tab stays current", await pg.get_attribute(".tabs a[data-tab='settings']", "aria-current") == "page")

        # 3. Offline, after one visit
        await ctx.set_offline(True)
        await pg.reload()
        await open_check(pg)
        t = await pg.locator(".ck-body").inner_text()
        check("Offline: the check still opens and says Offline", "Offline" in t and "The app is saved on this device" in t, t[:300])
        await ctx.set_offline(False)
        await ctx.close()

        # 4. No Hebrew voice: listed voices without one → how to add it; the test doesn't start
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, user_agent=IPHONE)
        await ctx.add_init_script(VOICES % "[{name: 'Melina', lang: 'el-GR', localService: true}]")
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await open_check(pg)
        t = await pg.locator(".ck-voice[data-lang='he']").inner_text()
        check("No Hebrew voice: says where to add one on an iPhone", "None installed" in t and "Spoken Content" in t, t)
        await pg.click("[data-test='he']")
        await pg.wait_for_timeout(200)
        rep = await pg.locator(".ck-report").inner_text()
        check("…and the report says the test didn't start", "Hebrew test: DID NOT START" in rep, rep)
        await ctx.close()

        # 5. No speech at all (some browsers)
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        await ctx.add_init_script("delete window.speechSynthesis; delete window.SpeechSynthesisUtterance;")
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await open_check(pg)
        t = await pg.locator(".ck-body").inner_text()
        check("No speech: says this browser can't speak aloud", "can't speak aloud" in t, t[:400])
        await ctx.close()

        # 6. 320px, largest text, dark
        ctx = await b.new_context(viewport={"width": 320, "height": 640}, color_scheme="dark", user_agent=IPHONE)
        await ctx.add_init_script(VOICES % BOTH)
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(f"{BASE}#/settings")
        await pg.evaluate("localStorage.setItem('ao:textSize', JSON.stringify('largest'))")
        await pg.reload()
        await open_check(pg)
        await pg.click("[data-test='grc']")
        over = await pg.evaluate("[...document.querySelectorAll('.screen *')].filter((e) => e.getBoundingClientRect().right > innerWidth + 1).map((e) => e.className || e.tagName).slice(0, 4)")
        check("320px, largest text, dark: everything fits", not over and not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"), str(over))
        await ctx.close()

        check("No console errors", not errs, str(errs[:4]))
        await b.close()
    print(f"\n{sum(res)}/{len(res)} passed")
    raise SystemExit(0 if all(res) else 1)


asyncio.run(main())
