"""Screenshot comparison: 12 key screens at phone and iPad sizes and the smallest phone at the largest text size, light and dark (72
pictures), compared with the
approved pictures in tools/fixtures/screens/. Catches layouts that break quietly (a shifted bar, text spilling at the
largest size). Run with the local server on :8765:

    python3 tools/test_screens.py            # compare; differences are saved to tools/reports/screens-<time>/
    python3 tools/test_screens.py --approve  # after a deliberate change: look at the new pictures, then approve them

The clock, the seeded progress and the voices are fixed so the pictures only change when the layout does. A small
amount of difference is allowed for rendering noise (anti-aliasing): a picture fails when more than 0.3% of its
pixels differ clearly.
"""
import asyncio, datetime, io, os, sys
import numpy as np
from PIL import Image
from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(__file__))
from crawl_app import SEED, BASE, CHROME

HERE = os.path.dirname(os.path.abspath(__file__))
APPROVED = os.path.join(HERE, "fixtures", "screens")
SCREENS = [
    ("today", "today", ".today-plan"), ("learn", "learn", ".path"), ("letters-greek", "alphabet/grc", ".ab-tile"),
    ("letters-hebrew", "alphabet/he", ".ab-tile"), ("john-1", "read/JHN/1", ".chapter .w"), ("genesis-1", "read/GEN/1", ".chapter .w"),
    ("septuagint-psalm-23", "lxx/PSA/23", ".lxx-text"), ("words", "words", "main h1"), ("logos", "words/G3056", ".entry-lemma"),
    ("review", "review", "main h1"), ("progress", "progress", ".pg-big"), ("lesson", "lesson/grc/grc-4", ".ls-stepbar"),
]
SIZES = [("phone", 390, 844, "normal"), ("ipad", 1180, 820, "normal"), ("small-largest", 320, 700, "largest")]
NOISE = 40        # a channel difference above this counts as a real change
ALLOWED = 0.003   # share of pixels that may differ


def differs(a, b):
    if a.size != b.size:
        return 1.0, None
    x, y = np.asarray(a.convert("RGB"), dtype=np.int16), np.asarray(b.convert("RGB"), dtype=np.int16)
    mask = (np.abs(x - y).max(axis=2) > NOISE)
    return mask.mean(), mask


async def main():
    approve = "--approve" in sys.argv
    os.makedirs(APPROVED, exist_ok=True)
    out = os.path.join(HERE, "reports", "screens-" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M"))
    fails, done = [], 0
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        for scheme in ("light", "dark"):
            for label, w, h, size in SIZES:
                ctx = await b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, service_workers="block",
                                          reduced_motion="reduce")
                pg = await ctx.new_page()
                await pg.clock.install(time=datetime.datetime(2026, 11, 3, 10, 0))
                await pg.goto(f"{BASE}#/settings")
                await pg.evaluate(SEED)
                if size != "normal":
                    await pg.evaluate(f"localStorage.setItem('ao:textSize', JSON.stringify('{size}'))")
                    await pg.reload()
                for name, route, ready in SCREENS:
                    await pg.goto(f"{BASE}#/today")
                    await pg.goto(f"{BASE}#/{route}")
                    await pg.wait_for_selector(ready, timeout=15000)
                    await pg.evaluate("document.fonts.ready")
                    await pg.wait_for_timeout(700)
                    # hide what changes on its own: caret, focus rings, the install tip
                    await pg.add_style_tag(content="*{caret-color:transparent!important;transition:none!important;animation:none!important}"
                                                   ".install-tip{display:none!important}")
                    await pg.evaluate("document.activeElement && document.activeElement.blur()")
                    shot = Image.open(io.BytesIO(await pg.screenshot()))
                    file = f"{name}-{label}-{scheme}.png"
                    path = os.path.join(APPROVED, file)
                    done += 1
                    if approve or not os.path.exists(path):
                        shot.save(path, optimize=True)
                        if not approve:
                            fails.append(f"{file}: no approved picture yet (saved this one: look at it, then run --approve)")
                        continue
                    share, mask = differs(Image.open(path), shot)
                    if share > ALLOWED:
                        os.makedirs(out, exist_ok=True)
                        shot.save(os.path.join(out, file.replace(".png", "-now.png")))
                        if mask is not None:
                            marked = np.asarray(shot.convert("RGB")).copy()
                            marked[mask] = [255, 0, 160]
                            Image.fromarray(marked).save(os.path.join(out, file.replace(".png", "-changes.png")))
                        fails.append(f"{file}: {share:.1%} of the picture changed (see {os.path.relpath(out, HERE)})")
                await ctx.close()
        await b.close()
    if approve:
        print(f"Approved {done} pictures in {os.path.relpath(APPROVED, os.path.dirname(HERE))}")
        return
    for f in fails:
        print("FAIL " + f)
    print(f"\n{done - len(fails)}/{done} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    asyncio.run(main())
