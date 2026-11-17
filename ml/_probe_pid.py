import json, sys
sys.path.insert(0, r"F:\Projects\VijualStudioski\TavlaAI_Project\ml")
import gnubg
import cube_bench as CB

cases = json.load(open(r"F:\Projects\VijualStudioski\TavlaAI_Project\ml\artifacts\stage_b_positions.json", encoding="utf-8"))["cases"]
for c in cases[:4]:
    b = CB.to_gnubg_board(c)
    print(c["name"], "turn", c["turn"], "->", gnubg.positionid(b))
