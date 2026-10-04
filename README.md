# SANGYAN — Pre-Payment Fraud Interception System

> **"Check Before You Pay"** — Paise bhejne se pehle check karein

SANGYAN is an open-source, public-good fraud detection system for Indian retail investors. It builds a 4-tier **proof chain** that independently verifies every claim in a suspicious investment message — before money changes hands.

---

## 🧠 What Makes SANGYAN Different

| Typical Scam Detector | SANGYAN |
|---|---|
| Returns "87% scam" | Returns **exact contradictions with sources** |
| Uses ML only | ML is **Tier 4** — never the verdict |
| English only | **Hindi + Hinglish + English** natively |
| Post-payment awareness | **Pre-payment interception** |
| No action guidance | **Specific next steps** for the user |

---

## 🔗 The Proof Chain

```
Claim → Entity → Regulator → Offer → Payment
```

If any link in the chain breaks or contradicts, SANGYAN intervenes **before** money changes hands.

**Output is not just a score. It shows:**
- ✅ What was verified (with source)
- ❓ What could not be verified (with reason)
- ⚡ What contradicts what (specific contradiction)
- 🔴🟡🟢 Final verdict: STOP / PAUSE / TRUST
- 👣 Next safe action for the user

---

## 🏗️ Architecture

```
sangyan/
├── app.py                          ← FastAPI backend (10-step pipeline)
├── requirements.txt
├── pipeline/
│   ├── input_handler.py            ← Step 1: Screenshot/text/URL/handle
│   ├── ocr_engine.py               ← Step 2: Tesseract + Google Vision
│   ├── entity_extractor.py         ← Step 3: SEBI reg, UPI, NER, keywords
│   ├── red_flag_engine.py          ← Tier 3: Deterministic rules
│   ├── ml_engine.py                ← Tier 4: TF-IDF LR + MuRIL
│   ├── proof_chain.py              ← Step 6+7: Build + consistency check
│   ├── trust_calculator.py         ← Step 8: Score + verdict
│   ├── next_best_proof.py          ← Step 9: Actionable next steps
│   └── verification/
│       ├── sebi_checker.py         ← Tier 1a: SEBI registry
│       ├── phishtank_checker.py    ← Tier 2a: PhishTank
│       ├── i4c_checker.py          ← Tier 2b: I4C suspect repository
│       ├── payment_checker.py      ← Tier 1b: UPI verification
│       └── social_checker.py       ← Tier 1d: Social handle check
├── data/
│   ├── authorised_brokers.json     ← 14 SEBI-registered brokers
│   ├── official_handles.json       ← Verified social handles
│   ├── authorised_apps.json        ← SEBI-authorised trading apps
│   └── red_flag_taxonomy.json      ← 7 categories, Hindi + English keywords
├── training/
│   ├── download_datasets.py        ← Download 5 HuggingFace datasets
│   ├── merge_and_clean.py          ← Merge 129k samples, standardise labels
│   ├── train_lr.py                 ← TF-IDF + Logistic Regression (Model A)
│   └── train_muril.py              ← MuRIL fine-tuning (Model B, run on Colab)
├── frontend/
│   ├── index.html                  ← Mobile-first SPA
│   ├── style.css                   ← Premium dark design
│   └── app.js                      ← All frontend logic
└── tests/
    ├── synthetic_test_cases.json   ← 30 hand-written cases
    └── run_test_cases.py           ← Test runner
```

---

## ⚡ Quick Start

### Step 1 — Install dependencies
```bash
cd sangyan
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### Step 2 — Configure environment
```bash
cp .env.example .env
# Edit .env to add your PHISHTANK_API_KEY
```

### Step 3 — Train models (optional — backend works without trained models)
```bash
python training/download_datasets.py
python training/merge_and_clean.py
python training/train_lr.py
# For MuRIL: upload training/train_muril.py to Google Colab (T4 GPU)
```

### Step 4 — Start backend
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Step 5 — Open frontend
```bash
# Option A: Open directly
start frontend/index.html

# Option B: Serve with Python
python -m http.server 3000 --directory frontend
```

### Step 6 — Run tests
```bash
python tests/run_test_cases.py
```

---

## 🔴🟡🟢 Trust Score

| Score | Verdict |
|---|---|
| 70–100 | 🟢 **TRUST ESTABLISHED** |
| 40–69  | 🟡 **PAUSE — More verification required** |
| 0–39   | 🔴 **STOP — Critical contradiction found** |

**Deductions** (selected):
- SEBI registration NOT FOUND: −50 pts
- Known phishing URL: −45 pts
- Remote access requested: −50 pts  
- Guaranteed returns claimed: −25 pts
- Personal UPI, not linked to entity: −30 pts

---

## 📡 API Reference

### `POST /analyze`
```json
{
  "input_type": "text",
  "content": "SEBI registered INH000FAKE1. Guaranteed 25% monthly. Pay profit@ybl"
}
```

Returns full proof chain, evidence table, contradictions, red flags, ML signal, and next steps.

### `GET /health`
```json
{"status": "ok", "models_loaded": {"tfidf_lr": false, "muril": false}}
```

---

## 🛡️ Mandatory Guardrails

1. **Never stores user input** — processed in memory only
2. **Never gives stock tips** — rejects price/buy/sell queries
3. **Never certifies 100% safe** — TRUST verdict always includes caveat
4. **Never labels identifiers as criminals** — only risk signals with disclaimer
5. **Never says PhishTank "not found" means safe** — always adds absence caveat
6. **Rate limited** — 10 requests per IP per minute

---

## 📊 Training Datasets

| Dataset | Samples | Languages |
|---|---|---|
| sidzzz07/scamshield-dataset | 86,000+ | English + Hindi + Hinglish |
| Shade63/scam-classification-multiclass | 14,000 | English (Indian context) |
| anmolshrivastav/scam_ham_india_14_languages | 14,000 | 14 Indian languages |
| DatasetNewUser/Indian_Cyber_Scam_PhoneCall_Hinglish | 10,000 | English/Hindi/Hinglish |
| Ridham115/indian-scam-sms-synthetic-audited | 1,580 | Hinglish + Hindi |
| **Total** | **~129,000** | **Multi-lingual** |

---

## 🎤 Demo Script (for judges)

**Demo Case 1 — STOP:**
> *"SEBI registered advisor INH000FAKE1. Guaranteed 25% monthly returns. Join t.me/stocktips99. Pay ₹5000 to profit@ybl. Today only!"*

Show: OCR → entity extraction → SEBI check FAILS → guaranteed returns violation → UPI unverifiable → 🔴 STOP

**Key lines:**
- *"We don't just say scam — we show you exactly what is broken"*
- *"This intervenes before money changes hands"*  
- *"The ML models are Tier 4 — they support the verdict, they never replace evidence"*
- *"Red = stop, yellow = wait, green = proceed carefully — works without reading English"*

---

## ⚖️ Disclaimer

SANGYAN is a public-good hackathon project. It does not provide legal, financial, or investment advice. All verification is based on publicly available information and may be incomplete. Always independently verify before transferring money.

Report cybercrime: **cybercrime.gov.in | Helpline: 1930**
