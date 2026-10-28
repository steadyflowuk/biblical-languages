"""Suggest Bible verses (New Testament for grc-…, Old Testament for he-…) for a lesson's Read step: verses made (mostly) of words the learner knows.

python3 tools/find_verses.py <lesson id> [extra keys…] [--min 4] [--max 14] [--top 20]

Known words = the review words of every lesson in that language up to and including <lesson id> (from lessons/index.json order)
plus any extra lexicon keys given (e.g. G3588 for the article). Prints verses ranked by the share of known words,
then by length; unknown words are shown in brackets.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = [a for a in sys.argv[1:] if not a.startswith("--")]
opt = {a.split("=")[0][2:]: int(a.split("=")[1]) for a in sys.argv[1:] if a.startswith("--") and "=" in a}
lesson_id, extra = args[0], args[1:]
num = lambda k: re.sub(r"^([GH])0*(\d+).*$", r"\1\2", k)
index = json.load(open(os.path.join(ROOT, "lessons", "index.json")))
known = set(num(k) for k in extra)
lang = "he" if lesson_id.startswith("he") else "grc"
for e in index[lang]:
    if e.get("file"):
        L = json.load(open(os.path.join(ROOT, e["file"])))
        for s in L["steps"]:
            for c in s["cards"]:
                for it in c.get("items", []):
                    known.add(num(it["k"]))
    if e["id"] == lesson_id:
        break
books = [b for b in json.load(open(os.path.join(ROOT, "data", "books.json"))) if b["lang"] == lang]


def main_key(w):
    """Greek: the key; Hebrew: the main part in {braces} (prefixes and suffixes like the article are taught as such)."""
    if lang == "grc":
        return num(w[3])
    m = re.search(r"\{(H\d+[A-Z]?)", str(w[3]))
    return num(m.group(1)) if m else num(str(w[3]).split("/")[0])
out = []
for b in books:
    d = json.load(open(os.path.join(ROOT, "data", "gnt" if lang == "grc" else "hot", f"{b['id']}.json")))
    for c, vs in d["ch"]:
        for v in vs:
            words = v[1]
            n = len(words)
            if not opt.get("min", 4) <= n <= opt.get("max", 14):
                continue
            k = sum(1 for w in words if main_key(w) in known)
            text = " ".join(w[0].replace("/", "") if main_key(w) in known else f"[{w[0].replace('/', '')}]" for w in words)
            out.append((k / n, -n, f"{b['id']} {c}:{v[0]}", k, n, text))
out.sort(reverse=True)
print(f"{len(known)} known words")
for r, _, ref, k, n, text in out[:opt.get("top", 20)]:
    print(f"{ref:12} {k}/{n}  {text}")
