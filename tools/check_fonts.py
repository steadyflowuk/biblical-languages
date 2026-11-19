"""Every character the app can show is in the font that shows it.

    python3 tools/check_fonts.py              # all data, lessons, guides, screens' text; then drawn in Chromium
    python3 tools/check_fonts.py --static     # the fonts' character lists only (no browser)
    python3 tools/check_fonts.py --self-test  # a planted character the fonts lack is caught

The fonts are subsets (assets/fonts, made small on purpose). A character missing from the subset is drawn from some
other font on the phone, or as an empty box: a Greek accent from a different typeface, a Hebrew mark in the wrong
place, a ⟦ in a system font. Which font draws what (css/app.css):
  Greek text (New Testament, Septuagint, Greek headwords)   → Gentium, then the phone's fonts
  Hebrew text                                               → Noto Serif Hebrew, then Gentium ([ ] |)
  BSB English                                               → Gentium, then Noto Serif Hebrew (Ps 119's letters)
  everything else (screens, glosses, definitions, lessons)  → Atkinson, then Gentium, then Noto Serif Hebrew
Characters the app never shows (the voice's private marks U+2060, U+05C4/5 in voice text, line breaks) are ignored.
"""
import glob, json, os, re, sys, unicodedata
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
FONTS = {name: set(TTFont(f"assets/fonts/{f}").getBestCmap()) for name, f in (
    ("atkinson", "atkinson-regular.woff"), ("atkinson-bold", "atkinson-bold.woff"), ("gentium", "gentium-plus-regular.woff"),
    ("gentium-bold", "gentium-plus-bold.woff"), ("gentium-italic", "gentium-plus-italic.woff"), ("hebrew", "noto-serif-hebrew.woff"))}
UI = FONTS["atkinson"] | FONTS["gentium"] | FONTS["hebrew"]
IGNORE = {0x0A, 0x0D, 0x09, 0x2060, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0xFEFF, 0x00AD,
          0x0001, 0x00B6, 0x00AC}  # ¶ ¬ are paragraph signals in the data, never shown


def is_greek(c):
    o = ord(c)
    return 0x0370 <= o <= 0x03FF or 0x1F00 <= o <= 0x1FFF


def is_hebrew(c):
    o = ord(c)
    return 0x0590 <= o <= 0x05FF or 0xFB1D <= o <= 0xFB4F


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            yield from strings(k)
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


def collect():
    """{context: {char: example}} for every place text comes from."""
    ctx = {"greek": {}, "hebrew": {}, "scripture": {}, "ui": {}}

    def add(where, text, src):
        new = set(text).difference(ctx[where])
        for ch in new:
            if ord(ch) in IGNORE or ord(ch) < 0x20:
                continue
            ctx[where][ch] = f"{src}: {text[:60]}"

    for f in sorted(glob.glob("data/gnt/*.json")):
        d = json.load(open(f))
        for ch, vs in d["ch"]:
            for it in vs:
                for w in it[1]:
                    for i in (0, 5, 6):
                        if len(w) > i and isinstance(w[i], str):
                            add("greek", w[i], f"{d['id']} {ch}:{it[0]}")
                    add("ui", w[1] + w[2], f"{d['id']} {ch}:{it[0]} gloss")
        for v in d["lex"].values():
            add("greek", v[0], "Greek headword")
            add("ui", " ".join(v[1:]), "Greek headword gloss")
    for f in sorted(glob.glob("data/hot/*.json")):
        d = json.load(open(f))
        for ch, vs in d["ch"]:
            for it in vs:
                for w in it[1]:
                    for i in (0, 5, 7):
                        if len(w) > i and isinstance(w[i], str):
                            add("hebrew", w[i].replace("/", ""), f"{d['id']} {ch}:{it[0]}")
                    add("ui", w[1] + " " + w[2], f"{d['id']} {ch}:{it[0]} gloss")
        for v in d["lex"].values():
            add("hebrew", v[0], "Hebrew headword")
            add("ui", " ".join(str(x) for x in v[1:]), "Hebrew headword gloss")
    for f in sorted(glob.glob("data/lxx/text/*.json")):
        for s in strings(json.load(open(f))):
            add("greek", s, os.path.basename(f))
    for f in sorted(glob.glob("data/bsb/*.json")):
        for s in strings(json.load(open(f))):
            add("scripture", s, os.path.basename(f))
    for f in sorted(glob.glob("data/lex/*/*.json")) + sorted(glob.glob("data/lex/*.json")) + sorted(glob.glob("data/morph/*.json")) \
            + sorted(glob.glob("data/decks/*.json")) + ["data/books.json", "data/votd.json"]:
        for s in strings(json.load(open(f))):
            add("ui", re.sub(r"<[^>]+>", "", s), f)
    for f in sorted(glob.glob("lessons/**/*.json", recursive=True)):
        for s in strings(json.load(open(f))):
            add("ui", s, f)
    for f in sorted(glob.glob("js/*.js")) + ["index.html", "manifest.webmanifest"]:
        text = open(f, encoding="utf-8").read()
        # every character of the file: non-ASCII characters in code are in strings (or in regexes, harmlessly)
        add("ui", re.sub(r"<[^>]+>", " ", text) if f.endswith(".html") else text, f)
    return ctx


