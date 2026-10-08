# -*- coding: utf-8 -*-
"""验证语义层陷阱：用真实数据确认每条「陷阱」确实存在。"""
import json, sys, statistics, collections
sys.stdout.reconfigure(encoding="utf-8")

P = r"D:\秋招\宠物智能硬件用户洞察\data\clean\labeled.jsonl"
rows = [json.loads(l) for l in open(P, encoding="utf-8") if l.strip()]
print("N =", len(rows))

def med(v):
    return statistics.median(v) if v else 0

def summarize(rs):
    if not rs: return {}
    return dict(n=len(rs),
                play_median=int(med([r["play"] for r in rs])),
                play_mean=int(sum(r["play"] for r in rs)/len(rs)),
                play_max=max(r["play"] for r in rs),
                interact_mean=round(sum(r["interact"] for r in rs)/len(rs), 4),
                interact_median=round(med([r["interact"] for r in rs]), 4),
                like_rate=round(sum(r["like_rate"] for r in rs)/len(rs), 4),
                fav_rate=round(sum(r["fav_rate"] for r in rs)/len(rs), 4),
                dm_rate=round(sum(r["dm_rate"] for r in rs)/len(rs), 2))

A = [r for r in rows if r["final_label"] == "A"]
print("A =", len(A), " B =", sum(1 for r in rows if r['final_label']=='B'),
      " C =", sum(1 for r in rows if r['final_label']=='C'),
      " N =", sum(1 for r in rows if r['final_label']=='N'))

def pl(r):
    v = ((r.get("llm") or {}).get("product_line") or "").strip()
    return v or "其他硬件"

print("\n### 陷阱A：产品线口径 —— 大模型 product_line vs 词典 cat（仅A级）")
print("%-10s %6s %10s %10s | %6s %10s %10s" % ("产品线", "n", "播放中位", "互动率", "cat_n", "cat中位", "cat互动"))
by = collections.defaultdict(list); byc = collections.defaultdict(list)
for r in A:
    by[pl(r)].append(r)
    byc[r["cat"]].append(r)
for k in sorted(by, key=lambda x: -len(by[x])):
    s = summarize(by[k]); sc = summarize(byc.get(k) or [])
    print("%-10s %6d %10d %10.4f | %6d %10d %10.4f" % (
        k, s["n"], s["play_median"], s["interact_mean"],
        sc.get("n",0), sc.get("play_median",0), sc.get("interact_mean",0)))

print("\n### 陷阱B：小样本品类 —— 互动率被个别视频主导")
for k in sorted(byc, key=lambda x: len(byc[x])):
    g = byc[k]
    if k == "其他/泛宠物": continue
    top = max(g, key=lambda r: r["interact"])
    share = top["interact"]/sum(r["interact"] for r in g)
    print("%-10s n=%4d  互动率均值=%.4f  最大单条=%.4f(占%.0f%%)  去掉它后均值=%.4f  播放中位=%d 最大播放=%d" % (
        k, len(g), sum(r['interact'] for r in g)/len(g), top["interact"], share*100,
        sum(r['interact'] for r in g if r is not top)/(len(g)-1), int(med([r['play'] for r in g])), max(r['play'] for r in g)))

print("\n### 陷阱C：弹幕率量级 vs 点赞/收藏率")
print("like_rate mean=%.4f  fav_rate mean=%.4f  dm_rate mean=%.4f  → 弹幕率是点赞率的 %.1f 倍" % (
    sum(r['like_rate'] for r in rows)/len(rows), sum(r['fav_rate'] for r in rows)/len(rows),
    sum(r['dm_rate'] for r in rows)/len(rows),
    (sum(r['dm_rate'] for r in rows)/len(rows))/(sum(r['like_rate'] for r in rows)/len(rows))))

print("\n### 陷阱D：均值互动率 ≠ 总量互动率（同一批数据两种口径）")
for name, g in [("A 级全部", A), ("猫砂盆(A)", by.get("猫砂盆") or []), ("净化器(A)", by.get("净化器") or [])]:
    mean_of_ratio = sum(r["interact"] for r in g)/len(g)
    ratio_of_sum = sum(r["like"]+r["fav"] for r in g)/sum(r["play"] for r in g)
    print("%-12s n=%4d  均值口径=%.4f  总量口径=%.4f  倍数=%.2f" % (
        name, len(g), mean_of_ratio, ratio_of_sum, mean_of_ratio/ratio_of_sum))

print("\n### 陷阱E：播放量长尾（均值 vs 中位数）")
pl_all = [r["play"] for r in rows]
top = sorted(rows, key=lambda r: -r["play"])[:5]
print("全部样本 均值=%d 中位=%d 比值=%.1f  最大=%d(%s)" % (
    sum(pl_all)/len(pl_all), med(pl_all), (sum(pl_all)/len(pl_all))/med(pl_all), max(pl_all), top[0]["title"][:30]))
for k in ["猫砂盆", "净化器", "鱼缸", "摄像头"]:
    g = byc.get(k) or []
    if not g: continue
    p = [r["play"] for r in g]
    print("  %-6s n=%4d 均值=%8d 中位=%7d 最大=%9d 均值/中位=%.2f" % (
        k, len(g), sum(p)/len(p), med(p), max(p), (sum(p)/len(p))/med(p)))

print("\n### 陷阱F：官方内容全部集中在小佩系")
off = [r for r in rows if r["official"]]
print("official=True 共 %d 条；作者 top10：" % len(off))
for a, c in collections.Counter(r["author"] for r in off).most_common(10):
    print("   %-24s %d" % (a, c))
