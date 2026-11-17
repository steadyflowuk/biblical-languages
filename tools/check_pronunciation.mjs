// Pronunciation check (17 Nov 2026):  node tools/check_pronunciation.mjs [--examples N] [say WORD …]
//
// What a linguist listening to the app would notice. The phone has only Modern Greek and Israeli Hebrew voices, so the
// app hands them respelt text (js/sound.js). This check does not trust that code: it has its own models of
//   1. how each word SHOULD sound in the app's chosen pronunciations, written from the app's own teaching
//      (lessons/alphabet/grc.json for Erasmian and Restored Koine; lessons he-3…he-5 and standard grammar for
//      Hebrew: said and silent shewa, qamets and qamets hatuf, furtive patah, matres lectionis), and
//   2. how a Modern Greek or Israeli Hebrew voice READS the text it is given (Modern Greek spelling rules: η ι υ ει οι
//      all "i", αι "e", αυ/ευ "av/af", μπ ντ γκ voiced, σ voiced before β γ δ μ ν λ ρ, stress on the tonos, an
//      unstressed ι before a vowel gliding; Israeli: qamets "a", a plain shewa silent, …),
// then lines the two up sound by sound for every word the app can say, and names every difference.
// Differences a Modern voice can't avoid are listed as known limits with counts; anything else fails the check.
//
// It also checks:
//   • stress: the accented syllable is the one the voice stresses, in both Greek pronunciations;
//   • the respelling the app SHOWS (greekSay: "LO-gos", the Hebrew lists' and lessons' "de-va-RIM") against the model;
//   • whole verses as the "Listen to the verse" buttons give them: every word there, in order, said as on its own,
//     pauses where the text has them (Greek , . · ;  Hebrew atnah and sof pasuq), nothing that isn't Greek or Hebrew.
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const R = path.join(path.dirname(fileURLToPath(import.meta.url)), "..") + "/";
const S = await import(R + "js/sound.js");
const audio = await import(R + "js/audio.js").catch((e) => { console.log("js/audio.js couldn't load in Node: " + e.message); return null; });
const heVoice = audio && audio.heVoice;
const { heText, heJoined } = await import(R + "js/hebrew.js");
const json = (f) => JSON.parse(fs.readFileSync(R + f, "utf8"));
const argv = process.argv.slice(2);
const EXAMPLES = argv.includes("--examples") ? Number(argv[argv.indexOf("--examples") + 1]) : 4;

// ================================================================ sounds and alignment
// A sound is { p: "a", s: true } (s = stressed). Vowels: a e i o u y. Glides after a vowel are written as the vowel
// (ay = e i), so "ay" and a Modern "έι" compare equal. "j̯" = a glide made from a vowel letter (synizesis);
// "ʝ" = the Modern/Koine γ before e and i; "ju" = the "yu" Modern Greek writes for ü (ιου).
const VOWEL = /^(a|e|i|o|u|y|ju)$/;

/** Line up expected and heard sounds (Needleman–Wunsch); returns [[exp|null, got|null], …]. */
function align(A, B) {
  const n = A.length, m = B.length;
  const del = (i) => { const a = A[i - 1]; if (a.opt) return 0; if (VOWEL.test(a.p)) return 1; if (a.p === "h") return 0.5; return (A[i - 2] && A[i - 2].p === a.p) || (A[i] && A[i].p === a.p) ? 0.4 : 1; };
  const ins = (j) => (/^[mnŋ]$/.test(B[j - 1].p) && B[j] && /^[bdg]$/.test(B[j].p) ? 0.4 : 1);
  const NEAR = [["s", "z"], ["t", "d"], ["p", "b"], ["k", "g"], ["g", "ʝ"], ["ɣ", "ʝ"], ["y", "u"], ["y", "ju"], ["i", "j̯"], ["u", "ju"], ["e", "i"]];
  const vowelish = (x) => /^(a|e|i|o|u|y|ju|j̯)$/.test(x.p);
  const cost = (a, b) => (a.p === b.p || (a.alt && a.alt.includes(b.p)) ? 0 : NEAR.some(([x, y]) => (a.p === x && b.p === y) || (a.p === y && b.p === x)) ? 0.4
    : vowelish(a) === vowelish(b) ? 1 : 1.6);
  const D = Array.from({ length: n + 1 }, () => new Float64Array(m + 1));
  for (let i = 1; i <= n; i++) D[i][0] = D[i - 1][0] + del(i);
  for (let j = 1; j <= m; j++) D[0][j] = D[0][j - 1] + ins(j);
  for (let i = 1; i <= n; i++) for (let j = 1; j <= m; j++) {
    D[i][j] = Math.min(D[i - 1][j - 1] + cost(A[i - 1], B[j - 1]), D[i - 1][j] + del(i), D[i][j - 1] + ins(j));
  }
  const out = [];
  let i = n, j = m;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && D[i][j] === D[i - 1][j - 1] + cost(A[i - 1], B[j - 1])) { out.push([A[i - 1], B[j - 1]]); i--; j--; }
    else if (i > 0 && D[i][j] === D[i - 1][j] + del(i)) { out.push([A[i - 1], null]); i--; }
    else { out.push([null, B[j - 1]]); j--; }
  }
  return out.reverse();
}
const show = (ph) => ph.map((x) => (x.s ? "ˈ" : "") + x.p).join(" ");

// ================================================================ Greek: what it should sound like
const G_VOWELS = "αεηιουω";
const VOICELESS = /[θκξπστφχψς]/;

/** Polytonic word → letters with their marks. */
function gLetters(word) {
  const out = [];
  for (const c of String(word).normalize("NFD").toLowerCase()) {
    if (/[̀-ͯͅ]/.test(c)) {
      const L = out[out.length - 1];
      if (!L) continue;
      if (c === "̔") L.rough = true;
      else if (/[́̀͂]/.test(c)) L.acc = true;
      else if (c === "̈") L.dia = true;
      continue; // smooth breathing, iota subscript: silent
    }
    if (G_VOWELS.includes(c) || /[βγδζθκλμνξπρσςτφχψ]/.test(c)) out.push({ ch: c === "ς" ? "σ" : c });
  }
  return out;
}

/** Vowel units of a polytonic word: single vowels and the pairs said as one sound. */
function gUnits(L) {
  const U = [];
  for (let i = 0; i < L.length; i++) {
    const a = L[i], b = L[i + 1];
    if (G_VOWELS.includes(a.ch)) {
      const pair = b && ["αι", "ει", "οι", "υι", "ου", "αυ", "ευ", "ηυ"].includes(a.ch + b.ch) && !b.dia && !a.acc;
      if (pair) { U.push({ v: a.ch + b.ch, acc: !!(a.acc || b.acc), rough: !!(a.rough || b.rough) }); i++; }
      else U.push({ v: a.ch, acc: !!a.acc, rough: !!a.rough, dia: !!a.dia });
    } else U.push({ c: a.ch, rough: !!a.rough });
  }
  return U;
}

const ERASMIAN_V = { α: ["a"], ε: ["e"], η: ["e", "i"], ι: ["i"], ο: ["o"], υ: ["y"], ω: ["o"], αι: ["a", "i"], ει: ["e", "i"],
  οι: ["o", "i"], υι: ["u", "i"], ου: ["u"], αυ: ["a", "u"], ευ: ["e", "u"], ηυ: ["e", "i", "u"], ωυ: ["o", "u"] };