# Emoji and the screens' icon symbols are drawn by the phone's own fonts on purpose. An emoji newer than Unicode 13
# (iOS 14.2) shows as an empty box on an iPhone that isn't up to date, so those fail.
def phone_font(o):
    return (0x1F000 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF or 0x2190 <= o <= 0x21FF
            or 0x2900 <= o <= 0x297F or 0x25A0 <= o <= 0x25FF or o in (0xFE0F, 0x200D, 0x20E3))


NEW_EMOJI = [(0x1F979, 0x1F979), (0x1F7F0, 0x1F7F0), (0x1F6DC, 0x1F6DF), (0x1FA75, 0x1FA7C), (0x1FA87, 0x1FA88),
             (0x1FAA9, 0x1FAAF), (0x1FAB7, 0x1FABF), (0x1FAC3, 0x1FACF), (0x1FAD7, 0x1FADF), (0x1FAE0, 0x1FAFF)]


def problems(ctx):
    out = []
    for where, chars in ctx.items():
        for ch, src in sorted(chars.items()):
            o = ord(ch)
            if unicodedata.category(ch) == "Cn" and where == "ui" and src.startswith("js/"):
                continue  # the end of a range in a regular expression (\u1fff), not text
            if phone_font(o):
                if any(a <= o <= b for a, b in NEW_EMOJI):
                    out.append(f"{ch} U+{o:04X} {unicodedata.name(ch, '')}: an emoji newer than iOS 14.2 knows (Unicode 14+) — {src}")
                continue
            name = unicodedata.name(ch, f"U+{o:04X}")
            if is_greek(ch) or (0x0300 <= o <= 0x036F and where == "greek"):
                font, need = "Gentium", FONTS["gentium"]
                if o not in FONTS["gentium-bold"] and where == "ui":
                    out.append(f"{ch} U+{o:04X} {name}: not in Gentium bold — {src}")
            elif is_hebrew(ch):
                font, need = "Noto Serif Hebrew", FONTS["hebrew"]
                if where == "greek":
                    out.append(f"{ch} U+{o:04X} {name}: Hebrew in Greek text (the Greek fonts have no Hebrew) — {src}")
            elif where == "hebrew":  # Hebrew Serif, then Gentium (css --font-hebrew)
                font, need = "Noto Serif Hebrew or Gentium", FONTS["hebrew"] | FONTS["gentium"]
            elif where in ("greek", "scripture"):
                font, need = "Gentium", FONTS["gentium"]
            else:
                font, need = "Atkinson/Gentium/Noto Serif Hebrew", UI
            if o not in need:
                out.append(f"{ch} U+{o:04X} {name}: not in {font} ({where}) — {src}")
    return out


