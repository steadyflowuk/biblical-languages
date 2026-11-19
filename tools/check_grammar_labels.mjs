// Every grammar code the app uses, read by a decoder written here from the code systems' own definitions (Robinson's
// Greek codes as TAGNT uses them; the OSHB/TAHOT Hebrew codes), then compared with
//   1. STEPBible's wording of the code (data/morph/*.json): does it name the same case, tense, person …?
//   2. what a learner sees: friendlyGrammar/shortGrammar (Greek), heFriendlyGrammar/heShortGrammar (Hebrew): nothing
//      dropped, nothing contradicting the code (a 2nd person losing its "2nd", "masc." on a feminine form …).
//
//     node tools/check_grammar_labels.mjs              # every code in use (≈1,900)
//     node tools/check_grammar_labels.mjs --self-test  # planted mistakes are caught
import fs from "fs";
import path from "path";

const ROOT = path.dirname(path.dirname(new URL(import.meta.url).pathname));
globalThis.window = globalThis;
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {}, key: () => null, length: 0 };
globalThis.document = { addEventListener() {}, querySelector: () => null, querySelectorAll: () => [], documentElement: { dataset: {}, setAttribute() {} }, createElement: () => ({ style: {} }), body: {} };
globalThis.location = { hash: "" };
const reader = await import(path.join(ROOT, "js/reader.js"));
const hebrew = await import(path.join(ROOT, "js/hebrew.js"));
const load = (f) => JSON.parse(fs.readFileSync(path.join(ROOT, f), "utf8"));

// ---------------------------------------------------------------- Greek: Robinson codes
const CASE = { N: "nominative", G: "genitive", D: "dative", A: "accusative", V: "vocative" };
const NUM = { S: "singular", P: "plural" };
const GEN = { M: "masculine", F: "feminine", N: "neuter" };
const PERSON = { 1: "1st", 2: "2nd", 3: "3rd" };
const TENSE = { P: "present", I: "imperfect", F: "future", A: "aorist", R: "perfect", L: "pluperfect" };
const VOICE = { A: "active", M: "middle", P: "passive", E: "middle or passive", D: "middle deponent", O: "passive deponent", N: "middle or passive deponent", Q: "impersonal active", X: "no voice" };
const MOOD = { I: "indicative", S: "subjunctive", O: "optative", M: "imperative", N: "infinitive", P: "participle" };
const POS = { N: "noun", A: "adjective", T: "article", P: "personal pronoun", R: "relative pronoun", D: "demonstrative pronoun", C: "reciprocal pronoun", F: "reflexive pronoun", I: "interrogative pronoun", X: "indefinite pronoun", Q: "correlative", K: "correlative", S: "possessive" };
const SHORT = { nominative: "nom.", genitive: "gen.", dative: "dat.", accusative: "acc.", vocative: "voc.", singular: "sg.", plural: "pl.", masculine: "masc.", feminine: "fem.", neuter: "neut.", present: "pres.", imperfect: "impf.", future: "fut.", aorist: "aor.", perfect: "perf.", pluperfect: "plupf.", active: "act.", indicative: "ind.", subjunctive: "subj.", optative: "opt.", imperative: "impv.", infinitive: "inf.", participle: "ptc." };