const ERASMIAN_C = { β: "b", γ: "g", δ: "d", ζ: ["d", "z"], θ: "θ", κ: "k", λ: "l", μ: "m", ν: "n", ξ: ["k", "s"], π: "p", ρ: "r",
  σ: "s", τ: "t", φ: "f", χ: "x", ψ: ["p", "s"] };
const KOINE_V = { α: ["a"], ε: ["e"], η: ["e"], ι: ["i"], ο: ["o"], υ: ["y"], ω: ["o"], αι: ["e"], ει: ["i"], οι: ["y"], υι: ["y"],
  ου: ["u"], ωυ: ["o", "u"] };
const KOINE_C = { β: "v", γ: "ɣ", δ: "ð", ζ: "z", θ: "θ", κ: "k", λ: "l", μ: "m", ν: "n", ξ: ["k", "s"], π: "p", ρ: "r", σ: "s",
  τ: "t", φ: "f", χ: "x", ψ: ["p", "s"] };
const frontStart = (u) => u && u.v && /^(ε|η|ι|υ|αι|ει|οι|υι)/.test(u.v);

/** How the app teaches a Greek word to sound: system "erasmian" | "koine". */
function greekExpected(word, system) {
  const U = gUnits(gLetters(word));
  const ph = [];
  const er = system === "erasmian";
  U.forEach((u, i) => {
    const next = U[i + 1];
    if (u.v) {
      if (er && u.rough && !ph.length) ph.push({ p: "h" }); // only at the start of a word
      if (!er && /^[αεη]υ$/.test(u.v)) { // Koine αυ ευ ηυ: av/ev before a voiced sound, af/ef before a voiceless one or at the end
        ph.push({ p: u.v[0] === "α" ? "a" : "e", s: u.acc, nuc: true });
        ph.push({ p: !next || (next.c && VOICELESS.test(next.c)) ? "f" : "v" });
        return;
      }
      const main = er && u.v === "υι" ? 1 : 0; // "wee": the w glides into the i
      (er ? ERASMIAN_V : KOINE_V)[u.v].forEach((p, k) => ph.push({ p, s: k === main && u.acc, nuc: k === main }));
      return;
    }
    const c = u.c;
    if (c === "γ" && next && next.c && /[γκχξ]/.test(next.c)) { ph.push({ p: "ŋ" }); return; }
    if (c === "γ" && i && U[i - 1].c === "γ") { ph.push({ p: "g" }); return; } // γγ: ng-g in both
    if (!er && c === "γ" && frontStart(next)) { ph.push({ p: "ʝ" }); return; }
    if (!er && c === "σ" && next && next.c && /[βγδμ]/.test(next.c)) { ph.push({ p: "z" }); return; }
    const m = (er ? ERASMIAN_C : KOINE_C)[c];
    [].concat(m).forEach((p) => ph.push({ p }));
  });
  return ph;
}

// ================================================================ Greek: what a Modern Greek voice says
const MG_VOICED = /[βγδμνλρ]/;
/** Modern Greek letters (monotonic, as the app gives the voice) → the sounds an el-GR voice makes. */
function modernGreek(word) {
  const L = [];
  for (const c of String(word).normalize("NFD").toLowerCase()) {
    if (c === "́") { if (L.length) L[L.length - 1].acc = true; continue; }
    if (c === "̈") { if (L.length) L[L.length - 1].dia = true; continue; }
    if (/[̀-ͯ]/.test(c)) continue;
    if (G_VOWELS.includes(c) || /[βγδζθκλμνξπρσςτφχψ]/.test(c)) L.push({ ch: c === "ς" ? "σ" : c });
  }
  const ph = [];
  const isV = (x) => x && G_VOWELS.includes(x.ch);
  // the sound a vowel letter (or pair) starts with, to decide γ → ʝ and the glide rule
  const front = (i) => { const a = L[i], b = L[i + 1]; if (!a || !isV(a)) return false; if (/[εηιυ]/.test(a.ch)) return !(a.ch === "υ" && false); if ((a.ch === "α" || a.ch === "ο") && b && b.ch === "ι" && !b.dia && !a.acc) return true; if (a.ch === "ε" && b && b.ch === "ι") return true; return false; };
  for (let i = 0; i < L.length; i++) {
    const a = L[i], b = L[i + 1], c2 = L[i + 2];
    const start = i === 0;
    if (isV(a)) {
      // ιου: Modern Greek's "yu" (how it writes ü in foreign names)
      if (a.ch === "ι" && !a.acc && b && b.ch === "ο" && !b.acc && c2 && c2.ch === "υ" && !c2.dia) {
        if (a.dia && L[i - 1] && isV(L[i - 1])) ph.push({ p: "i" }, { p: "u", s: !!c2.acc }); // εϊου: i then u after the e
        else ph.push({ p: "ju", s: !!c2.acc });
        i += 2;
        continue;
      }
      const pairable = b && isV(b) && !b.dia && !a.acc;
      if (pairable && ["αι", "ει", "οι", "υι", "ου"].includes(a.ch + b.ch)) {
        ph.push({ p: { αι: "e", ει: "i", οι: "i", υι: "i", ου: "u" }[a.ch + b.ch], s: !!b.acc });
        i++;
        continue;
      }
      if (pairable && ["αυ", "ευ", "ηυ"].includes(a.ch + b.ch)) {
        ph.push({ p: { α: "a", ε: "e", η: "i" }[a.ch], s: !!b.acc });
        const n = L[i + 2];
        ph.push({ p: !n || (!isV(n) && VOICELESS.test(n.ch)) ? "f" : "v" });
        i++;
        continue;
      }
      let p = { α: "a", ε: "e", η: "i", ι: "i", ο: "o", υ: "i", ω: "o" }[a.ch];
      // an unstressed i-sound after a consonant and before a vowel glides into it (καρδιά): synizesis
      const prev = L[i - 1];
      if (p === "i" && !a.acc && !a.dia && prev && !isV(prev) && b && isV(b)) p = "j̯";
      ph.push({ p, s: !!a.acc });
      continue;
    }
    const n = b;
    const pair = n ? a.ch + n.ch : "";
    if (pair === "μπ") { if (!start) ph.push({ p: "m" }); ph.push({ p: "b" }); i++; continue; }
    if (pair === "ντ") { if (!start) ph.push({ p: "n" }); ph.push({ p: "d" }); i++; continue; }
    if (pair === "γκ") { if (!start) ph.push({ p: "ŋ" }); ph.push({ p: "g" }); i++; continue; }
    if (pair === "γγ") { ph.push({ p: "ŋ" }, { p: "g" }); i++; continue; }
    if (pair === "γχ" || pair === "γξ") { ph.push({ p: "ŋ" }); continue; }
    if (pair === "τζ") { ph.push({ p: "d" }, { p: "z" }); i++; continue; }
    if (pair === "τσ") { ph.push({ p: "t" }, { p: "s" }); i++; continue; }
    if (n && n.ch === a.ch) continue; // double letters are said once
    if (a.ch === "γ") { ph.push({ p: front(i + 1) ? "ʝ" : "ɣ" }); continue; }
    if (a.ch === "σ") { ph.push({ p: n && !isV(n) && MG_VOICED.test(n.ch) ? "z" : "s" }); continue; }
    const m = { β: "v", δ: "ð", ζ: "z", θ: "θ", κ: "k", λ: "l", μ: "m", ν: "n", ξ: ["k", "s"], π: "p", ρ: "r", τ: "t", φ: "f", χ: "x", ψ: ["p", "s"] }[a.ch];
    [].concat(m).forEach((p) => ph.push({ p }));
  }
  return ph;
}

