"""Build the frequency decks for the review trainer (Session 9).

python3 tools/build_decks.py          (reads data/lex and data/hot; writes data/decks/greek.json and hebrew.json)

A deck is every word used at least MIN times (319 Greek words, the classic "50 or more" list; about 700 Hebrew),
most common first. Senses the lexicon splits (κύριος, בֵּן) become one card: the commonest sense's key, the counts
added, the general part of its gloss. Prefix/suffix labels (H9001+) and Aramaic-only words are left out.

  { "lang": "grc", "min": 50, "words": [[key, lemma, gloss, count, say]], "alias": {other sense key: card key} }

Greek "say" is empty: the app respells Greek itself (js/sound.js greekSay). Hebrew "say" comes from the commonest
transliteration of the word on its own in the text (TAHOT marks the stressed syllable), e.g. "ME-lekh".
"""
import glob, json, os, re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
MIN = 50
CANT = re.compile("[֑-ֽ֯]")  # cantillation, ole (stress mark in some lemmas), meteg


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def entries(letter):
    out = {}
    for f in glob.glob(os.path.join(DATA, "lex", letter, "*.json")):
        out.update(load(f))
    return out


def gloss_text(gloss):
    """Same rule as glossText in js/dictionary.js: "to love: lover" → "to love (lover)" unless one contains the other."""
    general, _, specific = str(gloss or "").partition(": ")
    if not specific:
        return general
    g, s = general.lower().removeprefix("to "), specific.lower().removeprefix("to ")
    return general if g == s or s in g else f"{general} ({specific})"


