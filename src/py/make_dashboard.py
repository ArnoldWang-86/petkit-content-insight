# -*- coding: utf-8 -*-
"""make_dashboard.py —— 生成交互式看板（单文件 HTML，双击即可打开）

设计：
  · 单文件内嵌 plotly.js（约 3.5MB）→ 断网也能打开，方便交给 HR
  · 数据全部来自 results/ 下的分析 CSV，不再重新计算口径
  · 每张图都写明「支持什么决策」，与项目「先定决策、再找数据」的原则一致
"""
import csv
import os
import sys

import plotly.graph_objects as go

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pipeline_common import ROOT, RESULTS

OUT = os.path.join(ROOT, "docs", "index.html")   # 放 docs/ 下，GitHub Pages 才能直接在线打开
FONT = dict(family="Microsoft YaHei, SimHei, sans-serif", size=13)
PALETTE = ["#2E5C9A", "#C0504D", "#9BBB59", "#8064A2", "#4BACC6", "#F79646", "#7F7F7F"]


def load(name):
    p = os.path.join(RESULTS, name)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def fig_bar(rows, x, y, title, note, color=None, pct=False, horizontal=False):
    vals = [num(r[y]) * (100 if pct else 1) for r in rows]
    names = [r[x] for r in rows]
    f = go.Figure(go.Bar(
        x=vals if horizontal else names, y=names if horizontal else vals,
        orientation="h" if horizontal else "v",
        marker_color=color or PALETTE[0],
        text=["%.1f%%" % v if pct else ("%d" % v) for v in vals],
        textposition="auto"))
    f.update_layout(title=dict(text=title + "<br><sup>" + note + "</sup>", font=FONT),
                    font=FONT, height=420, margin=dict(l=10, r=10, t=80, b=10),
                    yaxis=dict(autorange="reversed") if horizontal else {})
    return f


def fig_group(rows, x, series, title, note):
    f = go.Figure()
    for i, (key, label) in enumerate(series):
        f.add_trace(go.Bar(name=label, x=[r[x] for r in rows], y=[num(r[key]) for r in rows],
                           marker_color=PALETTE[i % len(PALETTE)]))
    f.update_layout(barmode="group", title=dict(text=title + "<br><sup>" + note + "</sup>", font=FONT),
                    font=FONT, height=420, margin=dict(l=10, r=10, t=80, b=10))
    return f


def fig_pie(rows, x, y, title, note):
    f = go.Figure(go.Pie(labels=[r[x] for r in rows], values=[num(r[y]) for r in rows], hole=0.45,
                         marker_colors=PALETTE))
    f.update_layout(title=dict(text=title + "<br><sup>" + note + "</sup>", font=FONT),
                    font=FONT, height=420, margin=dict(l=10, r=10, t=80, b=10))
    return f


def fig_scatter(rows, x, y, label, title, note):
    f = go.Figure(go.Scatter(
        x=[num(r[x]) for r in rows], y=[num(r[y]) for r in rows], mode="markers+text",
        text=[r[label] for r in rows], textposition="top center",
        marker=dict(size=14, color=PALETTE[3])))
    f.update_layout(title=dict(text=title + "<br><sup>" + note + "</sup>", font=FONT),
                    font=FONT, height=440, margin=dict(l=10, r=10, t=80, b=10),
                    xaxis_title=x, yaxis_title=y)
    return f


