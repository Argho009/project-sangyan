"""
SANGYAN — Dataset Downloader
Downloads and caches all 6 training datasets from HuggingFace.
Run: python training/download_datasets.py
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")
os.makedirs(DATA_DIR, exist_ok=True)


def download_huggingface_dataset(dataset_id: str, save_name: str, config: str = None):
    """Download a HuggingFace dataset and save as parquet."""
    try:
        from datasets import load_dataset
        logger.info(f"Downloading {dataset_id} ...")
        kwargs = {}
        if config:
            kwargs["name"] = config
        ds = load_dataset(dataset_id, **kwargs, trust_remote_code=True)

        save_path = os.path.join(DATA_DIR, save_name)
        os.makedirs(save_path, exist_ok=True)

        for split_name, split_ds in ds.items():
            out = os.path.join(save_path, f"{split_name}.parquet")
            split_ds.to_parquet(out)
            logger.info(f"  Saved {split_name} → {out} ({len(split_ds)} rows)")

        return True
    except Exception as exc:
        logger.error(f"Failed to download {dataset_id}: {exc}")
        return False


def main():
    datasets = [
        {
            "id": "sidzzz07/scamshield-dataset",
            "name": "dataset1_scamshield",
            "description": "Primary — 86,000+ samples, English + Hindi + Hinglish",
        },
        {
            "id": "Shade63/scam-classification-multiclass",
            "name": "dataset2_multiclass",
            "description": "14,000 samples — Indian context, 5 categories",
        },
        {
            "id": "anmolshrivastav/scam_ham_india_14_languages",
            "name": "dataset3_14languages",
            "description": "14,000 samples — 14 Indian languages",
        },
        {
            "id": "DatasetNewUser/Indian_Cyber_Scam_PhoneCall_Hinglish_Dataset",
            "name": "dataset4_hinglish",
            "description": "10,000 samples — WhatsApp/Telegram focus",
        },
        {
            "id": "Ridham115/indian-scam-sms-synthetic-audited",
            "name": "dataset5_hard_negatives",
            "description": "1,580 samples — hard negatives",
        },
    ]

    success = 0
    for ds_info in datasets:
        logger.info(f"\n{'='*60}")
        logger.info(f"Dataset: {ds_info['description']}")
        if download_huggingface_dataset(ds_info["id"], ds_info["name"]):
            success += 1

    logger.info(f"\n{'='*60}")
    logger.info(f"Downloaded {success}/{len(datasets)} datasets successfully.")
    logger.info(f"Data saved to: {DATA_DIR}")
    logger.info("Next step: python training/merge_and_clean.py")


if __name__ == "__main__":
    main()