GLOSS_FIX = {"[Obj.]": "(marks the object)", "[obj.]": "(marks the object)"}
# Our own wording where the short lexicon gloss would mislead on a flashcard (checked against the full entries).
OVERRIDES = {
    "grc": {
        "ὁ": "the", "αὐτός": "he, she, it; self, same", "δέ": "and, but", "ἐν": "in, on, among", "εἰς": "into, to",
        "οὐ": "not", "οὗτος": "this", "ὅτι": "that, because", "ἐκ": "out of, from", "ἐπί": "on, upon, to, against",
        "ἐγώ": "I", "ἔχω": "to have", "πρός": "to, towards, with", "γίνομαι": "to become, happen, be",
        "ἵνα": "so that", "διά": "through; because of", "ἔρχομαι": "to come, go", "ποιέω": "to do, make",
        "τίς": "who? what?", "ἄνθρωπος": "person, human being", "τις": "someone, something", "ὡς": "as, like",
        "οὖν": "so, therefore", "μετά": "with; after", "εἴδω": "to see", "πολύς": "much, many", "ὑπό": "by; under",
        "ἑαυτοῦ": "himself, herself, itself", "λαμβάνω": "to take, receive", "πιστεύω": "to believe, trust",
        "θέλω": "to want, wish", "οὕτως": "so, in this way", "παρά": "from; beside, with", "μέν": "(on the one hand)",
        "ἄν": "(would; -ever)", "ἔθνος": "nation; Gentiles", "ὑπέρ": "for, on behalf of; above",
        "πορεύω": "to go, travel", "ἐγείρω": "to raise, rise", "ἀφίημι": "to let go, forgive", "λαός": "people",
        "εἶναι": "to be (εἰμί)", "αἰών": "age, eternity", "ἀρχιερεύς": "high priest", "μέλλω": "to be about to",
        "παρακαλέω": "to urge, comfort", "πῶς": "how?", "δεῖ": "it is necessary", "ἴδιος": "one's own",
        "ὅσος": "as much as, as many as", "μηδείς": "no one, nothing", "πίπτω": "to fall", "ἄρχω": "to rule; begin",
        "προσέρχομαι": "to come to, approach", "ἀπολλύω": "to destroy, lose", "πληρόω": "to fill, fulfil",
        "ὥστε": "so that", "ἐκκλησία": "church, assembly", "καιρός": "time, season", "ῥῆμα": "word, saying",
        "τρεῖς": "three", "φημί": "to say", "ὑπάρχω": "to be, exist", "ἀσπάζομαι": "to greet", "θεωρέω": "to see, watch",
        "μέσος": "middle", "τοιοῦτος": "such", "εὐαγγελίζομαι": "to proclaim good news", "οὐχί": "not (surely not?)",
        "ποτέ": "once, ever", "ὅπως": "so that; how", "ἔσχατος": "last", "γραφή": "writing, Scripture",
        "κακός": "bad, evil", "ἔξω": "outside", "κηρύσσω": "to preach, proclaim", "θέλημα": "will",
        "ὅστις": "whoever, who", "μηδέ": "and not, nor", "ἀποκρίνω": "to answer", "εὑρίσκω": "to find",
        "ψυχή": "soul, life", "κύριος": "lord, master; the Lord", "δύναμαι": "to be able", "οὐδείς": "no one, nothing", "εἰ": "if",
    },
    "he": {
        "יְהֹוָה": "the LORD (YHWH)", "יְהֹוִה": "GOD (YHWH)", "עַל": "on, over, against", "אֶל": "to, towards",
        "כֹּל": "all, every", "אֲשֶׁר": "who, which, that", "כִּי": "for, because, that", "אֶרֶץ": "land, earth",
        "הוּא": "he, it", "עַד": "until, as far as", "יָשַׁב": "to sit, live", "עָלָה": "to go up",
        "הִנֵּה": "look! (behold)", "אַיִן": "there is not", "אַתָּה": "you (to a man)", "כֵּן": "so, thus",
        "אַל": "do not", "נָשָׂא": "to lift, carry", "הֵמָּה": "they", "טוֹב": "good", "כַּאֲשֶׁר": "as, when",
        "תַּחַת": "under; instead of", "נָכָה": "to strike", "צָבָא": "army, host", "פֶּה": "mouth",
        "רָעָה": "to shepherd", "עוֹלָם": "forever; long ago", "אַף": "nose; anger", "בַּיִן": "between",
        "נְאֻם": "declares (the LORD)", "רַע": "bad, evil", "עֶבֶד": "servant, slave", "פָּנֶה": "face",
        "בּוֹא": "to come, go in", "מִן־": "from", "דָבַר": "to speak", "עַיִן": "eye; spring", "אֱנוֹשׁ": "human, mankind",
        "אָדָם": "man, mankind", "גּוֹי": "nation", "שַׂר": "official, ruler", "תָּוֶךְ": "middle",
    },
}
SAY_FIX = {"he": {"יְהֹוָה": "a-do-NAI", "יְהֹוִה": "e-lo-HIM"}}  # read aloud as Adonai / Elohim, as is customary


def he_plain(s):
    return CANT.sub("", s or "")


def mark_key(s):
    """Hebrew compared with each letter's marks sorted (sources order dagesh and vowels differently); never NFC."""
    out, marks = [], []
    for ch in he_plain(s):
        if "\u05b0" <= ch <= "\u05c7":
            marks.append(ch)
        else:
            out.append("".join(sorted(marks)) + ch)
            marks = []
    return "".join(out) + "".join(sorted(marks))


def he_say(tr):
    """TAHOT "'E.lo.Him" → "e-lo-HIM": the last capitalised syllable carries the stress (a capital E at the start
    can be a hataf vowel); aleph/ayin apostrophes and maqaf hyphens dropped."""
    tr = tr.strip().rstrip("-").replace("'", "").replace("’", "")
    syl = [x for x in tr.split(".") if x]
    caps = [i for i, x in enumerate(syl) if re.search("[A-Z]", x)]
    out = [x.lower() for x in syl]
    if len(out) > 1 and caps:
        out[caps[-1]] = out[caps[-1]].upper()
    return "-".join(out)


