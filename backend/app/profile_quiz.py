"""跌倒体质测试：12 道情景题 → 你最可能在哪里跌倒。

设计原则：
- 全部用情景题而非自评题——"你觉得自己理性吗"人人都答理性，
  "浮盈浮亏各一只必须卖一只你卖哪只"才测得出处置效应（Odean 1998 经典场景）；
- 每个选项给 14 种死法（failures.py）加权，没有"标准答案"的道德感；
- 结果人格命名自嘲友好——用户愿意晒出来的测试才有传播力；
- 处方直接复用跌倒地图的"芒格式逆向"，测试和内容库闭环。
"""
from .failures import FAILURES

_BY_ID = {f["id"]: f for f in FAILURES}

# 每个选项: {"text": ..., "w": {failure_id: 分}}
QUESTIONS = [
    {
        "id": "q1", "scene": "刷手机看到一只股票今天 +15%，相关新闻铺天盖地。你的第一反应是？",
        "options": [
            {"text": "马上买一点，再不上车就来不及了", "w": {"chase_hot": 3}},
            {"text": "加进自选，花两天研究清楚再说", "w": {}},
            {"text": "找找有没有同概念还没涨的股票", "w": {"chase_hot": 2, "narrative": 1}},
            {"text": "已经涨完了，与我无关", "w": {}},
        ],
    },
    {
        "id": "q2", "scene": "你持有 A（浮盈 30%）和 B（浮亏 30%），急需用钱必须卖掉一只。你卖？",
        "options": [
            {"text": "卖 A 落袋为安，B 放着等回本", "w": {"avg_down": 3}},
            {"text": "卖 B，亏损的说明我看错了", "w": {}},
            {"text": "各卖一半，雨露均沾", "w": {"avg_down": 1, "no_plan": 1}},
            {"text": "想办法借钱，一只都不卖", "w": {"leverage": 2, "avg_down": 2}},
        ],
    },
    {
        "id": "q3", "scene": "重仓股突发利空跌了 15%，当初买入的逻辑被动摇了。你会？",
        "options": [
            {"text": "立刻补仓摊低成本，便宜了 15%", "w": {"avg_down": 3, "falling_knife": 1}},
            {"text": "重新研究，逻辑真坏了就认错卖出", "w": {}},
            {"text": "卸载 App 装死，过阵子再看", "w": {"echo_chamber": 2, "no_plan": 1}},
            {"text": "先减一半仓，看清楚再决定", "w": {}},
        ],
    },
    {
        "id": "q4", "scene": "诚实地说，你觉得自己的选股水平在所有股民里排在？",
        "options": [
            {"text": "前 20%", "w": {"overtrade": 2, "bull_genius": 2}},
            {"text": "中等偏上", "w": {"overtrade": 1, "bull_genius": 1}},
            {"text": "平均水平吧", "w": {}},
            {"text": "大概率跑不赢指数，所以主仓是 ETF", "w": {}},
        ],
    },
    {
        "id": "q5", "scene": "开盘时间，你看行情的频率是？",
        "options": [
            {"text": "基本常驻盘面，分钟级刷新", "w": {"info_overload": 3, "overtrade": 2}},
            {"text": "一天看好几次", "w": {"info_overload": 1}},
            {"text": "每天收盘看一次", "w": {}},
            {"text": "想起来才看", "w": {}},
        ],
    },
    {
        "id": "q6", "scene": "二选一：① 100% 拿到 $500；② 10% 概率拿到 $4,500（90% 什么都没有）。",
        "options": [
            {"text": "果断选 ②，搏一搏单车变摩托", "w": {"lottery": 3}},
            {"text": "纠结之后选 ②", "w": {"lottery": 1}},
            {"text": "果断选 ①", "w": {}},
            {"text": "算了下期望值，① 更划算（450<500）", "w": {}},
        ],
    },
    {
        "id": "q7", "scene": "回想一下，你的买入决策最常来自？",
        "options": [
            {"text": "群里或朋友给的消息", "w": {"tips": 3}},
            {"text": "关注的大V/博主的分析", "w": {"guru": 3}},
            {"text": "当天的新闻热点", "w": {"chase_hot": 2, "narrative": 1}},
            {"text": "自己看财报和数据", "w": {}},
        ],
    },
    {
        "id": "q8", "scene": "看到一篇分析你重仓股的利空文章，写得有理有据。你通常？",
        "options": [
            {"text": "逐条反驳它，越看越坚定", "w": {"echo_chamber": 3}},
            {"text": "认真读完，把它说对的点列出来", "w": {}},
            {"text": "划走不看，眼不见心不烦", "w": {"echo_chamber": 2}},
            {"text": "心里一慌，想先卖了再说", "w": {"panic": 2}},
        ],
    },
    {
        "id": "q9", "scene": "下单买入之前，你会写下'什么情况发生我就卖出'吗？",
        "options": [
            {"text": "从来没写过，到时候看感觉", "w": {"no_plan": 3}},
            {"text": "心里大概有个价位", "w": {"no_plan": 1}},
            {"text": "有明确的卖出条件，而且执行过", "w": {}},
            {"text": "买入就没打算卖，无条件长持", "w": {"no_plan": 1, "echo_chamber": 1}},
        ],
    },
    {
        "id": "q10", "scene": "大盘连跌一周，你的账户 -15%，新闻全是坏消息。你最可能？",
        "options": [
            {"text": "先清仓避险，等跌完了再回来", "w": {"panic": 3}},
            {"text": "关掉 App，眼不见为净", "w": {"no_plan": 1}},
            {"text": "按事先的计划定投或再平衡", "w": {}},
            {"text": "上杠杆抄底，遍地黄金", "w": {"leverage": 3, "falling_knife": 1}},
        ],
    },
    {
        "id": "q11", "scene": "一只人人都听过的明星股，从高点跌了 70%。你的反应？",
        "options": [
            {"text": "跌成这样肯定超跌了，建仓", "w": {"falling_knife": 3}},
            {"text": "先查清楚它为什么跌", "w": {}},
            {"text": "等它开始反弹了再进", "w": {"chase_hot": 1}},
            {"text": "跌 70% 一定有它的理由，不碰", "w": {}},
        ],
    },
    {
        "id": "q12", "scene": "假设你今年收益 +40%，同期大盘 +30%。你觉得主要原因是？",
        "options": [
            {"text": "我的方法被验证了", "w": {"bull_genius": 3}},
            {"text": "主要是行情好，我顺了点风", "w": {}},
            {"text": "没想过这个问题", "w": {"bull_genius": 1, "no_plan": 1}},
            {"text": "+10% 超额里要先扣掉运气和风险敞口才算数", "w": {}},
        ],
    },
]

