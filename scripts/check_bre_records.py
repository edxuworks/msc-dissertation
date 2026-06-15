import json

with open("data/gold_standard/epd_gold_normalised.json") as f:
    records = json.load(f)

# BRE records are indices 10-16 (000xxx.pdf files with AGG values)
bre_indices = [i for i, r in enumerate(records) if r.get("GWP-TOTAL", {}).get("A1") == "AGG"]
print(f"BRE-style records (A1=AGG): indices {bre_indices}\n")

for i in bre_indices:
    r = records[i]
    gwp = r.get("GWP-TOTAL", {})
    pert = r.get("PERT", {})
    penrt = r.get("PENRT", {})
    fw = r.get("FRESH WATER", {})
    acid = r.get("ACIDIFICATION", {})
    eutr = r.get("EUTROFICATION", {})
    print(f"[{i:02d}] {r['file_name']}")
    print(f"  GWP-TOTAL  : {gwp}")
    print(f"  PERT       : {pert}")
    print(f"  PENRT      : {penrt}")
    print(f"  FRESH WATER: {fw}")
    print(f"  ACIDIFIC.  : {acid}")
    print(f"  EUTROFIC.  : {eutr}")
    print()
