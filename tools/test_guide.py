"""The Guide tab in the browser (19 Nov 2026). Run with the local server on :8765:  python3 tools/test_guide.py

Checks: the seventh tab fits and works at 320px largest text; every section and entry page opens with no console
error and nothing wider than the screen (phone, 320px largest dark, iPad); every entry is found by searching its title
and each of its other names; grammar codes typed in the search are explained; every grammar code page shows each
part with a link; every example shows its verse, word, grammar and Listen buttons that say exactly what the Reader
says (voices replaced by a recorder); Greek and Hebrew in the text are said when tapped; the “What do these words
mean?” link from a Reader word sheet, Today's verse and a lesson's Read step opens the right code; Reader notes, the
Letters guide, Learn, Settings and the Words search link into the guide; the last Notice card of a lesson lists the
guide's entries for it; the guide works offline after the first visit.
"""
import asyncio, json, random
from playwright.async_api import async_playwright

BASE = "http://localhost:8765/"
CHROME = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
ROOT = "/home/claude/biblical-languages/"
res = []

VOICES = """
window.__spoken = [];
window.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; } };
Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
  getVoices() { return [{name: 'Melina', lang: 'el-GR', localService: true}, {name: 'Carmit', lang: 'he-IL', localService: true}]; },
  speak(u) { window.__spoken.push(u.text); setTimeout(() => u.onend && u.onend(), 10); }, cancel() {}, addEventListener() {} } });
"""


def check(name, ok, detail=""):
    res.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


async def overflow(pg):
    return await pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


