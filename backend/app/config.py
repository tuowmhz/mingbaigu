"""全局配置：跟踪列表、银行映射、缓存时长。"""
import os
from pathlib import Path


def _load_env():
    """加载 backend/.env（API key 等本地密钥，已 gitignore）。"""
    p = Path(__file__).resolve().parent.parent / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()

# 默认跟踪的美股列表：六大银行 + 大盘权重股
WATCHLIST = [
    # ticker, 中文名, 类别
    ("JPM", "摩根大通", "bank"),
    ("BAC", "美国银行", "bank"),
    ("WFC", "富国银行", "bank"),
    ("C", "花旗集团", "bank"),
    ("GS", "高盛", "bank"),
    ("MS", "摩根士丹利", "bank"),
    ("AAPL", "苹果", "tech"),
    ("MSFT", "微软", "tech"),
    ("NVDA", "英伟达", "tech"),
    ("GOOGL", "谷歌", "tech"),
    ("AMZN", "亚马逊", "tech"),
    ("META", "Meta", "tech"),
    ("TSLA", "特斯拉", "tech"),
    # A股核心资产（上海 .SS / 深圳 .SZ）
    ("600519.SS", "贵州茅台", "cn"),
    ("300750.SZ", "宁德时代", "cn"),
    ("601318.SS", "中国平安", "cn"),
    ("600036.SS", "招商银行", "cn"),
    ("000858.SZ", "五粮液", "cn"),
    ("002594.SZ", "比亚迪", "cn"),
    ("688981.SS", "中芯国际", "cn"),
    ("000333.SZ", "美的集团", "cn"),
    ("601899.SS", "紫金矿业", "cn"),
    ("600900.SS", "长江电力", "cn"),
]


def market_of(ticker: str) -> str:
    """按代码后缀识别市场：.SS/.SZ 为 A 股，其余按美股处理。"""
    return "CN" if ticker.upper().endswith((".SS", ".SZ")) else "US"


# 各市场的基准与货币符号
BENCHMARK_OF = {"US": ("SPY", "标普500"), "CN": ("000300.SS", "沪深300")}
CURRENCY_OF = {"US": "$", "CN": "¥"}

NAME_MAP = {t: n for t, n, _ in WATCHLIST}
CATEGORY_MAP = {t: c for t, _, c in WATCHLIST}

# FDIC BankFind 数据库中的银行主体编号 (CERT)。
# 上市的是控股公司，FDIC 数据对应其旗下受保银行实体。
# 若编号失效，banks.py 会按名称动态搜索兜底。
BANK_FDIC = {
    "JPM": {"cert": 628, "entity": "JPMorgan Chase Bank, National Association"},
    "BAC": {"cert": 3510, "entity": "Bank of America, National Association"},
    "WFC": {"cert": 3511, "entity": "Wells Fargo Bank, National Association"},
    "C": {"cert": 7213, "entity": "Citibank, National Association"},
    "GS": {"cert": 33124, "entity": "Goldman Sachs Bank USA"},
    "MS": {"cert": 32992, "entity": "Morgan Stanley Bank, National Association"},
}

# 无风险利率（年化），用于夏普比率；可按当下美债收益率调整
RISK_FREE_RATE = 0.045

# 缓存时长（秒）
CACHE_TTL_PRICES = 300      # 行情 5 分钟（前端自动刷新同频）
CACHE_TTL_NEWS = 300        # 新闻 5 分钟
CACHE_TTL_FUNDAMENTALS = 86400  # 基本面 1 天
CACHE_TTL_FDIC = 86400      # FDIC 季报数据 1 天
CACHE_TTL_MODEL = 3600      # 模型预测 1 小时
