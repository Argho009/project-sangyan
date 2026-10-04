"""
SANGYAN — Dataset Merger & Cleaner
Merges all downloaded datasets into a single clean dataset.
Standardises labels: 1 = scam, 0 = legitimate.
Run: python training/merge_and_clean.py
"""

import os
import re
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
MERGED_PATH = os.path.join(OUT_DIR, "merged_dataset.parquet")
MERGED_CSV_PATH = os.path.join(OUT_DIR, "merged_dataset.csv")


# ---------------------------------------------------------------------------
# Per-dataset loaders
# ---------------------------------------------------------------------------

def load_dataset1_scamshield() -> pd.DataFrame:
    """sidzzz07/scamshield-dataset — English + Hindi + Hinglish"""
    path = os.path.join(RAW_DIR, "dataset1_scamshield")
    frames = []
    for split in ["train", "test", "validation"]:
        fpath = os.path.join(path, f"{split}.parquet")
        if os.path.exists(fpath):
            df = pd.read_parquet(fpath)
            frames.append(df)
    if not frames:
        logger.warning("Dataset 1 not found — skipping")
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)

    # Standardise columns — try common column names
    text_col = _find_col(df, ["text", "message", "content", "sms"])
    label_col = _find_col(df, ["label", "is_scam", "scam", "class"])

    df = df[[text_col, label_col]].rename(columns={text_col: "text", label_col: "label"})
    df["label"] = df["label"].apply(_normalise_label)
    df["source"] = "scamshield"
    return df.dropna(subset=["text", "label"])


def load_dataset2_multiclass() -> pd.DataFrame:
    """Shade63/scam-classification-multiclass — use financial_fraud category"""
    path = os.path.join(RAW_DIR, "dataset2_multiclass")
    frames = []
    for split in ["train", "test"]:
        fpath = os.path.join(path, f"{split}.parquet")
        if os.path.exists(fpath):
            frames.append(pd.read_parquet(fpath))
    if not frames:
        logger.warning("Dataset 2 not found — skipping")
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)

    text_col = _find_col(df, ["text", "message", "content"])
    label_col = _find_col(df, ["category", "label", "class", "type"])

    df = df[[text_col, label_col]].rename(columns={text_col: "text", label_col: "label_raw"})
    # financial_fraud → 1, others → 0 (or keep all non-ham as 1)
    df["label"] = df["label_raw"].apply(
        lambda x: 1 if str(x).lower() in ("financial_fraud", "scam", "fraud", "1") else 0
    )
    df["source"] = "multiclass"
    return df[["text", "label", "source"]].dropna()


def load_dataset3_languages() -> pd.DataFrame:
    """anmolshrivastav/scam_ham_india_14_languages"""
    path = os.path.join(RAW_DIR, "dataset3_14languages")
    frames = []
    for split in ["train", "test"]:
        fpath = os.path.join(path, f"{split}.parquet")
        if os.path.exists(fpath):
            frames.append(pd.read_parquet(fpath))
    if not frames:
        logger.warning("Dataset 3 not found — skipping")
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)

    text_col = _find_col(df, ["text", "message", "sms"])
    label_col = _find_col(df, ["label", "is_scam", "scam"])

    df = df[[text_col, label_col]].rename(columns={text_col: "text", label_col: "label"})
    df["label"] = df["label"].apply(_normalise_label)
    df["source"] = "14languages"
    return df.dropna(subset=["text", "label"])


def load_dataset4_hinglish() -> pd.DataFrame:
    """DatasetNewUser/Indian_Cyber_Scam_PhoneCall_Hinglish_Dataset"""
    path = os.path.join(RAW_DIR, "dataset4_hinglish")
    frames = []
    for split in ["train", "test"]:
        fpath = os.path.join(path, f"{split}.parquet")
        if os.path.exists(fpath):
            frames.append(pd.read_parquet(fpath))
    if not frames:
        logger.warning("Dataset 4 not found — skipping")
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)

    text_col = _find_col(df, ["text", "message", "transcript"])
    label_col = _find_col(df, ["label", "is_scam", "scam", "category"])

    df = df[[text_col, label_col]].rename(columns={text_col: "text", label_col: "label"})
    df["label"] = df["label"].apply(_normalise_label)
    df["source"] = "hinglish"
    return df.dropna(subset=["text", "label"])


