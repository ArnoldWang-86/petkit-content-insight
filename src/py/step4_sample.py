# -*- coding: utf-8 -*-
"""step4_sample.py —— 第4步：生成人工抽检表（方案B）

方案B：分层随机 200 条（用于**度量**准确率）+ 主动学习 100 条（用于**发现错误**）

为什么必须分开（本步最重要的约束）：
  主动学习刻意挑最不确定的样本，其错误率必然偏高。
  用它算准确率是**系统性错误**，因此两组不可混用。

参考：A Survey of Deep Active Learning (arXiv:2009.00236)
      Reliable Programmatic WS with Confidence Intervals (arXiv:2508.03896)
"""
import csv
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pipeline_common import ROOT, DATA_CLEAN, RESULTS
from active_learning import select_audit, to_rows

RANDOM_N = 200
ACTIVE_N = 100


def main():
    p = os.path.join(DATA_CLEAN, "labeled.jsonl")
    if not os.path.exists(p):
        print("找不到 data/clean/labeled.jsonl，请先运行「6_聚合标注.bat」")
        return 1
    recs = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    print("读取已标注记录 %d 条" % len(recs))

    # 组装抽检所需的三份输入
    labels, rules_info = [], []
    for r in recs:
        labels.append(r.get("llm") or {})
        rules_info.append({
            "label": r.get("final_label"),
            "confidence": 0.5 + (r.get("margin") or 0) / 2,
            "reason": "",
            "scores": r.get("vote_scores") or {},
            "lf_votes": r.get("lf_votes") or {},
        })

    print("")
    print("--- 抽检选取 ---")
    rand_pick, act_pick = select_audit(recs, labels, rules_info,
                                       random_n=RANDOM_N, active_n=ACTIVE_N)
    print("  随机组 %d 条（用于度量）分布：%s" % (
        len(rand_pick), dict(Counter(p["rel"] for p in rand_pick))))
    print("  主动组 %d 条（用于改进）平均不确定性：%.3f" % (
        len(act_pick), sum(p["score"] for p in act_pick) / max(1, len(act_pick))))
    print("  随机组平均不确定性：%.3f  <- 应明显低于主动组" % (
        sum(p["score"] for p in rand_pick) / max(1, len(rand_pick))))

    rows = to_rows(rand_pick, "随机(度量用)") + to_rows(act_pick, "主动(改进用)")
    out = os.path.join(RESULTS, "人工抽检_300条_方案B.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)

    print("")
    print("已写出 results/人工抽检_300条_方案B.csv（共 %d 条）" % len(rows))
    print("")
    print("请打开该文件，在「人工核对(填A/B/C/N)」列填入 A / B / C / N。")
    print("  只有「随机(度量用)」那 200 条可用于计算准确率；")
    print("  「主动(改进用)」那 100 条只用于发现错误。")
    print("")
    print("填完后双击「8_评估标注质量.bat」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
