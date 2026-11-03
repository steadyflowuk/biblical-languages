"""Rebuild and compare: build every data file again from the sources, in a spare copy of the app, and compare it file
by file with data/. Catches data edited by hand (the once hand-patched Today file) or left stale after a build script
changed. Exit code 0 = identical.

    python3 tools/check_rebuild.py            # sources already fetched (SOURCES, default /home/claude/src)
    python3 tools/check_rebuild.py --fresh    # fetch the sources again first: also shows changes upstream (e.g. a
                                              # new dated BSB file), which then need a deliberate rebuild
"""
import filecmp, json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.environ.get("SOURCES", "/home/claude/src")


def main():
    fresh = "--fresh" in sys.argv
    work = tempfile.mkdtemp(prefix="aleph-rebuild-")
    src = SRC
    if fresh:
        src = os.path.join(work, "src")
        os.makedirs(src)
        print(f"Fetching the sources again into {src} …")
        subprocess.run(["bash", os.path.join(ROOT, "tools", "fetch_sources.sh"), src], check=True)
    copy = os.path.join(work, "app")
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git", "reports", "__pycache__"))
    shutil.rmtree(os.path.join(copy, "data"))  # build from nothing, so a file the build no longer makes shows up
    print(f"Rebuilding in {copy} from {src} …")
    p = subprocess.run([sys.executable, "tools/build_data.py", src], cwd=copy, capture_output=True, text=True)
    if p.returncode:
        print(p.stdout[-2000:], p.stderr[-2000:])
        print("FAIL: the build itself failed")
        sys.exit(1)

    old, new = os.path.join(ROOT, "data"), os.path.join(copy, "data")
    listing = lambda base: {os.path.relpath(os.path.join(d, f), base) for d, _, fs in os.walk(base) for f in fs}
    a, b = listing(old), listing(new)
    missing, extra = sorted(a - b), sorted(b - a)
    changed = []
    for rel in sorted(a & b):
        if filecmp.cmp(os.path.join(old, rel), os.path.join(new, rel), shallow=False):
            continue
        if rel.endswith(".json"):
            try:
                if json.load(open(os.path.join(old, rel), encoding="utf-8")) == json.load(open(os.path.join(new, rel), encoding="utf-8")):
                    continue  # same content, written differently
            except ValueError:
                pass
        changed.append(rel)
    total = len(a | b)
    print(f"{total} data files compared")
    for label, items in (("Only in data/ (not made by the build)", missing), ("Made by the build but not in data/", extra),
                         ("Different from a fresh build", changed)):
        if items:
            print(f"\n{label} ({len(items)}):")
            for x in items[:40]:
                print("  - " + x)
    bad = len(missing) + len(extra) + len(changed)
    print(f"\n{'All checks passed' if not bad else f'{bad} problems'}")
    shutil.rmtree(work, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
