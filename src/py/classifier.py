# -*- coding: utf-8 -*-
"""classifier.py —— 规则层（Labeling Functions，可弃权）

设计依据（arXiv:2202.05433 综述中 LF 的正式定义）：

    λ : X → Y ∪ {-1}

即每条规则对一条数据要么投出一个类别，要么**弃权（-1）**。
规则是「错误率各不相同的带噪投票者」，多条规则之间会 overlap 与 conflict，
最终判定应由聚合层（aggregator.py）加权得出，而不是由某条规则一票否决。

本模块相对旧版的改动（旧版违反了 LF 定义）：
  1. 规则改为**可弃权**：只有证据充分时才投票
  2. 每条规则独立返回投票，互不覆盖
  3. 记录 coverage（非弃权比例）与命中明细，供后续测精度、定权重

类别体系（本项目的 4 个相关性级别）：
  A 直接相关（智能硬件本体） / B 延伸相关 / C 用户语境 / N 非宠物
"""

# ============================================================
#  词汇表
# ============================================================
NOISE_WORDS = [
    "洗车机", "高压水枪", "电饭煲", "洗衣机", "冰箱", "空调", "洗碗机",
    "净水器", "净饮机", "茶吧机", "管线机", "吹风机", "浴霸", "空气炸锅",
    "破壁机", "电风扇", "加湿器", "投影仪", "显示器", "鼠标", "键盘",
    "宝宝", "婴儿", "母婴", "奶瓶", "辅食", "喂养台", "奶粉", "纸尿裤",
    "咖啡", "奶茶", "魔芋", "除草", "果园", "三农", "养鸡", "养蜂",
    "iPhone", "显卡", "平板电脑",
]
GAME_WORDS = ["我的世界", "星露谷", "模组", "沙盒游戏", "游戏解说", "实况"]

# 通用安防：不是宠物摄像头（实测会误导"宠物摄像头"这个词）
SECURITY_WORDS = ["POE", "安防", "监控方案", "景点", "直播摄像头", "家用监控",
                  "海康威视", "萤石", "摄像头捕捉", "行车记录", "门禁"]
BRAND_WORDS = ["小佩", "petkit", "霍曼", "homerun", "catlink", "糯雪", "鸟语花香",
               "pidan", "有陪", "未卡", "猫洁易", "petshy", "小壹"]
# 品牌竞争型宠物智能硬件（命中即支持判 A）
# 注意：「摄像头/监控」收紧为宠物专用组合词，避免命中通用安防内容
HW_WORDS = ["猫砂盆", "铲屎机", "自动厕所", "猫厕所", "饮水机", "喝水机", "饮水器",
            "喂食器", "喂食机", "投食器", "喂粮器",
            "宠物摄像头", "宠物监控", "宠物摄像机", "宠物看家",
            "烘干箱", "烘干机", "吹干箱", "烘干房",
            "净化器", "吸猫毛", "鱼缸", "智能鱼缸", "水族箱"]

# 非智能基础用品：命中则不支持判 A（加热垫、猫窝等）
PLAIN_GOODS = ["加热垫", "加热棒", "保温灯", "温控器", "猫窝", "猫爬架", "猫抓板", "食盆", "水碗"]

# 产品导向信号：出现这些词说明内容在讨论"产品本身"
PRODUCT_FOCUS = ["测评", "评测", "横评", "对比", "推荐", "怎么选", "选购", "开箱",
                 "上手", "避坑", "指南", "攻略", "测评", "评价", "使用感受",
                 "值得买", "值不值", "性价比", "优缺点", "哪个好", "哪款", "排行",
                 "榜单", "教程", "安装", "维修", "拆解", "实测", "体验"]

# 宠物行为信号：出现这些词说明内容是"记录宠物行为"，产品只是道具
PET_BEHAVIOR = ["玩", "搞笑", "可爱", "日常", "记录", "vlog", "反应", "逗",
                "萌", "上头", "笑死", "沙雕", "行为", "表情", "睡", "蹭"]

# 「天生即智能」品类：这些品类本身有电子/联网/自动控制，标题不写"智能"也算 A
# （实测：宠物净化器、烘干箱、鱼缸的标题通常不写"智能"二字，若要求关键字会大面积误判为 B）
AUTO_SMART_HW = ["净化器", "吸猫毛", "鱼缸", "智能鱼缸", "水族箱",
                 "烘干箱", "烘干机", "吹干箱", "烘干房",
                 "智能猫砂盆", "自动猫砂盆", "全自动猫砂盆", "自动喂食器", "自动饮水机"]