/** Features of a Greek code: [{name, value}] where name is case/num/gen/person/tense/voice/mood. */
export function greekFeatures(code) {
  const out = [];
  const add = (name, value) => out.push({ name, value });
  for (const part of code.split("+")) {
    const bits = part.split("-");
    const head = bits[0];
    if (head === "V") {
      const m = (bits[1] || "").match(/^(2?)([PIFARL])([AMPEDONQX])([ISOMNP])$/);
      if (!m) { add("bad", part); continue; }
      add("tense", TENSE[m[2]]); add("voice", VOICE[m[3]]); add("mood", MOOD[m[4]]);
      const rest = bits[2] || "";
      if (m[4] === "P") { const c = rest.match(/^([NGDAV])([SP])([MFN])$/); if (c) { add("case", CASE[c[1]]); add("num", NUM[c[2]]); add("gen", GEN[c[3]]); } else if (rest) add("bad", part); }
      else if (m[4] !== "N") { const c = rest.match(/^([123])([SP])$/); if (c) { add("person", PERSON[c[1]]); add("num", NUM[c[2]]); } else if (rest) add("bad", part); }
      continue;
    }
    if (!POS[head]) continue; // CONJ, PREP, ADV, PRT, INJ, COND, HEB, ARAM …: nothing to inflect
    const body = bits[1] || "";
    let m;
    if (head === "S") m = body.match(/^([123])([SP])([NGDAV])([SP])([MFN])$/);
    if (m) { add("person", PERSON[m[1]]); add("possnum", NUM[m[2]]); add("case", CASE[m[3]]); add("num", NUM[m[4]]); add("gen", GEN[m[5]]); continue; }
    if ((m = body.match(/^([123])([NGDAV])([SP])([MFN])?$/))) { add("person", PERSON[m[1]]); add("case", CASE[m[2]]); add("num", NUM[m[3]]); if (m[4]) add("gen", GEN[m[4]]); continue; }
    if ((m = body.match(/^([NGDAV])([SP])([MFN])?$/))) { add("case", CASE[m[1]]); add("num", NUM[m[2]]); if (m[3]) add("gen", GEN[m[3]]); continue; }
    if (body && !/^(NUI|LI|OI|PRI)$/.test(body)) add("bad", part); // indeclinable numbers/letters/names
  }
  return out;
}

const has = (text, word) => new RegExp(`(^|[^\\w])${word.replace(/[.()]/g, "\\$&")}([^\\w]|$)`, "i").test(text);

const PERSON_EXPLAIN = { "1st": "speaking or writing", "2nd": "spoken or written to", "3rd": "discussed" };
const PERSON_EXAMPLE = { "1st singular": /^I\b/, "1st plural": /^we\b/i, "2nd singular": /^you\b/i, "2nd plural": /^you all\b/i, "3rd singular": /^(he|she|it)\b/i, "3rd plural": /^they\b/i };

function checkGreek(code, desc, explain, example) {
  const bad = [];
  const pf = greekFeatures(code).find((f) => f.name === "person");
  const nf = greekFeatures(code).find((f) => f.name === "num");
  if (pf && code[0] === "V" && explain) {  // the sentence under the label says who does it, and its example agrees
    if (!explain.includes(PERSON_EXPLAIN[pf.value])) bad.push(`explanation doesn't fit the ${pf.value} person: ${explain}`);
    if (example && nf && !PERSON_EXAMPLE[`${pf.value} ${nf.value}`].test(example)) bad.push(`example doesn't fit ${pf.value} ${nf.value}: ${example}`);
  }
  const feats = greekFeatures(code);
  if (feats.some((f) => f.name === "bad")) bad.push(`code not understood: ${code}`);
  const friendly = reader.friendlyGrammar(desc);
  const short = reader.shortGrammar(desc);
  for (const { name, value } of feats) {
    if (name === "bad" || name === "possnum") continue;
    const want = name === "voice" ? value.split(" ")[0] : value;
    if (!has(desc, want)) bad.push(`STEPBible's wording lacks ${name} "${want}": ${desc}`);
    if (!has(friendly, want)) bad.push(`full label drops ${name} "${want}": ${friendly}`);
    const s = name === "voice" ? (/deponent/.test(value) || value === "no voice" || value === "impersonal active" ? "" : SHORT[want] || "")
      : name === "person" ? value : SHORT[value];
    if (s && !has(short, s)) bad.push(`short label drops ${name} "${s}": ${short}`);
  }
  // nothing contradicting: a case, number, gender, tense or mood the code doesn't have
  for (const [name, table] of [["case", CASE], ["num", NUM], ["gen", GEN], ["tense", TENSE], ["mood", MOOD], ["person", PERSON]]) {
    const mine = feats.filter((f) => f.name === name || (name === "num" && f.name === "possnum")).map((f) => f.value);
    for (const v of Object.values(table)) {
      if (mine.includes(v)) continue;
      if (name === "tense" && mine.some((x) => x.includes(v))) continue; // "pluperfect" contains "perfect"
      const ab = name === "person" ? v : SHORT[v];
      if (has(friendly, v) || (ab && has(short, ab) && !(name === "tense" && v === "perfect" && mine.includes("pluperfect")))) {
        // "2nd" also names the second aorist/perfect: a person only when it isn't before a tense
        if (name === "person" && !new RegExp(`${v} (singular|plural|sg\\.|pl\\.)`, "i").test(friendly + " " + short)) continue;
        bad.push(`label says ${name} "${v}" but the code doesn't: ${short}`);
      }
    }
  }
  if (/\b2nd (perf|fut|plupf|aor)/i.test(short)) bad.push(`short label keeps "2nd" before a tense (reads like a person): ${short}`);
  return bad;
}

