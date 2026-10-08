# -*- coding: utf-8 -*-
"""build_agent.py —— 组装「运营问数 Agent」

两种产物
--------
1) agent/问数Agent_本机演示.html
   内嵌 DeepSeek API Key，双击就能用。**这个文件已在 .gitignore 里，永不提交。**
2) agent/问数Agent.html
   不含任何 Key，双击后需要自己填 Key。这个才会提交到仓库。

为什么必须分成两个
------------------
Key 一旦进了公开仓库，几分钟内就会被爬虫扫走并盗用。
所以「本机演示用」和「可以给别人看」必须是两个文件。

用法： python agent/src/build_agent.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.abspath(os.path.join(HERE, ".."))
PROJ = os.path.abspath(os.path.join(AGENT, ".."))
DATA_CLEAN = os.path.join(PROJ, "data", "clean")

TEMPLATE = os.path.join(HERE, "template.html")
SHEETJS = os.path.join(AGENT, "tools", "xlsx.full.min.js")
OUT_PUBLIC = os.path.join(AGENT, "问数Agent.html")            # 无 Key，提交
OUT_LOCAL = os.path.join(AGENT, "问数Agent_本机演示.html")     # 含 Key，不提交（gitignore）

LABELED = os.path.join(DATA_CLEAN, "labeled.jsonl")

COLS = ["t", "pl", "c", "ct", "b", "pn", "sc", "fm", "d",
        "p", "l", "f", "r", "dm", "it", "fr", "y", "o", "m", "k"]

# 标注质量：来自 src/py/step5_eval.py 最近一次运行；重跑评估后请同步这里
ACCURACY = {
    "main": 88.0, "ci": [82.8, 91.8], "post": 87.3,
    "reviewed": 93.5, "self_consistency": 38.2,
}


def num(x, n=4):
    try:
        return round(float(x), n)
    except (TypeError, ValueError):
        return None


def read_env_key():
    """从项目根的 .env 读取 Key（该文件已被 gitignore）。"""
    p = os.path.join(PROJ, ".env")
    if not os.path.exists(p):
        return ""
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def build_data():
    recs = [json.loads(l) for l in open(LABELED, encoding="utf-8") if l.strip()]
    cols = {k: [] for k in COLS}
    for r in recs:
        llm = r.get("llm") or {}
        cols["t"].append(r.get("title", ""))
        cols["pl"].append(llm.get("product_line", "") or "")
        cols["c"].append(r.get("final_label") or "?")
        cols["ct"].append(r.get("cat", "") or "")
        cols["b"].append(r.get("brands") or [])
        cols["pn"].append(r.get("pains") or [])
        cols["sc"].append(r.get("scenes") or [])
        cols["fm"].append(r.get("fmt", "") or "")
        cols["d"].append(int(r.get("duration_s") or 0))
        cols["p"].append(int(r.get("play") or 0))
        cols["l"].append(int(r.get("like") or 0))
        cols["f"].append(int(r.get("fav") or 0))
        cols["r"].append(int(r.get("reply") or 0))
        cols["dm"].append(int(r.get("dm") or 0))
        cols["it"].append(num(r.get("interact"), 4))
        cols["fr"].append(num(r.get("fav_rate"), 4))
        cols["y"].append(int(r.get("pub_year") or 0))
        cols["o"].append(1 if r.get("official") else 0)
        cols["m"].append(r.get("mid"))
        cols["k"].append(r.get("_keyword", "") or "")

    def uniq(key):
        s = set()
        for v in cols[key]:
            if isinstance(v, list):
                s.update(v)
            elif v:
                s.add(v)
        return sorted(s)

    dist = {}
    for c in cols["c"]:
        dist[c] = dist.get(c, 0) + 1

    meta = {
        "n_rows": len(recs),
        "label_dist": dist,
        "creators": len({m for m in cols["m"] if m}),
        "accuracy": ACCURACY,
        "brands": uniq("b"),
        "product_lines": sorted({v for v in cols["pl"] if v}),
        "cats": sorted({v for v in cols["ct"] if v}),
        "pains": uniq("pn"),
        "scenes": uniq("sc"),
        "formats": sorted({v for v in cols["fm"] if v}),
        "keywords": sorted({v for v in cols["k"] if v}),
        "year_range": [min(y for y in cols["y"] if y), max(cols["y"])],
    }
    return {"meta": meta, "cols": COLS, "rows": cols}


def main():
    if not os.path.exists(LABELED):
        print("找不到 %s" % LABELED)
        return 1

    data = build_data()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    print("数据打包：%d 行 / %.2f MB" % (data["meta"]["n_rows"], len(payload.encode("utf-8")) / 1048576))

    with open(SHEETJS, encoding="utf-8") as f:
        xlsx = f.read()
    xlsx = xlsx.replace("</script>", "<\\/script>")   # 防止提前闭合 <script>
    print("SheetJS 内联：%.2f MB" % (len(xlsx.encode("utf-8")) / 1048576))

    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("/*__DATA__*/", "window.DATA=" + payload + ";")
    html = html.replace("/*__XLSX__*/", xlsx)

    key = read_env_key()

    # ---- 公开版：不含 Key ----
    # 注意：必须用专用占位符替换，不能用 </head> ——
    # SheetJS 源码内部也含 "...<html><head>...</head>..." 字符串，
    # 按 </head> 替换会把 Key 注进它的字符串字面量，直接把脚本搞坏（已踩过）。
    pub = html.replace("__AGENT_KEY__", "")
    with open(OUT_PUBLIC, "w", encoding="utf-8") as f:
        f.write(pub)
    print("已生成 %s（%.2f MB，不含 Key）" % (os.path.relpath(OUT_PUBLIC, PROJ),
                                            os.path.getsize(OUT_PUBLIC) / 1048576))

    # ---- 本机演示版：内嵌 Key ----
    if key:
        loc = html.replace("__AGENT_KEY__", key)
        with open(OUT_LOCAL, "w", encoding="utf-8") as f:
            f.write(loc)
        print("已生成 %s（%.2f MB，已内嵌 Key，该文件不会被提交，已在 .gitignore 里）" %
              (os.path.relpath(OUT_LOCAL, PROJ), os.path.getsize(OUT_LOCAL) / 1048576))
    else:
        print("警告：.env 里没有 DEEPSEEK_API_KEY，跳过本机演示版")
    return 0


if __name__ == "__main__":
    sys.exit(main())
