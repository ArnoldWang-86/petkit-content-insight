# -*- coding: utf-8 -*-
"""step2_vote.py —— 第2步：自一致性投票（仅低置信度样本）

依据：Self-Consistency (arXiv:2203.11171)
做法：对置信度 < 阈值的样本再问 3 次（temperature=0.8 制造多样性），取多数票，
      以「投票一致率」作为新的置信度（比模型自报置信度更客观）。
结果写入 data/clean/label_cache.json，作为最终标注缓存。
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pipeline_common import ROOT, DATA_CLEAN, CKPT, CACHE, load_records, load_labels
from llm_labeler import LLMLabeler

THRESHOLD = 0.8
VOTES = 3
BATCH = 25


def main():
    recs = load_records()
    if recs is None:
        return 1
    labels, src = load_labels()
    if labels is None:
        print("找不到已标注结果，请先运行「4_大模型标注.bat」")
        return 1
    total = len(labels)
    print("已标注 %d 条（来源：%s）" % (total, src))

    targets = [i for i, lb in enumerate(labels)
               if lb and isinstance(lb.get("confidence"), (int, float))
               and lb["confidence"] < THRESHOLD and lb.get("relevance") != "?"]
    print("置信度 < %.1f 的样本：%d 条（占 %.1f%%）" % (THRESHOLD, len(targets), len(targets) / total * 100))
    if not targets:
        print("无需投票，直接保存缓存。")
        json.dump(labels, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        print("下一步：双击「6_聚合标注.bat」")
        return 0
    print("将进行 %d 轮投票，约 %d 次 API 调用" % (VOTES, (len(targets) * VOTES + BATCH - 1) // BATCH))
    print("")

    lab = LLMLabeler(ROOT)
    t0 = time.time()
    labels = lab.vote_low_confidence(recs, labels, threshold=THRESHOLD, votes=VOTES, batch_size=BATCH)
    print("")
    print("完成：%d 次调用 / %d tokens / %.0f 秒" % (lab.calls, lab.tokens, time.time() - t0))

    json.dump(labels, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    print("已保存 data/clean/label_cache.json")
    dist = {}
    for lb in labels:
        k = (lb or {}).get("relevance", "?")
        dist[k] = dist.get(k, 0) + 1
    print("投票后分布：" + str(dist))
    print("")
    print("下一步：双击「6_聚合标注.bat」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
