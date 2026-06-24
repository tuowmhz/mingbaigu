"""股票池：SPY（标普500 ETF）前 100 大权重股（约 2026 年初快照）。

注意：用"今天的成分股"回测历史存在幸存者偏差（被剔除的弱者不在池子里），
结果会系统性偏乐观，应用层已如实披露。GOOG/GOOGL 同一公司只保留 GOOGL。
"""

TOP100 = [
    "NVDA", "MSFT", "AAPL", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "BRK-B",
    "JPM", "LLY", "V", "UNH", "XOM", "MA", "COST", "HD", "PG", "WMT", "NFLX",
    "JNJ", "ABBV", "CRM", "BAC", "ORCL", "CVX", "WFC", "KO", "CSCO", "AMD",
    "ACN", "ADBE", "PEP", "LIN", "MCD", "IBM", "PM", "TMO", "GE", "ISRG",
    "ABT", "GS", "CAT", "INTU", "VZ", "TXN", "QCOM", "BKNG", "SPGI", "MS",
    "RTX", "C", "PLTR", "NEE", "LOW", "DIS", "AMGN", "PFE", "UNP", "T",
    "BLK", "SYK", "TJX", "HON", "BSX", "COP", "VRTX", "ETN", "PANW", "SCHW",
    "AMAT", "ANET", "ADP", "MU", "DE", "GILD", "LMT", "BX", "MDT", "CB",
    "ADI", "MMC", "PLD", "SBUX", "BMY", "INTC", "SO", "UPS", "NOW", "ICE",
    "ELV", "MO", "CME", "DUK", "WM", "AON", "CI", "KLAC", "SHW", "APH",
]

# AI 产业链上"有话语权/卡位"的中盘股——多数不在前100权重，模型此前看不见。
# 上游设备/材料、数据中心水电煤、连接与光、电力瓶颈、EDA。
# 注意：部分为近年上市（ALAB/GEV/CEG/VST/CRDO/ARM 历史短），训练样本有限，
# 但纳入后模型至少"看得见"、可在推理时给出评级。
AI_CHAIN = [
    "ASML", "LRCX", "SNPS", "CDNS", "ARM", "TSM",        # 设备/EDA/IP/代工
    "MPWR", "MRVL", "ENTG", "ALAB", "CRDO",              # 供电/连接/材料芯片
    "VRT", "NVT", "MOD", "FIX",                          # 数据中心 供电/散热/机电
    "COHR", "LITE", "FN",                                # 光通信/光模块
    "GEV", "VST", "CEG", "PWR",                          # AI 电力瓶颈：燃机/核电/电网
]

# 纳指100 其余成分（科技重仓的宽池）。实证：扩到这一层比精挑的小池更诚实、
# 覆盖更广，且不像全 S&P500 那样把"顶档跑赢"信号稀释（非AI股顶档命中仅45%）。
NASDAQ100_EXTRA = [
    "GFS", "ON", "NXPI", "MCHP", "TTD", "APP", "DDOG", "CRWD", "ZS", "TEAM",
    "WDAY", "ADSK", "MDB", "CTSH", "GEHC", "SMCI",          # AI/科技
    "TMUS", "CMCSA", "CHTR", "WBD", "EA", "TTWO", "MELI", "ABNB", "MAR",
    "ORLY", "ROST", "LULU", "MDLZ", "MNST", "KDP", "CCEP", "KHC", "VRTX",
    "REGN", "BIIB", "DXCM", "IDXX", "PAYX", "CTAS", "FAST", "VRSK", "CPRT",
    "ROP", "PCAR", "CSGP", "AEP", "EXC", "XEL", "FANG", "BKR", "PYPL",
    "CDW", "DASH", "ODFL", "AZN",                            # 其余纳指100（增广度）
]

# 训练/评估用全集（去重，保持顺序）——科技重仓宽池
TRAIN_UNIVERSE = list(dict.fromkeys(TOP100 + AI_CHAIN + NASDAQ100_EXTRA))

BENCHMARK = "SPY"