def he_say_guess(translit, lemma):
    """No clean occurrence: the lexicon's syllables, stress on the last unless the lemma marks it earlier (ole ֫) or
    it is a two-segol noun (מֶלֶךְ) or ends in a furtive patah (רוּחַ)."""
    syl = [x for x in (translit or "").replace("'", "").split(".") if x]
    if not syl:
        return ""
    k = len(syl) - 1
    vowels = re.findall("[ְ-ֻ]", lemma)
    if len(syl) > 1 and ("֫" in lemma or vowels[-2:] == ["ֶ", "ֶ"] or re.search("[חעה]ַ$", he_plain(lemma))):
        k -= 1
    return "-".join(x.upper() if i == k and len(syl) > 1 else x.lower() for i, x in enumerate(syl))


def hebrew_says():
    """{key: Counter(transliteration)} for words standing alone (no prefix or suffix) in the Hebrew text."""
    seen = defaultdict(Counter)
    for f in glob.glob(os.path.join(DATA, "hot", "*.json")):
        for _, vs in load(f)["ch"]:
            for v in vs:
                for w in v[1]:
                    if "/" in w[0] or "/" in str(w[3]):
                        continue
                    m = re.match(r"\{(H\d+[A-Z]?)\}", str(w[3]))
                    if m:
                        seen[m.group(1)][(he_plain(w[0]), w[1])] += 1
    return seen


def build(lang):
    letter, name = ("G", "greek") if lang == "grc" else ("H", "hebrew")
    index = load(os.path.join(DATA, "lex", f"{name}-index.json"))
    E = entries(letter)
    groups = defaultdict(list)
    for r in index:
        if len(r) < 5 or not r[4]:
            continue
        key, lemma, translit, gloss, count = r[:5]
        if lang == "he" and int(re.sub(r"\D", "", key) or 0) >= 9000:
            continue  # prefix and suffix labels
        morph = (E.get(key) or [None, None, ""])[2] or ""
        if morph.startswith("A:"):
            continue  # Aramaic
        first = lemma.split(",")[0].strip()
        norm = he_plain(first) if lang == "he" else first
        groups[norm].append((count, key, first, translit, gloss))
    says = hebrew_says() if lang == "he" else {}
    words, alias = [], {}
    for norm, senses in groups.items():
        total = sum(s[0] for s in senses)
        if total < MIN:
            continue
        senses.sort(key=lambda s: -s[0])
        count, key, lemma, translit, gloss = senses[0]
        g = GLOSS_FIX.get(gloss) or (gloss.partition(": ")[0] if len(senses) > 1 else gloss_text(gloss))
        say = ""
        if lang == "he":
            plain = he_plain(lemma)
            cands = Counter()
            for s in senses:
                for (form, tr), n in says.get(s[1], {}).items():
                    if form == plain:
                        cands[tr] += n
            say = he_say(cands.most_common(1)[0][0]) if cands else he_say_guess(translit, lemma)
            lemma = plain
        look = mark_key if lang == "he" else (lambda x: x)
        over = {look(k): v for k, v in OVERRIDES[lang].items()}
        sayfix = {look(k): v for k, v in SAY_FIX.get(lang, {}).items()}
        g = over.get(look(lemma), g).replace("/", ", ")
        say = sayfix.get(look(lemma), say).replace("ph", "f")
        words.append([key, lemma, g, total, say])
        for s in senses[1:]:
            alias[s[1]] = key
    words.sort(key=lambda w: (-w[3], w[0]))
    return {"lang": lang, "min": MIN, "words": words, "alias": alias}


def main():
    os.makedirs(os.path.join(DATA, "decks"), exist_ok=True)
    for lang, fn in (("grc", "greek"), ("he", "hebrew")):
        deck = build(lang)
        with open(os.path.join(DATA, "decks", f"{fn}.json"), "w", encoding="utf-8") as f:
            json.dump(deck, f, ensure_ascii=False, separators=(",", ":"))
        print(f"{fn}: {len(deck['words'])} words used {MIN}+ times ({len(deck['alias'])} extra senses folded in)")


if __name__ == "__main__":
    main()
