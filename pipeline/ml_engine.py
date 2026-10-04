"""
SANGYAN — ML Engine (Tier 4)
Runs TF-IDF + Logistic Regression (Model A) and
MuRIL fine-tuned classifier (Model B) in parallel.

ML score is a SUPPORTING SIGNAL only — never the verdict basis.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
LR_MODEL_PATH = os.path.join(MODEL_DIR, "lr_model.pkl")
VECTORIZER_PATH = os.path.join(MODEL_DIR, "tfidf_vectorizer.pkl")
MURIL_MODEL_PATH = os.path.join(MODEL_DIR, "muril-scam-detector")

NOTE = "Supporting signal only — ML models assist but do not determine the verdict."


# ---------------------------------------------------------------------------
# Lazy-loaded model singletons
# ---------------------------------------------------------------------------

_lr_model = None
_vectorizer = None
_muril_tokenizer = None
_muril_model = None


def _load_lr() -> Tuple[object, object]:
    global _lr_model, _vectorizer
    if _lr_model is None:
        try:
            import joblib
            _vectorizer = joblib.load(VECTORIZER_PATH)
            _lr_model = joblib.load(LR_MODEL_PATH)
        except Exception as exc:
            logger.warning(f"LR model not found/loadable: {exc}. Using dummy.")
            _lr_model = False
            _vectorizer = False
    return _lr_model, _vectorizer


def _load_muril():
    global _muril_tokenizer, _muril_model
    if _muril_tokenizer is None:
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch
            _muril_tokenizer = AutoTokenizer.from_pretrained(MURIL_MODEL_PATH)
            _muril_model = AutoModelForSequenceClassification.from_pretrained(MURIL_MODEL_PATH)
            _muril_model.eval()
        except Exception as exc:
            logger.warning(f"MuRIL model not found/loadable: {exc}. Using dummy.")
            _muril_tokenizer = False
            _muril_model = False
    return _muril_tokenizer, _muril_model


# ---------------------------------------------------------------------------
# Inference functions
# ---------------------------------------------------------------------------

def _run_lr(text: str) -> Tuple[float, List[str]]:
    """Run TF-IDF + LR model. Returns (score, top_words)."""
    lr_model, vectorizer = _load_lr()
    if not lr_model or not vectorizer:
        return 0.5, []  # neutral when unavailable

    try:
        import numpy as np
        vec = vectorizer.transform([text])
        score = float(lr_model.predict_proba(vec)[0][1])  # class 1 = scam

        # Extract top scam-triggering words
        feature_names = vectorizer.get_feature_names_out()
        feature_scores = vec.toarray()[0] * lr_model.coef_[0]
        top_idx = feature_scores.argsort()[-5:][::-1]
        top_words = [
            feature_names[i]
            for i in top_idx
            if feature_scores[i] > 0
        ]
        return score, top_words

    except Exception as exc:
        logger.error(f"LR inference error: {exc}")
        return 0.5, []


def _run_muril(text: str) -> float:
    """Run MuRIL fine-tuned classifier. Returns scam probability."""
    tokenizer, model = _load_muril()
    if not tokenizer or not model:
        return 0.5  # neutral when unavailable

    try:
        import torch
        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=128,
            padding="max_length",
        )
        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.softmax(outputs.logits, dim=1)
            scam_prob = float(probs[0][1])
        return scam_prob
    except Exception as exc:
        logger.error(f"MuRIL inference error: {exc}")
        return 0.5


# ---------------------------------------------------------------------------
# Public result dataclass
# ---------------------------------------------------------------------------

@dataclass
class MLResult:
    lr_score: float
    muril_score: float
    combined_score: float
    top_words: List[str] = field(default_factory=list)
    lr_available: bool = True
    muril_available: bool = True
    note: str = NOTE


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def run_ml_analysis(text: str) -> MLResult:
    """
    Run both models on the input text.
    Returns MLResult with individual and combined scores.
    """
    lr_score, top_words = _run_lr(text)
    muril_score = _run_muril(text)

    lr_avail = lr_score != 0.5 or bool(top_words)
    muril_avail = muril_score != 0.5

    combined = (lr_score + muril_score) / 2

    return MLResult(
        lr_score=round(lr_score, 4),
        muril_score=round(muril_score, 4),
        combined_score=round(combined, 4),
        top_words=top_words,
        lr_available=lr_avail,
        muril_available=muril_avail,
        note=NOTE,
    )
