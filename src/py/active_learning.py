# -*- coding: utf-8 -*-
"""active_learning.py —— 抽检样本选取（分层随机 + 主动学习）

采用方案B：随机 200（用于**度量**准确率）+ 主动学习 100（用于**发现错误**）。

为什么要分开（这是本模块最重要的设计约束）：
  · 主动学习刻意挑选最不确定的样本，其错误率必然偏高。
    用它计算准确率不是「有误差」而是**系统性错误**，数字无效。
  · 因此：**随机样本负责度量，主动学习样本负责改进**，两者不可混用。

抽样方式：
  · 分层随机：按相关性级别分层，层内随机抽（保证无偏 + 每层都有覆盖）
  · 主动学习：按不确定性排序，选取最不确定的样本

参考：A Survey of Deep Active Learning (arXiv:2009.00236)；
      Reliable Programmatic WS with Confidence Intervals (arXiv:2508.03896)
"""
import json
import math
import random


def wilson_interval(k, n, z=1.96):
    """Wilson 置信区间（小样本比例估计的标准做法，优于正态近似）"""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(center - half, 4), round(center + half, 4))


def uncertainty_score(rule_label, rule_conf, llm_rel, llm_conf, agreement):
    """综合不确定性（0~1，越大越该给人看）"""
    scores = []
    if rule_label in (None, "?"):
        scores.append(0.9)
    else:
        scores.append(1.0 - float(rule_conf or 0.5))
    scores.append(1.0 - float(llm_conf or 0.5))
    if agreement is not None:
        scores.append(1.0 - float(agreement))
    # 规则与大模型冲突
    if rule_label in ("A", "B", "C", "N") and llm_rel in ("A", "B", "C", "N"):
        if rule_label != llm_rel:
            scores.append(0.85)
            if {rule_label, llm_rel} == {"A", "N"}:
                scores.append(1.0)
    return round(max(scores) if scores else 0.5, 4)


def _build_pool(records, labels, rules_info):
    pool = []
    for i, (rec, lb, ri) in enumerate(zip(records, labels, rules_info)):
        lb = lb or {}
        ri = ri or {}
        sc = uncertainty_score(ri.get("label"), ri.get("confidence", 0.5),
                               lb.get("relevance"), lb.get("confidence", 0.5),
                               lb.get("agreement"))
        pool.append({
            "idx": i, "score": sc,
            "rel": lb.get("relevance", "?"),
            "title": rec.get("title", ""), "tag": rec.get("tag", ""),
            "play": rec.get("play", 0),
            "theme": lb.get("theme", ""), "product_line": lb.get("product_line", ""),
            "llm_conf": lb.get("confidence", 0),
            "agreement": lb.get("agreement"),
            "votes": lb.get("votes", ""),
            "llm_reason": lb.get("reason", ""),
            "rule_label": ri.get("label"), "rule_conf": ri.get("confidence", 0),
            "rule_reason": ri.get("reason", ""),
            "rule_scores": ri.get("scores", {}),
            "lf_votes": ri.get("lf_votes", {}),
        })
    return pool


# 方案B的分层配额
RANDOM_QUOTA = {"A": 80, "B": 40, "C": 60, "N": 20}


def select_audit(records, labels, rules_info, random_n=200, active_n=100,
                 quota=None, seed=2026):
    """返回 (随机样本, 主动学习样本)

    随机样本按级别分层配额抽取；不足配额时从剩余样本补齐，超出则截断。
    主动学习样本从**未被随机抽中**的样本里按不确定性排序选取。
    """
    quota = quota or RANDOM_QUOTA
    pool = _build_pool(records, labels, rules_info)
    rng = random.Random(seed)

    random_pick, used = [], set()
    # 1) 按配额分层随机
    for rel, q in quota.items():
        cand = [p for p in pool if p["rel"] == rel]
        rng.shuffle(cand)
        take = cand[:q]
        random_pick.extend(take)
        used.update(p["idx"] for p in take)

    # 2) 配额不足/超出时的处理
    if len(random_pick) < random_n:
        rest = [p for p in pool if p["idx"] not in used]
        rng.shuffle(rest)
        for p in rest:
            if len(random_pick) >= random_n:
                break
            random_pick.append(p)
            used.add(p["idx"])
    elif len(random_pick) > random_n:
        random_pick = random_pick[:random_n]
        used = {p["idx"] for p in random_pick}

    # 3) 主动学习：从剩余里挑最不确定的
    rest = sorted([p for p in pool if p["idx"] not in used], key=lambda x: -x["score"])
    active_pick = rest[:active_n]
    return random_pick, active_pick


def to_rows(picked, group_name):
    rows = []
    for n, p in enumerate(picked, 1):
        rows.append({
            "抽样组": group_name,
            "编号": n,
            "标题": p["title"],
            "标签": p["tag"],
            "播放量": p["play"],
            "规则判定": p["rule_label"] if p["rule_label"] else "(弃权)",
            "规则理由": p["rule_reason"],
            "规则得分": json.dumps(p["rule_scores"], ensure_ascii=False),
            "规则明细": json.dumps(p["lf_votes"], ensure_ascii=False),
            "大模型相关性": p["rel"],
            "大模型主题": p["theme"],
            "大模型产品线": p["product_line"],
            "大模型置信度": p["llm_conf"],
            "投票一致率": p["agreement"] if p["agreement"] is not None else "",
            "大模型理由": p["llm_reason"],
            "不确定性": p["score"],
            "人工核对(填A/B/C/N)": "",
            "人工备注": "",
        })
    return rows
