// Hebrew and Aramaic helpers for the Reader: word parts, pronunciation, English and grammar labels.
// Data format (see tools/build_data.py): [text, translit, english, strongs, morph, after, flag, note]
//   text/english/strongs/morph keep "/" between joined parts, e.g. "הָ/אָֽרֶץ", "the/ earth", "H9009/{H0776G}", "HTd/Ncfsa".
//   Hebrew is not Unicode-normalised: never call normalize() on it.

/** The word as printed: joined parts without the "/" separators. */
export const heText = (w) => String(w[0] || "").replace(/\//g, "");

/** "be./re.Shit" → "be·re·Shit" (dots mark syllables; the capitalised syllable carries the stress). */
export const heTranslit = (t) => String(t || "").replace(/[\u0591-\u05c7]/g, "") // a few source entries carry a stray Hebrew vowel
  .replace(/\//g, "").replace(/\./g, "·").replace(/·{2,}/g, "·");

/** "in/ beginning" → "in beginning". */
export const heEnglish = (e) => String(e || "").replace(/\s*\/\s*/g, " ").trim()
  .replace(/^\((.*?):\s*written, not read\)$/, "$1"); // the 14 words written but not read: the note explains

/** Punctuation printed after a word: keep maqaf ־, sof pasuq ׃, paseq ׀ and inverted nun ׆; drop paragraph letters פ ס. */
export const heAfter = (after) => String(after || "").replace(/(^|\s)[פס](?=\s|$)/g, "").trim()
  .replace(/\s*([׀׆])/g, " $1").replace(/\s+(?![׀׆])/g, "");

/** True when the word is joined to the next by a maqaf (no space between them). */
export const heJoined = (after) => /־\s*$/.test(String(after || ""));

/** True when the source marks a paragraph break (פ open, ס closed) after this word. */
export const heParagraphAfter = (after) => /(^|\s)[פס](\s|$)/.test(String(after || ""));

export const isAramaic = (w) => String(w[4] || "").startsWith("A");

/**
 * The parts of a joined word: prefixes, the main word and suffixes.
 * [{ text, key, code, main }] — key is the Strong's key, code the full grammar code (with H/A prefix).
 */
export function heParts(w) {
  const texts = String(w[0] || "").split("/");
  const keys = String(w[3] || "").split("/").map((k) => k.split("\\")[0]);
  const segs = String(w[4] || "").split("/");
  const lang = segs[0].charAt(0) || "H";
  const parts = [];
  texts.forEach((t, i) => {
    if (!t.trim() || t.trim() === "־") return; // the space or maqaf inside compound names
    const rawKey = keys[i] || "";
    const code = i === 0 ? segs[0] : segs[i] ? lang + segs[i] : "";
    const key = rawKey.replace(/[{}+\s]/g, "");
    // main = the part(s) in {braces}; H9001+ are prefix/suffix labels, never the main word
    parts.push({ text: t, key, code, main: /[{}]/.test(rawKey) && !/^H90\d\d/.test(key) });
  });
  if (parts.length && !parts.some((p) => p.main)) parts[0].main = true;
  return parts;
}

/** The main word's Strong's key: the part in {braces}, e.g. "H9002/{H0776G}\H9016" → "H0776G". */
export function heMainKey(w) {
  const raw = String(w[3] || "");
  const m = raw.match(/\{([^}]+)\}/);
  const keys = (m ? m[1] : raw).split(/[/\\+\s]/).map((k) => k.replace(/[{}]/g, "")).filter(Boolean);
  return keys.find((k) => !/^H90\d\d/.test(k)) || keys[0] || "";
}

// ---------------------------------------------------------------- grammar labels

const PERSON = { first: "1", second: "2", third: "3" };
const GENDER = { masculine: "m", feminine: "f", "either gender": "c", "both genders": "c", either: "c" };
const NUMBER = { singular: "s", plural: "p", dual: "d" };

/** "third singular masculine" → "3ms"; "(plural masculine, construct)" → "mp cstr." */
function pgn(desc) {
  const d = desc.toLowerCase();
  const p = (d.match(/\b(first|second|third)\b/) || [])[1];
  const g = (d.match(/\b(masculine|feminine|either gender|both genders)\b/) || [])[1];
  const n = (d.match(/\b(singular|plural|dual)\b/) || [])[1];
  let out = `${p ? PERSON[p] : ""}${g ? GENDER[g] : ""}${n ? NUMBER[n] : ""}`;
  if (/\bconstruct\b/.test(d) && !/infinitive construct/.test(d)) out += out ? " cstr." : "cstr.";
  return out;
}

/** Verb form, in the names Hebrew grammars use. */
function verbForm(d) {
  if (/consecutive imperfect/.test(d)) return "wayyiqtol";
  if (/consecutive perfect/.test(d)) return "weqatal";
  if (/infinitive construct/.test(d)) return "inf. cstr.";
  if (/infinitive absolute/.test(d)) return "inf. abs.";
  if (/passive participle|participle passive/.test(d)) return "pass. ptc.";
  if (/participle/.test(d)) return "ptc.";
  if (/imperative/.test(d)) return "impv.";
  if (/imperfect \(future\/present jussive\)/.test(d)) return "jussive";
  if (/imperfect \(future\/present cohortative\)/.test(d)) return "cohort.";
  if (/imperfect/.test(d)) return "impf.";
  if (/perfect/.test(d)) return "pf.";
  return "";
}

/** Short label for under a word, e.g. "Qal wayyiqtol 3ms", "noun fs", "suffix 3ms", "prep.". */
export function heShortGrammar(desc) {
  const s = String(desc || "");
  const d = s.toLowerCase();
  const stem = (s.match(/^Verb:\s*([A-Za-z]+)/) || [])[1];
  if (stem) return [stem.charAt(0).toUpperCase() + stem.slice(1), verbForm(d), pgn(d)].filter(Boolean).join(" ");
  const label = (name) => [name, pgn(d)].filter(Boolean).join(" ");
  if (d.startsWith("proper noun")) {
    return /location/.test(d) ? "name (place)" : /title/.test(d) ? "name (title)" : /gentilic/.test(d) ? "name (people)" : "name (person)";
  }
  if (d.startsWith("noun")) return label(/gentilic/.test(d) ? "noun (people)" : /numerical|cardinal|ordinal/.test(d) ? "number" : "noun");
  if (d.startsWith("numerical position")) return label("number (order)");
  if (d.startsWith("numerical")) return label("number");
  if (d.startsWith("adjective")) return label(/numerical|cardinal|ordinal/.test(d) ? "number" : "adj.");
  if (d.startsWith("paragogic")) return "added ending";
  if (d.startsWith("suffix")) return label(/paragogic/.test(d) ? "added ending" : "suffix");
  if (d.startsWith("pronoun")) return label("pronoun");
  if (d.startsWith("preposition")) return /definite/.test(d) ? "prep. + the" : "prep.";
  if (d.startsWith("consecutive conjunction")) return "and (narrative)";
  if (d.startsWith("conjunction")) return "conj.";
  if (d.startsWith("definite article")) return "the";
  if (d.startsWith("object indicator")) return "object marker";
  if (d.startsWith("relative")) return "relative";
  if (d.startsWith("negative")) return "not";
  if (d.startsWith("interrogative")) return "question word";
  if (d.startsWith("interjection")) return "exclamation";
  if (d.startsWith("demonstrative")) return label("this/that");
  if (d.startsWith("adverb")) return "adv.";
  if (d.startsWith("directional")) return "toward (ending)";
  if (d.startsWith("conditional")) return "conj. (if/for)"; // כִּי and אִם share this tag
  return s.split(/[\s(]/)[0].toLowerCase();
}

/** Full label for the word details: tidy the source's wording. */
export function heFriendlyGrammar(desc) {
  return String(desc || "")
    .replace(/transtive/g, "transitive")
    .replace(/\beither gender\b/g, "male or female")
    .replace(/\s+/g, " ")
    .trim();
}