# 人格原型：按死法分组聚合，命名自嘲友好（用户才愿意晒）
ARCHETYPES = [
    {"key": "chaser", "name": "热血追风型", "emoji": "🔥",
     "ids": ["chase_hot", "tips", "guru", "narrative"],
     "desc": "你的多巴胺和热搜联动：新闻越响、群里越热闹，你的手越快。优点是永远不缺行动力，代价是常年在山顶站岗。"},
    {"key": "diamond", "name": "死磕到底型", "emoji": "💎",
     "ids": ["avg_down", "echo_chamber"],
     "desc": "你的字典里没有'认错'：越跌越补、利空不看。这股劲头放在对的股票上叫坚定，放在错的股票上叫殉葬——问题是你分不出来的时候居多。"},
    {"key": "itchy", "name": "手速惊人型", "emoji": "⚡",
     "ids": ["overtrade", "info_overload"],
     "desc": "你把'操作'当成'掌控'：盘面常驻、月月调仓。研究显示交易最勤的组年化落后市场 6.5 个百分点——你的手续费单是券商的下午茶。"},
    {"key": "gambler", "name": "艺高人胆大型", "emoji": "🎲",
     "ids": ["lottery", "leverage", "falling_knife"],
     "desc": "你嫌慢：杠杆、末日期权、接飞刀，要的就是心跳。市场对你这类选手有个专门安排——它叫强制平仓，永远发生在最低点。"},
    {"key": "rabbit", "name": "惊弓之鸟型", "emoji": "🫨",
     "ids": ["panic"],
     "desc": "你的止损线长在情绪上：跌势里的坏消息会让你在最不该卖的那天清仓。你不缺判断力，缺的是把卖出决策从'感受'手里抢回来的机制。"},
    {"key": "peacock", "name": "天选之子型", "emoji": "🦚",
     "ids": ["bull_genius"],
     "desc": "牛市给的运气，你签收成了实力。这是最贵的一种体质——因为它的学费在熊市才收，而且是加倍收。"},
    {"key": "drifter", "name": "随缘漂流型", "emoji": "🍃",
     "ids": ["no_plan"],
     "desc": "你买入靠灵感，卖出靠心情：涨了舍不得、跌了不甘心、横盘拿不住。标的常常选对了，钱却没赚到——中间隔着的那段叫纪律。"},
]


