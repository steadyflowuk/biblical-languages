"""Accessibility check: axe-core (tools/vendor/axe.min.js, MPL-2.0; used here only, never shipped) on every main screen
and an open word sheet, at phone and iPad sizes, light and dark. Serious and critical issues fail; moderate and minor
ones are listed. Run with the local server on :8765:  python3 tools/test_a11y.py

Finds only what can be measured (names, labels, contrast, roles); VoiceOver on a real device is still the real test.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(__file__))
from crawl_app import START, SEED, BASE, CHROME  # the same screens and seeded progress as the crawl

AXE = open(os.path.join(os.path.dirname(__file__), "vendor", "axe.min.js"), encoding="utf-8").read()
SIZES = [("phone", 390, 844), ("iPad", 1180, 820)]
# Rules we decide on knowingly (each with its reason); everything else counts
SKIP = {
    "region": "the Reader's word-by-word text is one landmark; axe asks for every block to sit in one",
}
RUN = """async () => {
  const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
                                      resultTypes: ['violations'] });
  return r.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help,
    nodes: v.nodes.slice(0, 3).map((n) => n.target.join(' ') + (n.failureSummary ? ' — ' + n.failureSummary.split('\\n').slice(1, 2).join('') : '')),
    count: v.nodes.length }));
}"""


async def main():
    fails, notes, pages = [], [], 0
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        for scheme in ("light", "dark"):
            for label, w, h in SIZES:
                ctx = await b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, service_workers="block")
                pg = await ctx.new_page()
                await pg.goto(f"{BASE}#/settings")
                await pg.evaluate(SEED)
                targets = [(r, None) for r in START] + [("read/JHN/1", "sheet"), ("read/GEN/1", "sheet"), ("lesson/grc/grc-4", "practise")]
                for route, extra in targets:
                    await pg.goto(f"{BASE}#/today")
                    await pg.goto(f"{BASE}#/{route}")
                    try:
                        await pg.wait_for_function("document.querySelector('main h1, main .ls-stepbar, main .chapter, main .lxx-text, main .entry-lemma')", timeout=15000)
                    except Exception:
                        fails.append(f"{scheme} {label} #{route}: nothing drew")
                        continue
                    await pg.wait_for_timeout(600)
                    where = f"#/{route}"
                    if extra == "sheet":
                        await pg.locator(".chapter .w").first.click()
                        await pg.wait_for_selector(".sheet-panel", timeout=5000)
                        await pg.wait_for_timeout(400)
                        where += " (word sheet)"
                    elif extra == "practise":
                        for _ in range(12):  # Continue through the Hear and Notice steps to the first drill
                            if await pg.locator(".ls-option").count():
                                break
                            btn = pg.locator("main [data-next]")
                            if not await btn.count():
                                break
                            await btn.first.click()
                            await pg.wait_for_timeout(250)
                        where += " (a drill)"
                    await pg.add_script_tag(content=AXE) if not await pg.evaluate("!!window.axe") else None
                    found = await pg.evaluate(RUN)
                    pages += 1
                    for v in found:
                        if v["id"] in SKIP:
                            continue
                        line = f"{scheme} {label} {where}: [{v['impact']}] {v['id']} — {v['help']} ({v['count']}×) {v['nodes'][:2]}"
                        (fails if v["impact"] in ("serious", "critical") else notes).append(line)
                await ctx.close()
        await b.close()
    print(f"{pages} pages checked with axe-core")
    if notes:
        print(f"\nWorth a look ({len(notes)}):")
        for n in notes[:40]:
            print("  - " + n)
    if fails:
        print(f"\nFAIL: {len(fails)} serious or critical")
        for f in fails[:60]:
            print("  - " + f)
    print(f"\n{'All checks passed' if not fails else f'{len(fails)} problems'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    asyncio.run(main())
