import csv

with open("data/corpus_audit/audit.csv") as f:
    rows = list(csv.DictReader(f))

print(f"Rows: {len(rows)}")
hard = [r for r in rows if r["complexity_tier"] == "Hard"]
medium = [r for r in rows if r["complexity_tier"] == "Medium"]
simple = [r for r in rows if r["complexity_tier"] == "Simple"]

print(f"\nHARD ({len(hard)}):")
for r in sorted(hard, key=lambda x: -int(x["page_count"])):
    fail = " [DOCLING FAIL]" if r["docling_success"] != "True" else ""
    lang = f" [{r['language']}]" if r["language"] != "en" else ""
    print(f"  {r['filename']:50s}  {r['page_count']:>4}p  {r['table_count']:>3}t{fail}{lang}")

print(f"\nMEDIUM ({len(medium)}):")
for r in sorted(medium, key=lambda x: -int(x["page_count"])):
    print(f"  {r['filename']:50s}  {r['page_count']:>4}p  {r['table_count']:>3}t")

print(f"\nSIMPLE ({len(simple)}): (none)")

print("\nDocling failures:")
for r in rows:
    if r["docling_success"] != "True":
        print(f"  {r['filename']}: {r['docling_error'][:100]}")

print("\nNon-English:")
for r in rows:
    if r["language"] not in ("en", "unknown", "insufficient_text"):
        print(f"  {r['filename']}: lang={r['language']}")

print("\nGold standard matches:")
matched = [r for r in rows if r["gold_standard_match"]]
unmatched = [r for r in rows if not r["gold_standard_match"]]
print(f"  Matched: {len(matched)}/43")
print(f"  Unmatched PDFs:")
for r in unmatched:
    print(f"    {r['filename']}")
