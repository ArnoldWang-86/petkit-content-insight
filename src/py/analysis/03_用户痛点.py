# -*- coding: utf-8 -*-
"""03_用户痛点.py —— 用户到底在抱怨什么、哪些痛点能引发高互动

要支持的决策：内容主打哪个卖点、产品迭代优先级。

除了「哪个痛点被讨论最多」，还做一层交叉：
  同一痛点用不同内容形态讲，效果差多少 —— 这才叫可执行的结论
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import summarize, group_by
from collections import Counter

# 痛点属于"需求与语境"，按纪律使用 A（产品吐槽）+ B（耗材/健康）+ C（用户语境）
LEVELS = ("A", "B", "C")


def run(data):
    brands = sorted({b for x in data for b in x["brands"]})
    pain_keys = sorted({p for x in data for p in x["pains"]})

    rows = []
    for pk in pain_keys:
        g = [x for x in data if pk in x["pains"]]
        s = summarize(g)
        rows.append({
            "pain": pk, "n": s["n"], "play_median": s["play_median"],
            "interact_mean": s["interact_mean"], "fav_rate": s["fav_rate"],
            "dm_rate": s["dm_rate"], "creators": s["creators"],
            "cat_dist": {k: len(v) for k, v in group_by(g, lambda x: x["cat"]).items()},
            "brand_dist": {b: len([x for x in g if b in x["brands"]]) for b in brands},
            "label_dist": dict(Counter(x.get("final_label") or "?" for x in g)),
        })
    rows.sort(key=lambda r: -r["n"])

    # 交叉：痛点 x 内容形态
    pain_by_format = {}
    for r in rows[:12]:
        g = [x for x in data if r["pain"] in x["pains"]]
        pain_by_format[r["pain"]] = {
            k: {
                "n": len(v),
                "interact_mean": round(sum(x["interact"] for x in v) / len(v), 4),
                "fav_rate": round(sum(x["fav_rate"] for x in v) / len(v), 4),
            }
            for k, v in group_by(g, lambda x: x["fmt"]).items()
        }

    return {"key": "pain_points", "title": "用户痛点", "data": rows,
            "cross": {"pain_by_format": pain_by_format}}


def print_report(r):
    print("--- 三、用户痛点（内容打什么卖点）---")
    for p in r["data"][:12]:
        print("  %-18s 内容%5d  播放中位%7d  互动率%5.2f%%  收藏率%5.2f%%" % (
            p["pain"], p["n"], p["play_median"],
            p["interact_mean"] * 100, p["fav_rate"] * 100))
