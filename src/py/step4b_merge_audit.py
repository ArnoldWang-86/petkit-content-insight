# -*- coding: utf-8 -*-
"""step4b_merge_audit.py —— 抽检表合并（方案甲：复用人工标注，刷新模型/规则列）

背景
----
results/人工抽检_300条_方案B(打分).csv 是上一轮流程产出的抽检表。
它里面的人工标注（一轮「人工核对」+ 二轮「人工复核」）**是有效资产**，
但「规则明细 / 大模型*」几列是**旧口径**（12 条旧规则 + 旧提示词 + 旧模型）。

本脚本按「标题 + 播放量」把两边的数据接起来：
  · 抽样结构（随机 200 / 主动 100）与人工标注  → 从旧表**原样搬过来**
  · 规则层与模型层的全部字段                  → 用新流程的产物刷新

为什么这样是成立的：
  · 人工判断只看标题+标签，与流程版本无关，且总体（3,747 条）自那次抽样后未变
  · 全量 300 条标题+播放量都能 100% 精确匹配到当前数据集（含 2 条重名标题，用播放量可区分）
  · 因此「同一批 items + 同一份人工判断 + 全新的系统输出」= 可公平评价新流程

产出
----
results/人工抽检_300条_方案B.csv     （新文件；旧表 (打分).csv 一个字节都不改）
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pipeline_common import ROOT, DATA_CLEAN, RESULTS
from aggregator import aggregate, load_weights

OLD = os.path.join(RESULTS, "人工抽检_300条_方案B(打分).csv")
NEW = os.path.join(RESULTS, "人工抽检_300条_方案B.csv")
LABELED = os.path.join(DATA_CLEAN, "labeled.jsonl")

HUMAN = "人工核对(填A/B/C/N)"
HUMAN2 = "人工复核(2轮)"

COLS = ["抽样组", "编号", "标题", "标签", "播放量",
        "规则判定", "规则得分", "规则明细",
        "大模型相关性", "大模型主题", "大模型产品线", "大模型置信度", "投票一致率", "大模型理由",
        "final_label", "agg_label", "优势度margin",
        HUMAN, HUMAN2, "人工备注"]


def main():
    if not os.path.exists(OLD):
        print("找不到 %s" % OLD)
        return 1
    if not os.path.exists(LABELED):
        print("找不到 data/clean/labeled.jsonl，请先跑「6_聚合标注.bat」")
        return 1

    old_rows = list(csv.DictReader(open(OLD, encoding="utf-8-sig")))
    labeled = [json.loads(l) for l in open(LABELED, encoding="utf-8") if l.strip()]
    weights, calibrated = load_weights(ROOT)
    print("旧表 %d 条；新流程 labeled.jsonl %d 条" % (len(old_rows), len(labeled)))
    print("聚合权重来源：%s" % ("人工抽检校准" if calibrated else "默认先验"))

    # 按「标题 + 播放量」建索引（标题可能重名，用播放量唯一化）
    index = {}
    for x in labeled:
        index[(x.get("title", ""), str(x.get("play", "")))] = x

    rows, miss = [], []
    for n, r in enumerate(old_rows, 1):
        key = (r.get("标题", ""), str(r.get("播放量", "")).strip())
        x = index.get(key)
        if x is None:
            miss.append((n, r.get("标题", "")))
            continue
        lf = x.get("lf_votes") or {}
        only_rules = aggregate(lf, weights=weights, llm_label=None)
        lb = x.get("llm") or {}
        rows.append({
            "抽样组": r.get("抽样组", ""),
            "编号": r.get("编号", ""),
            "标题": x.get("title", ""),
            "标签": x.get("tag", ""),
            "播放量": x.get("play", 0),
            "规则判定": only_rules.get("label") or "全弃权",
            "规则得分": json.dumps(only_rules.get("scores") or {}, ensure_ascii=False),
            "规则明细": json.dumps(lf, ensure_ascii=False),
            "大模型相关性": lb.get("relevance", ""),
            "大模型主题": lb.get("theme", ""),
            "大模型产品线": lb.get("product_line", ""),
            "大模型置信度": lb.get("confidence", ""),
            "投票一致率": lb.get("agreement", "") if lb.get("agreement") is not None else "",
            "大模型理由": lb.get("reason", ""),
            "final_label": x.get("final_label", ""),
            "agg_label": x.get("agg_label", ""),
            "优势度margin": x.get("margin", ""),
            HUMAN: r.get(HUMAN, ""),
            HUMAN2: r.get(HUMAN2, ""),
            "人工备注": r.get("人工备注", ""),
        })

    if miss:
        print("")
        print("[警告] 有 %d 条在数据集中找不到对应记录：" % len(miss))
        for n, t in miss[:10]:
            print("   行%d %s" % (n, t[:50]))

    with open(NEW, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)

    # ---- 核对：人工列必须与旧表逐行一致 ----
    same = sum(1 for a, b in zip(old_rows, rows) if a.get(HUMAN, "") == b[HUMAN])
    same2 = sum(1 for a, b in zip(old_rows, rows) if a.get(HUMAN2, "") == b[HUMAN2])
    print("")
    print("已写出 results/人工抽检_300条_方案B.csv（%d 条）" % len(rows))
    print("人工列一致性校验：一轮 %d/%d，二轮 %d/%d" % (same, len(rows), same2, len(rows)))

    n_h2 = sum(1 for b in rows if b[HUMAN2].strip())
    n_rule = sum(1 for b in rows if b["规则判定"] != "全弃权")
    print("二轮复核列非空 %d 条；有规则投票的 %d 条" % (n_h2, n_rule))
    print("")
    print("下一步：运行「8_评估标注质量.bat」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