def main():
    lab = load("11_标签分布.csv")
    cat = load("01_产品线.csv")
    brand = load("02_品牌声量.csv")
    pain = load("03_用户痛点.csv")
    fmt = load("04_内容形态.csv")
    dur = load("05_时长效果.csv")
    tier = load("07_创作者分层.csv")
    scene = load("08_使用场景.csv")
    og = load("09_官方vs达人.csv")
    sov = load("10_横评份额.csv")
    theme = load("13_内容主题.csv")
    if not cat:
        print("results/ 下没有分析 CSV，请先跑「9_跑分析.bat」")
        return 1

    figs = []
    figs.append(("标签分布：3,747 条内容里有多少是真正的硬件讨论",
                 "支持决策：内容洞察的样本结构是否健康（A 直接相关 / B 延伸 / C 用户语境 / N 非宠物）",
                 fig_pie(lab, "final_label", "内容数", "相关性四级分布",
                         "A=品牌竞争型智能硬件本体；C 占比高是真实内容生态，不是错误")))
    figs.append(("产品线讨论度（仅 A 级）",
                 "支持决策：内容资源先投哪条产品线",
                 fig_bar(cat, "产品线", "n", "各产品线内容量", "只统计 final_label=A 的记录", PALETTE[0], horizontal=True)))
    figs.append(("产品线互动效率（仅 A 级）",
                 "支持决策：哪条线的内容更容易引发互动（不是播放量，而是互动率）",
                 fig_bar(cat, "产品线", "interact_mean", "各产品线平均互动率", "互动率 = (点赞+收藏)/播放", PALETTE[1], pct=True, horizontal=True)))
    figs.append(("品牌声量：强信号 vs 弱信号（仅 A 级）",
                 "支持决策：和谁对标、用户真正在讨论谁",
                 fig_group(brand, "品牌", [("强信号", "强信号(标题提及)"), ("弱信号", "弱信号(仅标签)")],
                           "品牌提及量", "强信号=标题直接出现品牌名，更可能是真实产品讨论")))
    figs.append(("横评内份额：更公平的声量口径（仅 A 级）",
                 "支持决策：谁是横评里的「必提品牌」",
                 fig_pie(sov, "品牌", "横评中出现次数", "横评/选购类内容中的品牌份额",
                         "同一条横评里各品牌被一起比较，与采集方式无关")))
    figs.append(("官方内容 vs 达人内容（仅 A 级）",
                 "支持决策：投放该信官方还是信达人",
                 fig_group([r for r in og if r["来源"] != ""], "品牌", [("interact_mean", "互动率"), ("fav_rate", "收藏率")],
                           "官方 vs 达人：互动率与收藏率", "小佩官方 75 条、达人 207 条")))
    figs.append(("用户痛点：内容量 vs 播放中位数",
                 "支持决策：内容主打哪个卖点",
                 fig_scatter(pain, "内容数", "播放中位数", "痛点", "痛点内容量与播放中位数",
                             "右上=又热又多人做；左上=播放高但内容少，是机会点")))
    figs.append(("内容形态效率（A+B 级）",
                 "支持决策：做什么形式的内容",
                 fig_bar(fmt, "内容形态", "interact_mean", "各内容形态平均互动率", "只用 A+B 级记录", PALETTE[2], pct=True, horizontal=True)))
    figs.append(("时长档效率（A+B 级）",
                 "支持决策：视频该做多长",
                 fig_group(dur, "时长档", [("interact_mean", "互动率"), ("fav_rate", "收藏率")],
                           "不同时长档的互动与收藏", "长视频互动高可能受创作者专业度影响，需结合分层看")))
    figs.append(("创作者分层效率（A+B 级）",
                 "支持决策：达人投放该投头部还是腰部",
                 fig_group(tier, "层级", [("interact_mean", "互动率"), ("fav_rate", "收藏率")],
                           "头部/腰部/长尾的效率对比", "按播放量排名 前10%/10-40%/40-100%")))
    figs.append(("使用场景分布（A+B+C 级）",
                 "支持决策：用户是谁、在什么处境下买",
                 fig_bar(scene, "场景", "n", "场景内容量", "词典命中的场景；未标注占比高说明多数内容不绑定场景", PALETTE[4], horizontal=True)))
    figs.append(("内容主题分布",
                 "支持决策：内容生态里各主题的供给结构",
                 fig_bar(theme, "大模型主题", "内容数", "主题内容量", "来自大模型 theme 字段", PALETTE[5], horizontal=True)))

    parts = []
    for i, (title, note, f) in enumerate(figs):
        parts.append('<div class="card"><h2>%s</h2><p class="note">%s</p>%s</div>'
                     % (title, note, f.to_html(full_html=False, include_plotlyjs=("inline" if i == 0 else False),
                                               config={"displayModeBar": False})))
    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>宠物智能硬件用户洞察 · 交互式看板</title>
<style>
 body{font-family:"Microsoft YaHei",sans-serif;background:#f5f7fa;margin:0;padding:24px;color:#22303f}
 h1{color:#1F3864;margin:0 0 6px}
 .sub{color:#5a6b7d;margin-bottom:20px}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:18px}
 .card{background:#fff;border-radius:10px;padding:16px 18px;box-shadow:0 2px 10px rgba(20,40,80,.08)}
 .card h2{font-size:16px;color:#1F3864;margin:0 0 4px}
 .note{font-size:12.5px;color:#6b7c8f;margin:0 0 8px}
 footer{margin-top:24px;color:#8b98a6;font-size:12.5px;line-height:1.9}
</style></head><body>
<h1>宠物智能硬件用户洞察 · 交互式看板</h1>
<div class="sub">数据来源：B站 35 个关键词搜索结果 · 有效样本 3,747 条 ·
标注口径：大模型主判（低置信样本自一致性投票）· 人工抽检准确率 89.5%（Wilson 95%CI 84.5%~93.0%）</div>
<div class="grid">
<<FIGURES>>
</div>
<footer>
 说明：数据来自关键词搜索，<b>不是随机抽样</b>，只能做相对比较，不能做绝对市场判断。<br>
 分析纪律：产品线与品牌结论只用 A 级（智能硬件本体）记录；痛点/场景用 A+B+C；内容形态用 A+B。<br>
 图表可交互：悬停看数值、点击图例可筛选。生成脚本：src/py/make_dashboard.py
</footer></body></html>""".replace("<<FIGURES>>", "\n".join(parts))

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成 docs/index.html（%.1f MB，双击即可打开，断网可用）" % (os.path.getsize(OUT) / 1048576.0))
    print("图表数：%d" % len(figs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
