import json, sys, collections, io
sys.stdout.reconfigure(encoding="utf-8")

p = r"D:\秋招\宠物智能硬件用户洞察\data\clean\labeled.jsonl"
rows = []
with open(p, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
print("total rows:", len(rows))

# field coverage
keys = collections.Counter()
for r in rows:
    for k in r:
        keys[k] += 1
print("\n--- fields (count) ---")
for k, v in keys.most_common():
    print(f"{k:24s} {v}")

r0 = rows[0]
print("\n--- sample record ---")
for k, v in r0.items():
    s = json.dumps(v, ensure_ascii=False)
    print(f"{k:16s} {type(v).__name__:8s} {s[:160]}")

def dist(field):
    c = collections.Counter()
    for r in rows:
        v = r.get(field)
        if isinstance(v, list):
            for x in v:
                c[x] += 1
        else:
            c[v] += 1
    return c

for f in ["final_label", "llm.relevance", "cat", "official", "pub_year", "llm.theme", "llm.product_line", "fmt", "_keyword"]:
    if "." in f:
        a, b = f.split(".")
        c = collections.Counter((r.get(a) or {}).get(b) for r in rows)
    else:
        c = dist(f)
    print(f"\n--- {f} ---")
    for k, v in c.most_common(40):
        print(f"  {k!r:28s} {v}")

print("\n--- list fields distinct values ---")
for f in ["brands", "brand_strong", "pains", "scenes"]:
    c = dist(f)
    print(f"\n### {f}  ({len(c)} distinct)")
    for k, v in c.most_common(60):
        print(f"  {k!r:24s} {v}")

print("\n--- numeric ranges ---")
for f in ["play", "like", "fav", "dm", "reply", "duration_s", "interact", "like_rate", "fav_rate", "dm_rate", "margin"]:
    vals = [r.get(f) for r in rows if isinstance(r.get(f), (int, float))]
    if vals:
        print(f"{f:12s} n={len(vals):5d} min={min(vals):.6g} max={max(vals):.6g} mean={sum(vals)/len(vals):.6g}")

print("\n--- pubdate range ---")
pd = [r.get("pubdate") for r in rows if r.get("pubdate")]
import datetime
print(min(pd), max(pd))
print(datetime.datetime.utcfromtimestamp(min(pd)), datetime.datetime.utcfromtimestamp(max(pd)))

print("\n--- _keyword list ---")
kw = collections.Counter(r.get("_keyword") for r in rows)
for k, v in kw.most_common(40):
    print(f"  {k!r:28s} {v}")

print("\n--- labels by keyword sample ---")
print(json.dumps(rows[1], ensure_ascii=False)[:1200])
