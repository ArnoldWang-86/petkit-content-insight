# -*- coding: utf-8 -*-
"""aggregator.py —— 加权投票聚合层

设计依据：
  1. 不加权的多数投票会失效 —— 高精度低覆盖与低精度高覆盖的来源冲突时，
     应按估计精度加权，冲突时听信精度更高的那条。
     —— Snorkel (arXiv:1711.10160) Example 1.1
  2. 但不引入完整生成式 label model：Snorkel 原文实测「建模优势」在部分数据集
     仅 0.1%，且理论上以 O(标签密度²) 增长；本项目规则少（十余条）、类别少（4 类），
     标签密度低，按原文结论**加权投票即可**。
     —— Snorkel (arXiv:1711.10160) Proposition 1 (Low-Density Upper Bound)

因此本模块实现「按精度加权的多数投票」，权重可由人工抽检实测的精度覆盖默认先验。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classifier import lf_votes

# 默认权重（先验）。可由人工抽检实测精度覆盖（见 load_weights / calibrate）
DEFAULT_WEIGHTS = {
    "LF_A_BRAND_HW":     1.60,   # 宠物品牌+硬件词：最强证据
    "LF_A_PET_HW_SMART": 1.30,
    "LF_A_PRODUCT_FOCUS": 1.20,
    "LF_C_PET_BEHAVIOR":  1.20,
    "LF_SECURITY":        0.90,
    "LF_C_PET_ONLY":     1.00,
    "LF_B_PET_HW_PLAIN": 1.10,   # 宠物+硬件但无智能属性 → 普通用品
    "LF_SUPPLY":         0.90,
    "LF_HEALTH":         0.90,
    "LF_NOISE":          0.45,   # 先验故意压低：实测它误杀过真内容
    "LF_GAME":           0.95,
}

WEIGHTS_FILE = "rule_weights.json"


def load_weights(root=None):
    """读取经人工抽检校准过的权重；没有则用默认先验"""
    if root:
        p = os.path.join(root, "data", "clean", WEIGHTS_FILE)
        if os.path.exists(p):
            import json
            try:
                w = json.load(open(p, encoding="utf-8"))
                merged = dict(DEFAULT_WEIGHTS)
                merged.update(w)
                return merged, True
            except Exception:
                pass
    return dict(DEFAULT_WEIGHTS), False


def calibrate_weights(rule_precision, base=None, lo=0.4, hi=1.8):
    """用实测精度校准权重（借鉴 ULF 的规则校验思想）

    精度 50%（等于瞎猜）→ 权重压到 lo；精度 100% → 权重提到 hi。
    """
    w = dict(base or DEFAULT_WEIGHTS)
    for rid, s in (rule_precision or {}).items():
        if rid not in w:
            continue
        p = s.get("precision")
        if p is None:
            continue
        # 映射：0.5 -> lo, 1.0 -> hi
        t = max(0.0, min(1.0, (p - 0.5) / 0.5))
        w[rid] = round(lo + (hi - lo) * t, 3)
    return w


def aggregate(lf, weights=None, llm_label=None, llm_weight=None):
    """加权投票

    lf         : lf_votes() 的输出
    weights    : 规则权重
    llm_label  : 大模型的判定（作为一条额外的高权重投票者）
    llm_weight : 大模型投票的权重

    返回 {"label":..., "scores": {类别: 得分}, "voters": [...], "abstained": [...]}
    """
    w = weights or DEFAULT_WEIGHTS
    scores = {}
    voters = []
    abstained = []

    for rid, info in lf.items():
        if info.get("vote"):
            wt = w.get(rid, 0.5)
            scores[info["vote"]] = scores.get(info["vote"], 0) + wt
            voters.append({"rule": rid, "vote": info["vote"], "weight": wt})
        else:
            abstained.append(rid)

    if llm_label in ("A", "B", "C", "N"):
        wt = llm_weight if llm_weight is not None else 1.50   # 大模型作为强投票者
        scores[llm_label] = scores.get(llm_label, 0) + wt
        voters.append({"rule": "LLM", "vote": llm_label, "weight": wt})

    if not scores:
        return {"label": None, "scores": {}, "voters": [], "abstained": abstained}

    label = max(scores.items(), key=lambda kv: kv[1])[0]
    total = sum(scores.values()) or 1
    return {"label": label,
            "scores": {k: round(v, 3) for k, v in scores.items()},
            "margin": round((scores[label] - sorted(scores.values())[-2]) / total, 4)
                      if len(scores) > 1 else 1.0,
            "voters": voters, "abstained": abstained}
