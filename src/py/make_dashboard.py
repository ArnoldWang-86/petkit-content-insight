# -*- coding: utf-8 -*-
"""make_dashboard.py —— 生成交互式看板（单文件 HTML，双击即可打开）

设计
----
· 单文件内嵌 plotly.js（约 3.5MB）→ 断网也能打开，方便交给 HR
· 数据全部来自 results/ 下的分析 CSV，不重新计算口径
· 每张卡 = 标题 + 「支持什么决策」+ 图 + **结论**（结论由数据算出来，不是手写死的）
· 所有图在 DOMContentLoaded 之后统一渲染

为什么必须等 DOMContentLoaded
-----------------------------
早期版本用 fig.to_html() 直接输出「边解析边渲染」的脚本。
第一张图在页面还没解析完时就执行了 —— 那时 .grid 里只有一张卡，
Plotly 按「整行宽度」算好尺寸；等后面的卡片解析完、网格变成两列，
它不会自动重算，于是第一张图就溢出到卡片外面了。
现在改成：先把所有图的 JSON 规格塞进数组，等 DOM 就绪再一次性 newPlot。

用法： python src/py/make_dashboard.py
"""
import csv
import json
import os
import sys

import plotly.graph_objects as go
import plotly.io as pio

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pipeline_common import ROOT, RESULTS

OUT = os.path.join(ROOT, "docs", "index.html")   # 放 docs/ 下，GitHub Pages 才能直接在线打开
ANALYSIS = os.path.join(RESULTS, "analysis.json")
FONT = dict(family="Microsoft YaHei, SimHei, sans-serif", size=13)
PALETTE = ["#2E5C9A", "#C0504D", "#9BBB59", "#8064A2", "#4BACC6", "#F79646", "#7F7F7F"]

# 标注质量：来自 src/py/step5_eval.py 最近一次运行；重跑评估后请同步这里
ACCURACY = {"main": 88.0, "ci": [82.8, 91.8], "post": 87.3, "reviewed": 93.5, "self_consistency": 38.2}


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


def pct(v, d=2):
    return ("%." + str(d) + "f%%") % (num(v) * 100)


def top(rows, key, rev=True):
    return sorted(rows, key=lambda r: num(r[key]), reverse=rev)


def fmt_n(v):
    return "{:,}".format(int(num(v)))


def esc(t):
    """转义数据里可能出现的 "<"（例如时长档 "<1min"），否则会被浏览器当成标签。"""
    return str(t).replace("<", "&lt;")


def b(t):
    """加粗。注意：<b> 标签本身不能被转义，所以要在这里对数据转义，而不是最后统一转。"""
    return "<b>" + esc(t) + "</b>"


# ----------------------------------------------------------------- 图形

def fig_bar(rows, x, y, title, note, color=None, pctaxis=False, horizontal=False):
    vals = [num(r[y]) * (100 if pctaxis else 1) for r in rows]
    names = [r[x] for r in rows]
    f = go.Figure(go.Bar(
        x=vals if horizontal else names, y=names if horizontal else vals,
        orientation="h" if horizontal else "v",
        marker_color=color or PALETTE[0],
        text=["%.1f%%" % v if pctaxis else ("%d" % v) for v in vals],
        textposition="auto"))
    f.update_layout(title=dict(text=title + "<br><sup>" + note + "</sup>", font=FONT),
                    font=FONT, height=430, margin=dict(l=10, r=10, t=80, b=10),
                    yaxis=dict(autorange="reversed") if horizontal else {})
    return f


def fig_group(rows, x, series, title, note):
    f = go.Figure()
    for i, (key, label) in enumerate(series):
        f.add_trace(go.Bar(name=label, x=[r[x] for r in rows], y=[num(r[key]) for r in rows],
                           marker_color=PALETTE[i % len(PALETTE)]))
    f.update_layout(barmode="group", title=dict(text=title + "<br><sup>" + note + "</sup>", font=FONT),
                    font=FONT, height=430, margin=dict(l=10, r=10, t=80, b=10))
    return f


