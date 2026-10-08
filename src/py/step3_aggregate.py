# -*- coding: utf-8 -*-
"""step3_aggregate.py —— 第3步：产出最终标签（大模型主判）+ 规则层覆盖度报告

【口径决定 · 有实测依据，不是拍脑袋】
最终标签 final_label = **大模型**（temperature=0 主判，低置信样本经自一致性投票）。
规则层（19 条 LF）仍然逐条投票并加权聚合，但结果写入 agg_label 字段，**不再覆盖大模型**。

依据（200 条分层随机抽检 = 无偏度量集，对比人工标注）：
    只用大模型 ............ 89.5%
    默认先验权重聚合 ...... 87.5%
    精度校准后聚合 ........ 81.0%（校准只在 100 条主动样本上做，小样本把好规则误杀）
    修复子串 bug 后聚合 ... 88.5%（LF_SUPPLY 精度 14.9% → 40.0%）
  → 规则层在本数据集上**不能提升最终标签质量**，故降级为「可解释性 + 覆盖度」报告。
  → 这与项目既定决策一致：「LLM 主判，规则辅助」。

规则层的价值保留在三处：
  ① 每条规则的 coverage 与实测精度（见 step5 评估）；
  ② agg_label 作为独立视角参与评估；
  ③ 错误分析时定位"规则为什么错"，用于回补词典（本轮已据此修掉「猫砂盆」子串 bug）。

产出：
  data/clean/labeled.jsonl    final_label（大模型）+ agg_label（规则聚合）+ 投票明细
  results/规则coverage.json   每条规则的覆盖率（非弃权比例）
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pipeline_common import ROOT, DATA_CLEAN, RESULTS, load_records, load_labels
from classifier import lf_votes, coverage_and_votes
from aggregator import aggregate, load_weights


def main():
    recs = load_records()
    if recs is None:
        return 1
    labels, src = load_labels()
    if labels is None:
        print("找不到标注结果，请先完成「4_大模型标注.bat」和「5_大模型投票.bat」")
        return 1
    if len(labels) != len(recs):
        print("标注数与记录数不一致（%d vs %d），请检查" % (len(labels), len(recs)))
        return 1
    print("记录 %d 条，标注来源：%s" % (len(recs), src))

    # ---- 规则层 ----
    print("")
    print("--- 规则层 coverage（非弃权比例）---")
    lf_all = [lf_votes(r.get("title", ""), r.get("tag", "")) for r in recs]
    cov = coverage_and_votes(recs)
    for rid, s in sorted(cov.items(), key=lambda kv: -kv[1]["coverage"]):
        if s["coverage"] > 0:
            print("  %-22s %6.1f%%   %s" % (rid, s["coverage"] * 100, s["by_class"]))
    any_vote = sum(1 for v in lf_all if any(x.get("vote") for x in v.values())) / len(recs)
    print("  至少一条规则投票的记录：%.1f%%" % (any_vote * 100))

    weights, calibrated = load_weights(ROOT)
    print("  权重来源：%s" % ("人工抽检校准" if calibrated else "默认先验"))

    # ---- 聚合 ----
    print("")
    print("--- 加权投票聚合 ---")
    final = []
    for rec, lf, lb in zip(recs, lf_all, labels):
        llm_rel = (lb or {}).get("relevance")
        res = aggregate(lf, weights=weights, llm_label=llm_rel)
        # final_label 取大模型判定；agg_label 保留规则层独立加权投票的结果（仅作对照）
        final_label = llm_rel if llm_rel in ("A", "B", "C", "N") else res["label"]
        final.append({"label": final_label, "agg_label": res["label"],
                      "scores": res["scores"], "margin": res.get("margin"), "llm": lb,
                      "lf_votes": lf, "n_voted": len(res["voters"]),
                      "n_abstain": len(res["abstained"])})

    dist = Counter(f["label"] for f in final)
    print("  最终标签分布（final_label = 大模型主判）：")
    for k in ["A", "B", "C", "N", None]:
        if dist.get(k):
            print("    %-6s %5d  (%.1f%%)" % (str(k), dist[k], dist[k] / len(final) * 100))
    adist = Counter(f["agg_label"] for f in final)
    print("  规则层独立聚合（agg_label，仅作对照）：" + str(dict(adist)))
    diff = sum(1 for f in final if f["label"] != f["agg_label"])
    print("  两者不一致的记录：%d 条 (%.1f%%)" % (diff, diff / len(final) * 100))
    low = sum(1 for f in final if (f["margin"] or 1) < 0.15)
    print("  低优势样本（margin<0.15）：%d 条 (%.1f%%)" % (low, low / len(final) * 100))

    # ---- 落盘 ----
    with open(os.path.join(DATA_CLEAN, "labeled.jsonl"), "w", encoding="utf-8") as f:
        for rec, fi in zip(recs, final):
            row = dict(rec)
            row["final_label"] = fi["label"]
            row["agg_label"] = fi["agg_label"]
            row["vote_scores"] = fi["scores"]
            row["margin"] = fi["margin"]
            row["llm"] = fi["llm"]
            row["lf_votes"] = fi["lf_votes"]
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(os.path.join(RESULTS, "规则coverage.json"), "w", encoding="utf-8") as f:
        json.dump(cov, f, ensure_ascii=False, indent=2)
    print("")
    print("已写出 data/clean/labeled.jsonl")
    print("已写出 results/规则coverage.json")
    print("")
    print("下一步：双击「7_生成抽检表.bat」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
