"""The full check: every data check, content audit, sweep and test suite, with one summary at the end.

    python3 tools/check_all.py          # everything (~60-75 min): whole Bible, Septuagint, every dictionary entry
    python3 tools/check_all.py quick    # no whole-Bible sweeps (~20 min): for small changes
    python3 tools/check_all.py only test_app audit_content   # just these jobs

Starts the local server on :8765 if it isn't running, fetches the data sources if they're missing (needed by
check_data), and writes logs plus SUMMARY.md to tools/reports/<date-time>/ (not committed). A suite that fails is
run once more on its own, since timing checks can trip when everything runs at once; a pass on that second run is
reported as "passed on retry" so it can still be looked at. Exit code 0 = everything passed.

After this, read tools/REVIEW_BRIEF.md: an independent reviewer (a separate agent) checks the things code can't judge.
"""
import concurrent.futures as cf, datetime, os, re, shutil, socket, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
SRC = os.environ.get("SOURCES", "/home/claude/src")
STAMP = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
OUT = os.path.join(ROOT, "tools", "reports", STAMP)
PY = sys.executable

# name: (command, stage, minutes roughly)
JOBS = {
    # 1. files and data (no browser)
    "check_data":      ([PY, "tools/check_data.py", f"{SRC}/sblgnt", f"{SRC}/morphhb"], 1, 2),
    "check_lessons":   ([PY, "tools/check_lessons.py"], 1, 1),
    "check_speech":    (["node", "tools/check_speech.mjs"], 1, 2),
    "audit_static":    ([PY, "tools/audit_content.py", "--static"], 1, 3),
    "check_rebuild":   ([PY, "tools/check_rebuild.py"], 1, 2),
    "check_grammar":   ([PY, "tools/check_grammar.py"], 1, 1),
    # 2. sweeps: every chapter, every Septuagint chapter, every dictionary entry, every screen
    "sweep_reader":    ([PY, "tools/sweep_reader.py", "all"], 2, 45),
    "sweep_lxx":       ([PY, "tools/sweep_lxx.py", "all"], 2, 40),
    "sweep_dictionary": ([PY, "tools/sweep_dictionary.py", "all"], 2, 15),
    "crawl_app":       ([PY, "tools/crawl_app.py"], 2, 10),
    # 3. test suites
    "test_app":        ([PY, "tools/test_app.py"], 3, 6),
    "test_lessons":    ([PY, "tools/test_lessons.py"], 3, 8),
    "test_dictionary": ([PY, "tools/test_dictionary.py"], 3, 5),
    "test_review":     ([PY, "tools/test_review.py"], 3, 6),
    "test_alphabet":   ([PY, "tools/test_alphabet.py"], 3, 3),
    "test_journey":    ([PY, "tools/test_journey.py"], 3, 5),
    "test_progress":   ([PY, "tools/test_progress.py"], 3, 4),
    "test_reader_edges": ([PY, "tools/test_reader_edges.py"], 3, 4),
    "test_check":      ([PY, "tools/test_check.py"], 3, 5),
    "test_translations": ([PY, "tools/test_translations.py"], 3, 12),
    "test_a11y":       ([PY, "tools/test_a11y.py"], 3, 4),
    "test_backups":    ([PY, "tools/test_backups.py"], 3, 1),
    "test_screens":    ([PY, "tools/test_screens.py"], 3, 3),
    # 4. what a learner sees: tapped words, Reader notes in every layout, dictionary senses, credits
    "audit_content":   ([PY, "tools/audit_content.py"], 4, 10),
    # 5. timing, on its own so other jobs don't slow it down
    "test_slow":       ([PY, "tools/test_slow.py"], 5, 2),
}
QUICK_SKIP = {"sweep_reader", "sweep_lxx", "sweep_dictionary"}
# What each job must have covered: a run that stops early, or quietly checks less, fails (numbers as of Session 14)
COVERAGE = {
    "sweep_reader": [(r"([\d,]+) chapters,", 1189)],
    "sweep_lxx": [(r"(\d+) OT chapters side by side", 929), (r"(\d+) Septuagint chapters", 1259)],
    "sweep_dictionary": [(r"([\d,]+) entries opened", 21234)],
    "crawl_app": [(r"phone light: (\d+) screens", 28)],
    "check_lessons": [(r"All (\d+) lessons pass", 21)],
    "test_app": [(r"\d+/(\d+) passed", 115)], "test_lessons": [(r"\d+/(\d+) passed", 78)],
    "test_dictionary": [(r"\d+/(\d+) passed", 52)], "test_review": [(r"\d+/(\d+) passed", 48)],
    "test_alphabet": [(r"\d+/(\d+) passed", 42)], "test_journey": [(r"\d+/(\d+) passed", 35)],
    "test_progress": [(r"\d+/(\d+) passed", 47)], "test_reader_edges": [(r"\d+/(\d+) passed", 28)],
    "test_check": [(r"\d+/(\d+) passed", 31)], "test_translations": [(r"\d+/(\d+) passed", 70)],
    "test_a11y": [(r"(\d+) pages checked", 104)], "test_backups": [(r"\d+/(\d+) passed", 35)],
    "test_screens": [(r"\d+/(\d+) passed", 48)], "test_slow": [(r"\d+/(\d+) passed", 12)],
    "check_rebuild": [(r"(\d+) data files compared", 433)],
    "check_grammar": [(r"(\d+) forms compared", 143)],
}
PARALLEL = {1: 4, 2: 4, 3: 4, 4: 1, 5: 1}


