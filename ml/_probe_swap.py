import json, sys
sys.path.insert(0, r"F:\Projects\VijualStudioski\TavlaAI_Project\ml")
import gnubg
import cube_bench as CB

cases = json.load(open(r"F:\Projects\VijualStudioski\TavlaAI_Project\ml\artifacts\stage_b_positions.json", encoding="utf-8"))["cases"]
ec = gnubg.evalcontext(0, 1, 1, 0, 0.0)
for c in cases[:1] + [x for x in cases if x["turn"] == 1][:1]:
    r0, r1 = CB.to_gnubg_board(c)
    print("==", c["name"], "turn", c["turn"])
    for label, b in (("as-is", (r0, r1)), ("swapped", (r1, r0))):
        for fm in (0, 1):
            ci = gnubg.cubeinfo(1, -1, fm, 0, (0, 0), 0, 0)
            ev = gnubg.evaluate(b, ci, ec)
            cf = gnubg.cfevaluate(b, ci, ec)
            print("  %-8s fm=%d eq=%+.4f  cf=(%+.3f,%+.3f,%+.3f,%+.3f) %s"
                  % (label, fm, float(ev[5]), float(cf[0]), float(cf[1]), float(cf[2]), float(cf[3]), cf[5]))
