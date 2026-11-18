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
const VOWEL = /^(a|e|i|o|oː|u|y|ju)$/;

/** Line up expected and heard sounds (Needleman–Wunsch); returns [[exp|null, got|null], …]. */
function align(A, B) {
  const n = A.length, m = B.length;
  const del = (i) => { const a = A[i - 1]; if (a.opt) return 0; if (VOWEL.test(a.p)) return 1; if (a.p === "h") return 0.5; return (A[i - 2] && A[i - 2].p === a.p) || (A[i] && A[i].p === a.p) ? 0.4 : 1; };
  const ins = (j) => (/^[mnŋ]$/.test(B[j - 1].p) && B[j] && /^[bdg]$/.test(B[j].p) ? 0.4 : 1);
  const NEAR = [["s", "z"], ["t", "d"], ["p", "b"], ["k", "g"], ["g", "ʝ"], ["ɣ", "ʝ"], ["y", "u"], ["y", "ju"], ["i", "j̯"], ["u", "ju"], ["e", "i"], ["oː", "o"]];
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

const ERASMIAN_V = { α: ["a"], ε: ["e"], η: ["e", "i"], ι: ["i"], ο: ["o"], υ: ["y"], ω: ["oː"], αι: ["a", "i"], ει: ["e", "i"],
  οι: ["o", "i"], υι: ["u", "i"], ου: ["u"], αυ: ["a", "u"], ευ: ["e", "u"], ηυ: ["e", "i", "u"], ωυ: ["oː", "u"] };
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
  "a rare form left to the voice": "Checked by hand (VOWELS_OK): too rare to write a rule for.",
  "ω said like ο": "Erasmian teaches ω as a longer o; Modern Greek has no long vowels, so the voice says both alike.",
  "one-syllable word stressed": "An unaccented one-syllable word keeps a stress mark only where it must: Erasmian έι/άι/όι, or the voice splits the pair (εἰς); Koine έ, ιού for ἡ, οἱ, or the voice may name the letter.",
};

const nextP0 = (pairs, k) => { const x = pairs[k + 1]; return x && !x[0] && x[1] ? x[1].p : ""; };
function classify(exp, got, pairs, k, system, word) {
  const e = exp && exp.p, g = got && got.p;
  const nextE = (pairs[k + 1] || [])[0], prevE = (pairs[k - 1] || [])[0];
  if (e === "h" && !g) return "rough breathing h not said";
  if (e === "oː" && g === "o") return "ω said like ο";
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
  ["ow", ["a", "u"]], ["eu", ["e", "u"]], ["ee", ["i"]], ["oh", ["oː"]], ["kh", ["x"]], ["th", ["θ"]], ["ps", ["p", "s"]],
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
 * How the app teaches a Hebrew word to sound (vowels, in order), the academic way, from its pointing and — where the
 * pointing can't settle it — its grammar and dictionary form. info: { joined, final (the verse's last word: its last
 * meteg sign is silluq, the stress), stem, form, person (STEPBible verb letters), article, directional, prefix (letters
 * before the main word), lemma }. Returns { vowels: [{p, alt?, opt?}], cons }.
 * Written apart from js/sound.js on purpose, from the grammar books' rules:
 *  shewa — said at the start of a word, after another shewa, after a long vowel (tsere, holam, shureq, hiriq or tsere
 *    with yod, a long qamets), under a doubled letter, before the same letter; silent at the end, under a throat letter
 *    (a said one would be hateph), after a stressed vowel, before a perfect's -tî/-tā/-nû ending, before the ה of
 *    direction;
 *  qamets — short o (qamets hatuf) in a closed syllable that isn't stressed: before a silent shewa, before a throat
 *    letter's shewa, before a hateph qamets (not the article's), in kol, in a mood verb's closed last syllable when the
 *    stress is earlier or the word is joined by maqqef; long a in perfects and participles there; before a plain
 *    shewa the grammar decides — verbs say the shewa (sha-me-RU) except a Qal imperative/infinitive and the Hophal
 *    (shom-RE-ni, hog-LU); a noun follows its dictionary form (קֹדֶשׁ → kod-SHO; יָד → ya-de-KHA).
 */
