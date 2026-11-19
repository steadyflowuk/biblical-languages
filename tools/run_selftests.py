"""Prove the checkers still catch what they were built to catch: each one's --self-test plants mistakes of its kind
(a wrong case, a vowel changed, a word listed under the wrong entry, an emoji too new for older iPhones …) and must
report every one.

    python3 tools/run_selftests.py
"""
import os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKERS = [
    [sys.executable, "tools/check_greek_tags.py", "--self-test"],
    [sys.executable, "tools/check_hebrew_text.py", "--self-test"],
    ["node", "tools/check_grammar_labels.mjs", "--self-test"],
    [sys.executable, "tools/check_fonts.py", "--self-test"],
    [sys.executable, "tools/check_text_hygiene.py", "--self-test"],
    [sys.executable, "tools/check_references.py", "--self-test"],
    [sys.executable, "tools/check_spelling.py", "--self-test"],
    [sys.executable, "tools/check_dictionary_integrity.py", "--self-test"],
    ["node", "tools/check_dates.mjs", "--self-test"],
    [sys.executable, "tools/check_drills.py", "--self-test"],
    [sys.executable, "tools/check_offline.py", "--self-test"],
]


def main():
    passed = total = 0
    for cmd in CHECKERS:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        m = re.findall(r"(\d+)/(\d+) passed", p.stdout)
        a, b = (int(m[-1][0]), int(m[-1][1])) if m else (0, 1)
        passed += a
        total += b
        name = os.path.basename(cmd[1])
        print(f"{'ok  ' if p.returncode == 0 and a == b else 'FAIL'} {name}: {a}/{b} planted mistakes caught")
        if p.returncode or a != b:
            print("     " + "\n     ".join((p.stdout + p.stderr).strip().splitlines()[-12:]))
    print(f"{passed}/{total} passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
