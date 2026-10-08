# -*- coding: utf-8 -*-
r"""migrate_ckpt.py —— 补采后迁移标注检查点（避免全量重标）

为什么需要它
------------
label_ckpt.json 里存着 n（当时的记录数）。补采后记录数变多，
step1 的续跑判断是  if ck.get("n") == len(records)  —— n 不匹配就整份作废，
会从第 1 批重新标全部记录（约 59 万 tokens / 25 分钟）。

本脚本把检查点从「按旧 n 分块」改成「按新 n 分块」：
  · 位置不变（第 i 条的标签还是第 i 条）
  · 只保留"整批都标好"的批次，其余留空 → step1 只补这些批
  · 新增记录天然落在尾部 → 只需重标最后十几批

顺带做一件重要的事：**检测旧记录里有没有"标签(tag)变了"的**。
去重规则是"同一 bvid 保留 tag 最长的一条"，补采可能让某条记录的 tag 变长，
而规则层与大模型都是看「标题 + 标签」的 —— 这类记录的旧标签就不可信了，
必须置空、让它重新标注。

用法
----
    python src\py\migrate_ckpt.py --old <补采前的 clean_detail.jsonl>          # 只检查
    python src\py\migrate_ckpt.py --old <旧的 clean_detail.jsonl> --apply      # 落盘
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pipeline_common import DATA_CLEAN, CKPT

BATCH = 25


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, help="补采前的 clean_detail.jsonl（备份）")
    ap.add_argument("--apply", action="store_true", help="真正写回检查点")
    args = ap.parse_args()

    new = load(os.path.join(DATA_CLEAN, "clean_detail.jsonl"))
    old = load(args.old)
    ck = json.load(open(CKPT, encoding="utf-8"))
    n_old = ck.get("n", 0)
    print("旧记录 %d 条 / 检查点 n=%d" % (len(old), n_old))
    print("新记录 %d 条（新增 %d 条）" % (len(new), len(new) - len(old)))

    # ---- 1) 复原 位置 -> 标签 ----
    labels = [None] * len(new)
    for bi_str, vals in ck.get("batches", {}).items():
        s = int(bi_str) * BATCH
        for off, v in enumerate(vals):
            if s + off < n_old and s + off < len(new):
                labels[s + off] = v
    filled = sum(1 for x in labels if x is not None)
    print("从检查点复原出 %d 条标签" % filled)

    # ---- 2) 检测旧记录里 tag / title 变了的 ----
    changed = []
    for i in range(min(len(old), len(new))):
        if (old[i].get("bvid") != new[i].get("bvid")
                or old[i].get("title") != new[i].get("title")
                or old[i].get("tag") != new[i].get("tag")):
            changed.append(i)
            labels[i] = None   # 旧标签不可信，置空重标
    print("")
    print("前 %d 条里，与补采前不一致的记录：%d 条" % (min(len(old), len(new)), len(changed)))
    for i in changed[:10]:
        print("   第 %d 条  %s" % (i, new[i].get("title", "")[:46]))
    if len(changed) > 10:
        print("   ...（共 %d 条）" % len(changed))
    if not changed:
        print("   [OK] 行序与内容完全一致，旧标签全部有效")

    # ---- 3) 按新 n 重新分块，只保留整批完整的 ----
    total = (len(new) + BATCH - 1) // BATCH
    batches, done_b = {}, []
    for b in range(total):
        s = b * BATCH
        seg = labels[s:min(s + BATCH, len(new))]
        if seg and all(x is not None for x in seg):
            batches[str(b)] = seg
            done_b.append(b)
    todo = [b for b in range(total) if b not in done_b]
    print("")
    print("重新分块后：完整批次 %d / %d，需要补标 %d 批（约 %d 条）"
          % (len(done_b), total, len(todo),
             sum(min(BATCH, len(new) - b * BATCH) for b in todo)))

    if not args.apply:
        print("")
        print("（这是预演，未写入。加 --apply 才会落盘）")
        return 0

    json.dump({"n": len(new), "batches": batches},
              open(CKPT, "w", encoding="utf-8"), ensure_ascii=False)
    print("")
    print("已写回 data/clean/label_ckpt.json（n=%d，完整批次 %d）" % (len(new), len(batches)))
    print("下一步：跑 4_大模型标注.bat，它会只补这 %d 批" % len(todo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
