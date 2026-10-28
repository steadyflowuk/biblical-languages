// Every word the app can send to a voice, checked offline (Session 10e):  node tools/check_speech.mjs
// Hebrew: every OT word (as the Reader's Listen gives it), every Hebrew dictionary headword, the Letters guide and the
// Hebrew lessons and list — the voice text must keep every letter (the divine name may become Adonai/Elohim).
// Greek: every NT word, every Greek headword and every Septuagint word, in Erasmian and Restored Koine — something
// sayable must be left, and no brackets or Latin letters may reach the voice.
// Words with nothing to say (a lone ס paragraph mark, Septuagint numerals) are listed: the app shows no Listen for them.
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const R = path.join(path.dirname(fileURLToPath(import.meta.url)), "..") + "/";
const s = await import(R + "js/sound.js");
const { heText } = await import(R + "js/hebrew.js");
const json = (f) => JSON.parse(fs.readFileSync(R + f, "utf8"));
const lemmaOf = (e) => String((Array.isArray(e) ? e[0] : e && e.lemma) || "").split(",")[0].trim();

const HE_LETTER = /[א-ת]/;
const GR_LETTER = /[Ͱ-Ͽἀ-῿]/;
const cons = (t) => t.replace(/[^א-ת]/g, "");
const problems = [];
const silent = new Set();
let n = 0;

function hebrew(where, t) {
  n++;
  const out = s.hebrewSpeech(t);
  if (!HE_LETTER.test(out)) { silent.add(t); return; }
  const kept = cons(t.replace(/(^|\s)[פס](?=\s|$)/g, "$1"));
  if (kept !== cons(out) && !/אֲדֹנָי|אֱלֹהִים/.test(out)) problems.push(`${where}: ${t} → ${out} (letters lost)`);
  if (/[^ְ-ׇא-ת ]/.test(out)) problems.push(`${where}: ${t} → ${out} (not Hebrew)`);
}

function greek(where, t) {
  n++;
  const eras = s.erasmianSpeech(t), koine = s.koineSpeech(t);
  if (!GR_LETTER.test(eras)) { silent.add(t); return; }
  for (const [mode, out] of [["Erasmian", eras], ["Koine", koine]]) {
    if (/[A-Za-z[\]()=]/.test(out)) problems.push(`${where}: ${t} → ${out} (${mode}: not Greek)`);
  }
}

for (const f of fs.readdirSync(R + "data/hot")) {
  const B = json("data/hot/" + f);
  for (const [c, vs] of B.ch) for (const item of vs) item[1].forEach((w, i) => hebrew(`${B.id} ${c}:${item[0]}.${i + 1}`, heText(w)));
}
for (const f of fs.readdirSync(R + "data/lex/H")) for (const [k, e] of Object.entries(json("data/lex/H/" + f))) { const l = lemmaOf(e); if (l) hebrew("lex " + k, l); }
const A = json("lessons/alphabet/he.json");
A.letters.forEach((L) => [L.nameT, L.example.t, L.example2 && L.example2.t].filter(Boolean).forEach((t) => hebrew("letters " + L.name, t)));
A.sections.forEach((sec) => (sec.examples || []).forEach((e) => hebrew("letters " + sec.title, e.t)));
json("data/decks/hebrew.json").words.forEach((d) => hebrew("list " + d[0], d[1]));
const walk = (o, where, fn) => {
  if (Array.isArray(o)) o.forEach((x) => walk(x, where, fn));
  else if (o && typeof o === "object") for (const [k, v] of Object.entries(o)) {
    // letter cards ("Β β", "γγ") have no Listen button
    if (typeof v === "string" && ["t", "text"].includes(k) && (HE_LETTER.test(v) || GR_LETTER.test(v)) && !/^(\S{1,2}\s?)+$/u.test(v.normalize("NFC")) ) fn(where, v);
    else walk(v, where, fn);
  }
};
for (const lang of ["he", "grc"]) for (const f of fs.readdirSync(R + "lessons/" + lang)) {
  walk(json(`lessons/${lang}/${f}`), `lesson ${lang}-${f}`, (w, v) => (HE_LETTER.test(v) ? hebrew(w, v) : greek(w, v)));
}

for (const f of fs.readdirSync(R + "data/gnt")) {
  const B = json("data/gnt/" + f);
  for (const [c, vs] of B.ch) for (const item of vs) item[1].forEach((w, i) => greek(`${B.id} ${c}:${item[0]}.${i + 1}`, w[0] + String(w[5] || "").replace(/[¶¬]/g, "")));
}
for (const f of fs.readdirSync(R + "data/lex/G")) for (const [k, e] of Object.entries(json("data/lex/G/" + f))) { const l = lemmaOf(e); if (l) greek("lex " + k, l); }
const G = json("lessons/alphabet/grc.json");
G.letters.forEach((L) => [L.nameT, L.example.t].forEach((t) => greek("letters " + L.name, t)));
G.sections.forEach((sec) => (sec.examples || []).forEach((e) => greek("letters " + sec.title, e.t)));
for (const f of fs.readdirSync(R + "data/lxx/text")) {
  const go = (o) => { if (typeof o === "string") o.split(/\s+/).filter((w) => GR_LETTER.test(w)).forEach((w) => greek("lxx " + f, w)); else if (o && typeof o === "object") Object.values(o).forEach(go); };
  go(json("data/lxx/text/" + f));
}

console.log(`${n.toLocaleString("en-GB")} words checked.`);
console.log(`No Listen button (nothing to say): ${[...silent].join("  ")}`);
if (problems.length) { console.log(`${problems.length} problems:`); problems.slice(0, 40).forEach((p) => console.log("  " + p)); process.exit(1); }
console.log("Every word reaches the voice whole.");
