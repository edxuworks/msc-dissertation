import json
with open("data/gold_standard/epd_gold_normalised.json") as f:
    records = json.load(f)
for i, r in enumerate(records):
    gwp = r.get("GWP-TOTAL", {})
    gwp_str = str(gwp)[:70] if gwp else "EMPTY"
    print(f"{i:02d} | {r.get('file_name','?'):<40} | GWP-TOTAL: {gwp_str}")
