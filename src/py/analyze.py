# -*- coding: utf-8 -*-
"""analyze.py —— 分析总入口（v2：基于 final_label，落实 A 级纪律）

【本版最重要的改动】
旧版读 clean_detail.jsonl、只用 common.py 的词典字段（cat/brands/pains/scenes/fmt），
**完全没有用到大模型标注出的 final_label** —— 文档 1.3 的「A 级纪律」形同虚设。

本版改为读 data/clean/labeled.jsonl，并**按标签层过滤后**再交给各分析模块：

    分析                使用层      依据（项目交接文档 1.3）
    01 产品线讨论度      仅 A        只有"智能硬件本体"的讨论才能代表产品线热度
    02 品牌声量          仅 A        品牌竞争发生在硬件本体
    03 用户痛点          A+B+C       产品吐槽(A) + 耗材/健康需求(B) + 用户语境(C)，分层报告
    04 内容策略          A+B         内容形态与时长是投放参考
    05 使用场景          A+B+C       回答"用户是谁"

设计说明：每一路分析仍是独立模块（analysis/ 下），可单独运行，也可被本文件统一调用。
加新维度时不用改动已有代码，只需在模块里声明 LEVELS。

产出：results/01~12_*.csv + results/analysis.json
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analysis import 产品线模块, 品牌模块, 痛点模块, 内容策略模块, 场景模块
from common import summarize

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES = os.path.join(ROOT, "results")
DATA_CLEAN = os.path.join(ROOT, "data", "clean")
IN = os.path.join(DATA_CLEAN, "labeled.jsonl")
CLASSES = ["A", "B", "C", "N"]


def load():
    if not os.path.exists(IN):
        print("找不到 data/clean/labeled.jsonl")
        print("请先运行「6_聚合标注.bat」")
        return None
    with open(IN, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_csv(name, rows):
    path = os.path.join(RES, name)
    if not rows:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write("")
        print("  写出 results/%s  (空)" % name)
        return
    keys = list(rows[0].keys())
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=keys)
        wr.writeheader()
        for r in rows:
            wr.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                         for k, v in r.items()})
    print("  写出 results/%s  (%d 行)" % (name, len(rows)))


def main():
    data = load()
    if data is None:
        return 1

    print("有效样本 %d 条，独立创作者 %d 位" % (len(data), len({x.get("mid") for x in data})))
    print("")
    print("--- 标签分布（final_label）---")
    dist = {}
    for x in data:
        k = x.get("final_label") or "?"
        dist.setdefault(k, []).append(x)
    for k in CLASSES + ["?"]:
        if k in dist:
            g = dist[k]
            print("  %-3s %5d 条 (%.1f%%)   播放中位 %7d" % (
                k, len(g), len(g) / len(data) * 100, summarize(g).get("play_median", 0)))
    print("")
    print("--- 各分析使用的标签层（落实文档 1.3 的 A 级纪律）---")

    modules = [产品线模块, 品牌模块, 痛点模块, 内容策略模块, 场景模块]
    results, overview, used = {}, {}, {}
    for m in modules:
        levels = tuple(getattr(m, "LEVELS", ("A", "B", "C", "N")))
        sub = [x for x in data if (x.get("final_label") or "") in levels]
        r = m.run(sub)
        used[r["title"]] = {"levels": list(levels), "n": len(sub)}
        print("   %-12s 用 %-10s → %4d 条" % (r["title"], "+".join(levels), len(sub)))
        results[r["key"]] = r["data"]
        if r.get("cross"):
            results[r["key"] + "_cross"] = r["cross"]
        if r.get("overview"):
            overview.update(r["overview"])
        m.print_report(r)
        if r["key"] != "by_scene":
            print("")

    # ---------- 标签分布表 ----------
    label_rows = []
    for k in CLASSES:
        g = dist.get(k, [])
        if not g:
            continue
        s = summarize(g)
        label_rows.append({"final_label": k, "内容数": s["n"],
                           "占比": round(s["n"] / len(data), 4),
                           "播放中位数": s["play_median"], "互动率": s["interact_mean"],
                           "收藏率": s["fav_rate"], "创作者数": s["creators"]})

    # ---------- 内容主题分布（来自大模型 theme，比词典 fmt 覆盖率高得多）----------
    theme_rows = []
    for k, g in sorted(__import__("collections").Counter(
            (x.get("llm") or {}).get("theme") or "(空)" for x in data).items(),
            key=lambda kv: -kv[1]):
        sub = [x for x in data if ((x.get("llm") or {}).get("theme") or "(空)") == k]
        s = summarize(sub)
        theme_rows.append({"大模型主题": k, "内容数": s["n"], "占比": round(s["n"] / len(data), 4),
                           "播放中位数": s["play_median"], "互动率": s["interact_mean"],
                           "收藏率": s["fav_rate"], "创作者数": s["creators"]})

    # ---------- 产品线口径校验（大模型 product_line vs 词典 cat）----------
    a_rows = [x for x in data if (x.get("final_label") or "") == "A"]
    matrix = {}
    cats = sorted({(x.get("cat") or "其他/泛宠物") for x in a_rows})
    for x in a_rows:
        pl = ((x.get("llm") or {}).get("product_line") or "").strip() or "(空)"
        d = x.get("cat") or "其他/泛宠物"
        matrix.setdefault(pl, {})
        matrix[pl][d] = matrix[pl].get(d, 0) + 1
    check_rows = []
    for pl in sorted(matrix, key=lambda k: -sum(matrix[k].values())):
        row = {"大模型产品线": pl, "合计": sum(matrix[pl].values())}
        for c in cats:
            row[c] = matrix[pl].get(c, 0)
        check_rows.append(row)

    # ---------- 导出 JSON ----------
    payload = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "sample_size": len(data),
        "label_discipline": used,
        "label_distribution": {k: len(v) for k, v in dist.items()},
        "overview": overview,
        "results": results,
    }
    with open(os.path.join(RES, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("输出文件：")
    write_csv("01_产品线.csv", [dict(产品线=k, **v) for k, v in results["by_category"].items()])
    write_csv("02_品牌声量.csv", [
        {"品牌": b["brand"], "提及数": b["n"], "强信号": b["strong_signal"],
         "弱信号": b["weak_signal"], "播放中位数": b["play_median"],
         "互动率": b["interact_mean"], "收藏率": b["fav_rate"],
         "创作者数": b["creators"], "官方内容": b["official"], "达人内容": b["ugc"]}
        for b in results["by_brand"]])
    write_csv("03_用户痛点.csv", [
        {"痛点": p["pain"], "内容数": p["n"], "播放中位数": p["play_median"],
         "互动率": p["interact_mean"], "收藏率": p["fav_rate"],
         "创作者数": p["creators"], "涉及产品线": p["cat_dist"],
         "标签层分布": p.get("label_dist", {})}
        for p in results["pain_points"]])
    write_csv("04_内容形态.csv", [dict(内容形态=k, **v) for k, v in results["by_format"].items()])
    write_csv("05_时长效果.csv", [dict(时长档=k, **v)
                                  for k, v in results["by_format_cross"]["by_duration"].items()])
    write_csv("06_关键词效率.csv", results["by_format_cross"]["by_keyword"])
    write_csv("07_创作者分层.csv", [dict(层级=k, **v)
                                    for k, v in results["by_format_cross"]["by_tier"].items()])
    write_csv("08_使用场景.csv", [dict(场景=k, **v) for k, v in results["by_scene"].items()])

    rows = []
    for brand, v in results["by_brand_cross"]["official_vs_ugc"].items():
        if v.get("official"):
            rows.append(dict(品牌=brand, 来源="官方", **v["official"]))
        if v.get("ugc"):
            rows.append(dict(品牌=brand, 来源="达人/用户", **v["ugc"]))
    write_csv("09_官方vs达人.csv", rows)

    sov = results["by_brand_cross"]["share_of_voice"]
    write_csv("10_横评份额.csv", [
        {"品牌": k, "横评中出现次数": sov["counts"][k], "份额": sov["share"][k]}
        for k in sorted(sov["counts"], key=lambda x: -sov["counts"][x])])

    write_csv("11_标签分布.csv", label_rows)
    write_csv("12_产品线口径校验.csv", check_rows)
    write_csv("13_内容主题.csv", theme_rows)

    print("")
    print("已写出 results/analysis.json")
    print("全部完成。打开 results/ 目录即可查看，CSV 可用 Excel 直接打开。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
