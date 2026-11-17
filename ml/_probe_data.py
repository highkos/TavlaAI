import json, collections
cases = json.load(open("ml/artifacts/stage_b_positions.json", encoding="utf-8"))["cases"]
print("n =", len(cases))
print("turn:", collections.Counter(c["turn"] for c in cases))
print("cubeValue:", collections.Counter(c["cubeValue"] for c in cases))
print("cubeOwner:", collections.Counter(c["cubeOwner"] for c in cases))
print("matchLength:", collections.Counter(c["matchLength"] for c in cases))
print("crawford:", collections.Counter(bool(c["isCrawfordGame"]) for c in cases))
print("names:", [c["name"] for c in cases[:12]])