def port_open(port=8765):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def failed(name, code, log):
    """A job fails on a non-zero exit, a FAIL line, reported issues, or covering less than it should."""
    if code != 0:
        return True
    if re.search(r"^FAIL\b", log, re.M):
        return True
    if re.search(r"issue types: [1-9]", log) or re.search(r"^\s*[1-9][\d,]* (problems|issues)\b", log, re.M):
        return True
    m = re.findall(r"(\d+)/(\d+) passed", log)
    if m and m[-1][0] != m[-1][1]:
        return True
    for pat, want in COVERAGE.get(name, []):
        got = re.findall(pat, log)
        if not got or int(got[-1].replace(",", "")) < want:
            return True
    return False


def headline(log):
    for pat in (r"\d+/\d+ passed", r"All checks passed|\d+ failed", r"All \d+ lessons pass.*", r"\d+ checks passed.*",
                r"issue types: \d+", r"\d+ problems", r"Every word reaches the voice whole\."):
        m = re.findall(pat, log)
        if m:
            return m[-1][:120]
    lines = [l for l in log.strip().splitlines() if l.strip()]
    return lines[-1][:120] if lines else "(no output)"


def run(name):
    cmd = JOBS[name][0]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    log = p.stdout + ("\n" + p.stderr if p.stderr.strip() else "")
    open(os.path.join(OUT, f"{name}.log"), "w").write(log)
    return name, p.returncode, log, time.time() - t0


def main():
    args = sys.argv[1:]
    quick = "quick" in args
    only = set(args[args.index("only") + 1:]) if "only" in args else None
    names = [n for n in JOBS if (only is None or n in only) and not (quick and n in QUICK_SKIP)]
    os.makedirs(OUT, exist_ok=True)

    # sources for check_data
    if "check_data" in names and not os.path.isdir(os.path.join(SRC, "sblgnt")):
        print(f"Fetching the data sources into {SRC} …")
        subprocess.run(["bash", "tools/fetch_sources.sh", SRC], check=False)
    # the local server
    server = None
    if not port_open():
        server = subprocess.Popen([PY, "-m", "http.server", "8765"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(40):
            if port_open():
                break
            time.sleep(0.25)
    if not shutil.which("node"):
        print("node not found: check_speech will fail")

    results = {}
    total = time.time()
    try:
        for stage in (1, 2, 3, 4, 5):
            batch = [n for n in names if JOBS[n][1] == stage]
            if not batch:
                continue
            print(f"\nStage {stage}: {', '.join(batch)}")
            with cf.ThreadPoolExecutor(PARALLEL[stage]) as ex:
                for name, code, log, secs in ex.map(run, batch):
                    bad = failed(name, code, log)
                    results[name] = {"ok": not bad, "secs": secs, "head": headline(log), "log": log, "retry": False}
                    print(f"  {'FAIL' if bad else 'pass'}  {name:18} {secs / 60:5.1f} min  {headline(log)}")
            # a failed suite gets one more run on its own (timing checks can trip under load)
            for name in batch:
                if stage in (3, 5) and not results[name]["ok"]:
                    print(f"  re-running {name} on its own …")
                    shutil.copy(os.path.join(OUT, f"{name}.log"), os.path.join(OUT, f"{name}.first-run.log"))
                    _, code, log, secs = run(name)
                    if not failed(name, code, log):
                        results[name].update(ok=True, retry=True, head=headline(log), log=log)
                        print(f"  pass  {name:18} on retry (first run: {name}.first-run.log)")
    finally:
        if server:
            server.terminate()

    # summary
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
    version = re.search(r'VERSION = "([^"]+)"', open("sw.js").read()).group(1)
    ok = all(r["ok"] for r in results.values())
    lines = [f"# Full check {STAMP}", "",
             f"Commit {sha} on {branch}, app version {version}. " + ("Something failed: see below." if not ok else
             f"Everything passed ({sum(r['retry'] for r in results.values())} only on a second run: see below)." if any(r["retry"] for r in results.values())
             else "Everything passed."),
             f"Took {(time.time() - total) / 60:.0f} minutes{' (quick: whole-Bible sweeps skipped)' if quick else ''}.", "",
             "| Job | Result | Minutes | Summary |", "|---|---|---|---|"]
    for n in names:
        r = results.get(n)
        if r:
            res = "passed on retry" if r["retry"] else ("pass" if r["ok"] else "**FAIL**")
            lines.append(f"| {n} | {res} | {r['secs'] / 60:.1f} | {r['head'].replace('|', '/')} |")
    for n, r in results.items():
        if not r["ok"] or r["retry"]:
            fails = [l for l in r["log"].splitlines() if re.match(r"\s*(FAIL|  - |\s{3,}\S)", l) or "issue" in l][:40]
            lines += ["", f"## {n}", "", "```", *(fails or r["log"].strip().splitlines()[-25:]), "```"]
    lines += ["", "Next: the independent review in tools/REVIEW_BRIEF.md (things code can't judge)."]
    open(os.path.join(OUT, "SUMMARY.md"), "w").write("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines[:6]))
    print(f"\nReport: {os.path.relpath(OUT, ROOT)}/SUMMARY.md")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
