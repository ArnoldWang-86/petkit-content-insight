# -*- coding: utf-8 -*-
"""02_品牌声量.py —— 小佩在用户搜索里占多少声量、和竞品差距、官方 vs 达人

要支持的决策：投放策略（信官方还是信达人）、竞品对标。

两个关键口径（报告里要区分，不能混）：
  1. 绝对提及量 —— 受采集方式影响（品牌词分配不等、品类词自然带出），只能作方向性参考
  2. 横评内份额 —— 同一条横评里各品牌被一起比较，与采集方式无关，是更公平的口径

另外把品牌提及拆成强/弱信号：
  强信号 = 标题里直接出现品牌名（更可能是真实产品讨论）
  弱信号 = 仅标签命中（可能只是蹭标签）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import summarize, group_by

# A 级纪律：品牌竞争发生在"硬件本体"，故品牌声量只用 final_label = A 的记录
LEVELS = ("A",)

REVIEW_RE = None  # 延迟编译，避免 import 时就依赖 re


def _is_review(row):
    """是否属于横评/选购类内容（含多品牌对比的语境）"""
    hay = row["title"] + " " + row["tag"]
    return any(k in hay for k in ["横评", "对比", "测评", "评测", "哪款", "怎么选"])


def run(data):
    brands = sorted({b for x in data for b in x["brands"]})
    pain_keys = sorted({p for x in data for p in x["pains"]})

    rows = []
    for b in brands:
        g = [x for x in data if b in x["brands"]]
        s = summarize(g)
        strong = len([x for x in g if b in x["brand_strong"]])
        official = len([x for x in g if x["official"]])
        cat_dist = {k: len(v) for k, v in group_by(g, lambda x: x["cat"]).items()}
        pain_dist = {pk: len([x for x in g if pk in x["pains"]]) for pk in pain_keys}
        rows.append({
            "brand": b, "n": s["n"], "play_median": s["play_median"],
            "interact_mean": s["interact_mean"], "fav_rate": s["fav_rate"],
            "dm_rate": s["dm_rate"], "creators": s["creators"],
            "strong_signal": strong, "weak_signal": s["n"] - strong,
            "official": official, "ugc": s["n"] - official,
            "cat_dist": cat_dist, "pain_dist": pain_dist,
        })
    rows.sort(key=lambda r: -r["n"])

    # 官方内容 vs 达人内容：若官方明显更低，说明用户更信 KOC
    official_vs_ugc = {}
    for r in rows[:10]:
        g = [x for x in data if r["brand"] in x["brands"]]
        own = [x for x in g if x["official"]]
        ugc = [x for x in g if not x["official"]]
        official_vs_ugc[r["brand"]] = {
            "official": summarize(own) if own else None,
            "ugc": summarize(ugc) if ugc else None,
        }

    # 品牌 x 产品线 交集矩阵
    cat_keys = [c for c in {x["cat"] for x in data} if c != "其他/泛宠物"]
    matrix = {}
    for r in rows[:12]:
        matrix[r["brand"]] = {
            c: len([x for x in data if r["brand"] in x["brands"] and x["cat"] == c])
            for c in cat_keys
        }

    # 横评内份额：更公平的声量口径
    reviews = [x for x in data if _is_review(x)]
    sov = {}
    for r in rows:
        sov[r["brand"]] = len([x for x in reviews if r["brand"] in x["brands"]])
    total_sov = sum(sov.values()) or 1
    sov_share = {k: round(v / total_sov, 4) for k, v in sov.items()}

    return {
        "key": "by_brand", "title": "品牌声量与口碑",
        "data": rows,
        "overview": {"review_count": len(reviews)},
        "cross": {
            "official_vs_ugc": official_vs_ugc,
            "brand_category_matrix": matrix,
            "share_of_voice": {"counts": sov, "share": sov_share},
        },
    }


def print_report(r):
    print("--- 二、品牌声量（含提及强度分层）---")
    for b in r["data"][:12]:
        print("  %-10s 提及%5d  强信号%4d  弱信号%4d  播放中位%7d  互动率%5.2f%%  官方%4d  达人%5d" % (
            b["brand"], b["n"], b["strong_signal"], b["weak_signal"],
            b["play_median"], b["interact_mean"] * 100, b["official"], b["ugc"]))
    sov = r["cross"]["share_of_voice"]["share"]
    if sov:
        print("")
        print("  横评/选购类内容的品牌份额（更公平的口径，共 %d 条横评）：" % r["overview"]["review_count"])
        for k, v in sorted(sov.items(), key=lambda kv: -kv[1]):
            print("    %-10s %5.1f%%" % (k, v * 100))
