"""对抗验证机制：多头(Bull) vs 空头(Bear) 互相找证据，裁判(Judge)综合裁决。

设计思路：单一模型容易过度自信。这里让两个立场相反的"分析师"
分别从技术面、消息面、基本面、模型回测四个维度找证据，
裁判再根据双方论据强度 + 模型样本外真实战绩，给出最终结论与置信度。
任何一方论据足够强、或模型回测没有真实优势时，置信度都会被压低。
"""


def _arg(side: str, dimension: str, text: str, weight: float) -> dict:
    return {"side": side, "dimension": dimension, "text": text,
            "weight": round(weight, 2)}


def _news_event_args(side: str, drivers: list[dict], max_n: int = 2) -> list[dict]:
    """把消息面研判中的关键事件新闻转成论据。"""
    args = []
    for d in drivers[:max_n]:
        if abs(d["impact"]) < 1.5:
            continue
        tag = "/".join(d["events"]) if d["events"] else ("重磅利好" if side == "bull" else "重磅利空")
        args.append(_arg(side, "消息面", f"〔{tag}〕{d['title'][:60]}", 0.9))
    return args


def build_bull_case(tech: dict, news_sig: dict | None, fundamentals: dict | None,
                    prediction: dict | None) -> list[dict]:
    args = []
    if tech["close_above_sma50"]:
        args.append(_arg("bull", "技术面", "股价站在 50 日均线之上，中期趋势仍是多头排列", 1.0))
    if tech["momentum_20d"] > 0.03:
        args.append(_arg("bull", "技术面",
                         f"近 20 个交易日上涨 {tech['momentum_20d']*100:.1f}%，动量为正", 0.8))
    if 30 < tech["rsi"] < 65:
        args.append(_arg("bull", "技术面", f"RSI 为 {tech['rsi']:.0f}，处于健康区间，没有超买", 0.5))
    if tech["rsi"] <= 30:
        args.append(_arg("bull", "技术面", f"RSI 仅 {tech['rsi']:.0f}，超卖后往往有技术性反弹", 0.6))

    if news_sig and news_sig["score"] >= 0.4:
        weight = min(1.6, 0.6 + news_sig["score"] * 0.4)
        args.append(_arg("bull", "消息面",
                         f"消息面综合信号 {news_sig['score']:+.1f}（{news_sig['direction_cn']}），"
                         f"近期 {news_sig['positive']} 条利好 vs {news_sig['negative']} 条利空", weight))
        args.extend(_news_event_args("bull", news_sig["drivers_positive"]))

    if fundamentals:
        eg = fundamentals.get("earnings_growth")
        if eg and eg > 0.05:
            args.append(_arg("bull", "基本面", f"盈利同比增长 {eg*100:.0f}%，业绩在改善", 1.0))
        roe = fundamentals.get("return_on_equity")
        if roe and roe > 0.12:
            args.append(_arg("bull", "基本面", f"ROE 达 {roe*100:.0f}%，赚钱效率不错", 0.6))
        rating = fundamentals.get("analyst_rating")
        if rating in ("buy", "strong_buy"):
            args.append(_arg("bull", "基本面", "华尔街分析师整体评级为买入", 0.5))

    if prediction and prediction["prob_up"] > 0.55:
        args.append(_arg("bull", "模型",
                         f"量化模型给出 {prediction['prob_up']*100:.0f}% 的跑赢大盘概率（未来约半年）", 0.7))
    return args


def build_bear_case(tech: dict, news_sig: dict | None, fundamentals: dict | None,
                    prediction: dict | None, risk: dict) -> list[dict]:
    args = []
    if not tech["close_above_sma50"]:
        args.append(_arg("bear", "技术面", "股价跌破 50 日均线，中期趋势转弱", 1.0))
    if tech["momentum_20d"] < -0.03:
        args.append(_arg("bear", "技术面",
                         f"近 20 个交易日下跌 {abs(tech['momentum_20d'])*100:.1f}%，动量为负", 0.8))
    if tech["rsi"] >= 70:
        args.append(_arg("bear", "技术面", f"RSI 高达 {tech['rsi']:.0f}，明显超买，追高风险大", 0.9))
    if tech["dist_52w_high"] < -0.15:
        args.append(_arg("bear", "技术面",
                         f"距 52 周高点仍有 {abs(tech['dist_52w_high'])*100:.0f}% 的距离，上方套牢盘压力大", 0.5))

    if news_sig and news_sig["score"] <= -0.4:
        weight = min(1.6, 0.6 + abs(news_sig["score"]) * 0.4)
        args.append(_arg("bear", "消息面",
                         f"消息面综合信号 {news_sig['score']:+.1f}（{news_sig['direction_cn']}），"
                         f"近期 {news_sig['negative']} 条利空 vs {news_sig['positive']} 条利好", weight))
        args.extend(_news_event_args("bear", news_sig["drivers_negative"]))

    if fundamentals:
        pe = fundamentals.get("trailing_pe")
        if pe and pe > 40:
            args.append(_arg("bear", "基本面", f"市盈率 {pe:.0f} 倍，估值不便宜，已透支不少预期", 0.7))
        eg = fundamentals.get("earnings_growth")
        if eg is not None and eg < -0.05:
            args.append(_arg("bear", "基本面", f"盈利同比下滑 {abs(eg)*100:.0f}%，业绩在恶化", 1.0))

    if risk["annual_volatility"] > 0.40:
        args.append(_arg("bear", "风险", f"年化波动率 {risk['annual_volatility']*100:.0f}%，属于高波动品种", 0.6))

    if prediction:
        if prediction["prob_up"] < 0.45:
            args.append(_arg("bear", "模型",
                             f"量化模型给出 {(1-prediction['prob_up'])*100:.0f}% 的跑输大盘概率（未来约半年）", 0.7))
        bt = prediction.get("backtest") or {}
        edge = bt.get("edge")
        if edge is not None and edge <= 0.01:
            args.append(_arg("bear", "模型",
                             "对抗审计：模型样本外没有跑赢『随机猜』基准，本次预测不应被高估", 0.9))
    return args


