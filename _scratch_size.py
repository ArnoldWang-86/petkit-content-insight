# -*- coding: utf-8 -*-
"""测量内联数据体积：列式 TSV vs JSON。"""
import json, sys, gzip, collections
sys.stdout.reconfigure(encoding="utf-8")

P = r"D:\秋招\宠物智能硬件用户洞察\data\clean\labeled.jsonl"
rows = [json.loads(l) for l in open(P, encoding="utf-8") if l.strip()]
print("rows:", len(rows), " raw jsonl bytes:", 6989641)

MT = {m: i for i, m in enumerate(
    ["健康监测/泌尿", "价格/性价比", "异味/除臭", "上班族/无人值守", "清洁/维护麻烦", "猫毛/掉毛",
     "智能互联/APP", "多猫/大猫适配", "故障/安全风险", "耗材/长期成本", "噪音", "猫咪不接受"])}
SC = {s: i for i, s in enumerate(["新手养猫", "上班族/白天独处", "预算敏感/学生党", "多猫家庭", "出差/旅行在外"])}
BD = {b: i for i, b in enumerate(["小佩", "小米", "CATLINK", "霍曼", "糯雪", "美的", "鸟语花香",
                                  "有陪", "pidan", "猫洁易", "petshy"])}
CAT = {c: i for i, c in enumerate(["其他/泛宠物", "猫砂盆", "饮水机", "喂食器", "烘干箱", "净化器", "摄像头", "鱼缸"])}
FMT = {f: i for i, f in enumerate(["其他", "横评/选购", "教程/指南", "DIY/改装", "使用体验/吐槽", "开箱/上手", "闲置/二手"])}
PL = {p: i for i, p in enumerate(["", "猫砂盆", "饮水机", "喂食器", "烘干箱", "其他硬件", "净化器", "摄像头", "鱼缸"])}
LB = {"A": 0, "B": 1, "C": 2, "N": 3}

def esc(s):
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", " ").replace("\r", " ")

cols = collections.OrderedDict()
cols["bvid"] = [r["bvid"] for r in rows]
cols["title"] = [esc(r["title"][:70]) for r in rows]
cols["play"] = [r["play"] for r in rows]
cols["like"] = [r["like"] for r in rows]
cols["fav"] = [r["fav"] for r in rows]
cols["dm"] = [r["dm"] for r in rows]
cols["reply"] = [r["reply"] for r in rows]
cols["dur"] = [r["duration_s"] for r in rows]
cols["ir"] = ["%.5f" % r["interact"] for r in rows]
cols["lr"] = ["%.5f" % r["like_rate"] for r in rows]
cols["fr"] = ["%.5f" % r["fav_rate"] for r in rows]
cols["dr"] = ["%.3f" % r["dm_rate"] for r in rows]
cols["lb"] = [LB[r["final_label"]] for r in rows]
cols["ct"] = [CAT.get(r["cat"], 0) for r in rows]
cols["pl"] = [PL.get(((r.get("llm") or {}).get("product_line") or "").strip(), 0) for r in rows]
cols["bd"] = ["|".join(str(BD[b]) for b in r["brands"]) for r in rows]
cols["bs"] = ["|".join(str(BD[b]) for b in r["brand_strong"]) for r in rows]
cols["of"] = [1 if r["official"] else 0 for r in rows]
cols["pn"] = ["|".join(str(MT[p]) for p in r["pains"]) for r in rows]
cols["sc"] = ["|".join(str(SC[s]) for s in r["scenes"]) for r in rows]
cols["fm"] = [FMT.get(r["fmt"], 0) for r in rows]
cols["kw"] = [r["_keyword"] for r in rows]
cols["yp"] = [r["pub_year"] for r in rows]
cols["th"] = [{"硬件产品": 0, "耗材日用": 1, "养护科普": 2, "健康医疗": 3, "日常vlog": 4,
               "非硬件选购": 5, "硬件DIY": 6, "行业资讯": 7, "领养救助": 8, "非宠物": 9}
              .get((r.get("llm") or {}).get("theme") or "", 10) for r in rows]

tsv = "\n".join("\t".join(str(v) for v in col) for col in cols.values())
print("columnar TSV chars:", len(tsv), " = %.0f KB" % (len(tsv)/1024))
print("utf8 bytes: %d (%.0f KB)" % (len(tsv.encode()), len(tsv.encode())/1024))
print("gzip:", len(gzip.compress(tsv.encode())), "bytes")
print("cols:", len(cols), "->", list(cols.keys()))
# 逐列体积
for k, v in cols.items():
    s = "\t".join(str(x) for x in v)
    print("  %-6s %8.1f KB" % (k, len(s)/1024))
