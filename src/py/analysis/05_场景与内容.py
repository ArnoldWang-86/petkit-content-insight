# -*- coding: utf-8 -*-
"""05_场景与内容.py —— 谁在什么处境下买（场景），各产品线跑出来的头部内容长什么样

要支持的决策：用户画像、内容选题参考。

头部内容清单不是「抄爆款」，而是回答「什么形式的内容在这个品类里跑得出来」。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import summarize, group_by, median

# 使用场景回答"用户是谁"，按纪律使用 A + B + C
LEVELS = ("A", "B", "C")


def run(data):
    by_scene = {k: summarize(v) for k, v in group_by(
        data, lambda x: x["scenes"][0] if x["scenes"] else "未标注场景").items()}
    by_scene = dict(sorted(by_scene.items(), key=lambda kv: -kv[1]["n"]))

    top_videos = {}
    for c in {x["cat"] for x in data}:
        g = sorted([x for x in data if x["cat"] == c], key=lambda x: -x["play"])[:8]
        top_videos[c] = [{
            "play": x["play"], "like": x["like"], "fav": x["fav"], "dm": x["dm"],
            "interact": round(x["interact"], 4), "fmt": x["fmt"],
            "title": x["title"][:60], "author": x["author"],
            "brands": "/".join(x["brands"]), "pains": "/".join(x["pains"]),
        } for x in g]

    base = summarize(data)
    year_dist = {str(k): len(v) for k, v in group_by(data, lambda x: x["pub_year"]).items()}
    overview = {
        "videos": len(data),
        "creators": len({x["mid"] for x in data}),
        "play_median": base.get("play_median", 0),
        "interact_mean": base.get("interact_mean", 0),
        "fav_rate": base.get("fav_rate", 0),
        "duration_median_min": round(median([x["duration_s"] for x in data]) / 60, 2) if data else 0,
        "year_dist": dict(sorted(year_dist.items())),
    }

    return {"key": "by_scene", "title": "场景与头部内容", "data": by_scene,
            "cross": {"top_videos": top_videos}, "overview": overview}


def print_report(r):
    print("--- 七、使用场景（谁在什么处境下买）---")
    for k, v in r["data"].items():
        print("  %-16s 内容%5d  播放中位%7d  互动率%5.2f%%" % (
            k, v["n"], v["play_median"], v["interact_mean"] * 100))