// ================================================================ Greek: naming the differences
// Known limits: differences a Modern Greek voice can't avoid, whatever it is given. Each carries the reason it is
// accepted; anything not listed here is an error.
const LIMITS = {
  "rough breathing h not said": "Modern Greek has no h; writing χ would give a harsh kh instead (Erasmian only).",
  "nt said nd, mp said mb, nk said ng": "Modern Greek voices a stop after a nasal (πάντα → panda); no spelling avoids it.",
  "σ said z before a voiced consonant": "Modern Greek voices σ there (κόσμος → kozmos); no spelling avoids it (Erasmian only).",
  "b, d, g respelt μπ ντ γκ: a nasal may be heard (mb, nd, ng)": "The only Modern Greek spellings of b, d, g; inside a word some voices add the nasal (Erasmian only).",
  "σ said z before λ ν ρ": "Modern Greek voices σ before any voiced consonant (Ἰσραήλ izra-EL); the guide gives z before β γ δ μ, and no spelling avoids it before λ ν ρ (Restored Koine).",
  "ü said i-u after a vowel": "After a vowel, ü is written ϊου so it isn't swallowed into a vowel pair (θεοί → θεϊού); Modern Greek says i-u (Restored Koine).",
  "double consonant said once": "Modern Greek says double letters once (ἐκκλησία → ek-li-…).",
  "υ said oo": "The Letters guide allows it for Erasmian: “ü as in French tu (or simply oo)”.",
  "ü said yu": "Modern Greek has no ü; ιου (yu) is how Greek writes ü in foreign names (Restored Koine).",
  "unstressed ι glides before a vowel": "A Modern voice may run ι into the next vowel (κύριος KÜ-ryos); no Modern spelling marks the gap.",
  "one-syllable word stressed": "A one-syllable word keeps a stress mark so έι stays one sound; it changes nothing heard.",
};

const nextP0 = (pairs, k) => { const x = pairs[k + 1]; return x && !x[0] && x[1] ? x[1].p : ""; };
function classify(exp, got, pairs, k, system, word) {
  const e = exp && exp.p, g = got && got.p;
  const nextE = (pairs[k + 1] || [])[0], prevE = (pairs[k - 1] || [])[0];
  if (e === "h" && !g) return "rough breathing h not said";
  if ((e === "t" && g === "d") || (e === "p" && g === "b") || (e === "k" && g === "g")) {
    if (prevE && /^[nmŋ]$/.test(prevE.p)) return "nt said nd, mp said mb, nk said ng";
  }
  if (e === "s" && g === "z" && system === "erasmian") return "σ said z before a voiced consonant";
  if (e === "s" && g === "z" && system === "koine" && nextE && /^[lnr]$/.test(nextE.p)) return "σ said z before λ ν ρ";
  if (system === "koine" && e === "y" && g === "i" && nextP0(pairs, k) === "u") return "ü said i-u after a vowel";
  if (system === "koine" && !e && g === "u" && pairs[k - 1] && pairs[k - 1][0] && pairs[k - 1][0].p === "y") return "ü said i-u after a vowel";
  if (system === "koine" && !e && g === "i" && (pairs[k + 1] || [])[0] && pairs[k + 1][0].p === "y" && pairs[k + 1][1] && pairs[k + 1][1].p === "u") return "ü said i-u after a vowel";
  if (system === "koine" && e === "y" && g === "u" && pairs[k - 1] && !pairs[k - 1][0] && pairs[k - 1][1] && pairs[k - 1][1].p === "i") return "ü said i-u after a vowel";
  const nextGot = (pairs.slice(k + 1).find((x) => x[1]) || [])[1];
  if (!e && /^[mnŋ]$/.test(g) && nextGot && /^[bdg]$/.test(nextGot.p) && system === "erasmian") return "b, d, g respelt μπ ντ γκ: a nasal may be heard (mb, nd, ng)";
  if (e && !g && !VOWEL.test(e) && ((prevE && prevE.p === e) || (nextE && nextE.p === e) || /([βγδζθκλμνξπρστφχψ])\1/.test(String(word).normalize("NFD").toLowerCase().replace(/[\u0300-\u036f]/g, "")))) return "double consonant said once";
  if (e === "y" && g === "u" && system === "erasmian") return "υ said oo";
  if (e === "y" && g === "ju" && system === "koine") return "ü said yu";
  if (e === "i" && g === "j̯") return "unstressed ι glides before a vowel";
  if (e === "i" && !g && (pairs[k + 1] || [])[1] && pairs[k + 1][1].p === "ju") return "unstressed ι glides before a vowel"; // διϋλίζω
  if (e === "y" && g === "ju" && system === "erasmian" && prevE && prevE.p === "i" && pairs[k - 1] && !pairs[k - 1][1]) return "unstressed ι glides before a vowel";
  // ι then ου heard as one glide + u ("ju"): the same gliding
  const nextP = pairs[k + 1] || [], prevP = pairs[k - 1] || [];
  if (e === "i" && !g && nextP[0] && nextP[0].p === "u" && nextP[1] && nextP[1].p === "ju") return "unstressed ι glides before a vowel";
  if (e === "u" && g === "ju" && prevP[0] && prevP[0].p === "i" && !prevP[1]) return "unstressed ι glides before a vowel";
  if (e === "i" && g === "ju" && nextP[0] && nextP[0].p === "u" && !nextP[1]) return "unstressed ι glides before a vowel";
  if (e === "u" && !g && prevP[0] && prevP[0].p === "i" && prevP[1] && prevP[1].p === "ju") return "unstressed ι glides before a vowel";
  return `${e || "∅"} heard as ${g || "∅"}`;
}

/** Compare one Greek word: returns [{cat, word, exp, got}] (stress problems included). */
function compareGreek(word, system) {
  const voice = system === "erasmian" ? S.erasmianSpeech(word) : S.koineSpeech(word);
  const exp = greekExpected(word, system);
  const got = modernGreek(voice);
  if (!exp.length) return [];
  const pairs = align(exp, got);
  const found = [];
  pairs.forEach(([e, g], k) => {
    if (e && g && e.p === g.p) return;
    // palatal variants of the same consonant before e/i are the same sound to a listener
    if (e && g && e.p === "g" && g.p === "ʝ") return found.push({ cat: `${e.p} heard as ${g.p}`, word, voice, exp, got });
    found.push({ cat: classify(e, g, pairs, k, system, word), word, voice, exp, got });
  });
  // stress: every accented vowel is the one the voice stresses, and the voice stresses no other
  const syllables = exp.filter((x) => x.nuc).length;
  for (const [e, g] of pairs) {
    if (e && e.s && !(g && g.s)) found.push({ cat: "stress lost or moved", word, voice, exp, got });
    if (g && g.s && !(e && e.s)) {
      if (syllables <= 1) found.push({ cat: "one-syllable word stressed", word, voice, exp, got });
      else found.push({ cat: "stress on the wrong syllable", word, voice, exp, got });
    }
  }
  return found;
}

