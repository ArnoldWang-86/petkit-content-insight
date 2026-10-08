# -*- coding: utf-8 -*-
"""llm_labeler.py —— 大模型标注层（含自一致性投票）

设计依据：
  · LLM 可以胜任数据标注，但需要「评估其产出」的机制
    —— Large Language Models for Data Annotation and Synthesis: A Survey (arXiv:2402.13446)
  · 多次采样取多数（自一致性）比单次贪心解码更稳定
    —— Self-Consistency Improves CoT Reasoning (arXiv:2203.11171)
  · 模型的「自报置信度」普遍过度自信，因此用「投票一致率」作为置信度更客观

流水线位置：
  规则层（classifier.py，高精度低召回）
    → 本模块（主判 + 低置信样本自一致性投票）
      → 主动学习抽检（active_learning.py）
"""
import json
import os
import time
from collections import Counter

import requests

THEMES = [
    "硬件产品", "硬件DIY", "耗材日用", "健康医疗", "养护科普",
    "日常vlog", "领养救助", "非硬件选购", "行业资讯", "非宠物",
]
PRODUCT_LINES = ["猫砂盆", "饮水机", "喂食器", "摄像头", "烘干箱",
                 "加热垫/猫窝", "净化器", "鱼缸", "其他硬件"]

SYSTEM_PROMPT = """你是一名宠物智能硬件行业的资深数据分析师，正在为 B站 内容做分类标注。

# 业务背景
我们做「宠物智能硬件」（智能猫砂盆、宠物饮水机、自动喂食器、宠物空气净化器、智能鱼缸等）
的用户内容洞察。数据来自 B站搜索接口，混入了不少与宠物无关的内容，需要准确分类。

# 标注维度

## relevance 相关性（四选一，最重要）
- A 直接相关：内容主体就是「品牌竞争型宠物智能硬件」产品
  （智能猫砂盆 / 宠物饮水机 / 自动喂食器 / 宠物摄像头 / 宠物烘干箱 /
   宠物净化器 / 智能鱼缸 的测评、横评、开箱、使用教程、官方发布、硬件DIY）
- B 延伸相关：不是智能硬件本身，但直接影响"买哪款硬件"的决策
  （猫砂 / 猫粮 等耗材测评；加热垫 / 猫窝 / 猫抓板 等非智能用品选购；
   宠物定位器等非智能硬件选购）
- C 用户语境：理解养宠的人是谁、在意什么
  （疾病健康、养护科普、日常vlog、领养救助、搞笑萌宠）
- N 非宠物：与宠物完全无关（家电、母婴、游戏、食品、数码3C、通用安防监控）

## theme 内容主题（选一个）
硬件产品（含使用体验/吐槽）/ 硬件DIY / 耗材日用 / 健康医疗 / 养护科普 /
日常vlog / 领养救助 / 非硬件选购 / 行业资讯 / 非宠物

## product_line 产品线（仅 relevance=A 时填，否则填空字符串）
猫砂盆 / 饮水机 / 喂食器 / 摄像头 / 烘干箱 / 净化器 / 鱼缸 / 其他硬件

# 判断原则（务必遵守）
1. 只看标题和标签，不要脑补内容
2. 【主体是谁】内容主体是"产品"还是"宠物行为"？
   - 主体是产品（测评/吐槽/教程）→ 按相关性 A 或 B
   - 主体是宠物行为（猫咪玩饮水机、萌宠日常）→ C，哪怕标题里出现硬件名
3. 【智能品类清单】只有以下品类算 A 级智能硬件：
   猫砂盆 / 饮水机 / 喂食器 / 摄像头 / 烘干箱 / 净化器 / 鱼缸
   注意：烘干箱、净化器本身即品牌竞争型硬件，标题不写"智能"也算 A
4. 【非智能用品】加热垫 / 加热棒 / 保温灯 / 猫窝 / 猫爬架 / 猫抓板
   → 一律 B（非智能用品选购），不算 A
5. 【健康与养护】疾病、治疗、养护科普 → 一律 C（理解用户为主，不是购买决策）
6. 【使用体验/吐槽】对某款硬件的长期使用反馈、吐槽、劝退 → 仍是 A
   （主体是产品）。请把 theme 标为「硬件产品」
7. 【通用品牌看语境】小米/米家/美的 必须同时有宠物语境才算宠物内容
8. 【子串陷阱】「鸟语花香」是宠物品牌名不是鸟；「猫眼」不是猫；「熊猫」不是猫
9. 【通用安防】家用监控、安防摄像头、景点直播 → N，不是宠物摄像头
10. 拿不准时，宁可给 B 或 C，不要轻易给 A

# 输出格式
只输出 JSON，不要任何解释文字：
{"results": [{"id": 1, "theme": "...", "relevance": "A|B|C|N",
              "product_line": "...", "confidence": 0.0~1.0,
              "reason": "20字以内的判断依据"}]}
confidence 表示你对这条判断的把握，0.5 表示拿不准。
"""