def get_quiz() -> dict:
    return {
        "title": "跌倒体质测试",
        "subtitle": "12 个真实场景，3 分钟，测出你最可能在哪里跌倒——“如果你知道你会在哪里跌倒，那就永远不要去那里。”",
        "questions": [{"id": q["id"], "scene": q["scene"],
                       "options": [o["text"] for o in q["options"]]}
                      for q in QUESTIONS],
    }


def score_quiz(answers: dict) -> dict:
    """answers: {question_id: option_index} → 体质报告。"""
    scores: dict[str, int] = {}
    answered = 0
    for q in QUESTIONS:
        idx = answers.get(q["id"])
        if idx is None or not (0 <= int(idx) < len(q["options"])):
            continue
        answered += 1
        for fid, w in q["options"][int(idx)]["w"].items():
            scores[fid] = scores.get(fid, 0) + w
    if answered < 8:
        return {"error": f"至少答完 8 题才能出报告（当前 {answered} 题）"}

    total = sum(scores.values())
    # 人格：聚合分最高的原型；全维度低分 → 修行者
    arch_scores = [(a, sum(scores.get(i, 0) for i in a["ids"])) for a in ARCHETYPES]
    arch_scores.sort(key=lambda x: -x[1])
    if total <= 6:
        archetype = {"key": "monk", "name": "六边形修行者", "emoji": "🧘",
                     "desc": "十二个坑你几乎一个都不踩——要么你已经亏出过完整的觉悟，要么你在答题时美化了自己（这本身是个值得警惕的信号）。保持纪律，定期回来复测。"}
    else:
        archetype = {k: arch_scores[0][0][k] for k in ("key", "name", "emoji", "desc")}

    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    max_possible = 9  # 单一死法理论高分约 3 题 × 3 分
    top = []
    for fid, sc in ranked[:3]:
        if sc <= 0:
            continue
        f = _BY_ID[fid]
        top.append({
            "id": fid, "emoji": f["emoji"], "title": f["title"],
            "score": sc, "pct": min(100, round(sc / max_possible * 100)),
            "hook": f["hook"], "inversion": f["inversion"],
        })

    share_text = (f"我在「明白股」测了跌倒体质：{archetype['emoji']} {archetype['name']}。"
                  + (f"最可能栽在：{'、'.join(t['title'] for t in top)}。" if top else "十二个坑几乎全躲开了。")
                  + "你呢？👉 mingbaigu.com")

    return {
        "archetype": archetype,
        "top_pitfalls": top,
        "total_score": total,
        "share_text": share_text,
        "note": "这是行为倾向的快照，不是判决书——体质会随着经验和纪律改变，建议每季度复测一次。",
    }
