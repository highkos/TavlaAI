import json, sys, os
sys.path.insert(0, os.path.abspath("ml"))
import gnubg_er as G
cases = json.load(open("ml/artifacts/stage_b_positions.json", encoding="utf-8"))["cases"]
sess = G.GnubgSession(G.find_gnubg(), plies=0)
sel = [c for c in cases if c["turn"] == 1][:3]
out = []
for c in sel:
    row = {"name": c["name"], "turn": c["turn"]}
    for t in (1, -1):
        table, _ = sess.eval_position(c["board"], t)
        row["text_turn%+d" % t] = table.get("1")
    out.append(row)
print(json.dumps(out, indent=1))
