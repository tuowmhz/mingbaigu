"""人话解释模块：把量化指标翻译成人人都看得懂的中文。"""


def synthesize(name: str, ticker: str, fundamentals: dict | None, risk: dict,
               judge: dict, signal: dict | None, prediction: dict | None,
               tech: dict, mood: dict | None = None) -> list[str]:
    """一页看懂：把所有面板的结论合成 5 句左右的人话总评。

    顺序刻意安排成你理解一只股票的自然顺序：
    这是家什么公司 → 生意现状 → 市场定价 → 多空力量 → 你该知道的底线。
    """
    out = []
    f = fundamentals or {}

    # 1. 公司画像
    mcap = f.get("market_cap")
    if mcap:
        if mcap >= 5e11:
            size = f"巨头级公司（市值 ${mcap/1e9:,.0f}B）"
        elif mcap >= 1e10:
            size = f"大盘股（市值 ${mcap/1e9:,.0f}B）"
        else:
            size = f"中小盘股（市值 ${mcap/1e9:.1f}B）——流动性和波动都要多留心"
        sector = f.get("sector")
        out.append(f"【这是谁】{name}（{ticker}），{sector + ' 行业，' if sector else ''}{size}。")

    # 2. 生意现状
    rg, margin = f.get("revenue_growth"), f.get("profit_margin")
    if rg is not None or margin is not None:
        parts = []
        if rg is not None:
            trend = "高速扩张" if rg > 0.25 else ("稳健增长" if rg > 0.05 else ("原地踏步" if rg > -0.03 else "收入在萎缩"))
            parts.append(f"收入同比 {rg*100:+.0f}%（{trend}）")
        if margin is not None:
            quality = "暴利生意" if margin > 0.25 else ("利润率健康" if margin > 0.1 else "薄利生意")
            parts.append(f"净利率 {margin*100:.0f}%（{quality}）")
        out.append(f"【生意如何】{'，'.join(parts)}。")

    # 3. 市场定价
    pe, tgt = f.get("trailing_pe"), f.get("analyst_target")
    pricing = []
    if pe:
        pricing.append(f"市盈率 {pe:.0f} 倍" + ("——市场在为高增长付高价" if pe > 35 else ("——定价中规中矩" if pe > 15 else "——市场给的是怀疑价")))
    if tgt and risk:
        pricing.append(f"华尔街目标价 ${tgt:.0f}")
    if pricing:
        out.append(f"【市场怎么定价】{'；'.join(pricing)}。")

    # 4. 多空力量（来自对抗验证 + 消息面）
    stance = f"对抗验证的裁决是「{judge['verdict_cn']}」（置信度{judge['confidence_label']}）"
    if signal:
        stance += f"，消息面{signal['direction_cn']}"
    if mood and mood["label"] in ("extreme_fear", "extreme_greed"):
        stance += f"；另外整个市场正处于「{mood['label_cn']}」——别忘了水位会影响所有船"
    out.append(f"【多空天平】{stance}。")

    # 5. 底线
    dd = abs(risk.get("max_drawdown", 0))
    vol = risk.get("annual_volatility", 0)
    out.append(
        f"【你该知道的底线】这只股票近两年最深跌过 {dd*100:.0f}%、年化波动 {vol*100:.0f}%。"
        f"任何看多的理由都不改变这两个数字——仓位大小应该由它们决定，而不是由信心决定。"
    )
    return out


