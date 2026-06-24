# 情感微服务 (sentiment_service)

金融特化情感打分,给主站 `news_signal` 调用:

- **英文** → [`ProsusAI/finbert`](https://huggingface.co/ProsusAI/finbert)(开箱即用三分类)
- **中文** → **FinBERT2 微调头**(`valuesimplex-ai-lab/FinBERT2-base` 在官方 SC_2 财经新闻情感数据上微调,2 类:利好/利空)

打分约定:返回 `[-1, 1]` 的期望极性 `Σ Pᵢ·polarityᵢ`(正 +1 / 负 -1 / 中性 0),比离散三分类更细腻,主站直接当 `text_override` 用。**服务挂了主站自动回落 VADER(英文)/ 中文词典,零影响。**

## 接口

```
GET  /health                      → {"ready":true,"device":"cpu","en":"loaded","zh":"loaded"}
POST /sentiment {texts, lang}     → {"scores":[...], "lang":...}   # lang: en|zh|auto
```

## 本地运行

```bash
# 需要 torch + transformers(可复用 ~/Desktop/FinGPT/.venv,或新建 venv 装 requirements.txt)
cd sentiment_service
uvicorn app:app --host 127.0.0.1 --port 8001
```

主站默认连 `http://127.0.0.1:8001`,可用 `SENTIMENT_URL` 覆盖。

## 中文 FinBERT2 情感头:训练

中文路依赖一个本地微调 checkpoint(`finbert2-zh-sentiment/`),不在仓库里,需先训练:

```bash
# 数据已下载在 data/(FinBERT2 官方 Fin-labeler SC_2)
EPOCHS=3 MAX_LEN=256 python train_finbert2_zh.py
# 产物 → ./finbert2-zh-sentiment/,服务按 ZH_MODEL_PATH 自动加载
```

Apple Silicon(MPS)/GPU 约 10-20 分钟;纯 CPU 慢得多。`checkpoint 不存在时,中文 /sentiment 返回 null,主站回落中文词典。`

> 域差说明:SC_2 是正文较长的财经新闻/公告,而线上打分的是「标题」,有轻度长度/风格差;金融褒贬信号可迁移。test 集真实指标见训练输出。

## 部署 (fly.io, 独立 app)

```bash
# 1. 先训练出 finbert2-zh-sentiment/(会打进镜像)
EPOCHS=3 python train_finbert2_zh.py
# 2. 部署情感服务
fly deploy -c fly.toml
# 3. 让主站 stockprediction-tuo 指向它(内网 flycast)
fly secrets set SENTIMENT_URL=http://stockprediction-sentiment.flycast -a stockprediction-tuo
```

**成本**:`min_machines_running = 0` → 没请求时休眠,零流量零计费;首个请求唤醒机器(几秒),期间主站那一次回落词典,之后命中模型。想常驻热机(消除冷启动回落)把它改成 `1`,但会持续计费。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `EN_MODEL_ID` | `ProsusAI/finbert` | 英文情感模型 |
| `ZH_MODEL_PATH` | `/app/finbert2-zh-sentiment` | 中文 FinBERT2 微调头目录 |
| `SENTIMENT_MAX_LEN` | `256` | 推理截断长度 |
| `SENTIMENT_URL`(主站侧) | `http://127.0.0.1:8001` | 主站连接地址 |