print("官方内容里提及品牌分布：", collections.Counter(b for r in off for b in r["brands"]).most_common(8))

print("\n### 陷阱G：横评份额的分母")
def is_review(r):
    hay = r["title"] + " " + r["tag"]
    return any(k in hay for k in ["横评", "对比", "测评", "评测", "哪款", "怎么选"])
rev = [r for r in A if is_review(r)]
cnt = collections.Counter(b for r in rev for b in r["brands"])
tot = sum(cnt.values())
print("A级横评 %d 条；品牌提及总次数（分母）= %d" % (len(rev), tot))
for b, c in cnt.most_common(6):
    print("   %-10s 提及%4d 次  提及次数占比=%5.2f%%  出现在多少条横评里=%4d (%.1f%% of %d 条)" % (
        b, c, c/tot*100, sum(1 for r in rev if b in r["brands"]),
        sum(1 for r in rev if b in r["brands"])/len(rev)*100, len(rev)))

print("\n### 陷阱H：各关键词记录的 A 级占比（关键词偏置）")
for k, g in sorted(collections.Counter(r["_keyword"] for r in rows).items(), key=lambda kv: -kv[1])[:8]:
    sub = [r for r in rows if r["_keyword"] == k]
    print("   %-12s n=%4d  A占比=%5.1f%%  A级播放中位=%6d  A级互动率=%.4f" % (
        k, len(sub), sum(1 for r in sub if r['final_label']=='A')/len(sub)*100,
        summarize([r for r in sub if r['final_label']=='A']).get('play_median',0),
        summarize([r for r in sub if r['final_label']=='A']).get('interact_mean',0)))

print("\n### 陷阱I：发布时间分布（含未来日期 / 长尾时长）")
yrs = collections.Counter(r["pub_year"] for r in rows)
print("  年份分布：", sorted(yrs.items()))
import datetime
ds = [r["pubdate"] for r in rows]
print("  最早 %s  最晚 %s" % (datetime.datetime.fromtimestamp(min(ds)).date(), datetime.datetime.fromtimestamp(max(ds)).date()))
print("  时长 top5：", sorted((r["duration_s"] for r in rows), reverse=True)[:5], " 最大=%.2f 小时" % (max(r['duration_s'] for r in rows)/3600))
print("  时长>3小时的记录数 =", sum(1 for r in rows if r["duration_s"] > 10800))

print("\n### 陷阱J：pains 是多标签（计数会超过样本数）")
pc = collections.Counter(p for r in rows for p in r["pains"])
print("  痛点命中总次数 = %d，而样本只有 %d 条 → 一条内容可命中多个痛点" % (sum(pc.values()), len(rows)))
for p, c in pc.most_common(4):
    print("   %-16s %d" % (p, c))
mixed = [r for r in rows if len(r["pains"]) >= 2]
print("  命中>=2个痛点的记录数 = %d (%.1f%%)" % (len(mixed), len(mixed)/len(rows)*100))

print("\n### 陷阱K：scenes 未标注占比")
nosc = sum(1 for r in rows if not r["scenes"])
print("  scenes 为空 = %d (%.1f%%)  ← 不是「没有场景」，而是关键词没命中" % (nosc, nosc/len(rows)*100))
print("  fmt = 其他 =", sum(1 for r in rows if r["fmt"] == "其他"), "(%.1f%%)" % (sum(1 for r in rows if r['fmt']=='其他')/len(rows)*100))
print("  cat = 其他/泛宠物 =", sum(1 for r in rows if r["cat"] == "其他/泛宠物"))

print("\n### 陷阱L：creator 与品牌的重叠（同一创作者多条）")
midc = collections.Counter(r["mid"] for r in rows)
print("  4,375 条来自 %d 位创作者；产出最多的创作者发了几条：" % len(midc), midc.most_common(5))
print("  提示：按内容条数统计会让高产创作者被重复计数（同一人作品高度同质）")

print("\n### 陷阱M：A级结论对 12% 误标的敏感性（用 95%CI 下界重算）")
# 用 final_label=A 的 n 缩放到 88% 时的粗略稳定区间（仅示意口径）
s = summarize(A)
print("  A 级 n=%d，若真实准确率 88%，则 A 级真实条数约 %d~%d 条" % (
    s["n"], int(s["n"]*0.88/0.94), int(s["n"]*1.0/0.88)))
print("  → 排名结论只在 A/B 两层差距 > 12%% 时才算稳健（本 Agent 会强制标注「小样本/差距不足」）")

print("\n### 陷阱N：内容形态 fmt 与痛点一样是多标签？")
print("  fmt 是全样本单值字段（每行一个），覆盖率为 100%，但 fmt=其他 占 %.1f%%" % (
    sum(1 for r in rows if r["fmt"]=="其他")/len(rows)*100))

print("\n### 数据字典实际取值域（给语义层用）")
print("  final_label:", sorted(set(r["final_label"] for r in rows)))
print("  cat:", sorted(set(r["cat"] for r in rows)))
print("  fmt:", sorted(set(r["fmt"] for r in rows)))
print("  brands(11):", sorted(set(b for r in rows for b in r["brands"])))
print("  pains(12):", sorted(set(p for r in rows for p in r["pains"])))
print("  scenes(5):", sorted(set(s for r in rows for s in r["scenes"])))
print("  theme(10):", sorted(set((r.get('llm') or {}).get('theme') or '' for r in rows)))
print("  关键词数:", len(set(r["_keyword"] for r in rows)))
