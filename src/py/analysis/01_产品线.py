# -*- coding: utf-8 -*-
"""01_产品线.py —— 哪条产品线用户讨论最热、竞争最激烈

要支持的决策：内容资源先投哪条产品线。
对应 JD 方向3「用户场景观察」中的「发现机会点」。

⚠️ A 级纪律（项目交接文档 1.3）：
   只有 final_label = A（品牌竞争型宠物智能硬件本体）的记录才用于产品线结论。
   C 级萌宠日常不是产品讨论，拿它算"产品线互动率"结论会废掉。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import summarize, group_by

LEVELS = ("A",)
OTHER = "其他硬件"


def product_line(x):
    """A 级记录的产品线：优先用大模型给出的 product_line，缺失时回退到词典 cat"""
    pl = ((x.get("llm") or {}).get("product_line") or "").strip()
    return pl if pl else (x.get("cat") or OTHER)


def run(data):
    groups = group_by(data, product_line)
    result = {k: summarize(v) for k, v in groups.items()}
    result = dict(sorted(result.items(), key=lambda kv: -kv[1]["n"]))

    # 口径交叉校验：大模型 product_line  vs  common.py 词典 cat
    def norm(v):
        return OTHER if (v or "").startswith("其他") else v

    pairs = [(norm(product_line(x)), norm(x.get("cat"))) for x in data
             if ((x.get("llm") or {}).get("product_line") or "").strip()]
    agree = sum(1 for a, b in pairs if a == b)
    check = {"n": len(pairs), "agree": agree,
             "rate": round(agree / len(pairs), 4) if pairs else 0}
    return {"key": "by_category", "title": "产品线讨论度", "data": result,
            "cross": {"口径校验_大模型vs词典": check}}


def print_report(r):
    print("--- 一、产品线讨论度（仅 A 级；哪条线值得投内容资源）---")
    for k, v in r["data"].items():
        print("  %-10s 内容%5d  播放中位%7d  互动率%5.2f%%  收藏率%5.2f%%  创作者%5d" % (
            k, v["n"], v["play_median"], v["interact_mean"] * 100,
            v["fav_rate"] * 100, v["creators"]))
    c = r["cross"]["口径校验_大模型vs词典"]
    print("  口径校验：大模型 product_line 与词典 cat 一致 %d/%d = %.1f%%" % (
        c["agree"], c["n"], c["rate"] * 100))


if __name__ == "__main__":
    import json
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open(os.path.join(root, "data", "clean", "labeled.jsonl"), encoding="utf-8") as fh:
        rows = [json.loads(l) for l in fh if l.strip()]
    print_report(run([x for x in rows if (x.get("final_label") or "") in LEVELS]))
