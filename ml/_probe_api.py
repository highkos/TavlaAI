import json, sys, os
sys.path.insert(0, r"F:\Projects\VijualStudioski\TavlaAI_Project\ml")
import gnubg
import cube_bench as CB

cases = json.load(open(r"F:\Projects\VijualStudioski\TavlaAI_Project\ml\artifacts\stage_b_positions.json", encoding="utf-8"))["cases"]
ec = gnubg.evalcontext(0, 1, 1, 0, 0.0)
res = []
for c in cases[:6]:
    b = CB.to_gnubg_board(c)
    row = {"name": c["name"], "turn": c["turn"]}
    for fm in (0, 1):
        ci = gnubg.cubeinfo(1, -1, fm, 0, (0, 0), 0, 0)
        row["fMove%d" % fm] = round(float(gnubg.evaluate(b, ci, ec)[5]), 4)
    res.append(row)
print(json.dumps(res, indent=1))