PET_WORDS = ["猫", "狗", "宠物", "喵", "汪", "铲屎", "养宠", "毛孩子", "主子",
             "幼犬", "小狗", "小猫", "犬", "猫咪", "狗狗", "橘猫", "布偶", "田园猫",
             "哈士奇", "金毛", "泰迪", "柯基", "边牧", "银渐层", "美短", "英短",
             "乌龟", "鹦鹉", "仓鼠", "龙猫", "水族", "观赏鱼", "养鱼", "爬宠"]
SMART_WORDS = ["智能", "自动", "全自动", "app", "远程", "联网", "wifi", "无线",
               "感应", "杀菌", "除菌", "uvc", "定时", "遥控", "语音", "物联网", "传感"]
# 耗材/日用（B 级信号）
# 注意：不放入过泛的「玩具」（实测假阳性 83%，如"泡泡玩具""饮水机沦为玩具"），
#       改用更具体的说法 —— 规则层只做「高精度、低召回」的投票。
SUPPLY_WORDS = ["猫砂", "猫粮", "狗粮", "罐头", "猫条", "冻干", "零食", "营养",
                "猫草", "猫玩具", "狗狗玩具", "宠物玩具", "猫抓板", "猫爬架",
                "逗猫棒", "洗护", "沐浴", "香波"]
# 健康医疗（B 级信号）
HEALTH_WORDS = ["猫癣", "疫苗", "驱虫", "绝育", "泌尿", "尿闭", "呕吐", "拉稀",
                "口炎", "生病", "医院", "体检", "疾病", "治疗"]


# 子串陷阱守卫：若"短词"出现的每一处都被某个"长词"包住，就不算它独立出现。
# 实测依据（全量 3,747 条）：「猫砂盆」使耗材规则 LF_SUPPLY 误投 B 共 514 票，
# 占该规则总票数的 59%；「熊猫」「猫眼」里的「猫」同理。
SUBSTRING_GUARDS = {
    "猫砂": ["猫砂盆", "自动猫砂盆", "智能猫砂盆", "猫厕所", "铲屎机", "自动厕所"],
    "猫":   ["熊猫", "猫眼"],
}


def _standalone(word, hay_low):
    """该词是否"独立"出现（未被 SUBSTRING_GUARDS 中的长词包住）"""
    longs = SUBSTRING_GUARDS.get(word)
    if not longs:
        return True
    rest = hay_low
    for L in longs:
        rest = rest.replace(L.lower(), "")
    return word.lower() in rest


def _hits(hay, words):
    low = hay.lower()
    return [w for w in words if w.lower() in low and _standalone(w, low)]


