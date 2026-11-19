"""The practice questions in every lesson can be answered one way only, and say nothing that contradicts their answer.

    python3 tools/check_drills.py [--self-test]

  choose:  2+ options, all different (also after removing accents and capitals, so two can't look the same), the
           answer one of them; the explanation names the right option, not a wrong one; the prompt doesn't give the
           answer away (the right option written in the question while no wrong one is)
  match:   left and right sides each all different, so each pair can be matched only one way
  build:   2+ tiles, not already in the right order (the engine shuffles, but a two-tile drill whose order can't be
           wrong is no drill), and the joined tiles appear in the explanation or the lesson
  parse:   every field's answer is one of its options, options all different
  scene/words: no empty Greek/Hebrew, English or pronunciation
(Whether a parse drill's answer matches the Bible's tagging is check_grammar.py's job.)
"""
import glob, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)


def same(s):
    """Two options look the same only if they are the same text (the marks are often the point of the drill)."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(s))).strip()


def fold(s):
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c) and not ("\u0591" <= c <= "\u05c7"))
    return re.sub(r"[\s\-’'.,;:!?“”()]+", " ", s).strip().lower()


def has(text, piece):
    """piece occurs in text as a whole word (short pieces) or anywhere (longer ones), marks and all."""
    t, p = same(text), same(piece)
    if len(p) < 4:
        return re.search(rf"(?<!\w){re.escape(p)}(?![\w\u0300-\u036f\u0591-\u05c7])", t) is not None
    return p in t


def script_only(s, marks=True):
    keep = r"[\u0370-\u03FF\u1F00-\u1FFF\u05D0-\u05EA" + (r"\u0300-\u036F\u0591-\u05C7]" if marks else "]")
    return "".join(re.findall(keep, unicodedata.normalize("NFD", str(s))))


def check_card(c, where):
    out = []
    t = c.get("type")
    if t == "choose":
        opts = c.get("options", [])
        a = c.get("answer")
        if len(opts) < 2:
            out.append("fewer than two options")
        if not isinstance(a, int) or not 0 <= a < len(opts):
            out.append(f"answer {a!r} isn't an option")
            return out
        folded = [same(o) for o in opts]
        if len(set(folded)) != len(folded):
            out.append(f"two options look the same: {opts}")
        right, wrong = opts[a], [o for i, o in enumerate(opts) if i != a]
        ex = c.get("explain", "")
        if ex and any(has(ex, w) and not has(w, right) and not has(right, w) for w in wrong) and not has(ex, right):
            out.append(f"the explanation names a wrong option, not the right one ({right!r}): {ex}")
        p = c.get("prompt", "")
        if has(p, right) and not any(has(p, w) for w in wrong) and not has(right, p):
            out.append(f"the question gives the answer away ({right!r} is in it): {p}")
    elif t == "match":
        pairs = c.get("pairs", [])
        lefts = [same(x[0]) for x in pairs]
        rights = [same(x[1]) for x in pairs]
        if len(set(lefts)) != len(lefts):
            out.append(f"two left-hand items look the same: {[x[0] for x in pairs]}")
        if len(set(rights)) != len(rights):
            out.append(f"two right-hand items look the same, so pairs can be matched two ways: {[x[1] for x in pairs]}")
        if len(pairs) < 2:
            out.append("fewer than two pairs")
    elif t == "build":
        tiles = c.get("tiles", [])
        if len(tiles) < 2:
            out.append("fewer than two tiles")
        joined = (c.get("join", " ")).join(x.strip("-") if c.get("join", " ") == "" else x for x in tiles)
        if len(set(tiles)) == 1 and len(tiles) > 1:
            out.append("every tile is the same")
        ex = c.get("explain", "")
        g = script_only(joined)
        if ex and g and g not in script_only(ex) and script_only(joined, False) not in script_only(ex, False):
            out.append(f"the built answer {joined!r} isn't in the explanation: {ex}")
    elif t == "parse":
        for f in c.get("fields", []):
            if f.get("answer") not in f.get("options", []):
                out.append(f"field {f.get('label')!r}: answer {f.get('answer')!r} isn't an option")
            if len(set(f.get("options", []))) != len(f.get("options", [])):
                out.append(f"field {f.get('label')!r}: two options the same")
    elif t == "scene":
        for k in ("text", "en"):
            if not str(c.get(k, "")).strip():
                out.append(f"scene with no {k}")
    elif t == "words":
        for it in c.get("items", []):
            for k in ("t", "en", "say"):
                if not str(it.get(k, "")).strip():
                    out.append(f"word {it.get('t')!r} with no {k}")
    return [f"{where}: {x}" for x in out]


def cards(lesson):
    for si, st in enumerate(lesson.get("steps", [])):
        for ci, c in enumerate(st.get("cards", [])):
            yield f"step {si + 1} card {ci + 1} ({c.get('type')})", c


def main():
    if "--self-test" in sys.argv:
        planted = [
            ("two options alike", {"type": "choose", "prompt": "?", "options": ["λόγος", "λόγος ", "ἄρτος"], "answer": 0}),
            ("explanation names a wrong option", {"type": "choose", "prompt": "What does βλέπομεν mean?", "options": ["we see", "they see"], "answer": 0, "explain": "-ομεν: they see."}),
            ("question gives the answer away", {"type": "choose", "prompt": "Which is ἀκούουσιν?", "options": ["ἀκούουσιν", "ἀκούομεν"], "answer": 0}),
            ("match two ways", {"type": "match", "pairs": [["-ει", "he"], ["-εις", "he"]]}),
            ("answer not an option", {"type": "parse", "fields": [{"label": "Who?", "options": ["I", "we"], "answer": "you"}]}),
            ("built answer not explained", {"type": "build", "tiles": ["πιστεύ-", "-ομεν"], "join": "", "explain": "λύ + ομεν"}),
        ]
        ok = 0
        for desc, c in planted:
            caught = bool(check_card(c, "planted"))
            print(("caught " if caught else "MISSED ") + desc)
            ok += caught
        print(f"{ok}/{len(planted)} passed")
        sys.exit(0 if ok == len(planted) else 1)
    problems, n = [], 0
    files = [f for f in sorted(glob.glob("lessons/*/*.json")) if re.search(r"/\d+\.json$", f)]
    for f in files:
        lesson = json.load(open(f))
        for where, c in cards(lesson):
            n += 1
            problems += check_card(c, f"{f} {where}")
    print(f"{n} cards checked in {len(files)} lessons")
    for p in problems:
        print("  ", p)
    print(f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
