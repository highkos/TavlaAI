import gnubg, json

def board(pairs):
    r0 = [0]*25; r1 = [0]*25
    for who, idx, n in pairs:
        (r0 if who == 0 else r1)[idx] = n
    return (tuple(r0), tuple(r1))

ec = gnubg.evalcontext(0, 1, 1, 0, 0.0)
tests = {
  "start":            [(0,0,2),(0,5,5),(0,7,3),(0,12,5),(0,23,2),(1,0,2),(1,5,5),(1,7,3),(1,12,5),(1,23,2)],
  "p0_15@0_p1_15@0":  [(0,0,15),(1,0,15)],
  "p0_15@0_p1_15@23": [(0,0,15),(1,23,15)],
  "p0_15@23_p1_15@0": [(0,23,15),(1,0,15)],
  "p0_1@0_p1_15@0":   [(0,0,1),(1,0,15)],
  "p0_1@23_p1_15@0":  [(0,23,1),(1,0,15)],
  "p0_1@0_p1_15@23":  [(0,0,1),(1,23,15)],
  "p0_1@23_p1_15@23": [(0,23,1),(1,23,15)],
}
res = {}
for name, pairs in tests.items():
    b = board(pairs)
    row = {}
    for fm in (0, 1):
        ci = gnubg.cubeinfo(1, -1, fm, 0, (0, 0), 0, 0)
        ev = gnubg.evaluate(b, ci, ec)
        row["fMove%d" % fm] = [round(float(x), 4) for x in ev]
    res[name] = row
print(json.dumps(res, indent=1))