def lf_votes(title, tag):
    """每条规则独立投票。返回 {规则id: {"vote": 类别或None, "hits": [...]}}

    vote = None 表示**弃权**（该规则对这条数据没有意见）
    """
    hay = (title + " " + tag).lower()
    out = {}

    def add(rid, words, vote, text=None):
        h = _hits(text if text is not None else hay, words)
        if h:
            out[rid] = {"vote": vote, "hits": h[:6]}
        else:
            out[rid] = {"vote": None, "hits": []}

    add("LF_NOISE", NOISE_WORDS, "N")
    add("LF_GAME", GAME_WORDS, "N")
    add("LF_SECURITY", SECURITY_WORDS, "N")   # 通用安防 → N
    add("LF_BRAND", BRAND_WORDS, None)      # 品牌本身不决定级别，只作证据
    add("LF_HW", HW_WORDS, None)            # 硬件词不决定级别
    add("LF_PET", PET_WORDS, None)          # 宠物词不决定级别
    add("LF_SMART", SMART_WORDS, None)      # 智能属性
    add("LF_PLAIN", PLAIN_GOODS, None)      # 非智能基础用品（只作负向证据）
    add("LF_AUTO_SMART", AUTO_SMART_HW, None)  # 天生即智能的品类（只作证据）
    add("LF_PRODUCT_FOCUS", PRODUCT_FOCUS, None)   # 产品导向信号
    add("LF_PET_BEHAVIOR", PET_BEHAVIOR, None)     # 宠物行为信号
    # LF_SUPPLY 只在**标题**里找证据：实测标签里的耗材词是噪声
    # （猫视频的标签普遍挂着"狗粮/遛狗/养狗"这类通用词，抽检 6/6 全是假阳性），
    # 只看标题可把该规则精度从 27% 提到 40%。
    add("LF_SUPPLY", SUPPLY_WORDS, "B", text=title)   # 耗材日用 → B
    add("LF_HEALTH", HEALTH_WORDS, "C")     # 健康医疗 → C（方案A：理解用户为主，非购买决策）

    # 组合规则：需要多个条件同时满足才投票，否则弃权
    brand = bool(out["LF_BRAND"]["hits"])
    hw = bool(out["LF_HW"]["hits"])
    pet = bool(out["LF_PET"]["hits"])
    smart = bool(out["LF_SMART"]["hits"])
    plain = bool(out["LF_PLAIN"]["hits"])   # 加热垫/猫窝等非智能用品
    auto_smart = bool(out["LF_AUTO_SMART"]["hits"])   # 天生即智能的品类
    prod_focus = bool(out["LF_PRODUCT_FOCUS"]["hits"])  # 在讨论产品本身
    pet_behavior = bool(out["LF_PET_BEHAVIOR"]["hits"]) # 在记录宠物行为

    # R_A1：宠物品牌 + 智能硬件词 → 直接相关（最强证据）
    # 但若同时命中非智能用品，则不投 A（例如"霍曼加热垫"应归 B）
    a1 = brand and hw and not plain
    out["LF_A_BRAND_HW"] = {"vote": "A" if a1 else None,
                            "hits": (out["LF_BRAND"]["hits"] + out["LF_HW"]["hits"])[:6] if a1 else []}
    # R_A2：宠物语境 + 硬件词 +（智能属性 或 天生即智能品类）→ 直接相关
    a2 = pet and hw and (smart or auto_smart) and not plain
    out["LF_A_PET_HW_SMART"] = {"vote": "A" if a2 else None,
                                "hits": (out["LF_SMART"]["hits"] + out["LF_AUTO_SMART"]["hits"])[:4] if a2 else []}
    # R_B1：非智能用品，或「宠物+硬件但无智能属性」→ 普通宠物用品（B）
    # 但若内容明显是「记录宠物行为」（产品只是道具），则交给 C
    b1 = (pet or brand) and plain and not (hw and smart and not plain)
    b2 = pet and hw and not smart and not auto_smart and not plain
    b_vote = "B" if (b1 and not (hw and smart)) else ("B" if b2 else None)
    if b_vote == "B" and pet_behavior and not prod_focus:
        b_vote = None   # 主体是宠物行为，不投 B
    out["LF_B_PET_HW_PLAIN"] = {"vote": b_vote,
                                "hits": (out["LF_PLAIN"]["hits"] + out["LF_HW"]["hits"])[:4] if b_vote else []}

    # R_A3：产品导向 + 硬件词 + 宠物语境 → 直接相关（不要求"智能"二字）
    a3 = prod_focus and hw and pet and not plain
    out["LF_A_PRODUCT_FOCUS"] = {"vote": "A" if a3 else None,
                                 "hits": out["LF_PRODUCT_FOCUS"]["hits"][:4] if a3 else []}

    # R_C1：宠物语境（无硬件词）→ 用户语境
    out["LF_C_PET_ONLY"] = {"vote": "C" if (pet and not hw) else None,
                            "hits": out["LF_PET"]["hits"][:4] if (pet and not hw) else []}

    # R_C3：宠物行为主导（硬件只是道具）→ 用户语境
    c3 = pet and pet_behavior and not prod_focus
    out["LF_C_PET_BEHAVIOR"] = {"vote": "C" if c3 else None,
                                "hits": out["LF_PET_BEHAVIOR"]["hits"][:4] if c3 else []}

    # R_C2：健康/医疗内容 → 用户语境（避免与耗材的 B 冲突）
    if out["LF_HEALTH"]["hits"]:
        out["LF_HEALTH"]["vote"] = "C"

    return out


def coverage_and_votes(records):
    """统计每条规则的 coverage（非弃权比例）与投票分布"""
    stat = {}
    for r in records:
        vs = lf_votes(r.get("title", ""), r.get("tag", ""))
        for rid, info in vs.items():
            s = stat.setdefault(rid, {"n": len(records), "voted": 0, "by_class": {}})
            if info["vote"]:
                s["voted"] += 1
                s["by_class"][info["vote"]] = s["by_class"].get(info["vote"], 0) + 1
    for rid, s in stat.items():
        s["coverage"] = round(s["voted"] / s["n"], 4) if s["n"] else 0
    return stat


def measure_rule_precision(audited):
    """用人工标注子集测量每条规则的精度（借鉴 ULF 的「校验规则」思想）

    audited: [{"lf_votes": {规则id: {"vote":...}}, "human": "A/B/C/N"}]
    只在规则**投了票**的样本上计算：投出的类别与人工判定一致 = 正确
    """
    stat = {}
    for row in audited:
        human = (row.get("human") or "").strip().upper()
        if human not in ("A", "B", "C", "N"):
            continue
        for rid, info in (row.get("lf_votes") or {}).items():
            if not info.get("vote"):
                continue
            s = stat.setdefault(rid, {"voted": 0, "correct": 0})
            s["voted"] += 1
            if info["vote"] == human:
                s["correct"] += 1
    out = {}
    for rid, s in stat.items():
        if s["voted"] > 0:
            out[rid] = {"voted": s["voted"], "correct": s["correct"],
                        "precision": round(s["correct"] / s["voted"], 4)}
    return out
