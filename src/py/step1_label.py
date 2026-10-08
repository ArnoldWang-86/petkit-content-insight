# -*- coding: utf-8 -*-
"""step1_label.py —— 第1步：大模型主判（可续跑）

每批 25 条，**每批落盘**到 data/clean/label_ckpt.json。
中断后重新运行会从断点继续，不重复调用 API。
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pipeline_common import ROOT, DATA_CLEAN, CKPT, load_records
from llm_labeler import LLMLabeler

BATCH = 25


def main():
    recs = load_records()
    if recs is None:
        return 1
    total = len(recs)
    print("待标注 %d 条，分 %d 批（每批 %d 条）" % (total, (total + BATCH - 1) // BATCH, BATCH))
    print("支持断点续跑：中断后重新运行本步即可继续。")
    print("")

    lab = LLMLabeler(ROOT)
    t0 = time.time()
    labels = lab.label_all(recs, batch_size=BATCH, ckpt_path=CKPT)
    print("")
    print("完成：%d 次调用 / %d tokens / %.0f 秒" % (lab.calls, lab.tokens, time.time() - t0))
    print("已保存到 data/clean/label_ckpt.json")
    print("")
    print("下一步：双击「5_大模型投票.bat」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
