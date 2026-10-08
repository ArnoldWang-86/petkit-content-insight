# -*- coding: utf-8 -*-
"""clean.py —— 数据清洗

输入  data/raw/search_raw.jsonl   （采集脚本产出的原始数据）
输出  data/clean/clean_detail.jsonl  （清洗后带派生指标与规则命中的明细）

清洗规则（按顺序执行，每一步剔除量都会打印出来）：
  1. 剔除无 bvid 的记录（广告位或异常返回）
  2. 按 bvid 去重（同一条视频会被多个关键词搜到）
  3. 剔除发布时间/时长为空的记录
  4. 剔除三项互动全为 0 的记录（疑似无效）
  5. 剔除播放量 < 100 的噪声样本

分类口径来自 classifier.py（规则层），每条记录保留「命中了哪些规则」，
便于后续用人工抽检反算各规则精度（ULF 思路）。

分类口径统一来自 common.py，不在这里另写一套。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (pick_category, pick_brands, pick_brands_strong,
                    pick_pains, pick_scenes, pick_format, OFFICIAL_RE)
from classifier import lf_votes

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES = os.path.join(ROOT, "results")
DATA_CLEAN = os.path.join(ROOT, "data", "clean")
RAW = os.path.join(ROOT, "data", "raw", "search_raw.jsonl")
os.makedirs(RES, exist_ok=True)
os.makedirs(DATA_CLEAN, exist_ok=True)


def parse_duration(d):
    """B站返回的时长格式是 "MM:SS"，如 "17:6" 表示 17 分 6 秒"""
    if isinstance(d, (int, float)):
        return int(d)
    try:
        parts = [int(x) for x in str(d or "").split(":")]
    except ValueError:
        return None
    if not parts:
        return None
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return parts[0]


def main():
    if not os.path.exists(RAW):
        print("找不到 data/raw/search_raw.jsonl，请先运行采集脚本")
        return 1

    raw = []
    with open(RAW, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    print("原始记录        : %d" % len(raw))

    rules = []

    # 规则 1：无 bvid
    no_bvid = [r for r in raw if not r.get("bvid")]
    rows = [r for r in raw if r.get("bvid")]
    rules.append(("剔除无 bvid 记录（广告位/异常）", len(no_bvid)))

    # 规则 2：按 bvid 去重，保留 tag 信息最全的一条
    by_bvid = {}
    for r in rows:
        prev = by_bvid.get(r["bvid"])
        if prev is None or len(str(r.get("tag") or "")) > len(str(prev.get("tag") or "")):
            by_bvid[r["bvid"]] = r
    dup = len(rows) - len(by_bvid)
    rows = list(by_bvid.values())
    rules.append(("按 bvid 去重（同一视频被多关键词命中）", dup))

    # 规则 3：发布时间/时长异常
    before = len(rows)
    rows = [r for r in rows if (r.get("pubdate") or 0) > 0 and (parse_duration(r.get("duration")) or 0) > 0]
    rules.append(("剔除发布时间/时长为空或异常", before - len(rows)))

    # 规则 4：三项互动全 0
    before = len(rows)
    rows = [r for r in rows
            if not ((r.get("play") or 0) == 0 and (r.get("like") or 0) == 0 and (r.get("favorites") or 0) == 0)]
    rules.append(("剔除三项互动全为 0（疑似无效记录）", before - len(rows)))

    # 规则 5：播放量过低
    before = len(rows)
    rows = [r for r in rows if (r.get("play") or 0) >= 100]
    rules.append(("剔除播放量 < 100 的噪声样本", before - len(rows)))

    # ---------- 派生指标与分类 ----------
    data = []
    for r in rows:
        title = str(r.get("title") or "")
        tag = str(r.get("tag") or "")
        hay = (title + " " + tag).lower()
        play = r.get("play") or 0
        like = r.get("like") or 0
        fav = r.get("favorites") or 0
        dm = r.get("danmaku") or 0
        data.append({
            "bvid": r.get("bvid"),
            "title": title,
            "tag": tag,
            "author": r.get("author"),
            "mid": r.get("mid"),
            "typename": r.get("typename"),
            "play": play,
            "like": like,
            "fav": fav,
            "dm": dm,
            "reply": r.get("review") or 0,
            "duration_s": parse_duration(r.get("duration")),
            "interact": (like + fav) / play if play else 0,
            "like_rate": like / play if play else 0,
            "fav_rate": fav / play if play else 0,
            "dm_rate": dm / play * 1000 if play else 0,
            "cat": pick_category(hay),
            "lf_votes": lf_votes(title, tag),
            "brands": pick_brands(hay),
            "brand_strong": pick_brands_strong(title, hay),
            "official": bool(OFFICIAL_RE.search(str(r.get("author") or ""))),
            "pains": pick_pains(hay),
            "scenes": pick_scenes(hay),
            "fmt": pick_format(hay),
            "_keyword": r.get("_keyword"),
            "pubdate": r.get("pubdate"),
            "pub_year": __import__("datetime").datetime.fromtimestamp(r.get("pubdate") or 0).year,
        })

    out_path = os.path.join(DATA_CLEAN, "clean_detail.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for d in data:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    # ---------- 清洗报告 ----------
    print("")
    print("--- 清洗规则与剔除量 ---")
    for name, n in rules:
        print("  %-34s%7d 条" % (name, n))
    print("")
    print("有效样本        : %d" % len(data))
    print("独立创作者      : %d" % len({d["mid"] for d in data}))
    print("覆盖产品线      : %d 类" % len({d["cat"] for d in data}))
    brands = {b for d in data for b in d["brands"]}
    print("提及品牌数      : %d 个" % len(brands))
    durs = sorted(d["duration_s"] for d in data)
    if durs:
        print("时长中位数      : %.1f 分钟" % (durs[len(durs) // 2] / 60))
    years = {}
    for d in data:
        years[d["pub_year"]] = years.get(d["pub_year"], 0) + 1
    print("发布年份分布    : " + "  ".join("%s:%d" % (y, n) for y, n in sorted(years.items())))
    print("")
    print("已写出 data/clean/clean_detail.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
