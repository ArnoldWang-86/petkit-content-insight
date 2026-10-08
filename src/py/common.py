# -*- coding: utf-8 -*-
"""common.py —— 公共库：分类词典 + 品牌归一化 + 统计函数

这份文件是「口径的唯一来源」。
清洗与分析都从这里取规则，避免出现「清洗时按 A 算、分析时按 B 算」。

两个关键设计：
  1. 品牌归一化：小佩 / PETKIT / petkit / 小佩宠物 视为同一品牌
  2. 通用词品牌的宠物语境约束：像「小米」这种通用词，必须同时出现宠物语境才算提及
     （实测不加约束时「小米」假阳性率 58%，会命中电饭煲、吹风机、净水器等无关测评）
"""
import re
import statistics

# ============================================================
#  一、分类词典
# ============================================================

# 产品线：标题 + 标签命中即归类，按顺序优先
# 产品线（品牌竞争型宠物智能硬件）
# 说明：这里只放「有品牌在做、按功能参数竞争、有专业横评」的品类。
# 加热垫/猫窝属于非智能基础用品，不计入本表（归入 pains 与内容形态即可）。
CATS = [
    ("猫砂盆",  ["猫砂盆", "铲屎机", "自动厕所", "猫厕所"]),
    ("饮水机",  ["饮水机", "喝水机", "饮水器", "活水"]),
    ("喂食器",  ["喂食器", "喂食机", "投食器", "自动喂食", "喂粮器"]),
    ("摄像头",  ["宠物摄像头", "宠物监控", "宠物摄像机", "宠物看家"]),
    ("烘干箱",  ["烘干箱", "烘干机", "吹干箱", "烘干房"]),
    ("净化器",  ["净化器", "吸猫毛", "除味机", "空气净化"]),
    ("鱼缸",    ["智能鱼缸", "鱼缸", "水族箱"]),
]

# 非智能基础用品：命中即说明不是智能硬件（用于相关性判定 B）
NON_SMART_GOODS = ["加热垫", "加热棒", "保温灯", "温控器", "猫窝", "猫爬架", "猫抓板"]

# 宠物语境：拦截通用词品牌的假阳性
PET_CTX = re.compile(r"猫|狗|宠物|喵|汪|主子|毛孩子|饮水机|喂食器|猫砂|铲屎|烘干|摄像头|养宠")

# 品牌别名表：(规范名, 别名列表, 是否需要宠物语境)
#   needs_pet_ctx = True  → 品牌名是通用词，必须同时出现宠物语境才算真实提及
#   needs_pet_ctx = False → 品牌名是专用词，命中即可信
BRAND_ALIAS = [
    ("小佩",     ["小佩", "petkit"],  False),
    ("霍曼",     ["霍曼", "homerun"], False),
    ("CATLINK",  ["catlink"],         False),
    ("糯雪",     ["糯雪"],            False),
    ("鸟语花香", ["鸟语花香"],        False),
    ("pidan",    ["pidan"],           False),
    ("有陪",     ["有陪"],            False),
    ("未卡",     ["未卡"],            False),
    ("猫洁易",   ["猫洁易"],          False),
    ("petshy",   ["petshy"],          False),
    ("小米",     ["小米", "米家"],    True),
    ("美的",     ["美的"],            True),
    ("小壹",     ["小壹"],            True),
]

# 用户痛点：用户用这些词表达困扰，是最直接的需求信号
PAINS = [
    ("清洁/维护麻烦",   ["清洗", "清洁", "拆洗", "难洗", "打理", "挂壁", "粘底", "结团", "换砂"]),
    ("异味/除臭",       ["异味", "除臭", "臭", "味道大", "串味"]),
    ("猫咪不接受",      ["不肯", "不进", "不敢", "排斥", "应激", "适应"]),
    ("故障/安全风险",   ["卡猫", "故障", "坏了", "维修", "报错", "失灵", "夹猫", "卡住", "安全"]),
    ("噪音",            ["噪音", "吵", "声音大", "静音"]),
    ("价格/性价比",     ["性价比", "智商税", "平替", "贵", "便宜", "预算", "值不值"]),
    ("耗材/长期成本",   ["耗材", "垃圾袋", "滤芯", "成本", "专用"]),
    ("健康监测/泌尿",   ["泌尿", "尿闭", "健康", "监测", "体重", "异常"]),
    ("多猫/大猫适配",   ["多猫", "大猫", "体型", "大体型", "双猫", "三猫", "空间"]),
    ("上班族/无人值守", ["上班", "出差", "无人", "长时间", "加班"]),
    ("智能互联/APP",    ["app", "手机", "联网", "智能联动", "远程", "语音"]),
    ("猫毛/掉毛",       ["掉毛", "猫毛", "粘毛", "除毛"]),
]

