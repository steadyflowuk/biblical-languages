"""Listening practice, everywhere it applies (19 Nov 2026). Server on :8765:  python3 tools/test_listening.py

Settings › Listening practice: Easy = a tapped word is said; Medium = that, and "Listen to the verse"; Hard = the whole
verse only (a tap shows the meaning silently, and verse words have no Listen buttons). For every place a verse is
shown, at every level, this checks what is on screen and exactly what the voice is asked to say:
  Today (Greek and Hebrew) · a lesson's Read step (Greek and Hebrew) · the Reader in all three layouts (Greek and
  Hebrew) · the Septuagint screen and Septuagint lines in the Reader · the Letters guide's verses (Greek and Hebrew).
"Exactly": a tapped word must give the voice the text the Bible data gives for that word (js/audio.js heVoice for
Hebrew, the Reader's own word for Greek, lxxTapWord for the Septuagint) and a verse button the whole verse
(audio.verseSpeech / lxxSpeech), after the same conversion the app makes (sound.speechText, Erasmian or Koine).
Also: the keyboard (Enter on a word) follows the level; the level is kept after a reload; the Reader's display options
and Settings change it together; Listen buttons outside verses (dictionary, review cards) stay at every level.
The phone's voices are replaced by a stand-in that records what it was asked to say.
"""
import asyncio, json, faulthandler
from playwright.async_api import async_playwright

faulthandler.dump_traceback_later(1500, exit=True)
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
  speak(u) { window.__spoken.push({ text: u.text, lang: u.lang }); setTimeout(() => u.onend && u.onend(), 20); },
  cancel() {}, addEventListener() {} } });
