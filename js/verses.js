// Starter verses for the Today screen until the full Bible data arrives (Session 2).
// Greek: SBLGNT (CC BY 4.0). Hebrew: Westminster Leningrad Codex (public domain).
// English: Berean Standard Bible (public domain).

export const VERSES = [
  {
    id: "john-1-1",
    lang: "grc",
    ref: "John 1:1",
    english: "In the beginning was the Word, and the Word was with God, and the Word was God.",
    words: [
      { t: "Ἐν", lemma: "ἐν", gloss: "in", parse: "preposition" },
      { t: "ἀρχῇ", lemma: "ἀρχή", gloss: "beginning", parse: "noun, dative singular feminine" },
      { t: "ἦν", lemma: "εἰμί", gloss: "was", parse: "verb, imperfect, he/she/it" },
      { t: "ὁ", lemma: "ὁ", gloss: "the", parse: "article, nominative singular masculine" },
      { t: "λόγος", p: ",", lemma: "λόγος", gloss: "word, message", parse: "noun, nominative singular masculine" },
      { t: "καὶ", lemma: "καί", gloss: "and", parse: "conjunction" },
      { t: "ὁ", lemma: "ὁ", gloss: "the", parse: "article, nominative singular masculine" },
      { t: "λόγος", lemma: "λόγος", gloss: "word, message", parse: "noun, nominative singular masculine" },
      { t: "ἦν", lemma: "εἰμί", gloss: "was", parse: "verb, imperfect, he/she/it" },
      { t: "πρὸς", lemma: "πρός", gloss: "with, toward", parse: "preposition" },
      { t: "τὸν", lemma: "ὁ", gloss: "the", parse: "article, accusative singular masculine" },
      { t: "θεόν", p: ",", lemma: "θεός", gloss: "God", parse: "noun, accusative singular masculine" },
      { t: "καὶ", lemma: "καί", gloss: "and", parse: "conjunction" },
      { t: "θεὸς", lemma: "θεός", gloss: "God", parse: "noun, nominative singular masculine" },
      { t: "ἦν", lemma: "εἰμί", gloss: "was", parse: "verb, imperfect, he/she/it" },
      { t: "ὁ", lemma: "ὁ", gloss: "the", parse: "article, nominative singular masculine" },
      { t: "λόγος", p: ".", lemma: "λόγος", gloss: "word, message", parse: "noun, nominative singular masculine" },
    ],
    focus: 4,
  },
  {
    id: "gen-1-1",
    lang: "he",
    ref: "Genesis 1:1",
    english: "In the beginning God created the heavens and the earth.",
    words: [
      { t: "בְּרֵאשִׁ֖ית", lemma: "רֵאשִׁית", gloss: "in the beginning", parse: "preposition בְּ “in” + noun, feminine singular" },
      { t: "בָּרָ֣א", lemma: "בָּרָא", gloss: "created", parse: "verb, Qal perfect, he" },
      { t: "אֱלֹהִ֑ים", lemma: "אֱלֹהִים", gloss: "God", parse: "noun, masculine plural in form" },
      { t: "אֵ֥ת", lemma: "אֵת", gloss: "(marks the object)", parse: "direct object marker, not translated" },
      { t: "הַשָּׁמַ֖יִם", lemma: "שָׁמַיִם", gloss: "the heavens", parse: "article הַ “the” + noun, masculine plural" },
      { t: "וְאֵ֥ת", lemma: "אֵת", gloss: "and (object)", parse: "conjunction וְ “and” + direct object marker" },
      { t: "הָאָֽרֶץ", p: "׃", lemma: "אֶרֶץ", gloss: "the earth", parse: "article הָ “the” + noun, singular" },
    ],
    focus: 2,
  },
];

// Alternate the language day by day.
export function verseForToday(date = new Date()) {
  const day = Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 864e5);
  return VERSES[day % VERSES.length];
}
