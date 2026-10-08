# -*- coding: utf-8 -*-
"""step5_eval.py —— 第5步：评估标注质量（口径已升级）

做五件事：
  1. 主口径：final_label（大模型主判）vs 一轮人工，**只用随机 200 条**（无偏、可公布）+ Wilson 95%CI
  2. 对照：agg_label（规则+大模型加权聚合）、大模型原始判定、规则层单独投票
  3. 后分层加权估计：按 final_label 分层、权重取全量 3,747 条的分布（稳健性检验）
  4. 人工噪声分析：一轮 vs 二轮盲判复核（自洽率 / 谁判错 / 真值区间）
  5. 每条规则的 coverage 与实测精度（借鉴 ULF 的规则校验思想）+ 导出错误清单

两条纪律（务必遵守）：
  · 准确率**只用随机组**算。主动组是按不确定性挑出来的，用它度量是系统性错误。
  · **不自动写 rule_weights.json**。在本次人工子集上调参、再回到同一子集评估 = 过拟合。
    规则精度只作为「错误分析」与「下一轮改规则」的依据。
"""
import csv
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pipeline_common import ROOT, DATA_CLEAN, RESULTS
from active_learning import wilson_interval

CSV = os.path.join(RESULTS, "人工抽检_300条_方案B.csv")
LABELED = os.path.join(DATA_CLEAN, "labeled.jsonl")
ERR_CSV = os.path.join(RESULTS, "抽检错误清单.csv")
PREC_JSON = os.path.join(RESULTS, "规则精度.json")

HUMAN = "人工核对(填A/B/C/N)"
HUMAN2 = "人工复核(2轮)"
CLASSES = ["A", "B", "C", "N"]


def pct(k, n):
    return 0.0 if not n else k / n * 100.0


def line(name, k, n, ci=True):
    s = "  %-32s %4d/%-4d = %5.1f%%" % (name, k, n, pct(k, n))
    if ci and n:
        lo, hi = wilson_interval(k, n)
        s += "   95%%CI %5.1f%%~%5.1f%%" % (lo * 100, hi * 100)
    return s


def norm(v):
    return (v or "").strip().upper()


def human_final(r):
    """可用的最佳人工判断：二轮复核非空则用二轮，否则用一轮"""
    h2 = norm(r.get(HUMAN2))
    return h2 if h2 else norm(r.get(HUMAN))


def err_type(model, human):
    if model == human:
        return ""
    if model == "A":
        return "A 假阳性（非硬件主体被判成 A）"
    if model == "B":
        return "B 假阳性（%s 被判成耗材/非智能用品）" % human
    if model == "C":
        return "C 假阳性（%s 被判成用户语境）" % human
    if model == "N":
        return "N 假阳性（宠物内容被判成非宠物）"
    return "其他"