// ================================================================ Greek: the respelling the app shows (Erasmian)
const RESPELL = [["ayoo", ["e", "i", "u"]], ["wee", ["u", "i"]], ["ay", ["e", "i"]], ["ai", ["a", "i"]], ["oi", ["o", "i"]], ["oo", ["u"]],
  ["ow", ["a", "u"]], ["eu", ["e", "u"]], ["ee", ["i"]], ["oh", ["o"]], ["kh", ["x"]], ["th", ["θ"]], ["ps", ["p", "s"]],
  ["dz", ["d", "z"]], ["ng", ["ŋ"]], ["x", ["k", "s"]], ["ü", ["y"]], ["f", ["f"]], ["h", ["h"]]];
function respellingSounds(say) {
  const ph = [];
  say.split(/\s+/).filter(Boolean).forEach((wd) => wd.split("-").forEach((syl) => {
    const stressed = syl !== syl.toLowerCase();
    let s = syl.toLowerCase(), first = true;
    while (s) {
      const hit = RESPELL.find(([k]) => s.startsWith(k));
      const [k, sounds] = hit || [s[0], [s[0]]];
      const main = k === "wee" ? 1 : 0; // "wee": the stress is on its i
      sounds.forEach((p, q) => { const v = VOWEL.test(p); ph.push({ p, s: stressed && v && first && q >= main }); if (v && q >= main) first = false; });
      s = s.slice(k.length);
    }
  }));
  // n before k, g or kh is the ng sound (en-ka, ANG-ge-los)

  return ph;
}

// ================================================================ Hebrew: what it should sound like (academic)
const H = {
  SHEWA: "ְ", HSEGOL: "ֱ", HPATAH: "ֲ", HQAMATS: "ֳ", HIRIQ: "ִ", TSERE: "ֵ", SEGOL: "ֶ",
  PATAH: "ַ", QAMATS: "ָ", HOLAM: "ֹ", HOLAMV: "ֺ", QIBBUTS: "ֻ", DAGESH: "ּ", METEG: "ֽ",
  RAFE: "ֿ", QQATAN: "ׇ",
};
const ACCENT = /[֑-֯]/;
// accents not written on the stressed syllable: pashta, segolta, zarqa, telisha qetanna (after it); telisha gedola,
// yetiv (before it). Words carrying only these leave the stress unknown.
const OFF_STRESS = /[֚֭֮֙֒֩֠]/; // + dehi, before it in the poetic books
const LETTER = /[א-ת]/;
const GUTTURAL = /[אהחע]/;
const BGDKPT = /[בגדכךפףת]/;

