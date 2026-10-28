// Study days (Session 11): what was done on each day, for the streak and the Progress calendar.
// Store "activity" = { "2026-10-28": { r: cards reviewed, l: lesson steps } }. Days follow the review day (it starts at
// 4am, like Review), so a late-night session still counts for the day it belongs to. About 400 days are kept.
import * as store from "./store.js";

const DAY_START = 4; // hours after midnight (same as review.js)
const KEEP = 400;

/** The study day a moment belongs to ("2026-10-28"). */
export function dayKey(d) {
  const x = new Date((d || new Date()).getTime() - DAY_START * 3600 * 1000);
  return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
}

/** The day key `n` days before (or after, when negative) a day key. */
export function shiftDay(key, n) {
  const [y, m, d] = key.split("-").map(Number);
  const x = new Date(y, m - 1, d - n, 12);
  return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
}

/** Every day with something done: { day: { r, l } }. Reviews from before Session 11 come from the review log. */
export function activity() {
  const a = Object.assign({}, store.get("activity") || {});
  const log = store.get("reviewLog") || {};
  Object.keys(log).forEach((d) => {
    const r = (log[d] && log[d].r) || 0;
    if (!a[d]) a[d] = { r, l: 0 };
    else if ((a[d].r || 0) < r) a[d] = Object.assign({}, a[d], { r });
  });
  return a;
}

/**
 * Note one thing done now: "l" a lesson step, or "r" after a review answer — Review has already counted the card in
 * its own log, which activity() reads, so "r" only keeps that day's count here for when the review log forgets it.
 */
export function logActivity(kind, now) {
  const a = activity();
  const d = dayKey(now);
  a[d] = Object.assign({ r: 0, l: 0 }, a[d]);
  if (kind !== "r") a[d][kind] = (a[d][kind] || 0) + 1;
  Object.keys(a).sort().slice(0, -KEEP).forEach((k) => { delete a[k]; });
  store.set("activity", a);
  const s = streak(now, a);
  if (s.current > (Number(store.get("bestStreak")) || 0)) store.set("bestStreak", s.current);
}

const did = (a, d) => !!a[d] && ((a[d].r || 0) + (a[d].l || 0)) > 0;

/** { current, best, today }: days in a row with study, counting today once something is done (else up to yesterday). */
export function streak(now, given) {
  const a = given || activity();
  const today = dayKey(now);
  const studiedToday = did(a, today);
  let d = studiedToday ? today : shiftDay(today, 1);
  let current = 0;
  while (did(a, d)) { current++; d = shiftDay(d, 1); }
  // the best run in what's kept, or the best ever noted
  let best = 0, run = 0;
  Object.keys(a).sort().forEach((k, i, keys) => {
    if (!did(a, k)) { run = 0; return; }
    run = i && keys[i - 1] === shiftDay(k, 1) && did(a, keys[i - 1]) ? run + 1 : 1;
    best = Math.max(best, run);
  });
  best = Math.max(best, current, Number(store.get("bestStreak")) || 0);
  return { current, best, today: studiedToday };
}

/** How much was done on a day (cards reviewed + lesson steps). */
export const amount = (a, d) => (a[d] ? (a[d].r || 0) + (a[d].l || 0) : 0);
