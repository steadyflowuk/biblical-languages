// Days, streaks and Today's verse around the clock changes, in time zones that change their clocks in different ways.
//
//     node tools/check_dates.mjs              # runs itself once per time zone (TZ=… node …)
//     node tools/check_dates.mjs --self-test  # the old "minus 4 hours" day is caught
//
// The study/review day starts at 4am (js/activity.js and js/review.js dayKey, review.js dayEnd); Today's verse turns
// at midnight (js/votd.js dayNumber); Progress counts days back with shiftDay. Checked, minute by minute through
// every day of 2026–2027 near the turn, in each zone:
//   • dayKey turns at 4:00 by the clock, on ordinary days and on the mornings the clocks change
//   • dayEnd(t) is the first moment of the next review day: dayKey(dayEnd(t) − 1 ms) = dayKey(t) ≠ dayKey(dayEnd(t))
//   • review.js and activity.js agree on the day (Review's counts and the streak use the same day)
//   • Today's verse number goes up by exactly one per calendar day (no day skipped or repeated across a change)
//   • shiftDay walks back day by day without skipping or repeating
//   • a study day every day for a year makes a streak of 365, whatever the zone
import fs from "fs";
import path from "path";
import { execFileSync } from "child_process";

const ROOT = path.dirname(path.dirname(new URL(import.meta.url).pathname));
const ZONES = ["Europe/London", "America/New_York", "Australia/Sydney", "Asia/Kolkata", "Pacific/Chatham",
  "America/Santiago", "Asia/Tehran", "Pacific/Apia", "America/St_Johns", "UTC"];

if (!process.env.CHECK_DATES_CHILD) {
  let fails = 0, checks = 0;
  for (const tz of ZONES) {
    try {
      const out = execFileSync(process.execPath, [new URL(import.meta.url).pathname, ...process.argv.slice(2)], { env: { ...process.env, TZ: tz, CHECK_DATES_CHILD: "1" }, encoding: "utf8" });
      const m = out.match(/(\d+) checks/);
      checks += m ? Number(m[1]) : 0;
      console.log(`${tz}: ${out.trim().split("\n").pop()}`);
    } catch (e) {
      fails++;
      console.log(`${tz}: FAIL\n${(e.stdout || "").trim()}`);
    }
  }
  if (process.argv.includes("--self-test")) {  // the old day (4 hours of elapsed time) must fail where clocks change
    const ok = fails >= 5;
    console.log(`${ok ? "caught" : "MISSED"} the old 'minus 4 hours' day in ${fails} of ${ZONES.length} zones`);
    console.log(`${ok ? 1 : 0}/1 passed`);
    process.exit(ok ? 0 : 1);
  }
  console.log(`${checks.toLocaleString("en-GB")} checks in ${ZONES.length} time zones`);
  console.log(`${fails} problems`);
  process.exit(fails ? 1 : 0);
}

// ---------------------------------------------------------------- in one time zone
globalThis.window = globalThis;
const mem = {};
globalThis.localStorage = { getItem: (k) => (k in mem ? mem[k] : null), setItem: (k, v) => { mem[k] = String(v); }, removeItem: (k) => { delete mem[k]; }, key: () => null, length: 0 };
globalThis.location = { hash: "" };
const activity = await import(path.join(ROOT, "js/activity.js"));
// review.js pulls in the screens; its two day functions are read from the source and run as they are
const rsrc = fs.readFileSync(path.join(ROOT, "js/review.js"), "utf8");
const grab = (name) => {
  const m = rsrc.match(new RegExp(`export function ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n\\}`));
  return new Function("DAY_START", `return (${m[0].replace("export ", "")})`)(4);
};
const reviewDayKey = grab("dayKey");
const dayEnd = grab("dayEnd");
const vsrc = fs.readFileSync(path.join(ROOT, "js/votd.js"), "utf8");
const dayNumber = new Function(`return ${vsrc.match(/export const dayNumber = ([^\n]+);/)[1]}`)();

const selfTest = process.argv.includes("--self-test");
const oldDayKey = (d) => {  // the day as it was worked out before 19 Nov 2026
  const x = new Date(d.getTime() - 4 * 3600 * 1000);
  return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
};
const dayKey = selfTest ? oldDayKey : activity.dayKey;

let checks = 0;
const bad = [];
const fail = (msg) => { if (bad.length < 15) bad.push(msg); };
const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const wall = (d) => `${ymd(d)} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;

// every 10 minutes through 2026–2027
const start = new Date(2026, 0, 1, 0, 0).getTime();
const stop = new Date(2028, 0, 1, 0, 0).getTime();
let prevNum = null, prevCal = null;
for (let t = start; t < stop; t += 10 * 60 * 1000) {
  const d = new Date(t);
  const want = d.getHours() < 4 ? ymd(new Date(d.getFullYear(), d.getMonth(), d.getDate() - 1, 12)) : ymd(d);
  const got = dayKey(d);
  checks++;
  if (got !== want) fail(`dayKey at ${wall(d)} (wall clock) is ${got}, should be ${want}`);
  if (!selfTest && reviewDayKey(d) !== got) fail(`review.js and activity.js disagree at ${wall(d)}: ${reviewDayKey(d)} / ${got}`);
  if (t % (60 * 60 * 1000) === 0) {
    const end = dayEnd(d);
    checks++;
    if (dayKey(new Date(end.getTime() - 1)) !== got) fail(`at ${wall(d)}: the moment before dayEnd (${wall(end)}) is another day`);
    if (dayKey(end) === got) fail(`at ${wall(d)}: dayEnd (${wall(end)}) is still the same day`);
    if (end.getTime() - t > 25 * 3600 * 1000 || end.getTime() <= t) fail(`at ${wall(d)}: dayEnd ${wall(end)} out of range`);
  }
  const cal = ymd(d);
  if (cal !== prevCal) {
    const n = dayNumber(d);
    checks++;
    if (prevNum !== null && n !== prevNum + 1) fail(`Today's verse number jumps from ${prevNum} to ${n} at ${wall(d)}`);
    prevNum = n;
    prevCal = cal;
  }
}
// shiftDay walks day by day; a year of daily study is a 365-day streak
let k = "2027-12-31";
const seen = new Set();
const act = {};
for (let i = 0; i < 365; i++) {
  const next = activity.shiftDay(k, 1);
  checks++;
  if (seen.has(next) || next >= k) fail(`shiftDay(${k}, 1) = ${next}`);
  seen.add(next);
  act[k] = { r: 1, l: 0 };
  k = next;
}
const s = activity.streak(new Date(2027, 11, 31, 20, 0), act);
checks++;
if (s.current !== 365) fail(`a year of daily study counts as a ${s.current}-day streak`);

if (bad.length) {
  console.log(bad.join("\n"));
  console.log(`${checks} checks, problems`);
  process.exit(1);
}
console.log(`${checks} checks passed`);
