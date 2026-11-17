import json, statistics, sys, os
sys.path.insert(0, os.path.abspath("ml"))
import gnubg_er as G

model = "ml/runs/stage_d_l2/onnx/model_v15.onnx"
print("model exists:", os.path.exists(model))
sc = G.OnnxScorer(model)
d = json.load(open("ml/artifacts/stage_f_cube_gnubg.json", encoding="utf-8"))["cases"]
pos = {c["name"]: c for c in json.load(open("ml/artifacts/stage_b_positions.json", encoding="utf-8"))["cases"]}
rows = []
for r in d:
    if r.get("skipped") or "error" in r.get("gnubg0", {}):
        continue
    g = r["gnubg0"]; v = r["diceAveraged"]; s = r["singleRecord"]
    if g.get("shouldDouble") is None or not v.get("evaluated", True):
        continue
    c = pos[r["name"]]
    vec = G.vectorize(c["board"], c["whiteOff"], c["blackOff"],
                      cube_value=c["cubeValue"], cube_owner=c["cubeOwner"],
                      match_length=c["matchLength"], white_score=c["whiteScore"],
                      black_score=c["blackScore"], is_crawford=c["isCrawfordGame"],
                      perspective=c["turn"])
    vec2 = G.vectorize(c["board"], c["whiteOff"], c["blackOff"],
                       cube_value=c["cubeValue"], cube_owner=c["cubeOwner"],
                       match_length=c["matchLength"], white_score=c["whiteScore"],
                       black_score=c["blackScore"], is_crawford=c["isCrawfordGame"],
                       perspective=-c["turn"])
    rows.append((r["name"], c["turn"], g["cubelessEquity"], s["equityNoDouble"], v["equityNoDouble"], vec, vec2))
vals = sc.values([x[5] for x in rows])
vals2 = sc.values([x[6] for x in rows])
print("n =", len(rows))
print("mean gnubg   = %+.4f" % statistics.mean(x[2] for x in rows))
print("mean single  = %+.4f" % statistics.mean(x[3] for x in rows))
print("mean dice    = %+.4f" % statistics.mean(x[4] for x in rows))
print("mean pyval   = %+.4f" % statistics.mean(vals))
print("mean -pyval2 = %+.4f" % statistics.mean(-v for v in vals2))
print("mean |pyval - single| = %.4f" % statistics.mean(abs(v - x[3]) for v, x in zip(vals, rows)))
print("mean |pyval - gnubg|  = %.4f" % statistics.mean(abs(v - x[2]) for v, x in zip(vals, rows)))
print("mean |pyval + pyval2| = %.4f" % statistics.mean(abs(v + w) for v, w in zip(vals, vals2)))
for x, v in list(zip(rows, vals))[:10]:
    print("%-12s turn%+d gnubg %+.3f single %+.3f dice %+.3f pyval %+.3f" % (x[0], x[1], x[2], x[3], x[4], v))
