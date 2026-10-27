"""Audit the Septuagint alignment: score every lined-up verse by Hebrew→Greek word pairs and compare with the
Septuagint verses either side. Lists verses where a neighbour fits clearly better (likely off by a verse).
Usage: python3 tools/audit_lxx.py <sources folder>   (rebuilds data/lxx the same way build_lxx does)"""
import sys, re, collections, io, contextlib
sys.path.insert(0, "tools")
import build_lxx

r = {}
with contextlib.redirect_stdout(io.StringIO()):
    build_lxx.build(sys.argv[1], report=r)
score, verses, order, result, hot = r["score"], r["verses"], r["order"], r["result"], r["hot"]
pos = {ref: i for i, ref in enumerate(order)}
flag, zero, total, scored, dist = [], [], 0, 0, collections.Counter()
for bid, chs in result.items():
    hv = {c: {v[0]: v for v in vs} for c, vs in hot[bid]["ch"]}
    for c, d in chs:
        if d["weak"]:
            continue
        for e in d["v"]:
            if not e[1]:
                continue
            total += 1
            v = hv[c][e[0]]
            gs = e[1].split(",")
            s, hits, n = score(v, gs)
            if s is None or n < 4:
                continue
            scored += 1
            dist[round(s, 1)] += 1
            code = gs[0].split(".")[0]
            i = pos[gs[0]]
            near = [x for x in order[max(0, i - 2):i + 3] if x.startswith(code + ".") and x not in gs]
            best = max(((score(v, [x])[0] or 0, x) for x in near), default=(0, None))
            if s == 0:
                zero.append(f"{bid} {c}:{e[0]} → {e[1]} (0/{n})")
            if best[0] >= s + 0.5 and score(v, [best[1]])[1] >= 3:
                flag.append(f"{bid} {c}:{e[0]} → {e[1]} scores {s:.2f}; {best[1]} scores {best[0]:.2f}")
print(f"{total} verses lined up; {scored} have ≥4 paired Hebrew words")
print("score distribution:", dict(sorted(dist.items())))
print(f"{len(zero)} with nothing in common:", zero[:20])
print(f"{len(flag)} where a neighbouring Septuagint verse fits clearly better:")
for x in flag[:80]:
    print("  ", x)
moved = r.get("moved", [])
print(f"\n{len(moved)} verses moved by run correction; by chapter:")
byc = collections.Counter(" ".join(m.split()[:2]).split(":")[0] for m in moved)
print("  ", ", ".join(f"{k} ({n})" for k, n in byc.most_common()))

# Greek verses given to two Hebrew verses, while an unused Greek verse nearby fits one of them
used = collections.defaultdict(list)
for bid, chs in result.items():
    for c, d in chs:
        for e in d["v"]:
            for g in (e[1].split(",") if e[1] else []):
                used[g].append((bid, c, e[0]))
hvs = {bid: {c: {v[0]: v for v in vs} for c, vs in hot[bid]["ch"]} for bid in result}
dups = []
for g, owners in used.items():
    if len(owners) < 2:
        continue
    for bid, c, vn in owners:
        v = hvs[bid][c][vn]
        s = score(v, [g])[0] or 0
        i = pos[g]
        code = g.split(".")[0]
        free = [x for x in order[max(0, i - 2):i + 3] if x.startswith(code + ".") and x not in used]
        alt = max(((score(v, [x])[0] or 0, x) for x in free), default=(0, None))
        if alt[1] and alt[0] >= s + 0.3:
            dups.append(f"{bid} {c}:{vn} shares {g} ({s:.2f}); unused {alt[1]} scores {alt[0]:.2f}")
print(f"\n{sum(1 for o in used.values() if len(o) > 1)} Greek verses shared by two or more Hebrew verses; {len(dups)} where an unused neighbour fits better:")
for x in dups[:60]:
    print("  ", x)
