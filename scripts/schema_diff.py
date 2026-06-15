"""Find fields that appear in some records but not others, and suggest canonical names."""
import json
from collections import Counter

with open("epd_extraction.json") as f:
    records = json.load(f)

# Count how many records have each field name
field_counts = Counter()
for r in records:
    for k in r.keys():
        field_counts[k] += 1

total = len(records)
print(f"Total records: {total}\n")

minority = {k: v for k, v in field_counts.items() if v < total}
majority = {k: v for k, v in field_counts.items() if v == total}

print(f"Fields present in ALL {total} records ({len(majority)} fields):")
for k in sorted(majority):
    print(f"  {k}")

print(f"\nFields present in SOME records only ({len(minority)} fields):")
for k, v in sorted(minority.items(), key=lambda x: -x[1]):
    print(f"  [{v}/{total}]  {k}")
