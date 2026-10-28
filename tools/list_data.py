"""Write data/files.json: every data file the app can load, with sizes, so Settings › "Save it all for offline use"
knows what to fetch. Run after any data rebuild (build_data.py calls it at the end):  python3 tools/list_data.py"""
import json, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data")
# the files the app never fetches on its own (this list itself)
SKIP = {"files.json"}


def main():
    files = []
    for dirpath, _, names in os.walk(DATA):
        for n in sorted(names):
            if not n.endswith(".json") or n in SKIP:
                continue
            p = os.path.join(dirpath, n)
            files.append([os.path.relpath(p, ROOT).replace(os.sep, "/"), os.path.getsize(p)])
    files.sort()
    with open(os.path.join(DATA, "files.json"), "w", encoding="utf-8") as f:
        json.dump({"files": files, "bytes": sum(s for _, s in files)}, f, separators=(",", ":"))
    print(f"data/files.json: {len(files)} files, {sum(s for _, s in files) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
