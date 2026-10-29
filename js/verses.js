// Built-in verses for the Today screen, shown at once and used if the verse data can't load
// (first open while offline). Today's verses come from data/votd.json.
// Greek: SBLGNT (CC BY 4.0). Hebrew: Westminster Leningrad Codex (public domain).
// English: Berean Standard Bible (public domain).

export const VERSES = [
  {
    id: "john-1-1",
    lang: "grc",
    ref: "John 1:1",
    english: "In the beginning was the Word, and the Word was with God, and the Word was God.",
    words: [
      { t: "Ἐν", lemma: "ἐν", en: "in", gloss: "in/on/among", parse: "preposition", k: "G1722" },
      { t: "ἀρχῇ", lemma: "ἀρχή", en: "beginning", gloss: "beginning", parse: "noun, dative singular feminine", k: "G0746" },
      { t: "ἦν", lemma: "εἰμί", en: "was", gloss: "to be", parse: "verb, imperfect, he/she/it", k: "G1510" },
      { t: "ὁ", lemma: "ὁ", en: "the", gloss: "the/this/who", parse: "article, nominative singular masculine", k: "G3588" },
      { t: "λόγος", p: ",", lemma: "λόγος", en: "word, message", gloss: "word", parse: "noun, nominative singular masculine", k: "G3056" },
      { t: "καὶ", lemma: "καί", en: "and", gloss: "and", parse: "conjunction", k: "G2532" },
      { t: "ὁ", lemma: "ὁ", en: "the", gloss: "the/this/who", parse: "article, nominative singular masculine", k: "G3588" },
      { t: "λόγος", lemma: "λόγος", en: "word, message", gloss: "word", parse: "noun, nominative singular masculine", k: "G3056" },
      { t: "ἦν", lemma: "εἰμί", en: "was", gloss: "to be", parse: "verb, imperfect, he/she/it", k: "G1510" },
      { t: "πρὸς", lemma: "πρός", en: "with, towards", gloss: "to/with", parse: "preposition", k: "G4314" },
      { t: "τὸν", lemma: "ὁ", en: "the", gloss: "the/this/who", parse: "article, accusative singular masculine", k: "G3588" },
      { t: "θεόν", p: ",", lemma: "θεός", en: "God", gloss: "God", parse: "noun, accusative singular masculine", k: "G2316" },
      { t: "καὶ", lemma: "καί", en: "and", gloss: "and", parse: "conjunction", k: "G2532" },
      { t: "θεὸς", lemma: "θεός", en: "God", gloss: "God", parse: "noun, nominative singular masculine", k: "G2316" },
      { t: "ἦν", lemma: "εἰμί", en: "was", gloss: "to be", parse: "verb, imperfect, he/she/it", k: "G1510" },
      { t: "ὁ", lemma: "ὁ", en: "the", gloss: "the/this/who", parse: "article, nominative singular masculine", k: "G3588" },
      { t: "λόγος", p: ".", lemma: "λόγος", en: "word, message", gloss: "word", parse: "noun, nominative singular masculine", k: "G3056" },
    ],
    focus: 4,
  },
  {
    id: "gen-1-1",
    lang: "he",
    ref: "Genesis 1:1",
    english: "In the beginning God created the heavens and the earth.",
    words: [
      { t: "בְּרֵאשִׁ֖ית", lemma: "רֵאשִׁית", en: "in the beginning", gloss: "beginning", parse: "preposition בְּ “in” + noun, feminine singular", k: "H7225G" },
      { t: "בָּרָ֣א", lemma: "בָּרָא", en: "created", gloss: "to create", parse: "verb, Qal perfect, he", k: "H1254A" },
      { t: "אֱלֹהִ֑ים", lemma: "אֱלֹהִים", en: "God", gloss: "God", parse: "noun, masculine plural in form", k: "H0430G" },
      { t: "אֵ֥ת", lemma: "אֵת", en: "(marks the object)", gloss: "[Obj.]", parse: "direct object marker, not translated", k: "H0853" },
      { t: "הַשָּׁמַ֖יִם", lemma: "שָׁמַיִם", en: "the heavens", gloss: "heaven", parse: "article הַ “the” + noun, masculine plural", k: "H8064" },
      { t: "וְאֵ֥ת", lemma: "אֵת", en: "and (object)", gloss: "[Obj.]", parse: "conjunction וְ “and” + direct object marker", k: "H0853" },
      { t: "הָאָֽרֶץ", p: "׃", lemma: "אֶרֶץ", en: "the earth", gloss: "country/planet", parse: "article הָ “the” + noun, singular", k: "H0776G" },
    ],
    focus: 2,
  },
];