def explain_risk(risk: dict, name: str) -> list[str]:
    out = []
    vol = risk["annual_volatility"]
    if vol < 0.20:
        level = "波动温和，属于相对稳健的股票"
    elif vol < 0.35:
        level = "波动中等，短期上下 2-3% 很常见"
    else:
        level = "波动剧烈，单日大涨大跌是家常便饭，心脏不好别重仓"
    out.append(f"【波动】{name}过去一年年化波动率约 {vol*100:.0f}%——{level}。")

    dd = abs(risk["max_drawdown"])
    out.append(
        f"【最大回撤】近两年最惨的时候从高点跌了 {dd*100:.0f}%。"
        f"换句话说：如果你买在最高点，账户最多缩水过 {dd*100:.0f}%，先想清楚自己能不能扛住。"
    )

    var = abs(risk["var_95_daily"])
    out.append(
        f"【单日风险】按过去一年的数据，95% 的交易日里单日亏损不超过 {var*100:.1f}%；"
        f"但每 20 个交易日大约会有 1 天跌得比这更狠。"
    )

    beta = risk.get("beta_vs_spy")
    if beta is not None:
        if beta > 1.2:
            beta_txt = f"大盘涨跌 1%，它平均跟着动 {beta:.1f}%——比大盘更激进"
        elif beta < 0.8:
            beta_txt = f"大盘涨跌 1%，它平均只动 {beta:.1f}%——比大盘更抗跌也更慢热"
        else:
            beta_txt = "基本跟着大盘走"
        out.append(f"【与大盘的关系】Beta 为 {beta:.2f}：{beta_txt}。")

    sharpe = risk["sharpe_ratio"]
    if sharpe > 1:
        s_txt = "过去一年承担的每份风险都换到了不错的回报"
    elif sharpe > 0:
        s_txt = "过去一年有回报，但相对承担的风险来说性价比一般"
    else:
        s_txt = "过去一年承担了风险却没赚到钱，风险收益比为负"
    out.append(f"【性价比】夏普比率 {sharpe:.2f}：{s_txt}。")
    return out


_TIER_CN = {"top": "最看好", "upper": "较看好", "mid": "中性", "lower": "较看淡", "bottom": "最看淡"}


def explain_prediction(prediction: dict | None, judge: dict, name: str) -> list[str]:
    out = []
    if prediction:
        prob = prediction["prob_up"]
        tier_cn = _TIER_CN.get(prediction.get("tier"), "中性")
        excess = prediction["expected_return_pct"]
        out.append(
            f"【模型预判】横截面量化模型把{name}评为「{tier_cn}」档（全池排名前 {prediction.get('rank_pct', 50):.0f}% 由高到低），"
            f"预测未来约半年（{prediction['horizon_days']} 个交易日）相对大盘的超额收益约 {excess:+.1f}%，"
            f"跑赢大盘的概率约 {prob*100:.0f}%。"
        )
        bt = prediction.get("backtest") or {}
        if bt.get("accuracy") is not None:
            ic = bt.get("ic")
            ls = bt.get("long_short_6m_pct")
            out.append(
                f"【模型靠不靠谱】在 {bt['n_oos']} 个从未见过的历史样本上：被模型评为最高档的股票，"
                f"半年后真正跑赢大盘的比例是 {bt['accuracy']*100:.0f}%（纯靠运气约 {bt['baseline']*100:.0f}% 一半一半），"
                f"高出 {bt['edge']*100:+.1f} 个百分点"
                + (f"；信息系数 IC {ic:+.3f}（>0 即有选股力）" if ic is not None else "")
                + (f"；最看好与最看淡两档半年收益差 {ls:+.1f}%" if ls is not None else "") + "。"
            )
            out.append(
                "【诚实提醒】模型的优势在『排序的两端』——对中段个股近乎掷硬币；"
                "且回测股票池为当前大盘权重股，存在幸存者偏差、结果偏乐观。请当参考，不是答案。"
            )
    out.append(
        f"【对抗验证结论】多头论据 {judge['bull_score']:.1f} 分 vs 空头论据 {judge['bear_score']:.1f} 分，"
        f"裁判结论：{judge['verdict_cn']}（置信度{judge['confidence_label']}，{judge['confidence']*100:.0f}%）。"
    )
    out.extend(f"【裁判备注】{n}" for n in judge.get("notes", []))
    return out


