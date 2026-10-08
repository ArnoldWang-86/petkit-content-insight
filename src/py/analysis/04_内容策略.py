# -*- coding: utf-8 -*-
"""04_内容策略.py —— 做什么形式的内容、视频做多长、哪些选题词效率高、达人怎么分层

要支持的决策：内容形式与时长规格、选题方向、达人投放层级。

注意一个方法学问题：
  「长视频互动率更高」很可能是假象 —— 长视频往往来自更专业的创作者。
  所以这里同时给出「时长 x 产品线」的交叉，避免把创作者能力误读成时长效应。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import summarize, group_by

# 内容形态/时长是投放参考，使用 A（硬件本体）+ B（延伸需求）两层
LEVELS = ("A", "B")


def duration_bin(row):
    d = row["duration_s"]
    if d < 60:
        return "<1min"
    if d < 180:
        return "1-3min"
    if d < 600:
        return "3-10min"
    return ">10min"


def run(data):
    by_format = {k: summarize(v) for k, v in group_by(data, lambda x: x["fmt"]).items()}
    by_format = dict(sorted(by_format.items(), key=lambda kv: -kv[1]["n"]))

    by_duration = {k: summarize(v) for k, v in group_by(data, duration_bin).items()}

    # 时长 x 产品线：同一条产品线内部比较时长，排除「产品线差异」的干扰
    duration_by_cat = {}
    cat_keys = [c for c in {x["cat"] for x in data} if c != "其他/泛宠物"]
    for c in cat_keys:
        g = [x for x in data if x["cat"] == c]
        duration_by_cat[c] = {k: summarize(v) for k, v in group_by(g, duration_bin).items()}

    # 关键词效率
    by_keyword = []
    for k, v in group_by(data, lambda x: x.get("_keyword") or "").items():
        s = summarize(v)
        by_keyword.append({"keyword": k, "n": s["n"], "play_median": s["play_median"],
                           "interact_mean": s["interact_mean"], "fav_rate": s["fav_rate"]})
    by_keyword.sort(key=lambda r: -r["n"])

    # 创作者分层：按播放量排名分头部/腰部/长尾
    sorted_rows = sorted(data, key=lambda x: -x["play"])
    rank = {x["bvid"]: i for i, x in enumerate(sorted_rows)}
    n = len(sorted_rows) or 1

    def tier(x):
        pct = rank.get(x["bvid"], 0) / n
        if pct < 0.1:
            return "头部(播放前10%)"
        if pct < 0.4:
            return "腰部(10-40%)"
        return "长尾(40-100%)"

    by_tier = {k: summarize(v) for k, v in group_by(data, tier).items()}

    return {
        "key": "by_format", "title": "内容策略", "data": by_format,
        "cross": {"by_duration": by_duration, "duration_by_cat": duration_by_cat,
                  "by_keyword": by_keyword, "by_tier": by_tier},
    }


def print_report(r):
    print("--- 四、内容形态效果 ---")
    for k, v in r["data"].items():
        print("  %-12s 内容%5d  播放中位%7d  互动率%5.2f%%  收藏率%5.2f%%" % (
            k, v["n"], v["play_median"], v["interact_mean"] * 100, v["fav_rate"] * 100))
    print("")
    print("--- 五、时长档效果 ---")
    for k, v in r["cross"]["by_duration"].items():
        print("  %-10s 内容%5d  播放中位%7d  互动率%5.2f%%  收藏率%5.2f%%" % (
            k, v["n"], v["play_median"], v["interact_mean"] * 100, v["fav_rate"] * 100))
    print("")
    print("--- 六、创作者分层效率 ---")
    for k, v in r["cross"]["by_tier"].items():
        print("  %-18s 内容%5d  播放中位%7d  互动率%5.2f%%" % (
            k, v["n"], v["play_median"], v["interact_mean"] * 100))