"""

# In the page: what the voice should get for a word or a verse of the Bible data (the app's own modules, so the
# expectation is built from the data, not from what is on screen)
HELPERS = """
window.__x = {
  async book(lang, id) { return fetch(`data/${lang === 'he' ? 'hot' : 'gnt'}/${id}.json`).then(r => r.json()); },
  async verse(lang, id, ch, v) { const b = await this.book(lang, id);
    return { words: ((b.ch.find(c => c[0] === ch) || [0, []])[1].find(x => x[0] === v) || [0, []])[1], lex: b.lex }; },
  async conv(raw, lang) { const S = await import('./js/sound.js');
    return S.speechText(raw, lang, JSON.parse(localStorage.getItem('ao:greekVoice') || 'null')); },
  async word(lang, w, lex) { const a = await import('./js/audio.js'); const h = await import('./js/hebrew.js');
    const raw = lang === 'he' ? a.heVoice(w, null, h.heJoined(w[5]), lex) + (h.heJoined(w[5]) ? '־' : '') : w[0];
    return this.conv(raw, lang); },
  async whole(lang, words, lex) { const a = await import('./js/audio.js'); return this.conv(a.verseSpeech(words, lang, lex), lang); },
};
"""

LEVELS = ["easy", "medium", "hard"]


def check(name, ok, detail=""):
    res.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def first_read(lang):
    """The first written lesson with a Read step, and the card position of that step (to open the lesson there)."""
    index = json.load(open(f"{ROOT}lessons/index.json"))
    for e in index[lang]:
        if not e.get("file") or e["id"].endswith("-0"):
            continue
        L = json.load(open(ROOT + e["file"]))
        pos = 0
        for s in L["steps"]:
            for c in s["cards"]:
                if c["type"] == "verse":
                    sig = ",".join(f"{x['step']}:{len(x['cards'])}" for x in L["steps"])
                    return e["id"], pos, sig, c["ref"]
                pos += 1
    raise SystemExit(f"no Read step in the {lang} lessons")


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, has_touch=True)
        await ctx.add_init_script(VOICES)
        await ctx.add_init_script(HELPERS)
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

        async def said():
            await pg.wait_for_timeout(150)
            out = [x["text"] for x in await pg.evaluate("window.__spoken")]
            await pg.evaluate("window.__spoken = []")
            return out

        async def set_level(name, voice="erasmian"):
            await pg.goto(f"{BASE}#/settings")
            await pg.evaluate(f"localStorage.setItem('ao:listenLevel', JSON.stringify('{name}'))")
            await pg.evaluate(f"localStorage.setItem('ao:greekVoice', JSON.stringify('{voice}'))")

        async def tap_and_check(label, level, el, want_word, meaning_sel=None):
            """Tap el; Easy/Medium: the voice gets want_word (already converted) and nothing else; Hard: silence."""
            await pg.evaluate("window.__spoken = []")
            await el.click()
            got = await said()
            ok = got == ([want_word] if level != "hard" else [])
            if meaning_sel:
                shown = (await pg.locator(meaning_sel).inner_text()).strip()
                ok = ok and bool(shown)
            check(f"{level.title()}, {label}: a tap {'says ' + repr(want_word[:40]) if level != 'hard' else 'shows the meaning, silently'}", ok, f"said {got}")

        async def verse_button(label, level, sel, want_verse):
            n = await pg.locator(sel).count()
            if level == "easy":
                check(f"Easy, {label}: no whole-verse button", n == 0, str(n))
                return
            got = []
            if n:
                await pg.evaluate("window.__spoken = []")
                await pg.locator(sel).first.click()
                got = await said()
            check(f"{level.title()}, {label}: the verse button says the whole verse", n >= 1 and got == [want_verse],
                  f"{n} buttons; said {[g[:60] for g in got]} wanted {want_verse[:60]}")

        for level in LEVELS:
            await set_level(level)
            # ---------------- Today, both languages
            for lang in ("grc", "he"):
                await pg.goto(f"{BASE}#/today")
                await pg.click(f'[data-lang="{lang}"]')
                want_id = await pg.evaluate("""async (lang) => { const m = await import('./js/votd.js');
                  const [pool, books] = await Promise.all([fetch('data/votd-pool.json').then(r => r.json()), fetch('data/books.json').then(r => r.json())]);
                  return m.pickRef(m.poolRefs(pool, lang, books.map(b => b.id)), lang, m.dayNumber(new Date())).join('-'); }""", lang)
                await pg.wait_for_function(f"document.querySelector('.verse-slot')?.dataset.verse === {json.dumps(want_id)}", timeout=10000)
                bid, ch, v = want_id.split("-")
                words, lex = await pg.evaluate("async ([l, b, c, v]) => { const x = await __x.verse(l, b, c, v); return [x.words, x.lex]; }", [lang, bid, int(ch), int(v)])
                name = f"Today ({'Hebrew' if lang == 'he' else 'Greek'}, {bid} {ch}:{v})"
                for k in range(min(3, len(words))):
                    want = await pg.evaluate("([l, w, lex]) => __x.word(l, w, lex)", [lang, words[k], lex])
                    await tap_and_check(f"{name} word {k + 1}", level, pg.locator(".verse-original .w").nth(k), want, ".verse-gloss .meaning")
                gloss_btn = await pg.locator(".verse-gloss [data-say]").count()
                check(f"{level.title()}, {name}: the tapped word's own Listen button {'hidden' if level == 'hard' else 'there'}", gloss_btn == (0 if level == "hard" else 1), str(gloss_btn))
                want_verse = await pg.evaluate("([l, w, lex]) => __x.whole(l, w, lex)", [lang, words, lex])
                await verse_button(name, level, ".verse-listen [data-say]", want_verse)
                # the keyboard: Enter on a word does what a tap does
                await pg.evaluate("window.__spoken = []")
                await pg.locator(".verse-original .w").nth(1).focus()
                await pg.keyboard.press("Enter")
                got = await said()
                want = await pg.evaluate("([l, w, lex]) => __x.word(l, w, lex)", [lang, words[1], lex])
                check(f"{level.title()}, {name}: Enter on a word follows the level", got == ([want] if level != "hard" else []), str(got))

            # ---------------- a lesson's Read step, both languages
            for lang in ("grc", "he"):
                lid, pos, sig, ref = first_read(lang)
                await pg.goto(f"{BASE}#/settings")
                await pg.evaluate(f"localStorage.setItem('ao:lessons', JSON.stringify({{{json.dumps(lid)}: {{v: 1, sig: {json.dumps(sig)}, pos: {pos}, retries: [], first: {{}}}}}}))")
                await pg.goto(f"{BASE}#/learn")
                await pg.goto(f"{BASE}#/lesson/{lang}/{lid}")
                await pg.wait_for_selector(".ls-vw", timeout=10000)
                bk, cv = ref.split(" ")
                c, vv = map(int, cv.split(":"))
                words, lex = await pg.evaluate("async ([l, b, c, v]) => { const x = await __x.verse(l, b, c, v); return [x.words, x.lex]; }", [lang, bk, c, vv])
                name = f"lesson {lid} Read step ({ref})"
                for k in range(min(3, len(words))):
                    want = await pg.evaluate("([l, w, lex]) => __x.word(l, w, lex)", [lang, words[k], lex])
                    await tap_and_check(f"{name} word {k + 1}", level, pg.locator(".ls-vw").nth(k), want, ".ls-gloss")
                gloss_btn = await pg.locator(".ls-gloss [data-say]").count()
                check(f"{level.title()}, {name}: the tapped word's own Listen button {'hidden' if level == 'hard' else 'there'}", gloss_btn == (0 if level == "hard" else 1), str(gloss_btn))
                want_verse = await pg.evaluate("([l, w, lex]) => __x.whole(l, w, lex)", [lang, words, lex])
                await verse_button(name, level, ".ls-listen [data-say]", want_verse)

            # ---------------- the Reader: three layouts, Greek and Hebrew
            for layout in ("words", "text", "parallel"):
                for lang, bid, ch in (("grc", "JHN", 3), ("he", "GEN", 1)):
                    await pg.goto(f"{BASE}#/settings")
                    await pg.evaluate(f"localStorage.setItem('ao:readLayout', JSON.stringify('{layout}'))")
                    await pg.goto(f"{BASE}#/read/{bid}/{ch}")
                    await pg.wait_for_selector(".chapter .w")
                    book = await pg.evaluate("([l, b]) => __x.book(l, b)", [lang, bid])
                    verses = next(vs for c2, vs in book["ch"] if c2 == ch)
                    name = f"Reader {layout} ({bid} {ch})"
                    per_verse = await pg.locator(".v-listen [data-say]").count()
                    want_n = 0 if level == "easy" or layout == "text" else len(verses)
                    check(f"{level.title()}, {name}: a Listen after each verse: {want_n}", per_verse == want_n, str(per_verse))
                    if per_verse:
                        await pg.evaluate("window.__spoken = []")
                        await pg.locator(".v-listen [data-say]").nth(1).click()
                        got = await said()
                        vi = int(await pg.locator(".v-listen").nth(1).evaluate("e => e.closest('[data-vi]').dataset.vi"))
                        want = await pg.evaluate("([l, w, lex]) => __x.whole(l, w, lex)", [lang, verses[vi][1], book["lex"]])
                        check(f"{level.title()}, {name}: a verse's own Listen says that verse", got == [want], f"{[g[:50] for g in got]}")
                    # tap a word (the 3rd in verse 2): the voice gets that word; the sheet has the word and the verse
                    el = pg.locator('.chapter [data-vi="1"] .w[data-wi="2"]').first
                    w = verses[1][1][2]
                    want = await pg.evaluate("([l, w, lex]) => __x.word(l, w, lex)", [lang, w, book["lex"]])
                    await tap_and_check(f"{name} verse {verses[1][0]} word 3", level, el, want)
                    await pg.wait_for_selector(".sheet-panel")
                    word_btn = await pg.locator(".sheet .ws-translit [data-say]").count()
                    check(f"{level.title()}, {name}: the word sheet's Listen for the word {'hidden' if level == 'hard' else 'there'}", word_btn == (0 if level == "hard" else 1), str(word_btn))
                    want_verse = await pg.evaluate("([l, w, lex]) => __x.whole(l, w, lex)", [lang, verses[1][1], book["lex"]])
                    await verse_button(f"{name} word sheet", level, ".sheet .ws-verse-listen [data-say]", want_verse)
                    await pg.keyboard.press("Escape")
            await pg.goto(f"{BASE}#/settings")
            await pg.evaluate("localStorage.setItem('ao:readLayout', JSON.stringify('words'))")

            # ---------------- the Septuagint: its own screen (capitals, a numeral) and its lines in the Reader
            for where, url, sel in (("Septuagint screen GEN 1", "#/lxx/GEN/1", ".lv .lw"),
                                    ("Septuagint screen NUM 7 (numerals)", "#/lxx/NUM/7", "#v84 .lw"),
                                    ("Reader GEN 1 with Septuagint lines", "#/read/GEN/1", ".lxx .lw")):
                await pg.goto(f"{BASE}#/settings")
                await pg.evaluate("localStorage.setItem('ao:showLXX', JSON.stringify(true))")
                await pg.goto(f"{BASE}{url}")
                await pg.wait_for_selector(sel, timeout=10000)
                # the 1st word (GEN 1:1 ΕΝ in capitals), the 2nd, and in NUM 7:84 the numeral ιβ᾽
                ks = [0, 1]
                if "NUM" in url:
                    toks = await pg.locator(sel).all_inner_texts()
                    ks = [i for i, t in enumerate(toks) if t.strip().rstrip(",.").endswith("᾽")][:2] or [0]
                for k in ks:
                    el = pg.locator(sel).nth(k)
                    toks = await el.evaluate("e => [...e.parentElement.querySelectorAll('.lw')].map(x => x.textContent)")
                    i = await el.evaluate("e => [...e.parentElement.querySelectorAll('.lw')].indexOf(e)")
                    # (worked out from the whole-verse text, not from lxxTapWord, so a slip there shows: the word with
                    # the words either side, then those two taken off again)
                    want = await pg.evaluate("""async ([t, i]) => { const a = await import('./js/audio.js');
                      const three = a.lxxSpeech([t[i - 1], t[i], t[i + 1]].filter(Boolean).join(' ')).split(' ');
                      const mid = three.slice(t[i - 1] ? 1 : 0, t[i + 1] ? -1 : undefined).join(' ').replace(/[,.;·]+$/, '');
                      return __x.conv(mid, 'grc'); }""", [toks, i])
                    await tap_and_check(f"{where} word {toks[i]!r}", level, el, want)
                    await pg.wait_for_selector(".sheet-panel")
                    want_verse = await pg.evaluate("async (t) => { const a = await import('./js/audio.js'); return __x.conv(a.lxxSpeech(t.join(' ')), 'grc'); }", toks)
                    await verse_button(f"{where} word sheet", level, ".sheet .ws-translit .say-btn.with-label", want_verse)
                    await pg.keyboard.press("Escape")
            numeral = await pg.evaluate("async () => { const a = await import('./js/audio.js'); return a.lxxTapWord('ιβ᾽,', 'ἀργυραῖ', 'θυίσκαι').say; }")
            check(f"{level.title()}, Septuagint: a number written with letters is said as its number word (ιβ᾽ → δώδεκα)", numeral == "δώδεκα", numeral)

            # ---------------- the Letters guide's verses, both languages
            for lang in ("grc", "he"):
                await pg.goto(f"{BASE}#/alphabet/{lang}")
                await pg.wait_for_selector(".ab-verse")
                await pg.wait_for_function("document.querySelectorAll('.ab-verse .ab-verse-t').length > 0", timeout=10000)
                A = json.load(open(f"{ROOT}lessons/alphabet/{lang}.json"))
                pr = A["practice"][0]
                bk, cv = pr["ref"].split(" ")
                c, vv = map(int, cv.split(":"))
                words, lex = await pg.evaluate("async ([l, b, c, v]) => { const x = await __x.verse(l, b, c, v); return [x.words, x.lex]; }", [lang, bk, c, vv])
                name = f"Letters guide ({'Hebrew' if lang == 'he' else 'Greek'}, {pr['ref']})"
                first = pg.locator(".ab-verse").first
                n_words = await first.locator(".say-w").count()
                check(f"{level.title()}, {name}: words that say themselves {'none' if level == 'hard' else 'every word'}",
                      (n_words == 0) if level == "hard" else n_words >= len([w for w in words if w[6:7] != ['k']]) - 1, str(n_words))
                if n_words:
                    want = await pg.evaluate("([l, w, lex]) => __x.word(l, w, lex)", [lang, words[0], lex])
                    await tap_and_check(f"{name} word 1", level, first.locator(".say-w").nth(0), want)
                want_verse = await pg.evaluate("([l, w, lex]) => __x.whole(l, w, lex)", [lang, words, lex])
                await verse_button(name, level, ".ab-verse >> nth=0 >> .say-btn", want_verse)

            # ---------------- Listen buttons outside verses stay at every level
            await pg.goto(f"{BASE}#/words/G3056")
            await pg.wait_for_selector(".entry-listen [data-say]", timeout=10000)
            check(f"{level.title()}: the dictionary entry keeps its Listen button", await pg.locator(".entry-listen [data-say]").count() == 1)

        # ---------------- Restored Koine: the same buttons give the Koine voice its own text
        await set_level("medium", "koine")
        await pg.goto(f"{BASE}#/read/JHN/1")
        await pg.wait_for_selector(".v-listen [data-say]")
        await pg.evaluate("window.__spoken = []")
        await pg.locator(".v-listen [data-say]").first.click()
        got = await said()
        book = await pg.evaluate("([l, b]) => __x.book(l, b)", ["grc", "JHN"])
        want = await pg.evaluate("([l, w, lex]) => __x.whole(l, w, lex)", ["grc", book["ch"][0][1][0][1], book["lex"]])
        check("Restored Koine: Listen to verse 1 gives the voice the Koine text (η said ε, no Erasmian respelling)", got == [want] and "ἐν" not in got[0], str(got))
        await set_level("medium", "erasmian")

        # ---------------- the level is kept, and Settings and the Reader's display options agree both ways
        await pg.goto(f"{BASE}#/settings")
        await pg.click("input[name=listenLevel][value=hard]")
        await pg.reload()
        await pg.wait_for_selector("input[name=listenLevel]")
        kept = await pg.is_checked("input[name=listenLevel][value=hard]")
        await pg.goto(f"{BASE}#/read/JHN/3")
        await pg.wait_for_selector(".v .w")
        await pg.click("[data-display]")
        in_reader = await pg.is_checked("input[name=listenLevel][value=hard]")
        await pg.click("input[name=listenLevel][value=easy]")
        await pg.keyboard.press("Escape")
        await pg.wait_for_timeout(200)
        gone = await pg.locator(".v-listen [data-say]").count()
        await pg.goto(f"{BASE}#/settings")
        back = await pg.is_checked("input[name=listenLevel][value=easy]")
        check("The level is kept after a reload, shows the same in the Reader's display options, and a change there applies at once and shows in Settings",
              kept and in_reader and gone == 0 and back, f"{kept} {in_reader} {gone} {back}")
        check("No errors in the page", not errs, "; ".join(errs[:3]))
        await b.close()
    print(f"\n{sum(res)}/{len(res)} passed")
    return all(res)


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(main()) else 1)
