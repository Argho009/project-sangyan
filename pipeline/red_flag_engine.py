"""
SANGYAN — Red Flag Engine (Tier 3 Deterministic Rules)
Applies all keyword taxonomy rules and URL pattern checks.
Returns scored red flags with category, trigger phrase, and weight.
"""

import re
import json
import os
import logging
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load taxonomy
# ---------------------------------------------------------------------------

def _load_taxonomy() -> list:
    base = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(base, "data", "red_flag_taxonomy.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("categories", [])
    except Exception:
        return []


TAXONOMY = _load_taxonomy()

# URL shorteners and free hosting patterns
URL_SHORTENERS = set()
FREE_HOSTING = []
for cat in TAXONOMY:
    if cat["id"] == "suspicious_url":
        URL_SHORTENERS = set(cat.get("url_shorteners", []))
        FREE_HOSTING = cat.get("free_hosting_patterns", [])
        break

# Known broker domain fragments for misspelling check
BROKER_DOMAINS = [
    "zerodha", "groww", "upstox", "angelone", "icici",
    "hdfc", "kotak", "sharekhan", "sbismart", "fyers",
    "5paisa", "motilal", "dhan", "axis",
]

IP_URL_RE = re.compile(r'https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RedFlag:
    category: str
    category_label: str
    trigger: str
    points: int
    severity: str
    regulatory_note: str = ""


@dataclass
class RedFlagReport:
    flags: List[RedFlag] = field(default_factory=list)
    total_score_deduction: int = 0
    url_anomalies: List[str] = field(default_factory=list)

    def add(self, flag: RedFlag):
        self.flags.append(flag)
        self.total_score_deduction += flag.points

    def has_critical(self) -> bool:
        return any(f.severity == "CRITICAL" for f in self.flags)


# ---------------------------------------------------------------------------
# URL analysis helpers
# ---------------------------------------------------------------------------

def analyse_url(url: str) -> List[str]:
    """Return list of URL anomaly strings found."""
    anomalies = []
    try:
        parsed = urlparse(url if url.startswith("http") else "http://" + url)
        netloc = parsed.netloc.lower()
        scheme = parsed.scheme.lower()

        # IP address instead of domain
        if IP_URL_RE.match(url):
            anomalies.append("URL uses an IP address instead of a domain name")

        # HTTP not HTTPS
        if scheme == "http":
            anomalies.append("URL uses HTTP (unencrypted) instead of HTTPS")

        # URL shortener
        for shortener in URL_SHORTENERS:
            if shortener in netloc:
                anomalies.append(f"URL shortener detected ({shortener}) — actual destination is hidden")
                break

        # Free hosting
        for host in FREE_HOSTING:
            if host in netloc:
                anomalies.append(f"Free hosting domain used ({host}) — not appropriate for financial services")
                break

        # Domain misspelling check
        for broker in BROKER_DOMAINS:
            if broker in netloc:
                # Check for exact match (would be ok)
                # Misspelling: broker name present but with slight variation
                if not _is_official_domain(netloc, broker):
                    anomalies.append(
                        f"Domain '{netloc}' contains '{broker}' but may be a misspelling or clone site"
                    )
                break

    except Exception as exc:
        logger.debug(f"URL analyse error: {exc}")
    return anomalies


def _is_official_domain(netloc: str, broker: str) -> bool:
    """Very basic check — official domains are short e.g. 'zerodha.com'."""
    official_map = {
        "zerodha": "zerodha.com",
        "groww": "groww.in",
        "upstox": "upstox.com",
        "angelone": "angelone.in",
        "icici": "icicidirect.com",
        "hdfc": "hdfcsec.com",
        "kotak": "kotaksecurities.com",
        "sharekhan": "sharekhan.com",
        "sbismart": "sbismart.com",
        "fyers": "fyers.in",
        "5paisa": "5paisa.com",
        "motilal": "motilaloswal.com",
        "dhan": "dhan.co",
        "axis": "axisdirect.in",
    }
    return netloc == official_map.get(broker, "")


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

def run_red_flag_engine(text: str, urls: Optional[List[str]] = None) -> RedFlagReport:
    """
    Run all Tier 3 deterministic rules.
    text: raw message text
    urls: list of URLs extracted from text
    Returns: RedFlagReport
    """
    report = RedFlagReport()
    text_lower = text.lower()

    # --- Keyword rules ---
    for cat in TAXONOMY:
        if cat["id"] == "suspicious_url":
            continue  # handled separately

        keywords = cat.get("keywords", [])
        weight = cat.get("weight", 10)
        severity = cat.get("severity", "MEDIUM")
        label = cat.get("label", cat["id"])
        reg_note = cat.get("regulatory_note", "")

        for kw in keywords:
            if kw.lower() in text_lower:
                report.add(RedFlag(
                    category=cat["id"],
                    category_label=label,
                    trigger=kw,
                    points=weight,
                    severity=severity,
                    regulatory_note=reg_note,
                ))
                break  # one hit per category is sufficient to flag

    # --- URL anomaly rules ---
    for url in (urls or []):
        anomalies = analyse_url(url)
        for anomaly in anomalies:
            report.url_anomalies.append(f"{url}: {anomaly}")
            report.add(RedFlag(
                category="suspicious_url",
                category_label="Suspicious URL Pattern",
                trigger=f"{url} — {anomaly}",
                points=20,
                severity="MEDIUM-HIGH",
                regulatory_note=(
                    "Fraudulent websites often mimic legitimate broker domains. "
                    "Always manually type the official URL."
                ),
            ))

    return report