// ---------------------------------------------------------------- Hebrew: OSHB/TAHOT codes
const HE_PERSON = { 1: "first", 2: "second", 3: "third" };
const HE_GEN = { m: "masculine", f: "feminine", c: "either gender", b: "either gender" };
const HE_NUM = { s: "singular", p: "plural", d: "dual" };
const HE_FORM = { p: "pf.", q: "weqatal", i: "impf.", w: "wayyiqtol", u: "impf.", h: "cohort.", j: "jussive", v: "impv.", r: "ptc.", s: "pass. ptc.", a: "inf. abs.", c: "inf. cstr." };

/** {pos, stem?, form?, pgn, state?} of one segment of a Hebrew code, e.g. "Vqw3ms", "Ncfpc", "Sp3ms". */
export function hebrewSegment(seg) {
  let m;
  if ((m = seg.match(/^V(\w)(\w)(.*)$/))) {
    let [, stem, form, rest] = m;
    if (form === "c" && /^c/.test(rest)) { rest = rest.slice(1); form = "c"; }       // infinitive construct "cc"
    else if (form === "a" && /^a/.test(rest)) { rest = rest.slice(1); form = "a"; } // infinitive absolute "aa"
    else if (form === "c" && /^[123]/.test(rest)) form = "h";                          // TAHOT's cohortative
    else if (form === "c") form = "c";
    const p = rest.match(/^([123])?([mfcb])?([spd])?([ac])?$/) || [];
    return { pos: "verb", stem, form, pgn: `${p[1] || ""}${p[2] ? (p[2] === "b" ? "c" : p[2]) : ""}${p[3] || ""}`, state: p[4] || "" };
  }
  if ((m = seg.match(/^N([cgp])(.*)$/))) {
    const p = m[2].match(/^([mfcbl])?([spd])?([ac])?$/) || [];
    return { pos: m[1] === "p" ? "name" : "noun", pgn: m[1] === "p" ? "" : `${p[1] && p[1] !== "b" ? p[1] : ""}${p[2] || ""}`, state: p[3] || "" };
  }
  if ((m = seg.match(/^A([acgo])(.*)$/))) {
    const p = m[2].match(/^([mfcb])?([spd])?([ac])?$/) || [];
    return { pos: "adj", pgn: `${p[1] && p[1] !== "b" ? p[1] : ""}${p[2] || ""}`, state: p[3] || "" };
  }
  if ((m = seg.match(/^S([pd])(.*)$/))) {
    const p = m[2].match(/^([123])?([mfcb])?([spd])?$/) || [];
    return { pos: m[1] === "d" ? "directional" : "suffix", pgn: `${p[1] || ""}${p[2] ? (p[2] === "b" ? "c" : p[2]) : ""}${p[3] || ""}` };
  }
  if ((m = seg.match(/^P([pdfi])(.*)$/))) {
    const p = m[2].match(/^([123])?([mfcbx])?([spd])?$/) || [];
    return { pos: "pronoun", pgn: `${p[1] || ""}${p[2] && p[2] !== "x" ? (p[2] === "b" ? "c" : p[2]) : ""}${p[3] || ""}` };
  }
  return { pos: seg[0], pgn: "" };
}

