import json, os
import gnubg
ROOT = r"F:\Projects\VijualStudioski\TavlaAI_Project"
with open(os.path.join(ROOT, "ml", "artifacts", "stage_b_positions.json"), "r", encoding="utf-8") as f:
    positions = json.load(f)
case = positions["cases"][0]
print("case:", case["name"], "turn", case["turn"], "wOff", case["whiteOff"], "bOff", case["blackOff"])
print("board:", case["board"])
b = case["board"]
row0 = [b[i] for i in range(1, 25)] + [b[0]]
row1 = [-b[24 - i] for i in range(24)] + [-b[25]]
print("row0:", row0, "sum", sum(row0))
print("row1:", row1, "sum", sum(row1))
print("pid:", gnubg.positionid((tuple(row0), tuple(row1))))
print("back:", gnubg.positionfromid(gnubg.positionid((tuple(row0), tuple(row1)))))