def explain_news(analyzed: dict | None, name: str) -> list[str]:
    """把消息面研判翻译成人话：综合信号 + 关键驱动 + 诚实提示。"""
    if not analyzed or not analyzed.get("signal"):
        return ["【消息面】暂时抓不到{}的新闻数据，无法做消息面研判。".format(name)]
    sig = analyzed["signal"]
    out = [
        f"【消息面研判】最近 7 天抓到 {sig['n_items']} 条新闻"
        f"（{sig['positive']} 利好 / {sig['negative']} 利空 / {sig['neutral']} 中性），"
        f"综合信号 {sig['score']:+.1f}，方向：{sig['direction_cn']}。"
    ]
    out.append(f"【大致涨跌】{sig['trend_hint']}。")

    def fmt_drivers(ds):
        parts = []
        for d in ds:
            tag = "、".join(d["events"]) if d["events"] else "情绪面"
            parts.append(f"〔{tag}〕{d['title'][:50]}")
        return "；".join(parts)

    if sig["drivers_positive"]:
        out.append(f"【主要利好】{fmt_drivers(sig['drivers_positive'])}。")
    if sig["drivers_negative"]:
        out.append(f"【主要利空】{fmt_drivers(sig['drivers_negative'])}。")
    out.append(
        "【提示】市场消化新闻的速度以小时计——等你看到新闻时，价格往往已经部分反应。"
        "消息面信号适合做方向参考和风险预警，不适合当交易指令。"
    )
    return out


def explain_fundamentals(f: dict | None, name: str) -> list[str]:
    if not f:
        return []
    out = []
    pe, fpe = f.get("trailing_pe"), f.get("forward_pe")
    if pe:
        cheap = "估值偏贵" if pe > 30 else ("估值适中" if pe > 12 else "估值便宜")
        fwd = f"，按未来盈利预期算是 {fpe:.0f} 倍" if fpe else ""
        out.append(f"【估值】现在买入相当于花 {pe:.0f} 年的利润买下这家公司{fwd}——{cheap}。")
    dy = f.get("dividend_yield")
    if dy and dy > 0:
        # yfinance 的 dividendYield 已是百分数形式（如 2.5 表示 2.5%）
        dy_pct = dy if dy > 0.5 else dy * 100
        out.append(f"【分红】股息率约 {dy_pct:.1f}%，拿着不动每年也有这个比例的现金回报。")
    tgt = f.get("analyst_target")
    if tgt:
        out.append(f"【华尔街观点】分析师平均目标价 ${tgt:.0f}。")
    return out


def explain_bank(bank: dict | None) -> list[str]:
    if not bank or not bank.get("quarters"):
        return []
    q = bank["quarters"][0]
    out = []

    def fmt_usd(thousands):
        """FDIC 单位是千美元，换算成中文友好单位。"""
        if not thousands:
            return "-"
        dollars = thousands * 1e3
        if dollars >= 1e12:
            return f"{dollars/1e12:.2f} 万亿美元"
        return f"{dollars/1e8:,.0f} 亿美元"

    out.append(
        f"【银行体检·FDIC 官方数据】「{bank['entity']}」最新季报（{q['report_date']}）："
        f"总资产 {fmt_usd(q['total_assets_k'])}，存款 {fmt_usd(q['total_deposits_k'])}。"
    )
    if q.get("roe") is not None:
        roe_txt = "赚钱能力强" if q["roe"] > 12 else ("中规中矩" if q["roe"] > 8 else "盈利偏弱")
        out.append(f"【盈利能力】ROE {q['roe']:.1f}%（{roe_txt}），净息差 {q.get('net_interest_margin') or '-'}%。")
    trend = bank.get("trend", {})
    dep = trend.get("deposits_change_pct")
    if dep is not None:
        dep_txt = "存款在增长，根基稳" if dep > 0 else "存款在流失，需要警惕"
        out.append(f"【资金面】近两年存款变化 {dep:+.1f}%——{dep_txt}。")
    return out