const HE_EXPLAIN = { 1: "speaking or writing", 2: "addressed", 3: "discussed" };
function checkHebrew(code, desc, explain, example) {
  const bad = [];
  const vm = code.match(/V\w\w([123])([mfcb])?([spd])/);
  if (vm && explain) {  // the sentence under the label: who does it, how many, male or female
    const [, pp, gg, nn] = vm;
    if (!explain.includes(HE_EXPLAIN[pp])) bad.push(`explanation doesn't fit person ${pp}: ${explain}`);
    if (gg === "m" && /\bfemale\b/.test(explain) && !/male or female/.test(explain)) bad.push(`explanation says female for a masculine: ${explain}`);
    if (gg === "f" && /(^|[^e])\bmale\b/.test(explain.replace(/female/g, "")) && !/male or female/.test(explain)) bad.push(`explanation says male for a feminine: ${explain}`);
    if (nn === "p" && /\ba (male |female )?(person|thing)\b|\bthemself\b/.test(explain)) bad.push(`explanation is singular for a plural: ${explain}`);
    if (nn === "s" && /\bpeople\b|\bthemselves\b/.test(explain)) bad.push(`explanation is plural for a singular: ${explain}`);
    const exw = { "1s": /^I\b/, "1p": /^we\b/i, "2s": /^you\b/i, "2p": /^you\b/i, "3s": /^(he|she|it)\b/i, "3p": /^they\b/i }[pp + nn];
    if (example && exw && !exw.test(example)) bad.push(`example doesn't fit ${pp}${nn}: ${example}`);
  }
  const segs = code.slice(1).split("/");
  const s = hebrewSegment(segs[0]);
  const short = hebrew.heShortGrammar(desc);
  const full = hebrew.heFriendlyGrammar(desc);
  const d = desc.toLowerCase();
  // STEPBible's wording names the same person, gender and number as the code
  const p = s.pgn.match(/^([123])?([mfc])?([spd])?$/) || [];
  if (p[1] && !d.includes(HE_PERSON[p[1]])) bad.push(`wording lacks person ${HE_PERSON[p[1]]}: ${desc}`);
  if (p[2] && p[2] !== "c" && !d.includes(HE_GEN[p[2]])) bad.push(`wording lacks gender ${HE_GEN[p[2]]}: ${desc}`);
  if (p[3] && !d.includes(HE_NUM[p[3]])) bad.push(`wording lacks number ${HE_NUM[p[3]]}: ${desc}`);
  for (const [k, v] of Object.entries(HE_GEN)) if (k !== "c" && k !== "b" && d.includes(v) && p[2] && p[2] !== k && !(p[2] === "c")) bad.push(`wording says ${v}, code says ${p[2]}: ${desc}`);
  if (s.pos === "verb") {
    const want = HE_FORM[s.form];
    const ok = (want && short.includes(want)) || (s.form === "j" && short.includes("impf.")) || (s.form === "i" && short.includes("jussive"))
      || (s.form === "j" && s.pgn[0] === "1" && short.includes("cohort."));  // a 1st person jussive is a cohortative
    if (want && !ok) bad.push(`short label "${short}" lacks the form ${want} (code ${code})`);
    if (s.pgn && !short.endsWith(s.pgn) && !short.includes(` ${s.pgn}`)) bad.push(`short label "${short}" lacks ${s.pgn} (code ${code})`);
    if (!/^[A-Z]/.test(short)) bad.push(`short label doesn't start with the stem: "${short}" (code ${code})`);
  } else if (["noun", "adj", "suffix", "pronoun"].includes(s.pos)) {
    if (s.pgn && !short.includes(s.pgn)) bad.push(`short label "${short}" lacks ${s.pgn} (code ${code})`);
    if (s.state === "c" && !short.includes("cstr.")) bad.push(`short label "${short}" doesn't say construct (code ${code})`);
    if (s.state === "a" && short.includes("cstr.")) bad.push(`short label "${short}" says construct for an absolute (code ${code})`);
  }
  if (/transtive|  /.test(full)) bad.push(`full label not tidied: ${full}`);
  return bad;
}