/** A pointed word → clusters { ch, marks } (a letter and everything written on it). */
function hClusters(word) {
  const out = [];
  for (const c of String(word).replace(/\//g, "")) {
    if (LETTER.test(c)) out.push({ ch: c, m: "" });
    else if (out.length && /[֑-ׇ]/.test(c)) out[out.length - 1].m += c;
  }
  return out;
}
const vowelOf = (m) => {
  if (m.includes(H.QQATAN)) return "o";
  if (m.includes(H.HIRIQ) && (m.includes(H.PATAH) || m.includes(H.QAMATS))) return "ai"; // יְרוּשָׁלִַם: a, then (y)i
  for (const [mk, v] of [[H.HSEGOL, "e"], [H.HPATAH, "a"], [H.HQAMATS, "o"], [H.HIRIQ, "i"], [H.TSERE, "e"], [H.SEGOL, "e"], [H.PATAH, "a"],
    [H.QAMATS, "a"], [H.HOLAM, "o"], [H.HOLAMV, "o"], [H.QIBBUTS, "u"]]) if (m.includes(mk)) return v;
  return "";
};
const has = (c, mk) => !!c && c.m.includes(mk);

/**
 * Per cluster: { cons, vowel, said } for a Hebrew word, the academic way the app teaches it. joined: the word ends
 * in a maqqef (so it has no stress of its own). Returns { vowels: ["e", "a", …] in order, notes }.
 */
function hebrewExpected(word, joined, verb, form) {
  const C = hClusters(word);
  if (!C.length) return { vowels: [], cons: "" };
  // matres lectionis: letters standing for a vowel, not a consonant
  const role = C.map(() => "c");
  C.forEach((c, i) => {
    const prev = C[i - 1];
    const own = vowelOf(c.m) || has(c, H.SHEWA);
    if (c.ch === "ו" && i > 0 && !own && (has(c, H.HOLAM) || has(c, H.DAGESH)) && !(prev && (vowelOf(prev.m) && !has(prev, H.SHEWA) && has(c, H.DAGESH) && false))) {
      // וֹ holam vav, וּ shureq (a vav with a dagesh and no vowel, after a letter without a vowel of its own)
      if (has(c, H.HOLAM)) role[i] = "o";
      else if (prev && !vowelOf(prev.m) && !has(prev, H.SHEWA)) role[i] = "u";
    }
    if (c.ch === "ו" && i === 0 && has(c, H.DAGESH) && !own) role[i] = "u"; // the conjunction וּ
    if (c.ch === "י" && !own && !has(c, H.DAGESH) && prev && /[ִֵֶ]/.test(prev.m)) role[i] = "m"; // ִי ֵי ֶי
    if (c.ch === "א" && !own && !has(c, H.DAGESH) && !(C[i + 1] && C[i + 1].ch === "ו" && !vowelOf(C[i + 1].m) && /[ֹּ]/.test(C[i + 1].m))) role[i] = "m"; // quiescent א (not before וּ / וֹ)
    if (c.ch === "ה" && i === C.length - 1 && !own && !has(c, H.DAGESH)) role[i] = "m"; // final ה without mappiq
    if (c.ch === "ו" && !own && !has(c, H.DAGESH) && prev && has(prev, H.HOLAM) && i === C.length - 1) role[i] = "m";
  });
  const cons = C.map((c, i) => (role[i] === "c" ? c.ch : "")).join("");
  // the stressed cluster, from the accents
  let stress = -1;
  C.forEach((c, i) => { if (ACCENT.test(c.m) && !OFF_STRESS.test(c.m)) stress = Math.max(stress, i); });
  if (stress < 0 && C.some((c) => OFF_STRESS.test(c.m))) stress = -2; // unknown
  const consIdx = C.map((c, i) => i).filter((i) => role[i] === "c");
  const lastCons = consIdx[consIdx.length - 1];
  // a vowel's "length" for the shewa after it
  const longBefore = (i) => {
    // the vowel sound just before cluster i: look back past matres and quiescent letters
    for (let k = i - 1; k >= 0; k--) {
      if (role[k] === "o" || role[k] === "u") return { long: true, meteg: false };
      if (role[k] === "m") continue;
      const c = C[k];
      if (has(c, H.SHEWA) && !vowelOf(c.m)) return { long: false, shewa: true };
      const v = vowelOf(c.m);
      const meteg = has(c, H.METEG);
      const yod = C[k + 1] && role[k + 1] === "m" && C[k + 1].ch === "י";
      const long = has(c, H.TSERE) || has(c, H.HOLAM) || has(c, H.HOLAMV) || (has(c, H.HIRIQ) && yod) || (has(c, H.QAMATS) && meteg);
      return { long, meteg, v };
    }
    return null;
  };
  const said = C.map(() => false);
  const maybe = C.map(() => false); // a shewa after a qamets with no meteg: said after qamets (qa-te-LU), silent after qamets hatuf (chokh-MAH)
  C.forEach((c, i) => {
    if (!has(c, H.SHEWA) || role[i] !== "c") return;
    if (i === lastCons) return; // a shewa at the end of a word is silent
    // before a final quiescent letter (אַרְתַּחְשַׁסְתְּא) it is also the end of the word
    if (consIdx.indexOf(i) === consIdx.length - 1) return;
    if (i === consIdx[0]) { said[i] = true; return; }
    const before = longBefore(i);
    const next = C[consIdx[consIdx.indexOf(i) + 1]];
    const doubled = has(c, H.DAGESH) && before && !before.shewa && (!BGDKPT.test(c.ch) || before.v || before.long);
    if (GUTTURAL.test(c.ch)) return; // a throat letter's plain shewa is silent (a said one would be hateph)
    if (before && before.shewa) { said[i] = true; return; } // the second of two
    if (before && before.long) { said[i] = true; return; } // after a long vowel (qamets only with its meteg)
    if (before && before.v === "a" && C.slice(0, i).reverse().find((x, k) => role[i - 1 - k] === "c" && vowelOf(x.m)).m.includes(H.QAMATS)) {
      if (form === "p") said[i] = true; // a Qal perfect: sha-me-RU
      else if (form !== "v" && form !== "c") maybe[i] = true; // (imperative, infinitive: shom-RE-ni, silent)
    }
    if (doubled) { said[i] = true; return; }
    if (next && next.ch === c.ch) { said[i] = true; return; } // before the same letter
  });
  // qamets or qamets hatuf
  const vowels = [];
  const ki = C.findIndex((c) => c.ch === "כ" && c.m.includes(H.QAMATS));
  const isKol = ki >= 0 && ki <= 2 && C.length === ki + 2 && C[ki + 1].ch === "ל" && C.slice(0, ki).every((c, i) => (role[i] === "c" || (i === 0 && role[i] === "u")) && /[ובכלמהש]/.test(c.ch)) && (joined || !ACCENT.test(C[ki].m + C[ki + 1].m) || true);
  C.forEach((c, i) => {
    if (role[i] === "o") { vowels.push({ p: "o" }); return; }
    if (role[i] === "u") { vowels.push({ p: "u" }); return; }
    if (role[i] !== "c") return;
    if (has(c, H.SHEWA) && !vowelOf(c.m)) { if (said[i]) vowels.push({ p: "e" }); else if (maybe[i]) vowels.push({ p: "e", opt: true }); return; }
    let v = vowelOf(c.m);
    if (!v) return;
    if (isKol && c.ch === "כ" && c.m.includes(H.QAMATS)) { vowels.push({ p: "o" }); return; } // כָּל is always kol
    if (c.m.includes(H.QAMATS) && !c.m.includes(H.QQATAN)) {
      const ni = consIdx[consIdx.indexOf(i) + 1];
      const next = C[ni];
      const unstressed = stress >= 0 ? stress !== i : joined;
      const closedBySilentShewa = next && has(next, H.SHEWA) && !vowelOf(next.m) && !said[ni] && ni !== lastCons;
      const beforeHatefQamets = next && has(next, H.HQAMATS);
      const finalClosed = ni === lastCons && next && !vowelOf(next.m) && !(role[ni + 1] === "m" || role[ni + 1] === "u" || role[ni + 1] === "o") && i !== lastCons;
      // a closed syllable that isn't stressed is short: before a silent shewa, or the last syllable of a word joined by
      // maqqef or stressed earlier. In the last syllable that holds for verbs (va-YA-mot, ze-khor-, yish-mor-); a
      // noun keeps a long qamets there (A-dam, ha-am-, yam-), and a noun joined by maqqef may go either way (choq-, dat-)
      const article = i === 0 && /[בכלה]/.test(c.ch); // בָּ כָּ לָ הָ: the article (בָּאֳנִי)
      const beforeThroatShewa = next && GUTTURAL.test(next.ch) && has(next, H.SHEWA) && !vowelOf(next.m) && ni !== lastCons;
      if (verb && joined && finalClosed) v = "o"; // זְכָר־ ze-khor, also with a conjunctive accent (שְׁמָ֨ר־)
      else if (finalClosed && unstressed && (joined || stress >= 0)) {
        if (verb) v = "o";
        else if (joined) { vowels.push({ p: "a", alt: ["o"] }); return; }
      } else if (!has(c, H.METEG) && unstressed && closedBySilentShewa) v = "o";
      if (beforeHatefQamets && !article) v = "o";
      if (beforeThroatShewa && !has(c, H.METEG) && stress !== i) v = "o"; // רָחְבּוֹ roch-BO
      // before a shewa with no meteg the qamets may be either: only the word's grammar tells (qa-te-LU / chokh-MAH)
      if (closedBySilentShewa && maybe[ni] && !has(c, H.METEG) && stress !== i) { vowels.push({ p: "a", alt: ["o"] }); return; }
      if ((form === "v" || form === "c") && next && has(next, H.SHEWA) && !vowelOf(next.m) && ni !== lastCons && !has(c, H.METEG) && stress !== i) v = "o";
    }
    // furtive patah on a final ח, ע or הּ: said before the letter (order doesn't change the vowel list)
    if (v === "ai") { vowels.push({ p: "a" }, { p: "i" }); return; }
    vowels.push({ p: v });
  });
  return { vowels, cons, said, stress };
}

const vShow = (V) => V.map((x) => x.p + (x.alt ? "/" + x.alt.join("/") : "") + (x.opt ? "?" : "")).join(" ");

// ================================================================ Hebrew: what an Israeli voice says
/** Pointed text as given to the voice → the vowels an Israeli Hebrew voice says (it reads qamets as a, a shewa as nothing). */
function israeliVowels(word) {
  const C = hClusters(word);
  const vowels = [];
  C.forEach((c, i) => {
    const prev = C[i - 1];
    const own = vowelOf(c.m) || has(c, H.SHEWA);
    if (c.ch === "ו" && !own && has(c, H.HOLAM)) { vowels.push("o"); return; }
    if (c.ch === "ו" && !own && has(c, H.DAGESH) && (!prev || (!vowelOf(prev.m) && !has(prev, H.SHEWA)))) { vowels.push("u"); return; }
    if (has(c, H.SHEWA) && !vowelOf(c.m)) return; // the voice leaves a plain shewa silent
    const v = vowelOf(c.m);
    if (v) vowels.push(v);
  });
  return vowels;
}

// ================================================================ collecting what the app says
const problems = new Map(); // category → { n, examples }
const limits = new Map();
const note = (map, cat, ex) => { const r = map.get(cat) || { n: 0, ex: [] }; r.n++; if (r.ex.length < EXAMPLES) r.ex.push(ex); map.set(cat, r); };

// ---- debugging a word: node tools/check_pronunciation.mjs say λόγος בְּרֵאשִׁית
if (argv[0] === "say") {
  for (const w of argv.slice(1)) {
    if (/[א-ת]/.test(w)) {
      const exp = hebrewExpected(w, /־$/.test(w));
      const v = S.hebrewSpeech(w);
      console.log(`${w}  expected vowels ${vShow(exp.vowels)}  voice text ${v}  heard ${israeliVowels(v.replace(/[,.]/g, "")).join(" ")}`);
    } else {
      for (const sys of ["erasmian", "koine"]) {
        const f = compareGreek(w, sys);
        console.log(`${w} ${sys}: expected ${show(greekExpected(w, sys))} | voice ${sys === "erasmian" ? S.erasmianSpeech(w) : S.koineSpeech(w)} | heard ${show(modernGreek(sys === "erasmian" ? S.erasmianSpeech(w) : S.koineSpeech(w)))}`);
        f.forEach((x) => console.log("   - " + x.cat));
      }
      console.log(`   shown: ${S.greekSay(w)} → ${show(respellingSounds(S.greekSay(w)))}`);
    }
  }
  process.exit(0);
}

let nGreek = 0, nHebrew = 0, nVerses = 0;

// ---- Greek words: every NT form, every Septuagint form, every headword, lessons and Letters
const greekWords = new Set();
const gWord = (t) => String(t || "").replace(/[⟦⟧\[\]()]/g, "").split(/[\s·,;.]+/).filter((w) => /[Ͱ-Ͽἀ-῿]/.test(w)).forEach((w) => greekWords.add(w.replace(/[,.;·:!?’'᾽ʼ“”]+$/g, "")));
const ntBooks = fs.readdirSync(R + "data/gnt").map((f) => json("data/gnt/" + f));
ntBooks.forEach((B) => B.ch.forEach(([, vs]) => vs.forEach((v) => v[1].forEach((w) => gWord(w[0])))));
for (const f of fs.readdirSync(R + "data/lex/G")) Object.values(json("data/lex/G/" + f)).forEach((e) => gWord(String(e[0] || "").split(",")[0]));
for (const f of fs.readdirSync(R + "data/lxx/text")) {
  const go = (o) => { if (typeof o === "string") gWord(o); else if (o && typeof o === "object") Object.values(o).forEach(go); };
  go(json("data/lxx/text/" + f));
}
const walk = (o, fn) => { if (Array.isArray(o)) o.forEach((x) => walk(x, fn)); else if (o && typeof o === "object") for (const [k, v] of Object.entries(o)) { if (typeof v === "string" && ["t", "text"].includes(k)) fn(v); else walk(v, fn); } };
for (const f of fs.readdirSync(R + "lessons/grc")) walk(json("lessons/grc/" + f), (t) => { if (!/^(\S{1,2}\s?)+$/u.test(t.normalize("NFC"))) gWord(t); });
const GA = json("lessons/alphabet/grc.json");
GA.letters.forEach((L) => [L.nameT, L.example.t].forEach(gWord));

for (const w of greekWords) {
  if (/[’'᾽ʼ]$/.test(w) || !/[Ͱ-Ͽἀ-῿]/.test(w)) continue; // elided words are checked in their verses
  const letters = gLetters(w);
  if (!letters.length || letters.every((x) => !G_VOWELS.includes(x.ch))) continue; // numerals and letter names
  nGreek++;
  for (const sys of ["erasmian", "koine"]) {
    for (const f of compareGreek(w, sys)) {
      const ex = `${w} → ${f.voice}: expected ${show(f.exp)}, heard ${show(f.got)}`;
      note(LIMITS[f.cat] ? limits : problems, `${sys === "erasmian" ? "Erasmian" : "Restored Koine"}: ${f.cat}`, ex);
    }
  }
  // the respelling the app shows must match how the word is taught (Erasmian)
  const shown = respellingSounds(S.greekSay(w));
  const exp = greekExpected(w, "erasmian").map((x) => ({ ...x }));
  const firstStress = exp.findIndex((x) => x.s);
  exp.forEach((x, i) => { if (i !== firstStress) x.s = false; });
  [exp, shown].forEach((ph) => ph.forEach((x, i) => { if (x.p === "ŋ" && ph[i + 1] && /^[kx]$/.test(ph[i + 1].p)) x.p = "n"; }));
  const pairs = align(exp, shown);
  const off = pairs.filter(([e, g]) => !(e && g && e.p === g.p));
  if (off.length) note(problems, "Shown pronunciation (Erasmian respelling) differs from the guide", `${w}: shown ${S.greekSay(w)} = ${show(shown)}, guide ${show(exp)}`);
  if (pairs.some(([e, g]) => e && g && !!e.s !== !!g.s) && exp.filter((x) => x.nuc).length > 1) note(problems, "Shown pronunciation stresses the wrong syllable", `${w}: shown ${S.greekSay(w)}`);
}

// ---- Hebrew words: every OT word as a tap gives it, headwords, lists, lessons, Letters
const otBooks = fs.readdirSync(R + "data/hot").map((f) => json("data/hot/" + f));
const heSeen = new Map();
const isVerb = (code) => /(^[HA]|\/)V/.test(String(code || ""));
const heWord = (t, joined, where, w) => {
  const key = t + (joined ? "־" : "") + (isVerb(w[4]) ? "\u0001" : "");
  if (heSeen.has(key)) return;
  heSeen.set(key, { where, verb: isVerb(w[4]), w, text: t + (joined ? "־" : "") });
};
otBooks.forEach((B) => B.ch.forEach(([c, vs]) => vs.forEach((v) => v[1].forEach((w) => heWord(heText(w), heJoined(w[5]), `${B.id} ${c}:${v[0]}`, w)))));
const heParts = [];
for (const [, info] of heSeen) {
  const key = info.text;
  // a source word can hold a paseq and a space, or a maqqef: check each part on its own
  const parts = key.replace(/[׀׃]/g, " ").split(/\s+/).filter(Boolean)
    .flatMap((t) => { const ps = t.split("־"); return ps.map((x, i) => [x, i < ps.length - 1]); }).filter(([x]) => x);
  parts.forEach(([x, j]) => heParts.push([x + (j ? "־" : ""), info]));
}
for (const [key, { where, verb, w: dw }] of heParts) {
  const joined = key.endsWith("־");
  const word = joined ? key.slice(0, -1) : key;
  if (!/[ְ-ׇ]/.test(word)) continue; // unpointed (paragraph letters, ketiv-only)
  nHebrew++;
  const qal = String(dw && dw[4] || "").match(/(?:^[HA]|\/)Vq([pvc])/);
  const exp = hebrewExpected(word, joined, verb, qal ? qal[1] : "");
  // the voice text the app makes for this word (audio.heVoice knows its grammar), then the Israeli voice reading it
  const voice = S.hebrewSpeech(heVoice ? heVoice(dw, word, joined) + (joined ? "־" : "") : key).replace(/[,.]/g, "");
  if (/אֲדֹנָי|אֱלֹהִים/.test(voice) && !/אֲדֹנָי|אֱלֹהִים/.test(word.replace(/[֑-ֽֿ֯]/g, ""))) continue; // the divine name
  const heard = voice.split(" ").flatMap(israeliVowels);
  // spellings the scribes read differently (perpetual qere) must reach the voice as they are read
  if (/ִוא(\s|$)/.test(voice)) note(problems, "Hebrew: הִוא handed to the voice as written (read hi)", `${word} (${where}) → ${voice}`);
  if (/ִ[ַָ]|[ַָ]ִ/.test(voice)) note(problems, "Hebrew: two vowels on one letter handed to the voice (read a-yi)", `${word} (${where}) → ${voice}`);
  if (/[ְ-ׇ]ש[א-ת]/.test(voice)) note(problems, "Hebrew: a silent unpointed ש handed to the voice", `${word} (${where}) → ${voice}`);
  const pairs = align(exp.vowels, heard.map((p) => ({ p })));
  for (const [e, g] of pairs) {
    if (e && g && (e.p === g.p || (e.alt && e.alt.includes(g.p)))) continue;
    if (e && e.opt && !g) continue;
    const cat = e && e.p === "e" && !g ? "said shewa left silent"
      : !e && g && g.p === "e" ? "silent shewa said"
      : e && g && e.p === "o" && g.p === "a" ? "qamets hatuf (o) read as a"
      : e && g && e.p === "a" && g.p === "o" ? "qamets read o where it is a"
      : `${e ? e.p : "∅"} heard as ${g ? g.p : "∅"}`;
    note(problems, `Hebrew: ${cat}`, `${word}${joined ? "־" : ""} (${where}) → ${voice}: expected ${vShow(exp.vowels)}, heard ${heard.join(" ")}`);
  }
}

// ---- Hebrew shown pronunciations: the review lists' and lessons' "say" against the model (vowels)
// a respelling's vowels: ay/ai, ei, oi, ui are a vowel + yod (CHAI, BAYit), so the i isn't a vowel of its own
const sayVowels = (say) => String(say).toLowerCase().replace(/ch|kh|sh|ts/g, "c").replace(/([aeou])[iy](?=$|[^aeiou]|-)/g, "$1").match(/[aeiou]/g) || [];
const deck = json("data/decks/hebrew.json").words;
deck.forEach((d) => {
  if (!d[4] || /a-do-nai/i.test(d[4])) return;
  const exp = String(d[1]).split("־").flatMap((part, i, all) => hebrewExpected(part, i < all.length - 1).vowels);
  const shown = sayVowels(d[4]).map((p) => ({ p }));
  const bad = align(exp, shown).some(([e, g]) => !(e && g && (e.p === g.p || (e.alt && e.alt.includes(g.p)))) && !(e && e.opt && !g));
  if (bad) note(problems, "Hebrew list: shown pronunciation differs from the model", `${d[1]}: shown ${d[4]} (${shown.map((x) => x.p).join(" ")}), model ${vShow(exp)}`);
});

// ---- Hebrew: what Listen says on a card = the pronunciation the card shows (lists, lesson words, Letters examples)
const heCards = [];
deck.forEach((d) => d[4] && !/a-do-nai|e-lo-him/i.test(d[4]) && heCards.push(["list", d[1], d[4], d[0]]));
for (const f of fs.readdirSync(R + "lessons/he")) walk(json("lessons/he/" + f), () => {});
const walkSay = (o, where) => { if (Array.isArray(o)) o.forEach((x) => walkSay(x, where)); else if (o && typeof o === "object") { if (typeof o.t === "string" && typeof o.say === "string" && /[א-ת]/.test(o.t) && !/a-do-nai|e-lo-him/i.test(o.say)) heCards.push([where, o.t, o.say, o.k || ""]); Object.values(o).forEach((v) => walkSay(v, where)); } };
for (const f of fs.readdirSync(R + "lessons/he")) walkSay(json("lessons/he/" + f), "lesson he-" + f.replace(".json", ""));
walkSay(json("lessons/alphabet/he.json"), "Letters guide");
for (const [where, t, say] of heCards) {
  if (/\s/.test(t.trim()) || /־/.test(t)) continue; // phrases: their respellings join words
  const heard = israeliVowels(S.hebrewSpeech((S.hebrewForSay || ((x) => x))(t, say)).replace(/[,.]/g, "")).map((p) => ({ p })); // as the app's Listen gives it
  const shown = sayVowels(say).map((p) => ({ p }));
  if (heard.map((x) => x.p).join("") !== shown.map((x) => x.p).join("")) note(problems, "Hebrew: Listen doesn't say what the card shows", `${where}: ${t} shows ${say} (${shown.map((x) => x.p).join(" ")}), Listen says ${heard.map((x) => x.p).join(" ")}`);
}

// ---- Hebrew: the stress the cards show (capital syllable) = the accent the word carries in the Bible text
// Checked by hand and right as shown, with the reason:
const STRESS_OK = {
  "בָּקַע": "a verb: ba-KA, like every Qal perfect; its few occurrences have the stress drawn back before a stressed word",
};
const stressFromEnd = new Map(); // form without accents → Counter of "syllables from the end" of the accented vowel
const plainHe = (t) => String(t).replace(/[֑-ֽֿ֯\/]/g, "");
otBooks.forEach((B) => B.ch.forEach(([, vs]) => vs.forEach((v) => v[1].forEach((w) => {
  const t = heText(w);
  if (/[\s־׀]/.test(t) || heJoined(w[5])) return; // joined words have no stress of their own
  const C = hClusters(t);
  let at = -1;
  C.forEach((c, i) => { if (ACCENT.test(c.m) && !OFF_STRESS.test(c.m)) at = i; });
  if (at < 0) return;
  const exp = hebrewExpected(t, false, false);
  // vowels from the accented cluster to the end (its own vowel included); a furtive patah after it doesn't count
  const tail = hebrewExpected(C.slice(at).map((c) => c.ch + c.m).join(""), false, false).vowels.length;
  const fromEnd = tail - 1; // (a furtive patah counts: RU-ach is two syllables in a respelling too)
  const num = (String(w[3] || "").match(/\{H(\d+)/) || [])[1] || "";
  const key = plainHe(t) + "|" + num;
  const m = stressFromEnd.get(key) || new Map();
  m.set(fromEnd, (m.get(fromEnd) || 0) + 1);
  stressFromEnd.set(key, m);
}))));
const anyKey = (form) => { const all = new Map(); for (const [k, m] of stressFromEnd) if (k.startsWith(form + "|")) for (const [s, n] of m) all.set(s, (all.get(s) || 0) + n); return all.size ? all : null; };
for (const [where, t, say, key] of heCards) {
  // the same word (its Strong's number) where the card has one; otherwise any word written the same way
  const num = (String(key || "").match(/H(\d+)/) || [])[1];
  const m = num ? stressFromEnd.get(plainHe(t) + "|" + String(Number(num)).padStart(4, "0")) || stressFromEnd.get(plainHe(t) + "|" + num) : anyKey(plainHe(t));
  const syl = String(say).split(/[-\s]/).filter(Boolean);
  const cap = syl.findIndex((x) => x !== x.toLowerCase());
  if (!m || syl.length < 2 || cap < 0) continue;
  const shown = syl.length - 1 - cap;
  const usual = [...m].sort((a, b) => b[1] - a[1])[0][0];
  const sortMarks = (x) => hClusters(plainHe(x)).map((c) => c.ch + [...c.m].sort().join("")).join("");
  if (Object.keys(STRESS_OK).some((k) => sortMarks(k) === sortMarks(t))) continue;
  if (shown !== usual && !m.has(shown)) note(problems, "Hebrew: the stress a card shows isn't where the text accents it", `${where}: ${t} shows ${say}; the text stresses the ${usual === 0 ? "last" : usual === 1 ? "second-last" : usual + 1 + "th-last"} syllable`);
}

// ---- whole verses, as "Listen to the verse" gives them
const verseSpeech = audio && audio.verseSpeech;
if (!verseSpeech) note(problems, "Verses: js/audio.js couldn't be loaded in Node", "");
const PUNCT_G = { ",": ",", ".": ".", "·": ",", ";": "?", "—": ",", "–": "," };
if (verseSpeech) {
  for (const B of ntBooks) for (const [c, vs] of B.ch) for (const v of vs) {
    nVerses++;
    const words = v[1];
    const text = verseSpeech(words, "grc");
    for (const sys of ["erasmian", "koine"]) {
      const said = sys === "erasmian" ? S.erasmianSpeech(text) : S.koineSpeech(text);
      const where = `${B.id} ${c}:${v[0]} (${sys === "erasmian" ? "Erasmian" : "Koine"})`;
      if (/[^Ͱ-Ͽἀ-῿ ,.?!]/.test(said)) note(problems, "Verses: something that isn't Greek reaches the voice", `${where}: ${said}`);
      if (/\s{2,}|^\s|\s$/.test(said)) note(problems, "Verses: stray spaces", `${where}`);
      // every word is there, in order, said as it is on its own (elided words join the next one)
      const alone = words.map((w) => (sys === "erasmian" ? S.erasmianSpeech(w[0]) : S.koineSpeech(w[0])).replace(/[,.?]/g, ""));
      const inVerse = said.replace(/[,.?!]/g, "").split(" ").filter(Boolean);
      const elided = words.filter((w) => /^[βγδθκλμνπρστφχ][’'᾽ʼ]$/.test(w[0].normalize("NFC").toLowerCase().replace(/[̀-ͯ]/g, ""))).length;
      if (inVerse.length !== alone.filter(Boolean).length - elided) note(problems, "Verses: a word is lost or added in the whole verse", `${where}: ${inVerse.length} said, ${alone.length} words`);
      else if (!elided && inVerse.join(" ") !== alone.join(" ")) note(problems, "Verses: a word sounds different in the verse from on its own", `${where}: ${inVerse.find((x, i) => x !== alone[i])}`);
      // pauses: each , . · ; in the text gives a pause or question mark in the same place
      const marks = words.map((w) => (String(w[5] || "").normalize("NFC").match(/[,.·;—–]/) || [""])[0]).filter(Boolean).map((m) => PUNCT_G[m]);
      const heardMarks = said.match(/[,.?]/g) || [];
      if (marks.join("") !== heardMarks.join("")) note(problems, "Verses: pauses don't match the punctuation", `${where}: text ${marks.join("")} voice ${heardMarks.join("")}`);
    }
  }
  for (const B of otBooks) for (const [c, vs] of B.ch) for (const v of vs) {
    nVerses++;
    const words = v[1];
    const text = verseSpeech(words, "he");
    const said = S.hebrewSpeech(text);
    const where = `${B.id} ${c}:${v[0]}`;
    if (/[^ְ-ׇא-ת ,.]/.test(said)) note(problems, "Verses (Hebrew): something that isn't Hebrew reaches the voice", `${where}: ${said}`);
    const spoken = words.filter((w) => w[6] !== "k" && /[א-ת]/.test(heText(w).replace(/^[פס]$/, "")))
      .flatMap((w) => heText(w).replace(/׀/g, " ").split(/[\s־]+/).filter((x) => /[א-ת]/.test(x)));
    const n = said.replace(/[,.]/g, "").split(" ").filter(Boolean).length;
    if (n !== spoken.length) note(problems, "Verses (Hebrew): a word is lost or added in the whole verse", `${where}: ${n} said, ${spoken.length} words`);
    // (a word written but not read would make the count above one too many)
    // each word in the verse sounds as it does when tapped on its own (the same voice text)
    const alone = words.filter((w) => w[6] !== "k").flatMap((w) => S.hebrewSpeech((heVoice ? heVoice(w, null, heJoined(w[5])) : heText(w)) + (heJoined(w[5]) ? "־" : "")).split(" ")).filter((x) => /[א-ת]/.test(x));
    const inVerse = said.replace(/[,.]/g, "").split(" ").filter(Boolean);
    if (alone.length === inVerse.length && alone.some((x, i) => x !== inVerse[i])) note(problems, "Verses (Hebrew): a word sounds different in the verse from on its own", `${where}: ${inVerse.find((x, i) => x !== alone[i])} / ${alone.find((x, i) => x !== inVerse[i])}`);
    // pauses: the main division (atnah) and the end of the verse (sof pasuq) are heard as a pause and a full stop
    const atnah = words.slice(0, -1).some((w) => w[6] !== "k" && /֑/.test(w[0])); // on the last word, sof pasuq's stop covers it
    if (atnah && !/,/.test(said)) note(problems, "Verses (Hebrew): no pause at the atnah (the verse's main division)", where);
    const sofPasuq = /׃/.test(String((words[words.length - 1] || [])[5] || ""));
    if (sofPasuq && !/\.$/.test(said)) note(problems, "Verses (Hebrew): the verse doesn't end with a full stop (sof pasuq)", `${where}: …${said.slice(-20)}`);
  }
}

// ================================================================ report
console.log(`Pronunciation check: ${nGreek.toLocaleString("en-GB")} Greek words (Erasmian and Restored Koine), ${nHebrew.toLocaleString("en-GB")} Hebrew words, ${nVerses.toLocaleString("en-GB")} verses.`);
if (limits.size) {
  console.log("\nKnown limits of a Modern voice (accepted):");
  for (const [cat, r] of [...limits].sort((a, b) => b[1].n - a[1].n)) {
    console.log(`  ${r.n.toLocaleString("en-GB")} × ${cat}\n      why: ${LIMITS[cat.replace(/^[^:]+: /, "")]}\n      e.g. ${r.ex[0]}`);
  }
}
if (problems.size) {
  const total = [...problems.values()].reduce((a, r) => a + r.n, 0);
  console.log(`\n${total.toLocaleString("en-GB")} problems in ${problems.size} kinds:`);
  for (const [cat, r] of [...problems].sort((a, b) => b[1].n - a[1].n)) {
    console.log(`  ${r.n.toLocaleString("en-GB")} × ${cat}`);
    r.ex.forEach((e) => console.log("      " + e));
  }
  process.exit(1);
}
console.log("\nEvery word and verse sounds as taught, apart from the known limits above.");