def load_api_key(root):
    env_path = os.path.join(root, ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("DEEPSEEK_API_KEY")


class LLMLabeler:
    def __init__(self, root, model="deepseek-chat", retries=3, temperature=0.0):
        self.url = "https://api.deepseek.com/chat/completions"
        self.key = load_api_key(root)
        if not self.key:
            raise RuntimeError("未找到 DEEPSEEK_API_KEY（请在 .env 中配置）")
        self.model = model
        self.retries = retries
        self.temperature = temperature
        self.calls = 0
        self.tokens = 0

    def _chat(self, messages, temperature=None):
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": 4000,
            "response_format": {"type": "json_object"},
        }
        r = requests.post(self.url,
                          headers={"Authorization": "Bearer " + self.key,
                                   "Content-Type": "application/json"},
                          json=body, timeout=120)
        r.raise_for_status()
        j = r.json()
        self.calls += 1
        self.tokens += j.get("usage", {}).get("total_tokens", 0)
        return j["choices"][0]["message"]["content"]

    def _parse(self, content):
        data = json.loads(content)
        results = data.get("results") if isinstance(data, dict) else data
        if isinstance(results, dict):
            results = list(results.values())
        if not isinstance(results, list):
            return {}
        out = {}
        for r in results:
            i = r.get("id")
            if i is None:
                continue
            rel = str(r.get("relevance", "")).strip().upper()[:1]
            if rel not in ("A", "B", "C", "N"):
                rel = "C"
            try:
                conf = float(r.get("confidence", 0.7))
            except Exception:
                conf = 0.7
            out[int(i)] = {
                "theme": r.get("theme", "其他"),
                "relevance": rel,
                "product_line": r.get("product_line", "") or "",
                "confidence": max(0.0, min(1.0, conf)),
                "reason": (r.get("reason", "") or "")[:40],
            }
        return out

    def label_batch(self, items, temperature=None):
        payload = [{"id": it["id"], "title": it["title"][:80], "tag": it["tag"][:120]} for it in items]
        user = "请对下列 B站 内容做标注（只输出 JSON）：\n\n" + json.dumps(payload, ensure_ascii=False, indent=1)
        for attempt in range(self.retries):
            try:
                got = self._parse(self._chat(
                    [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": user}], temperature=temperature))
                if got:
                    return got
            except Exception as e:
                if attempt == self.retries - 1:
                    print("      [批次失败] " + type(e).__name__ + ": " + str(e)[:90])
                else:
                    time.sleep(2 * (attempt + 1))
        return {}

    def label_all(self, records, batch_size=25, verbose=True, ckpt_path=None):
        """分批标注。ckpt_path 非空时**每批落盘**，中断后可续跑（不重复调 API）。"""
        results = [None] * len(records)
        total = (len(records) + batch_size - 1) // batch_size
        done_batches = set()

        # 读取已有检查点
        if ckpt_path and os.path.exists(ckpt_path):
            try:
                ck = json.load(open(ckpt_path, encoding="utf-8"))
                if ck.get("n") == len(records):
                    for bi_str, vals in ck.get("batches", {}).items():
                        bi = int(bi_str)
                        start = bi * batch_size
                        for off, v in enumerate(vals):
                            if start + off < len(results):
                                results[start + off] = v
                        done_batches.add(bi)
                    if done_batches:
                        print("      从检查点恢复 %d/%d 批" % (len(done_batches), total))
            except Exception:
                pass

        for bi in range(total):
            if bi in done_batches:
                continue
            start = bi * batch_size
            idx = list(range(start, min((bi + 1) * batch_size, len(records))))
            items = [{"id": i, "title": records[i].get("title", ""), "tag": records[i].get("tag", "")} for i in idx]
            got = self.label_batch(items)
            for i in idx:
                results[i] = got.get(i, {"theme": "标注失败", "relevance": "?",
                                         "product_line": "", "confidence": 0.0, "reason": ""})
            if verbose:
                print("      批次 %d/%d  tokens=%d" % (bi + 1, total, self.tokens), flush=True)
            # 每批落盘
            if ckpt_path:
                batches = {}
                for b in range(total):
                    s = b * batch_size
                    seg = results[s:min(s + batch_size, len(records))]
                    if seg and all(x is not None for x in seg):
                        batches[str(b)] = seg
                try:
                    json.dump({"n": len(records), "batches": batches},
                              open(ckpt_path, "w", encoding="utf-8"), ensure_ascii=False)
                except Exception:
                    pass
            time.sleep(0.3)
        return results

    def vote_low_confidence(self, records, base_labels, threshold=0.8, votes=3, batch_size=25):
        """对低置信度样本做自一致性投票（arXiv:2203.11171）

        做法：把这些样本再问 votes 次（temperature>0 以产生多样性），与原判定一起投票。
        一致率作为新的置信度：3/3 一致 = 1.0，2/3 = 0.67。
        """
        targets = [i for i, lb in enumerate(base_labels)
                   if lb and lb.get("confidence", 0) < threshold and lb.get("relevance") != "?"]
        if not targets:
            print("      无低置信度样本，跳过投票")
            return base_labels
        print("      低置信度样本 %d 条，进行 %d 轮投票 ..." % (len(targets), votes))
        tally = {i: [base_labels[i]["relevance"]] for i in targets}
        for v in range(votes):
            for bi in range((len(targets) + batch_size - 1) // batch_size):
                idx = targets[bi * batch_size:(bi + 1) * batch_size]
                items = [{"id": j, "title": records[j].get("title", ""), "tag": records[j].get("tag", "")} for j in idx]
                got = self.label_batch(items, temperature=0.8)   # 升温以获得多样性
                for j in idx:
                    if j in got:
                        tally[j].append(got[j]["relevance"])
                time.sleep(0.2)
            print("        第 %d/%d 轮完成，tokens=%d" % (v + 1, votes, self.tokens))

        for i in targets:
            vs = tally[i]
            winner, n = Counter(vs).most_common(1)[0]
            base_labels[i]["relevance"] = winner
            base_labels[i]["agreement"] = round(n / len(vs), 2)
            base_labels[i]["confidence"] = round(n / len(vs), 2)   # 用一致率替代自报置信度
            base_labels[i]["votes"] = "/".join(vs)
        return base_labels
