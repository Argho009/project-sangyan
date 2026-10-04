"""
SANGYAN — MuRIL Fine-Tuning Script (Model B)
Fine-tunes google/muril-base-cased on the merged scam dataset.

IMPORTANT: Run this on Google Colab with T4 GPU for best results.
Expected training time: 45-60 minutes.
Expected accuracy: 93-96%.

Usage on Colab:
    !pip install transformers datasets accelerate
    !python training/train_muril.py
"""

import os
import logging
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, precision_score, recall_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "merged_dataset.parquet")
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
OUTPUT_DIR = os.path.join(MODEL_DIR, "muril-scam-detector")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MURIL_BASE = "google/muril-base-cased"
MAX_LENGTH = 128
BATCH_TRAIN = 16
BATCH_EVAL = 32
EPOCHS = 3
WARMUP_STEPS = 500
WEIGHT_DECAY = 0.01


def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = predictions.argmax(axis=1)
    return {
        "f1": f1_score(labels, predictions),
        "precision": precision_score(labels, predictions),
        "recall": recall_score(labels, predictions),
    }


def main():
    try:
        from transformers import (
            AutoTokenizer,
            AutoModelForSequenceClassification,
            TrainingArguments,
            Trainer,
        )
        from datasets import Dataset
    except ImportError:
        logger.error("transformers/datasets not installed. Run: pip install transformers datasets")
        return

    # ---- Load data ----
    logger.info(f"Loading dataset from {DATA_PATH}")
    if not os.path.exists(DATA_PATH):
        logger.error("Merged dataset not found! Run merge_and_clean.py first.")
        return

    df = pd.read_parquet(DATA_PATH)
    logger.info(f"Total samples: {len(df)}")

    # Subsample if very large (MuRIL training on free Colab T4 — limit 80k)
    if len(df) > 80000:
        df = df.sample(80000, random_state=42).reset_index(drop=True)
        logger.info("Subsampled to 80,000 for Colab T4 training budget")

    X = df["text"].fillna("").tolist()
    y = df["label"].tolist()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y
    )

    # ---- Build HuggingFace Dataset ----
    train_ds = Dataset.from_dict({"text": X_train, "label": y_train})
    test_ds = Dataset.from_dict({"text": X_test, "label": y_test})

    # ---- Load tokenizer & model ----
    logger.info(f"Loading MuRIL tokenizer: {MURIL_BASE}")
    tokenizer = AutoTokenizer.from_pretrained(MURIL_BASE)

    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            padding="max_length",
            truncation=True,
            max_length=MAX_LENGTH,
        )

    logger.info("Tokenizing datasets...")
    tokenized_train = train_ds.map(tokenize_function, batched=True)
    tokenized_test = test_ds.map(tokenize_function, batched=True)

    # ---- Load model ----
    logger.info(f"Loading MuRIL model with 2-class head...")
    model = AutoModelForSequenceClassification.from_pretrained(
        MURIL_BASE,
        num_labels=2,
    )

    # ---- Training arguments ----
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_TRAIN,
        per_device_eval_batch_size=BATCH_EVAL,
        warmup_steps=WARMUP_STEPS,
        weight_decay=WEIGHT_DECAY,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        fp16=True,                   # GPU only
        logging_dir=os.path.join(OUTPUT_DIR, "logs"),
        logging_steps=100,
        report_to="none",            # disable wandb
    )

    # ---- Trainer ----
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train,
        eval_dataset=tokenized_test,
        compute_metrics=compute_metrics,
    )

    logger.info("Starting MuRIL training...")
    trainer.train()

    # ---- Save ----
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    logger.info(f"\nMuRIL model saved → {OUTPUT_DIR}")

    # ---- Final eval ----
    results = trainer.evaluate()
    logger.info(f"Final evaluation: {results}")
    logger.info("Model B training complete!")


if __name__ == "__main__":
    main()