def main():
    if not os.path.exists(CSV):
        print("找不到 results/人工抽检_300条_方案B.csv")
        print("请先运行「7_生成抽检表.bat」，或先用 step4b_merge_audit.py 生成合并表")
        return 1
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    rand = [r for r in rows if (r.get("抽样组") or "").startswith("随机")]
    act = [r for r in rows if (r.get("抽样组") or "").startswith("主动")]
    print("读入抽检表 %d 条（随机组 %d / 主动组 %d）" % (len(rows), len(rand), len(act)))

    def acc(rs, field, hfield=HUMAN):
        return sum(1 for r in rs if norm(r.get(field)) == norm(r.get(hfield)))

    # ================= 一、主口径 =================
    print("")
    print("=" * 78)
    print("一、主口径准确率：final_label（大模型主判） vs 一轮人工")
    print("=" * 78)
    for name, rs in [("随机 200（无偏，可公布）", rand),
                     ("主动 100（难样本，不用于度量）", act),
                     ("全部 300", rows)]:
        print(line(name, acc(rs, "final_label"), len(rs)))

    print("")
    print("  同一批随机 200 条上的其它口径（对照）：")
    print(line("agg_label 规则+大模型加权聚合", acc(rand, "agg_label"), len(rand)))
    print(line("大模型相关性（投票后的原始判定）", acc(rand, "大模型相关性"), len(rand)))
    print(line("规则判定（规则层单独投票）", acc(rand, "规则判定"), len(rand)))

    # ================= 二、后分层加权 =================
    pop = Counter()
    if os.path.exists(LABELED):
        for ln in open(LABELED, encoding="utf-8"):
            if ln.strip():
                pop[json.loads(ln).get("final_label")] += 1
    if pop and rand:
        print("")
        print("=" * 78)
        print("二、后分层加权估计（按 final_label 分层，权重取全量 %d 条的分布）" % sum(pop.values()))
        print("=" * 78)
        tot = float(sum(pop.values()))
        num = den = 0.0
        for k in CLASSES:
            n_pop = pop.get(k, 0)
            if not n_pop:
                continue
            cell = [r for r in rand if norm(r.get("final_label")) == k]
            w = n_pop / tot
            if not cell:
                print("   层 %s：总体 %5d 条（%5.1f%%）  抽检 0 条 —— 无法估计" % (k, n_pop, w * 100))
                continue
            p = acc(cell, "final_label") / float(len(cell))
            num += w * p
            den += w
            print("   层 %s：总体 %5d 条（%5.1f%%）  抽检 %3d 条   层内准确率 %5.1f%%"
                  % (k, n_pop, w * 100, len(cell), p * 100))
        if den:
            naive = pct(acc(rand, "final_label"), len(rand))
            post = num / den * 100
            print("   → 后分层加权总体准确率：%.1f%%   （朴素估计 %.1f%%，相差 %.1f 个百分点）"
                  % (post, naive, abs(post - naive)))

    # ================= 三、人工噪声 =================
    print("")
    print("=" * 78)
    print("三、人工噪声分析（一轮 vs 二轮盲判复核）")
    print("=" * 78)
    judged = [r for r in rows if norm(r.get(HUMAN2))]
    if not judged:
        print("  二轮复核列全空，跳过。")
    else:
        changed = [r for r in judged if norm(r.get(HUMAN2)) != norm(r.get(HUMAN))]
        print("  二轮复核了 %d 条（都是模型与人工分歧的条目）" % len(judged))
        print("  其中改判 %d 条、维持原判 %d 条  →  人工自洽率 %.1f%%"
              % (len(changed), len(judged) - len(changed), pct(len(judged) - len(changed), len(judged))))
        jr = [r for r in judged if (r.get("抽样组") or "").startswith("随机")]
        cr = [r for r in jr if norm(r.get(HUMAN2)) != norm(r.get(HUMAN))]
        print("  随机组：复核 %d 条，改判 %d 条（仅随机组影响可公布的准确率）" % (len(jr), len(cr)))
        to_model = sum(1 for r in changed if norm(r.get("final_label")) == norm(r.get(HUMAN2)))
        print("  改判后有 %d 条与模型一致（= 一轮人工当时判错）" % to_model)
        a1 = pct(acc(rand, "final_label", HUMAN), len(rand))
        a2 = pct(sum(1 for r in rand if norm(r.get("final_label")) == human_final(r)), len(rand))
        print("")
        print("  随机 200 准确率：一轮原判 %.1f%%  →  二轮复核后 %.1f%%" % (a1, a2))
        print("  ⚠️ 复核只发生在模型提出异议的条目上，机制上只会让模型显得更好，")
        print("     且「模型与人工错到一块去」的条目查不出来 → 复核后的数字是**上限**。")
        print("     因此真值区间约为 [%.1f%%, %.1f%%]，公开建议用保守的一轮原判 %.1f%%。" % (a1, a2, a1))

    # ================= 四、规则精度 =================
    print("")
    print("=" * 78)
    print("四、各规则实测精度（借鉴 ULF 的规则校验思想）")
    print("=" * 78)
    prec_all, prec_rand = {}, {}
    for r in rows:
        try:
            lf = json.loads(r.get("规则明细") or "{}")
        except Exception:
            lf = {}
        h = norm(r.get(HUMAN))
        is_rand = (r.get("抽样组") or "").startswith("随机")
        for rid, info in (lf or {}).items():
            if not info or not info.get("vote"):
                continue
            for store in ((prec_all, prec_rand) if is_rand else (prec_all,)):
                s = store.setdefault(rid, [0, 0])
                s[0] += 1
                if info["vote"] == h:
                    s[1] += 1
    print("  %-22s %8s %8s | %8s %8s" % ("规则", "全300投票", "精度", "随机200投票", "精度"))
    for rid in sorted(prec_all, key=lambda k: -(prec_all[k][1] / max(1, prec_all[k][0]))):
        v, c = prec_all[rid]
        v2, c2 = prec_rand.get(rid, [0, 0])
        flag = "  <-- 精度偏低" if c / v < 0.8 else ""
        print("  %-22s %8d %7.1f%% | %8d %7.1f%%%s"
              % (rid, v, c / v * 100, v2, (c2 / v2 * 100 if v2 else 0.0), flag))
    json.dump({"all300": {k: {"voted": v, "correct": c, "precision": round(c / v, 4)} for k, (v, c) in prec_all.items()},
               "random200": {k: {"voted": v, "correct": c, "precision": round(c / v, 4)} for k, (v, c) in prec_rand.items()}},
              open(PREC_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("")
    print("  说明：**不自动写 rule_weights.json** —— 在本次人工子集上调参、又回到同一子集")
    print("        评估会过拟合（实测：用 100 条主动样本校准会让准确率从 87.5% 掉到 81.0%）。")

    # ================= 五、错误清单 =================
    print("")
    print("=" * 78)
    print("五、错误清单（final_label vs 最佳人工判断）")
    print("=" * 78)
    errs, types = [], Counter()
    for r in rows:
        m = norm(r.get("final_label"))
        h = human_final(r)
        if m == h:
            continue
        t = err_type(m, h)
        types[t] += 1
        errs.append({
            "抽样组": r.get("抽样组", ""), "编号": r.get("编号", ""),
            "标题": r.get("标题", ""), "标签": r.get("标签", ""),
            "人工一轮": norm(r.get(HUMAN)), "人工二轮": norm(r.get(HUMAN2)),
            "final_label": m, "agg_label": norm(r.get("agg_label")),
            "大模型原始判定": norm(r.get("大模型相关性")),
            "规则判定": r.get("规则判定", ""),
            "错误类型": t,
            "是否二轮改判": "是" if norm(r.get(HUMAN2)) and norm(r.get(HUMAN2)) != norm(r.get(HUMAN)) else "",
        })
    print("  错误共 %d 条（随机组 %d / 主动组 %d）" % (
        len(errs),
        sum(1 for e in errs if e["抽样组"].startswith("随机")),
        sum(1 for e in errs if e["抽样组"].startswith("主动"))))
    print("")
    print("  按错误类型分组：")
    for t, n in types.most_common():
        print("    %-34s %3d 条" % (t, n))
    if errs:
        with open(ERR_CSV, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(errs[0].keys()))
            w.writeheader()
            w.writerows(errs)
        print("")
        print("  已写出 results/抽检错误清单.csv")
    print("  已写出 results/规则精度.json")
    print("")
    print("下一步：跑「9_跑分析.bat」做五路分析")
    return 0


if __name__ == "__main__":
    sys.exit(main())
