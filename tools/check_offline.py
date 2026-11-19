"""Everything the app asks the server for can be had offline.

    python3 tools/check_offline.py        # server on :8765

Two lists decide what works without a connection: sw.js SHELL_FILES (saved when the app is installed or updated) and
data/files.json (what Settings › Offline › "Save it all" saves; Bible books are also saved as they are opened).
  1. every file in SHELL_FILES exists; every font, icon and file the page, CSS, manifest or code names is in it
  2. data/files.json lists every file in data/ (and nothing that isn't there), with its true size
  3. the app is opened on every kind of screen (Today, Learn, each lesson, Letters, Read in Greek and Hebrew, the
     Septuagint, Words and an entry, Review, Progress, Videos, Settings, Check this device) and every request it makes
     to the app's own server is checked: in SHELL_FILES, or in data/files.json — else that screen would break offline
"""
import asyncio, glob, json, os, re, sys
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
BASE = "http://localhost:8765/"


def shell_files():
    sw = open("sw.js", encoding="utf-8").read()
    block = sw[sw.index("SHELL_FILES"):sw.index("];", sw.index("SHELL_FILES"))]
    return set(re.findall(r'"([^"]+)"', block))


def static_checks(shell):
    bad = []
    for f in shell:
        if f != "./" and not os.path.exists(f):
            bad.append(f"SHELL_FILES lists {f}, which doesn't exist")
    named = set()
    css = open("css/app.css", encoding="utf-8").read()
    named |= {os.path.normpath(os.path.join("css", u)) for u in re.findall(r'url\("?([^")]+)"?\)', css) if not u.startswith("data:")}
    man = json.load(open("manifest.webmanifest"))
    named |= {os.path.normpath(i["src"]) for i in man.get("icons", [])}
    html = open("index.html", encoding="utf-8").read()
    named |= {os.path.normpath(u) for u in re.findall(r'(?:href|src)="([^"#:]+)"', html) if not u.startswith("http")}
    for f in glob.glob("js/*.js") + glob.glob("js/vendor/*.js"):
        for u in re.findall(r'from\s+"(\.[^"]+)"|import\(\s*"(\.[^"]+)"', open(f, encoding="utf-8").read()):
            u = u[0] or u[1]
            named.add(os.path.normpath(os.path.join(os.path.dirname(f), u)))
    for f in sorted(named):
        if f not in shell and f != ".":
            bad.append(f"{f} is used by the app but isn't in SHELL_FILES")
    files = json.load(open("data/files.json"))
    listed = {f[0] if isinstance(f, list) else f for f in files["files"]}
    sizes = {f[0]: f[1] for f in files["files"] if isinstance(f, list) and len(f) > 1}
    on_disk = {p for p in glob.glob("data/**/*.json", recursive=True) if p != "data/files.json"} | \
              {p for p in glob.glob("data/**/*", recursive=True) if os.path.isfile(p) and not p.endswith(".json") and "README" not in p and "LICENSE" not in p}
    for p in sorted(on_disk - listed - shell):
        bad.append(f"{p} isn't in data/files.json (Save it all wouldn't save it)")
    for p in sorted(listed - on_disk):
        bad.append(f"data/files.json lists {p}, which doesn't exist")
    for p, n in sizes.items():
        if os.path.exists(p) and os.path.getsize(p) != n:
            bad.append(f"data/files.json gives {p} {n} bytes; it has {os.path.getsize(p)}")
    return bad, listed


ROUTES = ["#/", "#/learn", "#/alphabet/grc", "#/alphabet/he", "#/read/JHN/1", "#/read/GEN/1", "#/read/PSA/23",
          "#/lxx/PSA/22", "#/words", "#/words/G3056", "#/words/H0430G", "#/review", "#/progress", "#/videos",
          "#/settings", "#/check"]


async def visit(shell, listed):
    from playwright.async_api import async_playwright
    seen = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1243/chrome-linux64/chrome")
        ctx = await b.new_context(service_workers="block", viewport={"width": 390, "height": 844})
        pg = await ctx.new_page()
        pg.on("request", lambda r: seen.setdefault(urlparse(r.url).path.lstrip("/") or "./", pg.url.split("#")[-1]) if r.url.startswith(BASE) else None)
        lessons = json.load(open("lessons/index.json"))
        routes = ROUTES + [f"#/lesson/{lang}/{x['id']}" for lang in ("grc", "he") for x in lessons[lang] if x.get("file")]
        await pg.goto(BASE)
        for r in routes:
            await pg.evaluate(f"location.hash = '{r}'")
            await pg.wait_for_timeout(900)
        await pg.wait_for_timeout(9000)  # the essentials saved 8 s after opening (js/offline.js)
        await b.close()
    bad = []
    for path, where in sorted(seen.items()):
        if path in shell or path in listed or path in ("./", "data/files.json") or path.startswith("__"):
            continue
        bad.append(f"{path} (asked for on #{where}) is in neither SHELL_FILES nor data/files.json")
    return len(routes), len(seen), bad


def main():
    shell = shell_files()
    if "--self-test" in sys.argv:  # a code file and a font dropped from SHELL_FILES are caught
        ok = 0
        for drop in ("js/votd.js", "assets/fonts/gentium-plus-regular.woff"):
            caught = any(drop in b for b in static_checks(shell - {drop})[0])
            print(("caught " if caught else "MISSED ") + f"{drop} left out of SHELL_FILES")
            ok += caught
        print(f"{ok}/2 passed")
        sys.exit(0 if ok == 2 else 1)
    bad, listed = static_checks(shell)
    n_routes, n_req, more = asyncio.run(visit(shell, listed))
    bad += more
    print(f"{len(shell)} shell files and {len(listed)} data files checked; {n_routes} screens opened, {n_req} files asked for")
    for x in bad:
        print("  ", x)
    print(f"{len(bad)} problems")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