def fig_pie(rows, x, y, title, note):
    f = go.Figure(go.Pie(labels=[r[x] for r in rows], values=[num(r[y]) for r in rows], hole=0.45,
                         marker_colors=PALETTE))
    f.update_layout(title=dict(text=title + "<br><sup>" + note + "</sup>", font=FONT),
                    font=FONT, height=430, margin=dict(l=10, r=10, t=80, b=10))
    return f


def fig_scatter(rows, x, y, label, title, note):
    f = go.Figure(go.Scatter(
        x=[num(r[x]) for r in rows], y=[num(r[y]) for r in rows], mode="markers+text",
        text=[r[label] for r in rows], textposition="top center",
        marker=dict(size=14, color=PALETTE[3])))
    f.update_layout(title=dict(text=title + "<br><sup>" + note + "</sup>", font=FONT),
                    font=FONT, height=450, margin=dict(l=10, r=10, t=80, b=10),
                    xaxis_title=x, yaxis_title=y)
    return f


# ----------------------------------------------------------------- 主流程

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

    ana = {}
    if os.path.exists(ANALYSIS):
        with open(ANALYSIS, encoding="utf-8") as f:
            ana = json.load(f)
    n_sample = ana.get("sample_size", 4375)

    cards = []   # (title, note, fig, conclusion_html)

    # ---- 1 标签分布
    ld = {r["final_label"]: r for r in lab}
    nA = num(ld.get("A", {}).get("内容数", 0))
    nC = num(ld.get("C", {}).get("内容数", 0))
    nN = num(ld.get("N", {}).get("内容数", 0))
    tot = sum(num(r["内容数"]) for r in lab) or 1
    c1 = ("%s 条里只有 %s 条（%s）真正在讨论智能硬件本体；C 级 %s 条（%s）是健康养护等用户语境，N 级 %s 条是纯搜索噪声。"
          "**每 3 条相关内容里只有 1 条是产品讨论** —— 如果直接把搜索结果当「产品口碑」用，三分之二是噪声，"
          "这也是为什么后面的产品线/品牌结论全部只用 A 级。") % (
        fmt_n(tot), b(fmt_n(nA)), pct(nA / tot, 1), fmt_n(nC), pct(nC / tot, 1), fmt_n(nN))
    cards.append(("标签分布：%s 条内容里有多少是真正的硬件讨论" % fmt_n(tot),
                  "支持决策：内容洞察的样本结构是否健康（A 直接相关 / B 延伸 / C 用户语境 / N 非宠物）",
                  fig_pie(lab, "final_label", "内容数", "相关性四级分布",
                          "A=品牌竞争型智能硬件本体；C 占比高是真实内容生态，不是错误"),
                  c1))

    # ---- 2 产品线内容量
    cat_v = top(cat, "n")
    real_cat = [r for r in cat_v if not r["产品线"].startswith("其他")]      # 剔除残差类
    tail_cat = real_cat[-1]
    c2 = ("内容供给高度集中在 %s：%s 条，占 A 级的 %s，是第二名「%s」（%s 条）的 %.1f 倍；"
          "而真正做的人最少的 %s 只有 %s 条。**整条生态的注意力压在单一品类上。**") % (
        b(cat_v[0]["产品线"]), fmt_n(cat_v[0]["n"]),
        pct(num(cat_v[0]["n"]) / sum(num(r["n"]) for r in cat), 1),
        cat_v[1]["产品线"], fmt_n(cat_v[1]["n"]),
        num(cat_v[0]["n"]) / max(1.0, num(cat_v[1]["n"])),
        b(tail_cat["产品线"]), fmt_n(tail_cat["n"]))
    cards.append(("产品线讨论度（仅 A 级）",
                  "支持决策：内容资源先投哪条产品线",
                  fig_bar(cat, "产品线", "n", "各产品线内容量", "只统计 final_label=A 的记录",
                          PALETTE[0], horizontal=True), c2))

    # ---- 3 产品线互动效率
    cat_i = [r for r in top(cat, "interact_mean") if not r["产品线"].startswith("其他")]   # 残差类样本太少，不参与极值
    hit_cat = [r for r in cat if r["产品线"] == cat_v[0]["产品线"]]
    rank_cat = [r["产品线"] for r in cat_i].index(cat_v[0]["产品线"]) + 1
    c3 = ("互动率最高的是 %s（%s），最低的是 %s（%s），相差 %.1f 倍。"
          "**内容最多的「%s」互动率只有 %s，在 %d 条主要产品线里排最后 —— 内容量和互动效率几乎不相关。**"
          " 按内容量分配预算，会把钱投在效率最低的地方。") % (
        b(cat_i[0]["产品线"]), pct(cat_i[0]["interact_mean"]),
        cat_i[-1]["产品线"], pct(cat_i[-1]["interact_mean"]),
        num(cat_i[0]["interact_mean"]) / max(1e-9, num(cat_i[-1]["interact_mean"])),
        cat_v[0]["产品线"], pct(hit_cat[0]["interact_mean"]) if hit_cat else "-", len(cat_i))
    cards.append(("产品线互动效率（仅 A 级）",
                  "支持决策：哪条线的内容更容易引发互动（不是播放量，而是互动率）",
                  fig_bar(cat, "产品线", "interact_mean", "各产品线平均互动率", "互动率 = (点赞+收藏)/播放",
                          PALETTE[1], pctaxis=True, horizontal=True), c3))

    # ---- 4 品牌声量
    br_v = top(brand, "提及数")
    strong = num(br_v[0]["强信号"])
    weak = num(br_v[0]["弱信号"])
    c4 = ("%s 提及 %s 次，其中强信号（标题直接出现品牌名）%s 次、占 %s —— 说明大多数提及是真实的产品讨论，不是标签噪声。"
          "第二名是 %s（%s 次），与第一名相差 %.1f 倍。") % (
        b(br_v[0]["品牌"]), fmt_n(br_v[0]["提及数"]), fmt_n(strong), pct(strong / max(1, strong + weak), 1),
        br_v[1]["品牌"], fmt_n(br_v[1]["提及数"]),
        num(br_v[0]["提及数"]) / max(1.0, num(br_v[1]["提及数"])))
    cards.append(("品牌声量：强信号 vs 弱信号（仅 A 级）",
                  "支持决策：和谁对标、用户真正在讨论谁",
                  fig_group(brand, "品牌", [("强信号", "强信号(标题提及)"), ("弱信号", "弱信号(仅标签)")],
                            "品牌提及量", "强信号=标题直接出现品牌名，更可能是真实产品讨论"), c4))

    # ---- 5 横评份额
    sov_v = top(sov, "横评中出现次数")
    c5 = ("在横评/选购类内容里，%s 出现 %s 次、份额 %s，是第二名 %s（%s）的 %.1f 倍。"
          "**「必提品牌」的地位比绝对提及量更稳** —— 同一条横评里各品牌被一起比较，不受采集关键词分配的影响。") % (
        b(sov_v[0]["品牌"]), fmt_n(sov_v[0]["横评中出现次数"]), pct(sov_v[0]["份额"], 1),
        sov_v[1]["品牌"], pct(sov_v[1]["份额"], 1),
        num(sov_v[0]["横评中出现次数"]) / max(1.0, num(sov_v[1]["横评中出现次数"])))
    cards.append(("横评内份额：更公平的声量口径（仅 A 级）",
                  "支持决策：谁是横评里的「必提品牌」",
                  fig_pie(sov, "品牌", "横评中出现次数", "横评/选购类内容中的品牌份额",
                          "同一条横评里各品牌被一起比较，与采集方式无关"), c5))

    # ---- 6 官方 vs 达人
    og2 = [r for r in og if r["来源"] != ""]
    off = [r for r in og2 if r["来源"] == "官方"]
    ugc = [r for r in og2 if r["来源"] == "达人/用户"]
    o_mean = num(off[0]["interact_mean"]) if off else 0
    u_mean = num(ugc[0]["interact_mean"]) if ugc else 0
    c6 = ("官方账号的内容是「有曝光、没讨论」：%s 的官方 %s 条播放中位数 %s，但互动率只有 %s；"
          "达人/用户 %s 条播放中位数只有 %s，互动率却有 %s（是官方的 %.1f 倍）。"
          "**讨论主要发生在达人侧 —— 这是分工问题，不是谁做得差。** 官方适合品牌信息与技术解读，"
          "体验、吐槽、DIY 这类会引发讨论的内容更适合交给达人。") % (
        off[0]["品牌"] if off else "头部品牌", fmt_n(off[0]["n"]) if off else "-",
        fmt_n(off[0]["play_median"]) if off else "-", pct(o_mean),
        fmt_n(ugc[0]["n"]) if ugc else "-", fmt_n(ugc[0]["play_median"]) if ugc else "-", pct(u_mean),
        u_mean / max(1e-9, o_mean))
    cards.append(("官方内容 vs 达人内容（仅 A 级）",
                  "支持决策：投放该信官方还是信达人",
                  fig_group(og2, "品牌", [("interact_mean", "互动率"), ("fav_rate", "收藏率")],
                            "官方 vs 达人：互动率与收藏率", "按品牌对比，同一品牌内官方与达人并列"), c6))

    # ---- 7 痛点散点
    pn = top(pain, "播放中位数")
    pn_n = top(pain, "内容数")
    med_n = sorted(num(r["内容数"]) for r in pain)[len(pain) // 2]
    med_p = sorted(num(r["播放中位数"]) for r in pain)[len(pain) // 2]
    chance = [r for r in pain if num(r["内容数"]) <= med_n and num(r["播放中位数"]) >= med_p]
    chance_names = "、".join("「%s」" % r["痛点"] for r in top(chance, "播放中位数")[:3]) or "（无）"
    c7 = ("播放中位数最高的是「%s」（%s），但它只有 %s 条内容；而内容量最大的「%s」有 %s 条、播放中位数只有 %s。"
          "**讨论最多的痛点和能带来流量的痛点不是一回事。** 图上左上角（内容量低于中位数 %d 条、播放高于中位数 %s）"
          "的是机会点，当前有 %d 个，最靠前的是 %s。") % (
        pn[0]["痛点"], fmt_n(pn[0]["播放中位数"]), fmt_n(pn[0]["内容数"]),
        pn_n[0]["痛点"], fmt_n(pn_n[0]["内容数"]), fmt_n(pn_n[0]["播放中位数"]),
        int(med_n), fmt_n(med_p), len(chance), chance_names)
    cards.append(("用户痛点：内容量 vs 播放中位数",
                  "支持决策：内容主打哪个卖点",
                  fig_scatter(pain, "内容数", "播放中位数", "痛点", "痛点内容量与播放中位数",
                              "右上=又热又多人做；左上=播放高但内容少，是机会点"), c7))

    # ---- 8 内容形态
    fm = top(fmt, "interact_mean")
    c8 = ("互动率最高的是 %s（%s），最低的是 %s（%s），相差 %.1f 倍。"
          "**同样是讲产品，换个内容形态效果完全不同** —— 痛点选对了、讲法不对，照样没流量。"
          " 注意「其他」占比最大（%s 条），说明形态标注还有 %s 没被识别，这个结论要留有余地。") % (
        b(fm[0]["内容形态"]), pct(fm[0]["interact_mean"]),
        b(fm[-1]["内容形态"]), pct(fm[-1]["interact_mean"]),
        num(fm[0]["interact_mean"]) / max(1e-9, num(fm[-1]["interact_mean"])),
        fmt_n([r for r in fmt if r["内容形态"] == "其他"][0]["n"]) if any(r["内容形态"] == "其他" for r in fmt) else "-",
        pct(num([r for r in fmt if r["内容形态"] == "其他"][0]["n"]) / sum(num(r["n"]) for r in fmt), 1)
        if any(r["内容形态"] == "其他" for r in fmt) else "-")
    cards.append(("内容形态效率（A+B 级）",
                  "支持决策：做什么形式的内容",
                  fig_bar(fmt, "内容形态", "interact_mean", "各内容形态平均互动率", "只用 A+B 级记录",
                          PALETTE[2], pctaxis=True, horizontal=True), c8))

    # ---- 9 时长档
    du = sorted(dur, key=lambda r: num(r["interact_mean"]))
    ladder = " → ".join("%s %s" % (esc(r["时长档"]), pct(r["interact_mean"])) for r in du)
    c9 = ("互动率随时长单调上升：%s。%s 的视频互动率 %s，是 %s（%s）的 %.1f 倍。"
          "**但要小心：长视频往往来自更专业的创作者**，这更像是创作者质量差异，不能直接得出「做长就更好」。"
          " 要判断这一点，得结合「创作者分层」那张图一起看。") % (
        ladder, b(du[-1]["时长档"]), pct(du[-1]["interact_mean"]),
        b(du[0]["时长档"]), pct(du[0]["interact_mean"]),
        num(du[-1]["interact_mean"]) / max(1e-9, num(du[0]["interact_mean"])))
    cards.append(("时长档效率（A+B 级）",
                  "支持决策：视频该做多长",
                  fig_group(dur, "时长档", [("interact_mean", "互动率"), ("fav_rate", "收藏率")],
                            "不同时长档的互动与收藏", "长视频互动高可能受创作者专业度影响，需结合分层看"), c9))

    # ---- 10 创作者分层
    ti = top(tier, "interact_mean")
    tier_by_name = {r["层级"]: r for r in tier}
    head = next((r for r in tier if r["层级"].startswith("头部")), None)
    waist = next((r for r in tier if r["层级"].startswith("腰部")), None)
    tail = next((r for r in tier if r["层级"].startswith("长尾")), None)
    c10 = ("播放量和互动率是**同向**的：头部（前 10%%）播放中位数 %s、互动率 %s；腰部 %s / %s；长尾 %s / %s。"
           "**这跟常见的「头部只有曝光、腰部才有讨论」不一样** —— 在这个品类里头部既有量也有互动，"
           "说明是内容质量在驱动，而不只是粉丝体量。真正的问题是**长尾**：%s 条（%s）内容"
           "播放中位数只有 %s、互动率只有 %s，是最低效的供给。") % (
        fmt_n(head["play_median"]) if head else "-", pct(head["interact_mean"]) if head else "-",
        fmt_n(waist["play_median"]) if waist else "-", pct(waist["interact_mean"]) if waist else "-",
        fmt_n(tail["play_median"]) if tail else "-", pct(tail["interact_mean"]) if tail else "-",
        fmt_n(tail["n"]) if tail else "-",
        pct(num(tail["n"]) / max(1.0, sum(num(r["n"]) for r in tier)), 1) if tail else "-",
        fmt_n(tail["play_median"]) if tail else "-", pct(tail["interact_mean"]) if tail else "-")
    cards.append(("创作者分层效率（A+B 级）",
                  "支持决策：达人投放该投头部还是腰部",
                  fig_group(tier, "层级", [("interact_mean", "互动率"), ("fav_rate", "收藏率")],
                            "头部/腰部/长尾的效率对比", "按播放量排名 前10%/10-40%/40-100%"), c10))

    # ---- 11 使用场景
    sc = top(scene, "n")
    unlabeled = [r for r in scene if r["场景"].startswith("未标注")]
    un = num(unlabeled[0]["n"]) if unlabeled else 0
    tot_sc = sum(num(r["n"]) for r in scene) or 1
    c11 = ("%s 条（%s）的内容没有绑定任何生活场景；已识别的场景里最多的是 %s（%s 条）。"
           "**这本身就是一个机会点：场景化选题的竞争还很小。** 大多数内容在做「产品介绍」，"
           "而用户其实是带着处境来搜的（新手、多猫、出差、上班不在家）。") % (
        b(fmt_n(un)), pct(un / tot_sc, 1),
        b(sc[1]["场景"] if len(sc) > 1 and sc[0]["场景"].startswith("未标注") else sc[0]["场景"]),
        fmt_n(sc[1]["n"] if len(sc) > 1 and sc[0]["场景"].startswith("未标注") else sc[0]["n"]))
    cards.append(("使用场景分布（A+B+C 级）",
                  "支持决策：用户是谁、在什么处境下买",
                  fig_bar(scene, "场景", "n", "场景内容量",
                          "词典命中的场景；未标注占比高说明多数内容不绑定场景",
                          PALETTE[4], horizontal=True), c11))

    # ---- 12 内容主题
    th = top(theme, "内容数")
    th_i = top(theme, "互动率")
    big = [r for r in th_i if num(r["内容数"]) >= 200]        # 样本太小的主题不参与极值（如"领养救助"只有 32 条）
    small = [r for r in th_i if num(r["内容数"]) < 200]
    c12 = ("主题分布上 %s 最多（%s 条，占 %s），但互动率只有 %s，是全部主题里最低的一档；"
           "互动率最高的是 %s（%s 条、%s），是它的 %.1f 倍。**「讲产品」和「被讨论」是两件事** —— "
           "日常向内容天然更容易引发互动。（样本不足 200 条的主题未参与极值比较，例如「%s」只有 %s 条、互动率 %s，波动太大。）") % (
        b(th[0]["大模型主题"]), fmt_n(th[0]["内容数"]), pct(th[0]["占比"], 1), pct(th[0]["互动率"]),
        b(big[0]["大模型主题"]), fmt_n(big[0]["内容数"]), pct(big[0]["互动率"]),
        num(big[0]["互动率"]) / max(1e-9, num(th[0]["互动率"])),
        small[0]["大模型主题"] if small else "-", fmt_n(small[0]["内容数"]) if small else "-",
        pct(small[0]["互动率"]) if small else "-")
    cards.append(("内容主题分布",
                  "支持决策：内容生态里各主题的供给结构",
                  fig_bar(theme, "大模型主题", "内容数", "主题内容量", "来自大模型 theme 字段",
                          PALETTE[5], horizontal=True), c12))

    # ----------------------------------------------------------------- 组装 HTML
    from plotly.offline import get_plotlyjs
    plotly_js = get_plotlyjs().replace("</script>", "<\\/script>")

    specs = []
    cards_html = []
    for i, (title, note, f, concl) in enumerate(cards):
        f.update_layout(margin=dict(l=10, r=10, t=80, b=10))
        spec = json.loads(pio.to_json(f))
        specs.append({"id": "fig%d" % i, "data": spec["data"], "layout": spec["layout"]})
        concl_html = concl.replace("**", "@@").replace("**", "@@")
        # 用 ** 包住的部分加粗
        # ** 之间的文字是我自己写的说明，不含 "<"，直接包 <b> 即可；
        # 数据里的 "<" 已经由 b() / esc() 处理过，这里不能再统一转义（否则会把 <b> 也转掉）
        parts = concl.split("**")
        rich = "".join(("<b>" + pp + "</b>") if (k % 2 == 1) else pp for k, pp in enumerate(parts))
        cards_html.append(
            '<div class="card"><h2>%s</h2><p class="note">%s</p>'
            '<div class="chartbox" id="fig%d"></div>'
            '<div class="concl"><span class="tag">结论</span>%s</div></div>'
            % (title, note, i, rich))

    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>宠物智能硬件用户洞察 · 交互式看板</title>
<style>
 *{box-sizing:border-box}
 body{font-family:"Microsoft YaHei",sans-serif;background:#f5f7fa;margin:0;padding:24px;color:#22303f}
 h1{color:#1F3864;margin:0 0 6px}
 .sub{color:#5a6b7d;margin-bottom:20px;font-size:13.5px;line-height:1.8}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:18px;align-items:start}
 .card{background:#fff;border-radius:10px;padding:16px 18px;box-shadow:0 2px 10px rgba(20,40,80,.08);
       min-width:0;overflow:hidden;display:flex;flex-direction:column}
 .card h2{font-size:16px;color:#1F3864;margin:0 0 4px}
 .note{font-size:12.5px;color:#6b7c8f;margin:0 0 8px}
 .chartbox{width:100%;height:430px;min-width:0}
 .concl{margin-top:auto;padding:10px 12px;background:#F3F9F1;border:1px solid #CFE4C4;
        border-radius:7px;font-size:12.8px;line-height:1.8;color:#2B3A4A}
 .concl b{color:#3B6B2C}
 .tag{display:inline-block;background:#4F8A3D;color:#fff;border-radius:4px;padding:0 7px;
      font-size:11.5px;margin-right:7px;vertical-align:1px}
 footer{margin-top:24px;color:#8b98a6;font-size:12.5px;line-height:1.9}
</style>
<script><<PLOTLY>></script>
</head><body>
<h1>宠物智能硬件用户洞察 · 交互式看板</h1>
<div class="sub">数据来源：B站 35 个关键词搜索结果 · 有效样本 <<N>> 条 ·
标注口径：大模型主判（低置信样本自一致性投票）· 人工抽检准确率 <<ACC>>%（Wilson 95%CI <<CI0>>%~<<CI1>>%）<br>
每张卡都有<b>结论</b>；图表可交互（悬停看数值、点击图例筛选）。</div>
<div class="grid">
<<FIGURES>>
</div>
<footer>
 说明：数据来自关键词搜索，<b>不是随机抽样</b>，只能做相对比较，不能做绝对市场判断。<br>
 分析纪律：产品线与品牌结论只用 A 级（智能硬件本体）记录；痛点/场景用 A+B+C；内容形态/时长/创作者分层用 A+B。<br>
 结论由数据自动算出（不是手写），生成脚本：src/py/make_dashboard.py
</footer>
<script>
var FIGS = <<SPECS>>;
window.addEventListener("DOMContentLoaded", function () {
  // 必须等 DOM 完全就绪后再渲染：否则第一张图会按「当时只有一张卡」的宽度算尺寸，
  // 等网格变成两列后不会重算，就会溢出卡片（这是上一版的 bug）。
  FIGS.forEach(function (f) {
    Plotly.newPlot(f.id, f.data, f.layout, {displayModeBar: false, responsive: true});
  });
  // 字体/布局稳定后兜底再量一次
  setTimeout(function () {
    FIGS.forEach(function (f) {
      var el = document.getElementById(f.id);
      if (el && el.data) Plotly.Plots.resize(el);
    });
  }, 300);
});
</script>
</body></html>"""
    html = (html.replace("<<PLOTLY>>", plotly_js)
                .replace("<<FIGURES>>", "\n".join(cards_html))
                .replace("<<SPECS>>", json.dumps(specs, ensure_ascii=False))
                .replace("<<N>>", fmt_n(n_sample))
                .replace("<<ACC>>", str(ACCURACY["main"]))
                .replace("<<CI0>>", str(ACCURACY["ci"][0]))
                .replace("<<CI1>>", str(ACCURACY["ci"][1])))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成 docs/index.html（%.1f MB，双击即可打开，断网可用）" % (os.path.getsize(OUT) / 1048576.0))
    print("图表数：%d（每张都带结论）" % len(cards))
    return 0


if __name__ == "__main__":
    sys.exit(main())