def load_dataset5_hard_negatives() -> pd.DataFrame:
    """Ridham115/indian-scam-sms-synthetic-audited"""
    path = os.path.join(RAW_DIR, "dataset5_hard_negatives")
    frames = []
    for split in ["train", "test"]:
        fpath = os.path.join(path, f"{split}.parquet")
        if os.path.exists(fpath):
            frames.append(pd.read_parquet(fpath))
    if not frames:
        logger.warning("Dataset 5 not found — skipping")
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)

    text_col = _find_col(df, ["text", "message", "sms"])
    label_col = _find_col(df, ["label", "is_scam", "scam"])

    df = df[[text_col, label_col]].rename(columns={text_col: "text", label_col: "label"})
    df["label"] = df["label"].apply(_normalise_label)
    df["source"] = "hard_negatives"
    return df.dropna(subset=["text", "label"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_col(df: pd.DataFrame, candidates: list) -> str:
    """Find the first matching column name (case-insensitive)."""
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand in cols_lower:
            return cols_lower[cand]
    # Fallback — return first column
    logger.warning(f"Could not find column from {candidates} in {list(df.columns)}. Using first column.")
    return df.columns[0]


def _normalise_label(value) -> int:
    """Normalise any label representation to 0 or 1."""
    if isinstance(value, int):
        return 1 if value > 0 else 0
    s = str(value).strip().lower()
    if s in ("1", "scam", "spam", "fraud", "financial_fraud", "true", "yes"):
        return 1
    if s in ("0", "ham", "legitimate", "safe", "non-scam", "false", "no"):
        return 0
    return -1   # unknown


def clean_text(text: str) -> str:
    """
    Preprocess text per training instructions:
    - Lowercase
    - Remove special characters except @ . / (needed for UPI/URLs)
    - Do NOT remove Hindi characters
    - Do NOT stem
    """
    if not isinstance(text, str):
        return ""
    text = text.lower().strip()
    # Keep: a-z, 0-9, Hindi Unicode range, space, @, ., /
    text = re.sub(r"[^\w\s@./\u0900-\u097F]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logger.info("Loading and merging datasets...")
    loaders = [
        load_dataset1_scamshield,
        load_dataset2_multiclass,
        load_dataset3_languages,
        load_dataset4_hinglish,
        load_dataset5_hard_negatives,
    ]

    frames = []
    for loader in loaders:
        df = loader()
        if not df.empty:
            frames.append(df[["text", "label", "source"]])
            logger.info(f"  {df['source'].iloc[0]}: {len(df)} rows (scam={df['label'].eq(1).sum()}, legit={df['label'].eq(0).sum()})")

    if not frames:
        logger.error("No datasets loaded! Run download_datasets.py first.")
        return

    merged = pd.concat(frames, ignore_index=True)

    # Remove unknown labels
    merged = merged[merged["label"].isin([0, 1])].copy()

    # Clean text
    logger.info("Cleaning text...")
    merged["text"] = merged["text"].apply(clean_text)

    # Remove empty texts
    merged = merged[merged["text"].str.len() > 5].copy()

    # Deduplicate
    before = len(merged)
    merged = merged.drop_duplicates(subset=["text"]).reset_index(drop=True)
    logger.info(f"Deduplicated: {before} → {len(merged)} rows")

    # Stats
    logger.info(f"\nFinal merged dataset: {len(merged)} rows")
    logger.info(f"  Scam (1): {merged['label'].eq(1).sum()}")
    logger.info(f"  Legitimate (0): {merged['label'].eq(0).sum()}")
    logger.info(f"  Sources: {merged['source'].value_counts().to_dict()}")

    # Save
    merged.to_parquet(MERGED_PATH, index=False)
    merged.to_csv(MERGED_CSV_PATH, index=False)
    logger.info(f"\nSaved: {MERGED_PATH}")
    logger.info("Next step: python training/train_lr.py")


if __name__ == "__main__":
    main()
