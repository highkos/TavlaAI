import json, sys, os
sys.path.insert(0, r"F:\Projects\VijualStudioski\TavlaAI_Project\ml")
import gnubg
import cube_bench as CB
fm = int(os.environ["FM"])
cases = json.load(open(r"F:\Projects\VijualStudioski\TavlaAI_Project\ml\artifacts\stage_b_positions.json", encoding="utf-8"))["cases"]
ec = gnubg.evalcontext(0, 1, 1, 0, 0.0)
for c in cases[:3]:
    b = CB.to_gnubg_board(c)
    ci = gnubg.cubeinfo(1, -1, fm, 0, (0, 0), 0, 0)
    print(c["name"], "fm=%d" % fm, round(float(gnubg.evaluate(b, ci, ec)[5]), 4))
