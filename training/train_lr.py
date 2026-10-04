"""
SANGYAN — TF-IDF + Logistic Regression Trainer (Model A)
Run: python training/train_lr.py
Expected accuracy: 89-93%
"""

import os
import logging
import joblib
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, f1_score
from imblearn.over_sampling import SMOTE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "merged_dataset.parquet")
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
os.makedirs(MODEL_DIR, exist_ok=True)

VECTORIZER_PATH = os.path.join(MODEL_DIR, "tfidf_vectorizer.pkl")
LR_MODEL_PATH = os.path.join(MODEL_DIR, "lr_model.pkl")


def main():
    # ---- Load data ----
    logger.info(f"Loading dataset from {DATA_PATH}")
    if not os.path.exists(DATA_PATH):
        logger.error("Merged dataset not found! Run merge_and_clean.py first.")
        return

    df = pd.read_parquet(DATA_PATH)
    logger.info(f"Loaded {len(df)} samples | Scam: {df['label'].eq(1).sum()} | Legit: {df['label'].eq(0).sum()}")

    X = df["text"].fillna("").tolist()
    y = df["label"].tolist()

    # ---- Train/test split ----
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y
    )
    logger.info(f"Train: {len(X_train)} | Test: {len(X_test)}")

    # ---- Vectorize ----
    logger.info("Fitting TF-IDF vectorizer (max_features=50000, ngram_range=(1,3))...")
    vectorizer = TfidfVectorizer(
        max_features=50000,
        ngram_range=(1, 3),
        min_df=2,
        analyzer="word",
        sublinear_tf=True,
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)
    logger.info(f"Vocabulary size: {len(vectorizer.vocabulary_)}")

    # ---- SMOTE for class imbalance ----
    logger.info("Applying SMOTE to balance classes...")
    smote = SMOTE(random_state=42)
    X_balanced, y_balanced = smote.fit_resample(X_train_vec, y_train)
    logger.info(f"After SMOTE: {X_balanced.shape[0]} samples")

    # ---- Train Logistic Regression ----
    logger.info("Training Logistic Regression...")
    model = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        C=1.0,
        solver="lbfgs",
    )
    model.fit(X_balanced, y_balanced)

    # ---- Evaluate ----
    y_pred = model.predict(X_test_vec)
    f1 = f1_score(y_test, y_pred)
    logger.info(f"\nTest F1: {f1:.4f}")
    logger.info("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Legitimate", "Scam"]))

    # ---- Demonstrate explanation function ----
    logger.info("\n--- Top scam words for a sample ---")
    sample = "guaranteed 25% monthly return, deposit now to UPI, SEBI approved"
    sample_vec = vectorizer.transform([sample])
    feature_names = vectorizer.get_feature_names_out()
    feature_scores = sample_vec.toarray()[0] * model.coef_[0]
    top_idx = feature_scores.argsort()[-5:][::-1]
    top_words = [(feature_names[i], round(float(feature_scores[i]), 4)) for i in top_idx if feature_scores[i] > 0]
    logger.info(f"Top scam words: {top_words}")

    # ---- Save models ----
    joblib.dump(vectorizer, VECTORIZER_PATH)
    joblib.dump(model, LR_MODEL_PATH)
    logger.info(f"\nSaved vectorizer → {VECTORIZER_PATH}")
    logger.info(f"Saved LR model  → {LR_MODEL_PATH}")
    logger.info("Model A training complete!")
    logger.info("Next step: Run train_muril.py on Google Colab (T4 GPU)")


if __name__ == "__main__":
    main()