def rendered(ctx):
    """In Chromium with the app's own CSS, each character in its own element: which font actually drew it."""
    import asyncio, html
    from playwright.async_api import async_playwright
    style = {"greek": 'lang="grc" style="font-family:var(--font-greek)"', "hebrew": 'lang="he" style="font-family:var(--font-hebrew)"',
             "scripture": 'lang="en" style="font-family:var(--font-scripture)"', "ui": 'lang="en" style="font-family:var(--font-ui)"'}
    items = [(w, ch) for w, chars in ctx.items() for ch in sorted(chars) if not phone_font(ord(ch)) and not ch.isspace()
             and unicodedata.category(ch) != "Cn" and not (0x0300 <= ord(ch) <= 0x036F) and not (0x0591 <= ord(ch) <= 0x05C7 and unicodedata.category(ch) == "Mn")]
    body = "".join(f'<p id="c{i}" {style[w]}>{html.escape(ch)}</p>' for i, (w, ch) in enumerate(items))
    page = f'<!DOCTYPE html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/css/app.css"></head><body>{body}</body></html>'
    ours = {"Atkinson Hyperlegible", "Gentium Plus", "Noto Serif Hebrew"}
    out = []

    async def go():
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1243/chrome-linux64/chrome")
            pg = await b.new_page()
            await pg.route("**/__fonts.html", lambda r: r.fulfill(body=page, content_type="text/html; charset=utf-8"))
            await pg.goto("http://localhost:8765/__fonts.html")
            await pg.evaluate("document.fonts.ready")
            await pg.wait_for_timeout(500)
            cdp = await pg.context.new_cdp_session(pg)
            await cdp.send("DOM.enable")
            await cdp.send("CSS.enable")
            doc = await cdp.send("DOM.getDocument", {"depth": -1})
            for i, (w, ch) in enumerate(items):
                n = await cdp.send("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": f"#c{i}"})
                fonts = {f["familyName"] for f in (await cdp.send("CSS.getPlatformFontsForNode", {"nodeId": n["nodeId"]}))["fonts"]}
                if fonts - ours:
                    out.append(f"{ch} U+{ord(ch):04X} ({w}) drawn with {', '.join(sorted(fonts - ours))} — {ctx[w][ch]}")
            await b.close()
    asyncio.run(go())
    return len(items), out


def main():
    ctx = collect()
    if "--self-test" in sys.argv:
        ok = 0
        planted = (("greek", "\u2c80", "a Coptic letter in Greek text"), ("hebrew", "\u05c8", "an unknown Hebrew mark"),
                   ("ui", "\U0001FAF5", "an emoji too new for older iPhones"), ("scripture", "\u0400", "a Cyrillic letter in the BSB"))
        for where, ch, desc in planted:
            test = {k: {} for k in ctx}
            test[where] = {ch: "planted"}
            caught = bool(problems(test))
            print(("caught " if caught else "MISSED ") + desc)
            ok += caught
        print(f"{ok}/{len(planted)} passed")
        sys.exit(0 if ok == len(planted) else 1)
    out = problems(ctx)
    if "--static" not in sys.argv:  # and in a real browser with the app's CSS (needs the server on :8765)
        n, more = rendered(ctx)
        print(f"{n} characters drawn one by one in Chromium with the app's fonts and CSS")
        out += more
    total = sum(len(v) for v in ctx.values())
    print(f"{total:,} distinct characters checked across {len(ctx)} kinds of text "
          f"({', '.join(f'{k} {len(v)}' for k, v in ctx.items())})")
    for p in out:
        print("  ", p)
    print(f"{len(out)} problems")
    sys.exit(1 if out else 0)


if __name__ == "__main__":
    main()