/** Per cluster: "c" consonant, "o"/"u" a vav standing for that vowel, "m" another letter standing for a vowel. */
function rolesOf(C) {
  const role = C.map(() => "c");
  C.forEach((c, i) => {
    const prev = C[i - 1];
    const own = vowelOf(c.m) || has(c, H.SHEWA);
    if (c.ch === "ו" && i > 0 && !own && (has(c, H.HOLAM) || has(c, H.DAGESH))) {
      if (has(c, H.HOLAM)) role[i] = "o"; // וֹ
      else if (prev && !vowelOf(prev.m) && !has(prev, H.SHEWA)) role[i] = "u"; // וּ after a letter with no vowel
    }
    if (c.ch === "ו" && i === 0 && has(c, H.DAGESH) && !own) role[i] = "u"; // the conjunction וּ
    if (c.ch === "י" && !own && !has(c, H.DAGESH) && prev && /[ִֵֶ]/.test(prev.m)) role[i] = "m";
    if (c.ch === "א" && !own && !has(c, H.DAGESH) && !(C[i + 1] && C[i + 1].ch === "ו" && !vowelOf(C[i + 1].m) && /[ֹּ]/.test(C[i + 1].m))) role[i] = "m";
    if (c.ch === "ה" && i === C.length - 1 && !own && !has(c, H.DAGESH)) role[i] = "m";
    if (c.ch === "ו" && !own && !has(c, H.DAGESH) && prev && has(prev, H.HOLAM) && i === C.length - 1) role[i] = "m";
  });
  return role;
}

