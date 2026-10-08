# -*- coding: utf-8 -*-
"""build_agent.py —— 把数据与页面模板组装成**单文件**「运营问数 Agent」

交付形态
--------
agent/运营问数Agent.html —— 双击即可打开，不联网也能跑（规则路由 + 浏览器内计算）。
勾选/填入 DeepSeek API Key 后，规则匹配不上的问题会交给大模型做意图识别。

为什么打包成单文件
------------------
和「平安银行运营指标监控」那个 Agent 一样：交付物要能双击打开、不需要后端。
浏览器读不了本地文件系统，所以数据必须内嵌。

打包策略（体积与表达力的权衡）
------------------------------
· 4,375 条记录按「列式」存储（一列一个数组），比行式 JSON 小约 40%
· 字符串列（品牌/痛点/场景）用列表，其余用数字
· 比率定点 4 位、时长取整
· 图表库 Plotly 内联，保证离线与视觉一致

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
OUT_HTML = os.path.join(AGENT, "运营问数Agent.html")

LABELED = os.path.join(DATA_CLEAN, "labeled.jsonl")

# 内嵌到网页的列（只留分析要用的，控制体积）
COLS = ["t", "pl", "c", "ct", "b", "pn", "sc", "fm", "d",
        "p", "l", "f", "r", "dm", "it", "fr", "y", "o", "m", "k"]

# 标注质量（来自 src/py/step5_eval.py 最近一次运行；重跑评估后请同步这里）
ACCURACY = {
    "main": 88.0, "ci": [82.8, 91.8], "post": 87.3,
    "reviewed": 93.5, "self_consistency": 38.2,
    "note": "随机 200 条分层抽样，人工抽检；自一致性投票有约 ±1.5pp 的方法方差",
}


def num(x, n=4):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, n)


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

    n = len(recs)
    dist = {}
    for c in cols["c"]:
        dist[c] = dist.get(c, 0) + 1

    meta = {
        "n_rows": n,
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
    print("数据打包：%d 行 / %.2f MB（JSON）" % (data["meta"]["n_rows"], len(payload.encode("utf-8")) / 1048576))

    try:
        from plotly.offline import get_plotlyjs
        plotly = get_plotlyjs()
        # 内联 JS 时若出现字面量 </script>，会把外层 <script> 提前闭合 —— 必须转义
        plotly = plotly.replace("</script>", "<\\/script>")
        print("Plotly 内联：%.2f MB" % (len(plotly.encode("utf-8")) / 1048576))
    except Exception as e:
        print("取 Plotly 失败（改为走 CDN）：", e)
        plotly = ""

    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("/*__DATA__*/", "window.DATA=" + payload + ";")
    if plotly:
        html = html.replace("/*__PLOTLY__*/", plotly)
    else:
        html = html.replace("/*__PLOTLY__*/",
                            "/* plotly 未内联：需要联网时从 CDN 加载 */")
        html = html.replace("</head>",
                            '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script></head>')

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成 %s（%.2f MB）" % (os.path.relpath(OUT_HTML, PROJ),
                                os.path.getsize(OUT_HTML) / 1048576))
    return 0


if __name__ == "__main__":
    sys.exit(main())