def judge(bull: list[dict], bear: list[dict], prediction: dict | None) -> dict:
    """裁决：综合双方论据强度与模型真实战绩，输出结论+置信度+理由。"""
    bull_score = sum(a["weight"] for a in bull)
    bear_score = sum(a["weight"] for a in bear)
    total = bull_score + bear_score
    net = (bull_score - bear_score) / total if total > 0 else 0.0

    if net > 0.2:
        verdict, verdict_cn = "bullish", "偏多"
    elif net < -0.2:
        verdict, verdict_cn = "bearish", "偏空"
    else:
        verdict, verdict_cn = "neutral", "中性"

    # 置信度：论据净差 × 模型可信度系数
    model_trust = 0.5
    notes = []
    if prediction:
        bt = prediction.get("backtest") or {}
        edge = bt.get("edge")
        if edge is not None:
            if edge > 0.03:
                model_trust = 0.9
                notes.append(f"模型样本外命中率比基准高 {edge*100:.1f} 个百分点，有真实但微弱的优势")
            elif edge > 0.01:
                model_trust = 0.7
                notes.append("模型样本外仅略好于基准，参考价值有限")
            else:
                model_trust = 0.4
                notes.append("模型样本外没有跑赢基准，结论主要依赖技术面/消息面/基本面证据")
        agree = (prediction["prob_up"] > 0.5) == (verdict == "bullish")
        if verdict != "neutral":
            if agree:
                notes.append("模型方向与多空论据方向一致，相互印证")
            else:
                notes.append("模型方向与论据方向矛盾，置信度已下调")

    confidence = min(0.95, abs(net)) * model_trust
    if prediction and verdict != "neutral":
        if (prediction["prob_up"] > 0.5) != (verdict == "bullish"):
            confidence *= 0.6  # 方向矛盾，再砍一刀

    if confidence >= 0.45:
        conf_label = "较高"
    elif confidence >= 0.25:
        conf_label = "中等"
    else:
        conf_label = "较低"

    return {
        "verdict": verdict,
        "verdict_cn": verdict_cn,
        "confidence": round(confidence, 2),
        "confidence_label": conf_label,
        "bull_score": round(bull_score, 2),
        "bear_score": round(bear_score, 2),
        "notes": notes,
    }


def run_adversarial(tech: dict, news_sig: dict | None, fundamentals: dict | None,
                    prediction: dict | None, risk: dict,
                    mood: dict | None = None) -> dict:
    bull = build_bull_case(tech, news_sig, fundamentals, prediction)
    bear = build_bear_case(tech, news_sig, fundamentals, prediction, risk)

    # 市场情绪（恐惧贪婪指数）：极端读数是逆向信号——
    # 它说的是"整个市场的定价水位"，不针对个股，所以权重温和
    if mood:
        if mood["label"] == "extreme_fear":
            bull.append(_arg("bull", "市场情绪",
                             f"恐惧贪婪指数 {mood['index']}（极度恐惧）：风险溢价被恐慌抬高，"
                             "历史上是布局优质资产的统计性好时点（逆向）", 0.7))
        elif mood["label"] == "extreme_greed":
            bear.append(_arg("bear", "市场情绪",
                             f"恐惧贪婪指数 {mood['index']}（极度贪婪）：人人都已上车，"
                             "此时追高的中期回报统计上显著偏低（逆向）", 0.7))
    verdict = judge(bull, bear, prediction)
    return {"bull_case": bull, "bear_case": bear, "judge": verdict}
