# -*- coding: utf-8 -*-
"""pipeline_common.py —— 分步脚本共用的加载函数"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_CLEAN = os.path.join(ROOT, "data", "clean")
RESULTS = os.path.join(ROOT, "results")
CKPT = os.path.join(DATA_CLEAN, "label_ckpt.json")
CACHE = os.path.join(DATA_CLEAN, "label_cache.json")


def load_records(sample=0, seed=11):
    p = os.path.join(DATA_CLEAN, "clean_detail.jsonl")
    if not os.path.exists(p):
        print("找不到 data/clean/clean_detail.jsonl")
        print("请先运行「3_清洗数据.bat」")
        return None
    recs = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    if sample and sample < len(recs):
        import random
        random.seed(seed)
        recs = random.sample(recs, sample)
    return recs


def load_labels():
    """从检查点或缓存读取已标注结果；返回与记录等长的列表"""
    if os.path.exists(CACHE):
        try:
            c = json.load(open(CACHE, encoding="utf-8"))
            if isinstance(c, list) and c:
                return c, "缓存(label_cache.json)"
        except Exception:
            pass
    if os.path.exists(CKPT):
        try:
            ck = json.load(open(CKPT, encoding="utf-8"))
            batch_size = 25
            n = ck.get("n", 0)
            out = [None] * n
            for bi_str, vals in ck.get("batches", {}).items():
                s = int(bi_str) * batch_size
                for off, v in enumerate(vals):
                    if s + off < n:
                        out[s + off] = v
            if all(x is not None for x in out):
                return out, "检查点(label_ckpt.json)"
        except Exception:
            pass
    return None, None