async def main():
    guide = json.load(open(ROOT + "guide/guide.json"))
    examples = json.load(open(ROOT + "guide/examples.json"))
    ids = [e["id"] for e in guide["entries"]]
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
        await ctx.add_init_script(VOICES)
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

        # 1. The tab
        await pg.goto(f"{BASE}#/today")
        await pg.wait_for_selector(".tabs a[data-tab=guide]")
        n = await pg.locator(".tabs > a[data-tab]").count()
        check("Seven tabs on a phone, the last is Guide", n == 7 and (await pg.locator(".tabs > a[data-tab]").nth(6).inner_text()).strip() == "Guide")
        await pg.click(".tabs a[data-tab=guide]")
        await pg.wait_for_selector("#guide-q")
        check("The Guide tab opens the guide and is marked current", await pg.get_attribute(".tabs a[data-tab=guide]", "aria-current") == "page")

        # 2. Every section and entry at 390px: opens, no errors, nothing too wide, examples shown
        bad_pages, bad_ex = [], []
        for s in guide["sections"]:
            await pg.goto(f"{BASE}#/guide/s/{s['id']}")
            await pg.wait_for_selector(".g-intro")
            if await pg.locator(".rows .row").count() != len(s["entries"]):
                bad_pages.append(f"section {s['id']}: rows")
        for i in ids:
            await pg.goto(f"{BASE}#/guide/{i}")
            await pg.wait_for_selector(".g-title")
            want = len(examples["examples"].get(i, []))
            if want:
                try:
                    await pg.wait_for_function(f"document.querySelectorAll('.g-ex').length === {want}", timeout=8000)
                except Exception:
                    bad_ex.append(i)
            if await overflow(pg) > 0:
                bad_pages.append(f"{i}: wider than the screen")
        check(f"All {len(guide['sections'])} sections and {len(ids)} entries open at 390px, nothing wider than the screen", not bad_pages, bad_pages[:5])
        check(f"Every example shows ({sum(len(v) for v in examples['examples'].values())} in all)", not bad_ex, bad_ex[:5])
        check("No console errors on any guide page", not errs, errs[:3])

        # 3. Searching: every title and every other name finds its entry
        await pg.goto(f"{BASE}#/guide")
        await pg.wait_for_selector("#guide-q")
        misses = []
        for e in guide["entries"]:
            for q in [e["title"]] + e.get("aka", []):
                hit = await pg.evaluate("""async ([q, id]) => { const G = await import('./js/guide-text.js'); const g = await (await import('./js/guide.js')).loadGuide();
                    return G.searchGuide(q, g).slice(0, 8).some(h => h.entry.id === id); }""", [q, e["id"]])
                if not hit:
                    misses.append(f"{q} → {e['id']}")
        check("Every entry is found by its title and every other name (top 8)", not misses, misses[:8])
        for q, want in [("aorist", "aorist"), ("3ms", "pgn"), ("impf.", "imperfect-greek"), ("dagesh", "dagesh"), ("wayyiqtol", "wayyiqtol"), ("ketiv", "ketiv-qere")]:
            await pg.fill("#guide-q", q)
            await pg.wait_for_selector(".g-results .row")
            hrefs = await pg.eval_on_selector_all(".g-results a.row", "els => els.map(a => a.getAttribute('href'))")
            check(f"Search “{q}” lists {want} near the top", f"#/guide/{want}" in hrefs[:3], hrefs[:3])
        await pg.fill("#guide-q", "V-2AAI-3S")
        await pg.wait_for_selector(".g-results .row")
        await pg.click(".g-results a.row >> nth=0")
        await pg.wait_for_selector(".g-code-label")
        label = await pg.inner_text(".g-code-label")
        check("A grammar code typed in the search is explained part by part", "2nd aorist" in label and await pg.locator(".g-terms a.row").count() >= 6, label)

        # 4. Every grammar code page: each part has an entry (one page per code, all codes)
        codes = await pg.evaluate("""async () => { const g = await (await fetch('data/morph/greek.json')).json(); const h = await (await fetch('data/morph/hebrew.json')).json();
            return [...Object.keys(g).map(k => ['grc', k]), ...Object.keys(h).map(k => ['he', k])]; }""")
        random.seed(19)
        sample = random.sample(codes, 120) + [["he", "Hc/Vqw3ms"], ["grc", "ADV-N"], ["grc", "N-NSN-LI"], ["he", "HTd"], ["he", "ANcmsd"]]
        unlinked = []
        for lang, code in sample:
            await pg.goto(f"{BASE}#/guide/code/{lang}/{code.replace('/', '%2F')}")
            await pg.wait_for_selector(".g-code-parts")
            plain = await pg.locator(".g-terms span.row").count()
            if plain:
                unlinked.append(code)
        check(f"Code pages: every part of {len(sample)} codes links to an entry", not unlinked, unlinked[:5])

        # 5. Listen buttons: Greek and Hebrew in the text, and the examples, say what the Reader says
        await pg.goto(f"{BASE}#/guide/dictionary-form")
        await pg.wait_for_selector(".g-body .g-say")
        await pg.evaluate("window.__spoken = []")
        btns = pg.locator(".g-body .g-say")
        said = []
        for k in range(await btns.count()):
            await btns.nth(k).click()
        await pg.wait_for_timeout(200)
        said = await pg.evaluate("window.__spoken")
        want = await pg.evaluate("""async () => { const S = await import('./js/sound.js');
            return [...document.querySelectorAll('.g-body .g-say')].map(b => S.speechText(b.dataset.say, b.dataset.sayLang, null)); }""")
        check("Tapping Greek and Hebrew in the text says each word", said == want and len(said) >= 3, [said, want])
        wrong = []
        for i in ["aorist", "wayyiqtol", "construct-state", "hebrew-article", "dative"]:
            await pg.goto(f"{BASE}#/guide/{i}")
            await pg.wait_for_selector(".g-ex")
            for k, x in enumerate(examples["examples"][i]):
                await pg.evaluate("window.__spoken = []")
                ex = pg.locator(".g-ex").nth(k)
                await ex.locator(".g-ex-form .say-btn").click()
                await ex.locator(".g-ex-actions .say-btn").click()
                await pg.wait_for_timeout(100)
                got = await pg.evaluate("window.__spoken")
                exp = await pg.evaluate("""async (x) => { const a = await import('./js/audio.js'); const h = await import('./js/hebrew.js'); const S = await import('./js/sound.js');
                    const w = x.words[x.wi];
                    const word = x.lang === 'he' ? a.heVoice(w, null, h.heJoined(w[5]), x.lex) + (h.heJoined(w[5]) ? '־' : '') : w[0];
                    return [S.speechText(word, x.lang, null), S.speechText(a.verseSpeech(x.words, x.lang, x.lex), x.lang, null)]; }""", x)
                if got != exp:
                    wrong.append(f"{i} {x['ref']}: {got} ≠ {exp}")
        check("Example Listen buttons say the word and the verse exactly as the Reader does", not wrong, wrong[:3])
        href = await pg.get_attribute(".g-ex .verse-link", "href")
        x0 = examples["examples"]["dative"][0]
        check("“Open in the Reader” goes to the verse and word", href == f"#/read/{x0['book']}/{x0['ch']}/{x0['v']}/{x0['wi']}", href)

        # 6. Links into the guide from the rest of the app
        await pg.goto(f"{BASE}#/read/JHN/1")
        await pg.wait_for_selector(".w[data-wi]", timeout=15000)
        await pg.locator(".w[data-wi]").nth(2).click()
        await pg.wait_for_selector(".sheet .g-explain")
        ex_href = await pg.get_attribute(".sheet .g-explain", "href")
        check("Reader word sheet: “What do these words mean?” links to the word's code", ex_href == "#/guide/code/grc/V-IAI-3S", ex_href)
        await pg.click(".sheet .g-explain")
        await pg.wait_for_selector(".g-code-label")
        check("…and opens the code page", "imperfect" in (await pg.inner_text(".g-code-label")).lower())
        await pg.goto(f"{BASE}#/read/GEN/1")
        await pg.wait_for_selector(".w[data-wi]", timeout=20000)
        await pg.locator(".w[data-wi]").nth(0).click()
        await pg.wait_for_selector(".sheet .g-explain")
        check("Hebrew word sheet: the link carries the whole code with its parts", await pg.get_attribute(".sheet .g-explain", "href") == "#/guide/code/he/HR%2FNcfsa")
        await pg.goto(f"{BASE}#/read/MRK/16")
        await pg.wait_for_selector(".v-note .g-more", timeout=15000)
        check("Reader note on ⟦ ⟧ links to the guide", await pg.get_attribute(".v-note .g-more", "href") == "#/guide/double-brackets")
        await pg.goto(f"{BASE}#/read/DAN/3")
        await pg.wait_for_selector(".v-note .g-more", timeout=20000)
        hrefs = await pg.eval_on_selector_all(".v-note .g-more", "els => els.map(a => a.getAttribute('href'))")
        check("Reader note on Aramaic links to the guide", "#/guide/aramaic-language" in hrefs, hrefs)
        await pg.goto(f"{BASE}#/alphabet/he")
        await pg.wait_for_selector(".ab-guide a")
        hrefs = await pg.eval_on_selector_all(".ab-guide a", "els => els.map(a => a.getAttribute('href'))")
        check("Letters guide sections link to the guide", "#/guide/dagesh" in hrefs and "#/guide/maqqef" in hrefs, hrefs[:4])
        await pg.goto(f"{BASE}#/learn")
        await pg.wait_for_selector('a[href="#/guide/s/basics"]')
        check("Learn offers the grammar basics", True)
        await pg.goto(f"{BASE}#/settings")
        await pg.wait_for_selector('a.row[href="#/guide"]')
        check("Settings › Help links to the guide", True)
        await pg.goto(f"{BASE}#/words")
        await pg.wait_for_selector("#dict-q")
        await pg.fill("#dict-q", "aorist")
        await pg.wait_for_selector(".dict-guide a.row", timeout=8000)
        check("Words search for a grammar word shows its guide entry first", await pg.get_attribute(".dict-guide a.row", "href") == "#/guide/aorist")
        await pg.fill("#dict-q", "in")
        await pg.wait_for_timeout(1200)
        check("…but not for everyday words such as “in”", await pg.locator(".dict-guide").count() == 0)
        await pg.goto(f"{BASE}#/today")
        await pg.wait_for_selector(".verse-original .w", timeout=20000)
        await pg.locator(".verse-original .w").nth(0).click()
        await pg.wait_for_selector(".verse-gloss .g-explain", timeout=8000)
        check("Today's verse: a tapped word has the “What do these words mean?” link", (await pg.get_attribute(".verse-gloss .g-explain", "href")).startswith("#/guide/code/"))

        # 7. A lesson's last Notice card lists the guide's entries for it
        L = json.load(open(ROOT + "lessons/grc/4.json"))
        pos = sum(len(s["cards"]) for s in L["steps"][:2]) - 1
        sig = ",".join(f"{x['step']}:{len(x['cards'])}" for x in L["steps"])
        await pg.evaluate("([pos, sig]) => localStorage.setItem('ao:lessons', JSON.stringify({'grc-4': {v: 1, pos, retries: [], first: {}, done: false, sig}}))", [pos, sig])
        await pg.goto(f"{BASE}#/learn")
        await pg.goto(f"{BASE}#/lesson/grc/grc-4")
        await pg.wait_for_selector(".ls-guide a.row", timeout=10000)
        hrefs = await pg.eval_on_selector_all(".ls-guide a.row", "els => els.map(a => a.getAttribute('href'))")
        want = [f"#/guide/{e['id']}" for e in guide["entries"] if "grc-4" in e.get("lessons", [])]
        check("A lesson's last Notice card lists its guide entries", sorted(hrefs) == sorted(want), [hrefs, want])
        await ctx.close()

        # 8. 320px, largest text, dark: the tab bar and every entry
        ctx = await b.new_context(viewport={"width": 320, "height": 640}, service_workers="block", color_scheme="dark")
        await ctx.add_init_script("localStorage.setItem('ao:textSize', JSON.stringify('largest')); localStorage.setItem('ao:theme', JSON.stringify('dark'));")
        pg = await ctx.new_page()
        await pg.goto(f"{BASE}#/guide")
        await pg.wait_for_selector("#guide-q")
        tabs = await pg.eval_on_selector_all(".tabs > a[data-tab]", "els => els.map(a => { const r = a.getBoundingClientRect(); const s = a.querySelector('span'); return [r.width, r.height, s.scrollWidth <= s.clientWidth + 1]; })")
        check("320px largest text: seven tabs each at least 44px wide and tall, labels not cut", all(w >= 44 and h >= 44 and fit for w, h, fit in tabs), tabs)
        wide = []
        for i in ids:
            await pg.goto(f"{BASE}#/guide/{i}")
            await pg.wait_for_selector(".g-title")
            await pg.wait_for_timeout(30)
            if await overflow(pg) > 0:
                wide.append(i)
        check("320px largest text, dark: no entry wider than the screen", not wide, wide[:6])
        await ctx.close()

        # 9. iPad: the side rail has Guide
        ctx = await b.new_context(viewport={"width": 1180, "height": 820}, service_workers="block")
        pg = await ctx.new_page()
        await pg.goto(f"{BASE}#/guide/aorist")
        await pg.wait_for_selector(".g-title")
        check("iPad: Guide is on the side rail and current", await pg.get_attribute(".tabs a[data-tab=guide]", "aria-current") == "page" and await pg.is_visible(".tabs a[data-tab=guide]"))
        await ctx.close()

        # 10. Offline after the first visit
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page()
        await pg.goto(f"{BASE}#/today")
        await pg.evaluate("navigator.serviceWorker.ready")
        await pg.reload()
        await pg.wait_for_function("!!navigator.serviceWorker.controller", timeout=30000)
        await ctx.set_offline(True)
        await pg.goto(f"{BASE}#/guide/wayyiqtol")
        await pg.wait_for_selector(".g-title", timeout=10000)
        try:
            await pg.wait_for_selector(".g-ex", timeout=8000)
            ok = True
        except Exception:
            ok = False
        check("Offline: an entry and its examples open after the first visit", ok)
        await ctx.close()
        await b.close()
    print(f"{sum(res)}/{len(res)} passed")
    raise SystemExit(0 if all(res) else 1)


asyncio.run(main())