# 使用场景：刻画「谁在什么处境下买」
SCENES = [
    ("上班族/白天独处", ["上班", "加班", "白天不在家", "打工人", "独处"]),
    ("出差/旅行在外",   ["出差", "旅行", "旅游", "出门几天", "长途"]),
    ("多猫家庭",        ["多猫", "两只猫", "三只猫", "双猫", "猫口"]),
    ("新手养猫",        ["新手", "第一次养猫", "入门", "小白"]),
    ("预算敏感/学生党", ["预算", "学生党", "平价", "性价比"]),
]

# 内容形态
# 内容形态（顺序即优先级：越靠前越优先匹配）
FORMATS = [
    # 先判长期使用反馈，避免被"测评/推荐"抢先匹配
    ("使用体验/吐槽", ["吐槽", "用了一年", "用了半年", "长期使用", "劝退", "后悔", "鸡肋",
                     "智商税", "翻车", "踩坑实录", "真实体验", "使用感受", "值得买吗",
                     "为什么不推荐", "避雷"]),
    ("横评/选购",    ["横评", "对比", "评测", "测评", "哪款", "推荐", "怎么选", "选购", "排行榜"]),
    ("教程/指南",    ["教程", "指南", "攻略", "怎么用", "使用指南", "避坑", "干货"]),
    ("开箱/上手",    ["开箱", "上手", "入手", "试用", "第一次用"]),
    ("DIY/改装",     ["diy", "自制", "手搓", "改装", "改造"]),
    ("闲置/二手",    ["闲置", "二手", "捡漏", "转卖", "退货"]),
]

# 官方账号识别：这些品牌的自营账号
OFFICIAL_RE = re.compile(r"小佩|petkit|霍曼|homerun|catlink", re.I)


# ============================================================
#  二、匹配函数
# ============================================================

def _hit(hay: str, keywords) -> bool:
    """标题+标签拼接后的文本里，是否命中任一关键词（大小写不敏感）"""
    low = hay.lower()
    return any(k.lower() in low for k in keywords)


def pick_category(hay: str) -> str:
    """判定内容属于哪条产品线"""
    for name, kws in CATS:
        if _hit(hay, kws):
            return name
    return "其他/泛宠物"


def pick_brands(hay: str) -> list:
    """判定提及了哪些品牌（含通用词品牌的宠物语境约束）"""
    out = []
    for name, aliases, needs_ctx in BRAND_ALIAS:
        if not _hit(hay, aliases):
            continue
        if needs_ctx and not PET_CTX.search(hay):
            continue
        out.append(name)
    return out


def pick_brands_strong(title: str, hay: str) -> list:
    """标题里直接出现的品牌 = 强信号（比仅标签命中更可信）"""
    low = title.lower()
    out = []
    for name, aliases, needs_ctx in BRAND_ALIAS:
        if not any(k.lower() in low for k in aliases):
            continue
        if needs_ctx and not PET_CTX.search(hay):
            continue
        out.append(name)
    return out


def pick_pains(hay: str) -> list:
    return [name for name, kws in PAINS if _hit(hay, kws)]


def pick_scenes(hay: str) -> list:
    return [name for name, kws in SCENES if _hit(hay, kws)]


def pick_format(hay: str) -> str:
    for name, kws in FORMATS:
        if _hit(hay, kws):
            return name
    return "其他"


# ============================================================
#  三、统计函数
# ============================================================

def median(values):
    return statistics.median(values) if values else 0


def q(values, p: float):
    """分位数（线性插值），p 取 0~1"""
    if not values:
        return 0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    idx = (len(s) - 1) * p
    lo, hi = int(idx), min(int(idx) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def summarize(rows: list) -> dict:
    """统一的分组指标。各分析模块都输出这个结构，便于横向比较与拼表"""
    if not rows:
        return {}
    plays = [r["play"] for r in rows]
    ints = [r["interact"] for r in rows]
    return {
        "n": len(rows),
        "play_median": int(median(plays)),
        "play_mean": int(sum(plays) / len(plays)),
        "play_p90": int(q(plays, 0.9)),
        "interact_mean": round(sum(ints) / len(ints), 4),
        "interact_median": round(median(ints), 4),
        "like_rate": round(sum(r["like_rate"] for r in rows) / len(rows), 4),
        "fav_rate": round(sum(r["fav_rate"] for r in rows) / len(rows), 4),
        "dm_rate": round(sum(r["dm_rate"] for r in rows) / len(rows), 2),
        "creators": len({r["mid"] for r in rows}),
    }


def group_by(rows: list, keyfn) -> dict:
    """按 keyfn 分组，返回 {键: [行]}"""
    out = {}
    for r in rows:
        out.setdefault(keyfn(r), []).append(r)
    return out