function hebrewExpected(word, info) {
  const I = info || {};
  const C = hClusters(word);
  if (!C.length) return { vowels: [], cons: "" };
  const role = rolesOf(C); // matres lectionis: letters standing for a vowel, not a consonant
  const cons = C.map((c, i) => (role[i] === "c" ? c.ch : "")).join("");
  const consIdx = C.map((c, i) => i).filter((i) => role[i] === "c");
  const lastCons = consIdx[consIdx.length - 1];
  const nextCons = (i) => consIdx[consIdx.indexOf(i) + 1];
  const plainShewa = (c) => !!c && has(c, H.SHEWA) && !vowelOf(c.m);
  // the stress: accents on the stressed syllable; a pashta written twice (the first); silluq on the verse's last word
  const on = C.map((c, i) => (ACCENT.test(c.m) && !OFF_STRESS.test(c.m) ? i : -1)).filter((i) => i >= 0);
  const pashtas = C.map((c, i) => (c.m.includes("֙") ? i : -1)).filter((i) => i >= 0);
  if (pashtas.length > 1) on.push(pashtas[0]);
  let silluq = -1;
  if (I.final) C.forEach((c, i) => { if (has(c, H.METEG)) silluq = i; });
  if (silluq >= 0) on.push(silluq);
  const stress = I.joined ? -1 : on.length ? Math.max(...on) : C.some((c) => ACCENT.test(c.m)) ? -2 : -1; // -2: written but not shown; joined: none of its own
  const meteg = (i) => has(C[i], H.METEG) && i !== silluq;
  const verb = !!I.form;
  const mood = verb && /[iwjhuvc]/.test(I.form) && !(I.form === "c" && I.person);
  // Qal imperative/infinitive and Hophal: qamets hatuf on the main word's first letter only (shom-RE-ni, hog-LU)
  const shortImperativeAt = (i) => verb && i === (I.prefix || 0) && ((I.stem === "q" && (I.form === "v" || (I.form === "c" && !I.person))) || I.stem === "H");
  // the perfect's 1st/2nd person ending: the consonant before its ת / נ has a silent shewa
  let endingShewa = -1;
  if ((I.form === "p" || I.form === "q") && /[12]/.test(I.person || "")) {
    for (let k = consIdx.length - 1; k >= 1 && k >= consIdx.length - 3; k--) if (/[תנ]/.test(C[consIdx[k]].ch)) { endingShewa = consIdx[k - 1]; break; }
  }
  let directionalShewa = -1;
  if (I.directional && consIdx.length >= 2) { const k = consIdx[consIdx.length - 2]; if (plainShewa(C[k])) directionalShewa = k; }
  const ki = C.findIndex((c) => c.ch === "כ" && c.m.includes(H.QAMATS));
  const isKol = !verb && ki >= 0 && ki <= 2 && C.length === ki + 2 && C[ki + 1].ch === "ל"
    && C.slice(0, ki).every((c, i) => (role[i] === "c" || (i === 0 && role[i] === "u")) && /[ובכלמהש]/.test(c.ch));
  const articleAt = I.article ? C.findIndex((c, k) => k < (I.prefix || 1) && /[הבכל]/.test(c.ch) && c.m.includes(H.QAMATS)) : -1;
  // the dictionary form's vowel at a consonant of the main word: "o" (holam, qamets hatuf, qibbuts), "a" or ""
  const lemmaVowel = (i) => {
    if (!I.lemma) return "";
    // the main word starts after the prefix letters (one cluster each); count its consonants up to cluster i and find
    // the same consonant in the dictionary form (for a name of several words, the word spelt like this one)
    const pre = I.prefix || 0;
    if (i < pre) return "";
    const nth = consIdx.filter((k) => k >= pre && k < i).length;
    const mainSkel = consIdx.filter((k) => k >= pre).map((k) => C[k].ch).join("");
    const words = String(I.lemma).replace(/[֑-ֽֿ֯]/g, "").split(/[\s־]+/).filter(Boolean);
    const lw = words.find((x) => mainSkel.startsWith(x.replace(/[^א-ת]/g, "").slice(0, 2))) || words[words.length - 1] || "";
    const L = hClusters(lw);
    const Lrole = rolesOf(L);
    const Lcons = L.map((c, k) => k).filter((k) => Lrole[k] === "c");
    const at = Lcons[nth];
    if (at == null) return "";
    const x = L[at], y = L[at + 1];
    if (!x) return "";
    if (/[ׇֹֻ]/.test(x.m) || (y && Lrole[at + 1] === "o")) return "o";
    if (/[ַָ]/.test(x.m)) return "a";
    return "";
  };
  // qamets first (it decides some shewas): q[i] = "a" | "o" | "?" ; said shewa after it: sayNext[i] = true | false | "?"
  const q = C.map(() => "");
  const sayNext = {};
  C.forEach((c, i) => {
    if (role[i] !== "c" || !c.m.includes(H.QAMATS) || c.m.includes(H.QQATAN) || vowelOf(c.m) === "ai") return;
    const ni = nextCons(i), N = C[ni];
    const stressed = stress === i;
    if (isKol && i === ki) { q[i] = "o"; return; }
    if (i === articleAt) { q[i] = "a"; if (plainShewa(N) && !GUTTURAL.test(N.ch)) sayNext[ni] = true; return; }
    if (N && has(N, H.HQAMATS)) { q[i] = "o"; return; }
    if (N && ni !== lastCons && GUTTURAL.test(N.ch) && plainShewa(N) && !stressed && !meteg(i)) { q[i] = "o"; return; }
    const finalClosed = ni === lastCons && N && !vowelOf(N.m) && !(["m", "u", "o"].includes(role[ni + 1]));
    if (finalClosed) {
      if (stressed) { q[i] = "a"; return; }
      if (verb) { q[i] = mood && !meteg(i) && (I.joined || stress >= 0 || (I.form === "w" && stress === -2)) ? "o" : "a"; return; }
      q[i] = I.joined ? "?" : "a";
      return;
    }
    const forcedSaid = N && (has(N, H.DAGESH) && !BGDKPT.test(N.ch) || (C[nextCons(ni)] && C[nextCons(ni)].ch === N.ch));
    if (N && ni !== lastCons && plainShewa(N) && !GUTTURAL.test(N.ch) && forcedSaid) { q[i] = shortImperativeAt(i) || (!verb && lemmaVowel(i) === "o") ? "o" : "a"; sayNext[ni] = true; return; }
    if (N && ni !== lastCons && plainShewa(N) && !GUTTURAL.test(N.ch)) {
      if (ni === endingShewa || ni === directionalShewa || stressed) { q[i] = "a"; sayNext[ni] = false; return; }
      if (shortImperativeAt(i)) { q[i] = "o"; sayNext[ni] = false; return; } // even with a meteg (שָֽׁמְרֵנִי)
      if (meteg(i)) { q[i] = "a"; sayNext[ni] = true; return; }
      if (verb) { q[i] = "a"; sayNext[ni] = true; return; }
      const lv = lemmaVowel(i);
      if (lv === "o") { q[i] = "o"; sayNext[ni] = false; return; }
      if (lv === "a") { q[i] = "a"; sayNext[ni] = true; return; }
      q[i] = "?"; sayNext[ni] = "?";
      return;
    }
    q[i] = "a";
  });
  // the vowel sound just before cluster i: is it long, a shewa, or stressed?
  const before = (i) => {
    for (let k = i - 1; k >= 0; k--) {
      if (role[k] === "o" || role[k] === "u") return { long: true, stressed: stress === k || stress === k - 1 };
      if (role[k] === "m") continue;
      const c = C[k];
      if (plainShewa(c)) return { shewa: true };
      const yod = C[k + 1] && role[k + 1] === "m" && C[k + 1].ch === "י";
      return { long: has(c, H.TSERE) || has(c, H.HOLAM) || has(c, H.HOLAMV) || (has(c, H.HIRIQ) && yod), stressed: stress === k, v: vowelOf(c.m) };
    }
    return null;
  };
  const said = C.map(() => false);
  const maybe = C.map(() => false);
  C.forEach((c, i) => {
    if (!plainShewa(c) || role[i] !== "c") return;
    if (i === lastCons || i === endingShewa || i === directionalShewa) return;
    if (i in sayNext) { if (sayNext[i] === "?") maybe[i] = true; else said[i] = sayNext[i]; return; }
    if (i === consIdx[0]) { said[i] = true; return; }
    if (GUTTURAL.test(c.ch)) return;
    const b = before(i);
    const next = C[nextCons(i)];
    if (b && b.shewa) { said[i] = true; return; }
    if (next && next.ch === c.ch) { said[i] = true; return; } // before the same letter: always said (אַלְלַי, נֹסְסָה)
    if (b && b.stressed && !has(c, H.DAGESH) && !(C[0] && i > 0 && consIdx.indexOf(i) === consIdx.findIndex((k) => k >= (I.prefix || 0)) && role[0] === "u")) return; // a stressed syllable it closes (not a doubled letter, not the main word's start after וּ)
    if (b && b.long) { said[i] = true; return; }
    if (has(c, H.DAGESH) && b && !b.shewa && (!BGDKPT.test(c.ch) || b.v)) { said[i] = true; return; }
    if (next && next.ch === c.ch) said[i] = true;
  });
  const vowels = [];
  C.forEach((c, i) => {
    if (role[i] === "o") { vowels.push({ p: "o" }); return; }
    if (role[i] === "u") { vowels.push({ p: "u" }); return; }
    if (role[i] !== "c") return;
    if (plainShewa(c)) { if (said[i]) vowels.push({ p: "e" }); else if (maybe[i]) vowels.push({ p: "e", opt: true }); return; }
    const v = vowelOf(c.m);
    if (!v) return;
    if (v === "ai") { vowels.push({ p: "a" }, { p: "i" }); return; }
    if (q[i] === "?") { vowels.push({ p: "a", alt: ["o"] }); return; }
    vowels.push({ p: q[i] || v });
  });
  return { vowels, cons, stress };
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

// Checked by hand: forms too rare to write a rule for, with what they should be
const VOWELS_OK = {
  "הַיְחָבְרְךָ": "PSA 94:20, a Pual with qamets hatuf (ha-ye-chov-re-KHA); the voice gets the qamets as a",
};

// ================================================================ collecting what the app says
const problems = new Map(); // category → { n, examples }
const limits = new Map();
const note = (map, cat, ex) => { const r = map.get(cat) || { n: 0, ex: [] }; r.n++; if (r.ex.length < EXAMPLES) r.ex.push(ex); map.set(cat, r); };

// ---- debugging a word: node tools/check_pronunciation.mjs say λόγος בְּרֵאשִׁית
if (argv[0] === "say") {
  for (const w of argv.slice(1)) {
    if (/[\u05D0-\u05EA]/.test(w)) {
      // WORD or WORD@CODE@LEMMA@final, e.g. וַיֵּ֣שְׁבוּ@HC/Vqw3mp@יָשַׁב
      const [wd, code, lemma, fin] = w.split("@");
      const info = { ...grammarOf(code), lemma, final: !!fin, joined: /־$/.test(wd) };
      const exp = hebrewExpected(wd.replace(/־$/, ""), info);
      const vt = heVoice ? heVoice(["", "", "", "", code || "", fin ? "׃" : ""], wd.replace(/־$/, ""), info.joined, lemma || undefined) : wd;
      const v = S.hebrewSpeech(vt);
      console.log(`${wd}  expected vowels ${vShow(exp.vowels)}  voice text ${v}  heard ${israeliVowels(v.replace(/[,.]/g, "")).join(" ")}`);
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
// The grammar a word's code shows (read here on its own, not through js/audio.js): verb stem/form/person, the article,
// the ה of direction, how many one-letter prefixes (conjunction, preposition, article) come before the main word.
function grammarOf(code) {
  const parts = String(code || "").replace(/^[HA]/, "").split("/");
  const v = parts.map((x) => x.match(/^V(\w)(\w)(\d)?/)).find(Boolean);
  const main = parts.findIndex((x) => !/^(C|R|Rd|Td)$/.test(x));
  return { stem: v ? v[1] : "", form: v ? v[2] : "", person: v && v[3] ? v[3] : "", article: parts.includes("Td") || parts.includes("Rd"),
    directional: parts.includes("Sd"), prefix: main > 0 ? main : 0 };
}
const heWord = (t, joined, where, w, lex) => {
  const final = /\u05C3/.test(String(w[5] || ""));
  const mainKey = (String(w[3] || "").match(/\{(H\d+[A-Za-z]?)/) || [])[1] || "";
  const lemma = mainKey && lex && lex[mainKey] ? String(lex[mainKey][0] || "").split(",")[0] : "";
  const key = [t, joined ? 1 : 0, final ? 1 : 0, w[4], lemma].join("|");
  if (heSeen.has(key)) return;
  heSeen.set(key, { where, w, lex, info: { ...grammarOf(w[4]), final, lemma }, text: t + (joined ? "־" : "") });
};
otBooks.forEach((B) => B.ch.forEach(([c, vs]) => vs.forEach((v) => v[1].forEach((w) => heWord(heText(w), heJoined(w[5]), `${B.id} ${c}:${v[0]}`, w, B.lex)))));
const heParts = [];
for (const [, info] of heSeen) {
  const key = info.text;
  // a source word can hold a paseq and a space, or a maqqef: check each part on its own
  const parts = key.replace(/[׀׃]/g, " ").split(/\s+/).filter(Boolean)
    .flatMap((t) => { const ps = t.split("־"); return ps.map((x, i) => [x, i < ps.length - 1]); }).filter(([x]) => x);
  parts.forEach(([x, j]) => heParts.push([x + (j ? "־" : ""), info]));
}
for (const [key, { where, w: dw, lex: dlex, info: dinfo }] of heParts) {
  const joined = key.endsWith("־");
  const word = joined ? key.slice(0, -1) : key;
  if (!/[ְ-ׇ]/.test(word)) continue; // unpointed (paragraph letters, ketiv-only)
  nHebrew++;
  const exp = hebrewExpected(word, { ...dinfo, joined });
  // the voice text the app makes for this word (audio.heVoice knows its grammar), then the Israeli voice reading it
  const voice = S.hebrewSpeech(heVoice ? heVoice(dw, word, joined, dlex) + (joined ? "־" : "") : key).replace(/[,.]/g, "");
  if (/א[ֱֲ]?דֹנָי|א[ֱֲ]?לֹהִים/.test(voice) && !/אֲדֹנָי|אֱלֹהִים/.test(word.replace(/[֑-ֽֿ֯]/g, ""))) continue; // the divine name
  const heard = voice.split(" ").flatMap(israeliVowels);
  // spellings the scribes read differently (perpetual qere) must reach the voice as they are read
  if (/ִוא(\s|$)/.test(voice)) note(problems, "Hebrew: הִוא handed to the voice as written (read hi)", `${word} (${where}) → ${voice}`);
  if (/ִ[ַָ]|[ַָ]ִ/.test(voice)) note(problems, "Hebrew: two vowels on one letter handed to the voice (read a-yi)", `${word} (${where}) → ${voice}`);
  if (/[ְ-ׇ]ש[א-ת]/.test(voice)) note(problems, "Hebrew: a silent unpointed ש handed to the voice", `${word} (${where}) → ${voice}`);
  if (VOWELS_OK[word.replace(/[\u0591-\u05AF\u05BD]/g, "")]) { note(limits, "Hebrew: a rare form left to the voice", `${word} (${where}): ${VOWELS_OK[word.replace(/[\u0591-\u05AF\u05BD]/g, "")]}`); continue; }
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
  const exp = String(d[1]).split("־").flatMap((part, i, all) => hebrewExpected(part, { joined: i < all.length - 1 }).vowels);
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
  "בָּטַח": "a verb: ba-TACH (2 Kgs 18:5 בָּטָ֑ח, and בָטַ֥ח without the dagesh 4 times); the one form written exactly so draws the stress back (PSA 112:7)",
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
  const exp = hebrewExpected(t, {});
  // vowels from the accented cluster to the end (its own vowel included); a furtive patah after it doesn't count
  const tail = hebrewExpected(C.slice(at).map((c) => c.ch + c.m).join(""), {}).vowels.length;
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

// ---- Hebrew: the consonants a card shows = the consonants the pointing gives (begadkefat by dagesh, shin/sin by
// their dot, matres and silent letters left out). Doubling, y and a final h are left out on both sides: respellings
// write doubled letters once (ki-PER), a yod after a vowel as part of it (a-do-NAI) and a final h for some vowels.
const SOUND_OF = { ב: ["b", "v"], ג: ["g", "g"], ד: ["d", "d"], ז: ["z"], ח: ["ch"], ט: ["t"], כ: ["k", "kh"], ך: ["k", "kh"],
  ל: ["l"], מ: ["m"], ם: ["m"], נ: ["n"], ן: ["n"], ס: ["s"], פ: ["p", "f"], ף: ["p", "f"], צ: ["ts"], ץ: ["ts"], ק: ["k"],
  ר: ["r"], ת: ["t", "t"] };
const HAS_VOWEL = /[ְ-ׇֻ]/; // shewa .. qibbuts, qamets hatuf (the vav shureq dagesh is handled on its own)
const ownVowel = (m) => /[ְ-ׇֻ]/.test(m.replace(/[ּֽ]/g, ""));
function pointedConsonants(text) {
  const out = [];
  String(text).replace(/[֑-ֽֿ֯׀]/g, "").split(/[\s־]+/).filter(Boolean).forEach((part) => {
    const C = hClusters(part);
    C.forEach((c, i) => {
      const prev = C[i - 1], last = i === C.length - 1, dag = c.m.includes(H.DAGESH);
      if (/[אע]/.test(c.ch)) return;
      if (c.ch === "ה") { if (!(last && !dag && !ownVowel(c.m))) out.push("h"); return; }
      if (c.ch === "ו") {
        const vowelless = !ownVowel(c.m.replace(/[ֹ]/g, ""));
        if (vowelless && c.m.includes(H.HOLAM) && i > 0 && !ownVowel(prev.m)) return; // holam vav
        if (vowelless && dag && (i === 0 || !ownVowel(prev.m))) return; // shureq
        if (!c.m && i > 0 && !(last && (prev.m.includes(H.QAMATS) || prev.ch === "י"))) return; // written, not pointed (but -ָו, -ָיו: "av")
        out.push("v"); return;
      }
      if (c.ch === "י") return; // y: left out (see above)
      if (c.ch === "ש") { out.push(c.m.includes("ׂ") ? "s" : "sh"); return; }
      const s = SOUND_OF[c.ch];
      if (!s) return;
      out.push(s.length === 2 && !dag ? s[1] : s[0]);
    });
  });
  return out.filter((x, i, a) => x !== a[i - 1]).filter((x, i, a) => !(x === "h" && i === a.length - 1));
}
function respeltConsonants(say) {
  const out = [];
  String(say).toLowerCase().replace(/[’'ʼ.]/g, "").split(/\s+/).forEach((w) => {
    let s = w.replace(/-/g, "");
    while (s) {
      const two = s.slice(0, 2);
      if (["sh", "ch", "kh", "ts", "tz"].includes(two)) { out.push(two === "tz" ? "ts" : two); s = s.slice(2); continue; }
      const c = s[0]; s = s.slice(1);
      if (/[aeiou]/.test(c) || c === "y") continue;
      if (c === "h" && !s) continue; // a final h is a vowel letter in a respelling
      out.push(c === "w" ? "v" : c);
    }
  });
  return out.filter((x, i, a) => x !== a[i - 1]).filter((x, i, a) => !(x === "h" && i === a.length - 1));
}
// the check must catch a wrong card and pass a right one (proof it can see the mistakes it is for)
for (const [t, say, ok] of [["מֶלֶךְ", "ME-lekh", 1], ["מֶלֶךְ", "ME-lek", 0], ["בַּיִת", "BA-yit", 1], ["בַּיִת", "VA-yit", 0],
  ["שָׂדֶה", "sa-DEH", 1], ["שָׂדֶה", "sha-DEH", 0], ["תּוֹרָה", "to-RAH", 1], ["עֵשָׂו", "e-SAV", 1], ["פֶּה", "peh", 1], ["פֶּה", "feh", 0],
  ["דָּוִד", "da-VID", 1], ["רוּחַ", "RU-ach", 1], ["רוּחַ", "RU-akh", 0]]) {
  if ((pointedConsonants(t).join(" ") === respeltConsonants(say).join(" ")) !== !!ok) note(problems, "Checker: card consonant self-test failed", `${t} ${say} should ${ok ? "pass" : "fail"}`);
}
for (const [where, t, say] of heCards) {
  if (!/[ְ-ׇֻ]/.test(t) || /יהוה/.test(t)) continue; // bare letters (the Letters guide's names) and the divine name
  const want = pointedConsonants(t).join(" "), shown = respeltConsonants(say).join(" ");
  if (want !== shown) note(problems, "Hebrew: a card's respelling has other consonants than the pointing", `${where}: ${t} shows ${say} (${shown}); the pointing gives ${want}`);
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
    const text = verseSpeech(words, "he", B.lex);
    const said = S.hebrewSpeech(text);
    const where = `${B.id} ${c}:${v[0]}`;
    if (/[^ְ-ׇא-ת ,.]/.test(said)) note(problems, "Verses (Hebrew): something that isn't Hebrew reaches the voice", `${where}: ${said}`);
    const spoken = words.filter((w) => w[6] !== "k" && /[א-ת]/.test(heText(w).replace(/^[פס]$/, "")))
      .flatMap((w) => heText(w).replace(/׀/g, " ").split(/[\s־]+/).filter((x) => /[א-ת]/.test(x)));
    const n = said.replace(/[,.]/g, "").split(" ").filter(Boolean).length;
    if (n !== spoken.length) note(problems, "Verses (Hebrew): a word is lost or added in the whole verse", `${where}: ${n} said, ${spoken.length} words`);
    // (a word written but not read would make the count above one too many)
    // each word in the verse sounds as it does when tapped on its own (the same voice text)
    const alone = words.filter((w) => w[6] !== "k").flatMap((w) => S.hebrewSpeech((heVoice ? heVoice(w, null, heJoined(w[5]), B.lex) : heText(w)) + (heJoined(w[5]) ? "־" : "")).split(" ")).filter((x) => /[א-ת]/.test(x));
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
console.log("\nNot checkable here: where an Israeli voice puts the stress in a Hebrew word. Hebrew text has no stress mark a voice"
  + "\n  reads (accents are stripped), so the voice decides; it usually follows Modern Hebrew (mostly the last syllable,"
  + "\n  as the Bible text too). The stress the cards show is checked against the text's accents above. Judge on a device.");
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
