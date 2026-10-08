# -*- coding: utf-8 -*-
"""gen_report.py —— 用大模型自动生成「运营方案报告」（核心交付物）

对齐 JD 方向1「AI 流程自动化」：把「五路分析」的结构化结果自动喂给大模型，
生成「问题 → 方案 → 预期效果」的运营方案，再人工润色。

为什么要这么做：
  · 分析结论已经量化，重复的"把数字翻译成动作"适合交给大模型
  · 脚本可复用：换一批数据，重新跑就能得到新报告

严格约束（写进提示词，避免模型编造）：
  · 只能用给定数字，不得虚构任何数据
  · 必须写明数据来源是关键词搜索、非随机抽样，只能做相对比较

产出：results/运营方案_宠物智能硬件内容运营.md
"""
import json
import os
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pipeline_common import ROOT, RESULTS
from llm_labeler import load_api_key

OUT_MD = os.path.join(RESULTS, "运营方案_宠物智能硬件内容运营.md")

CSVS = ["01_产品线.csv", "02_品牌声量.csv", "03_用户痛点.csv", "04_内容形态.csv",
        "05_时长效果.csv", "06_关键词效率.csv", "07_创作者分层.csv",
        "08_使用场景.csv", "09_官方vs达人.csv", "10_横评份额.csv",
        "11_标签分布.csv", "12_产品线口径校验.csv", "13_内容主题.csv"]

SYSTEM = """你是宠物智能硬件品牌「小佩 PETKIT」（上海张江）的运营管培生（AI 方向），
负责 B站 内容运营与用户洞察。你的任务：基于给定的数据分析结果，写一份**可执行**的运营方案。

硬性要求：
1. 每个结论都必须引用给定数据中的具体数字，**不得编造任何数据**。
2. 数据来自 B站 关键词搜索结果，**不是随机抽样**，只能做相对比较、不能做绝对市场判断——
   这一点必须在报告里明确写出。
3. 只输出 Markdown，不要任何解释性前后缀。
4. 面向运营动作：每条建议要说清「做什么、为什么、怎么衡量」。
"""

# 注意：下面的准确率来自 step5_eval.py 的最新一次运行，重跑评估后请同步这里的数字
PROMPT = """下面是我们对 B站 宠物智能硬件内容做的五路分析结果（有效样本 <<N>> 条）。

【标注质量（必须先说明口径）】
- 最终标签 = 大模型判定（temperature=0 主判 + 低置信样本自一致性投票）
- 在 200 条分层随机抽检上，与人工标注一致率 88.0%（Wilson 95%CI 82.8%~91.8%），后分层加权 87.3%
- 单一标注者、无重复核验；二轮盲判复核发现人工自身自洽率仅约 38%，故准确率是保守值
- 分析纪律：产品线与品牌结论**只用 A 级（智能硬件本体）记录**；痛点/场景用 A+B+C；内容形态用 A+B

【各分析结果】
<<DATA>>

请输出一份运营方案报告，结构如下：

# 宠物智能硬件内容运营方案（基于 B站 <<N>> 条内容洞察）

## 摘要
（3-5 条最关键的发现，每条带数字）

## 一、数据与方法口径
（数据来源、样本量、标注准确率、已知局限——务必写明"关键词搜索非随机抽样"）

## 二、核心发现与问题诊断
（分产品线 / 品牌 / 痛点 / 内容形态与时长 / 人群场景 五块，每块给出 2-4 条带数字的判断）

## 三、运营方案
（针对每个问题给出动作，建议分成"内容选题""形式与时长""达人投放""品牌对标"四类。
 每条方案写清：做什么 / 为什么（引用数字）/ 预期效果与衡量指标）

## 四、优先级与排期
（用表格给出：方案 / 优先级 / 预计投入 / 衡量指标 / 建议周期）

## 五、风险与局限
（数据偏差、标注误差、不能做什么判断）
"""


def read_csv_text(name):
    p = os.path.join(RESULTS, name)
    if not os.path.exists(p):
        return ""
    with open(p, encoding="utf-8-sig") as f:
        return "### %s\n%s\n" % (name, f.read().strip())


def main():
    body = "\n".join(x for x in (read_csv_text(n) for n in CSVS) if x)
    if not body.strip():
        print("results/ 下没有分析 CSV，请先跑「9_跑分析.bat」")
        return 1
    key = load_api_key(ROOT)
    if not key:
        print("找不到 DEEPSEEK_API_KEY")
        return 1
    model = "deepseek-chat"
    print("输入摘要 %d 字符，调用 %s 生成运营方案 ..." % (len(body), model))
    n = "?"
    ap = os.path.join(RESULTS, "analysis.json")
    if os.path.exists(ap):
        try:
            n = json.load(open(ap, encoding="utf-8")).get("sample_size", "?")
        except Exception:
            pass
    r = requests.post("https://api.deepseek.com/chat/completions",
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                      json={"model": model,
                            "messages": [{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": PROMPT.replace("<<N>>", str(n)).replace("<<DATA>>", body)}],
                            "temperature": 0.4, "max_tokens": 8000},
                      timeout=300)
    r.raise_for_status()
    j = r.json()
    text = j["choices"][0]["message"]["content"]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")
    print("已写出 results/运营方案_宠物智能硬件内容运营.md（%d 字）" % len(text))
    print("tokens: %s" % j.get("usage", {}).get("total_tokens"))
    print("")
    print("下一步：python src\\md2docx.py 生成 Word 版")
    return 0


if __name__ == "__main__":
    sys.exit(main())
