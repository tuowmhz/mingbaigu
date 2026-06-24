"""微调 FinBERT2-base → 中文金融情感分类头（2 类：利好/利空）。

数据：FinBERT2 官方 Fin-labeler 的 SC_2（中文财经新闻，1=利好 0=利空）。
产物：./finbert2-zh-sentiment（tokenizer+model），情感微服务按 ZH_MODEL_PATH 加载。

用法：
  python train_finbert2_zh.py                 # 默认 3 epoch，自动用 MPS/CUDA/CPU
  EPOCHS=2 MAX_LEN=256 python train_finbert2_zh.py

诚实说明：SC_2 是正文较长的财经新闻/公告；线上我们打分的是「标题」，
存在长度/风格的轻度域差，但金融褒贬信号可迁移。最终在 test 集报真实 acc / 宏 F1。
"""
import csv
import os

import torch
from torch.utils.data import Dataset
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          DataCollatorWithPadding, Trainer, TrainingArguments)

BASE_MODEL = os.environ.get("BASE_MODEL", "valuesimplex-ai-lab/FinBERT2-base")
OUT_DIR = os.environ.get("OUT_DIR", "./finbert2-zh-sentiment")
DATA_DIR = os.environ.get("DATA_DIR", "./data")
MAX_LEN = int(os.environ.get("MAX_LEN", "256"))
EPOCHS = float(os.environ.get("EPOCHS", "3"))
BATCH = int(os.environ.get("BATCH", "16"))

# SC_2: 1=利好(正面) 0=利空(负面)。命名带「正/负」让推理服务的极性映射能识别。
ID2LABEL = {0: "负面", 1: "正面"}
LABEL2ID = {v: k for k, v in ID2LABEL.items()}


def _device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_csv(path: str) -> tuple[list[str], list[int]]:
    """稳健读取：label 取最后一列且必须 ∈ {0,1}，text 取其余（丢弃换行错切的碎片行）。"""
    texts, labels = [], []
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if len(row) < 2 or row[-1] not in ("0", "1"):
                continue
            text = ",".join(row[:-1]).strip()
            if text:
                texts.append(text)
                labels.append(int(row[-1]))
    return texts, labels


class SentDataset(Dataset):
    def __init__(self, enc, labels):
        self.enc = enc
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, i):
        item = {k: v[i] for k, v in self.enc.items()}
        item["labels"] = self.labels[i]
        return item


def macro_f1(preds, golds) -> float:
    f1s = []
    for c in (0, 1):
        tp = sum(1 for p, g in zip(preds, golds) if p == c and g == c)
        fp = sum(1 for p, g in zip(preds, golds) if p == c and g != c)
        fn = sum(1 for p, g in zip(preds, golds) if p != c and g == c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(f1s) / len(f1s)


def main():
    dev = _device()
    print(f"[device] {dev}  | base={BASE_MODEL}  epochs={EPOCHS} max_len={MAX_LEN}")

    tr_texts, tr_labels = load_csv(os.path.join(DATA_DIR, "train_SC_2.csv"))
    te_texts, te_labels = load_csv(os.path.join(DATA_DIR, "test_SC_2.csv"))
    print(f"[data] train={len(tr_labels)} (利好{sum(tr_labels)}/利空{len(tr_labels)-sum(tr_labels)})"
          f"  test={len(te_labels)}")

    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=2, id2label=ID2LABEL, label2id=LABEL2ID)

    tr_enc = tok(tr_texts, truncation=True, max_length=MAX_LEN)
    te_enc = tok(te_texts, truncation=True, max_length=MAX_LEN)
    tr_ds, te_ds = SentDataset(tr_enc, tr_labels), SentDataset(te_enc, te_labels)

    args = TrainingArguments(
        output_dir=os.path.join(OUT_DIR, "_ckpt"),
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH,
        per_device_eval_batch_size=32,
        learning_rate=2e-5,
        warmup_ratio=0.1,
        weight_decay=0.01,
        logging_steps=50,
        save_strategy="no",
        report_to=[],
        use_mps_device=(dev == "mps"),
    )
    trainer = Trainer(model=model, args=args, train_dataset=tr_ds,
                      data_collator=DataCollatorWithPadding(tok))
    trainer.train()

    pred = trainer.predict(te_ds)
    preds = pred.predictions.argmax(-1).tolist()
    acc = sum(1 for p, g in zip(preds, te_labels) if p == g) / len(te_labels)
    print(f"\n[eval] test acc={acc:.4f}  macro-F1={macro_f1(preds, te_labels):.4f}")

    os.makedirs(OUT_DIR, exist_ok=True)
    model.save_pretrained(OUT_DIR)
    tok.save_pretrained(OUT_DIR)
    print(f"[saved] {OUT_DIR}")


if __name__ == "__main__":
    main()
