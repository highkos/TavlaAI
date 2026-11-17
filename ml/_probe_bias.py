import json, statistics
d = json.load(open("ml/artifacts/stage_f_cube_gnubg.json", encoding="utf-8"))["cases"]
pos = {c["name"]: c for c in json.load(open("ml/artifacts/stage_b_positions.json", encoding="utf-8"))["cases"]}
rows = []
for r in d:
    if r.get("skipped") or "error" in r.get("gnubg0", {}):
        continue
    g = r["gnubg0"]; v = r["diceAveraged"]; s = r["singleRecord"]
    if g.get("shouldDouble") is None or not v.get("evaluated", True):
        continue
    rows.append((r["name"], pos[r["name"]]["turn"], pos[r["name"]]["matchLength"], g["cubelessEquity"], s["equityNoDouble"], v["equityNoDouble"]))
print("n =", len(rows))
print("mean gnubg      = %+.4f" % statistics.mean(x[3] for x in rows))
print("mean single     = %+.4f" % statistics.mean(x[4] for x in rows))
print("mean diceAvg    = %+.4f" % statistics.mean(x[5] for x in rows))
for turn in (1, -1):
    sub = [x for x in rows if x[1] == turn]
    print("turn %+d n=%d  gnubg %+.4f  single %+.4f  dice %+.4f" % (turn, len(sub),
        statistics.mean(x[3] for x in sub), statistics.mean(x[4] for x in sub), statistics.mean(x[5] for x in sub)))
for ml in (0,):
    sub = [x for x in rows if x[2] == ml]
    print("money n=%d  gnubg %+.4f  single %+.4f  dice %+.4f" % (len(sub),
        statistics.mean(x[3] for x in sub), statistics.mean(x[4] for x in sub), statistics.mean(x[5] for x in sub)))
sub = [x for x in rows if x[2] != 0]
print("match n=%d  gnubg %+.4f  single %+.4f  dice %+.4f" % (len(sub),
    statistics.mean(x[3] for x in sub), statistics.mean(x[4] for x in sub), statistics.mean(x[5] for x in sub)))
print()
for x in rows[:10]:
    print("%-12s turn%+d ml=%d  gnubg %+.3f  single %+.3f  dice %+.3f" % x)