// ---------------------------------------------------------------- run
function run(greek, hebrewMorph) {
  const problems = [];
  let n = 0;
  for (const [code, v] of Object.entries(greek)) { n++; checkGreek(code, v[0], v[1], v[2]).forEach((b) => problems.push(`G ${code}: ${b}`)); }
  for (const [code, v] of Object.entries(hebrewMorph)) { n++; checkHebrew(code, v[0], v[1], v[2]).forEach((b) => problems.push(`H ${code}: ${b}`)); }
  return { n, problems };
}

const greek = load("data/morph/greek.json");
const hebrewMorph = load("data/morph/hebrew.json");

// how often each code is used, so the report says how many words a problem touches
function uses() {
  const c = {};
  for (const dir of ["gnt", "hot"]) {
    for (const f of fs.readdirSync(path.join(ROOT, "data", dir))) {
      const d = load(`data/${dir}/${f}`);
      for (const [, vs] of d.ch) for (const it of vs) for (const w of it[1]) {
        if (dir === "gnt") (w[4] || "").split("+").forEach((k) => { c["G " + k] = (c["G " + k] || 0) + 1; });
        else if (w[4]) { const segs = w[4].split("/"); const lang = segs[0][0]; c["H " + segs[0]] = (c["H " + segs[0]] || 0) + 1; segs.slice(1).filter(Boolean).forEach((s) => { c["H " + lang + s] = (c["H " + lang + s] || 0) + 1; }); }
      }
    }
  }
  return c;
}

if (process.argv.includes("--self-test")) {
  const tests = [
    ["Greek wording with the wrong case", () => run({ "N-GSM": ["Noun dative singular masculine"] }, {})],
    ["Greek label losing the person after a 2nd aorist", () => run({ "V-2AAI-2S": ["Verb 2nd aorist active indicative singular"] }, {})],
    ["Greek explanation for the wrong person", () => run({ "V-FAI-1S": ["Verb future active indicative 1st singular", "an action that will happen - by a person or thing being discussed", "I will teach"] }, {})],
    ["Greek wording with the wrong gender", () => run({ "A-NSF": ["Adjective nominative singular masculine"] }, {})],
    ["Hebrew wording with the wrong number", () => run({}, { HNcmpa: ["Noun (singular masculine, absolute)"] })],
    ["Hebrew wording with the wrong person", () => run({}, { HVqp3ms: ["Verb: Qal (simple, active) perfect (past/present indicative) first singular masculine"] })],
    ["Hebrew wayyiqtol labelled as a perfect", () => run({}, { HVqw3ms: ["Verb: Qal (simple, active) perfect (past/present indicative) third singular masculine"] })],
    ["Hebrew explanation plural for a singular", () => run({}, { HVqp2ms: ["Verb: Qal (simple, active) perfect (past/present indicative) second singular masculine", "performing an action that is done completely by male people or things being addressed", "you did rise"] })],
    ["Hebrew construct noun", () => run({}, { HNcfsc: ["Noun (singular feminine, absolute)"] })],
  ];
  let ok = 0;
  for (const [name, f] of tests) { const caught = f().problems.length > 0; console.log((caught ? "caught " : "MISSED ") + name); ok += caught; }
  console.log(`${ok}/${tests.length} passed`);
  process.exit(ok === tests.length ? 0 : 1);
}

const { n, problems } = run(greek, hebrewMorph);
const u = uses();
console.log(`${n.toLocaleString("en-GB")} grammar codes checked (${Object.keys(greek).length} Greek, ${Object.keys(hebrewMorph).length} Hebrew), labels as the app shows them`);
const unused = Object.keys(u).filter((k) => !(k.slice(2) in (k[0] === "G" ? greek : hebrewMorph)));
for (const k of unused) problems.push(`${k}: used ${u[k]} times but has no wording in data/morph`);
for (const p of problems) {
  const k = p.split(":")[0];
  console.log(`  ${p}  [${(u[k] || 0).toLocaleString("en-GB")} words]`);
}
console.log(`${problems.length} problems`);
process.exit(problems.length ? 1 : 0);
