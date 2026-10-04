"""
SANGYAN — Social Handle Verifier (Tier 1d)
Checks claimed Telegram handles and social media accounts against
official verified handles for known brokers.

Output: MATCHES_OFFICIAL | DOES_NOT_MATCH | UNKNOWN_ENTITY
"""

import json
import os
import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


def _load_handles() -> dict:
    base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    path = os.path.join(base, "data", "official_handles.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_HANDLE_DATA = _load_handles()
_OFFICIAL_HANDLES = _HANDLE_DATA.get("official_handles", [])
_FAKE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in _HANDLE_DATA.get("known_fake_patterns", [])
]


@dataclass
class SocialCheckResult:
    handle: str
    platform: str          # telegram | twitter | whatsapp | unknown
    status: str            # MATCHES_OFFICIAL | DOES_NOT_MATCH | UNKNOWN_ENTITY | FAKE_PATTERN
    matched_broker: Optional[str] = None
    official_handle: Optional[str] = None
    detail: str = ""


def _detect_platform(handle: str) -> str:
    h = handle.lower()
    if "t.me" in h or "telegram.me" in h:
        return "telegram"
    if "twitter.com" in h or "x.com" in h:
        return "twitter"
    if "wa.me" in h or "chat.whatsapp.com" in h:
        return "whatsapp"
    return "telegram"  # default for @handles


def _clean_handle(handle: str) -> str:
    """Strip URL prefix and @, lowercase."""
    handle = re.sub(r'https?://(t\.me|telegram\.me|twitter\.com|x\.com)/', '', handle, flags=re.IGNORECASE)
    return handle.lstrip("@").lower().strip()


def check_social_handle(handle: str) -> SocialCheckResult:
    platform = _detect_platform(handle)
    clean = _clean_handle(handle)

    # Check against known fake patterns first
    for pattern in _FAKE_PATTERNS:
        if pattern.search(clean):
            return SocialCheckResult(
                handle=handle,
                platform=platform,
                status="FAKE_PATTERN",
                detail=(
                    f"The handle '{handle}' matches a known fake/fraudulent pattern. "
                    f"Official institutions (SEBI, NSE, BSE) do not operate Telegram tip groups."
                ),
            )

    # Check against official handles
    for broker_entry in _OFFICIAL_HANDLES:
        broker_name = broker_entry["broker"]
        platform_handles = broker_entry.get(platform, [])
        for official in platform_handles:
            if clean == official.lower():
                return SocialCheckResult(
                    handle=handle,
                    platform=platform,
                    status="MATCHES_OFFICIAL",
                    matched_broker=broker_name,
                    official_handle=official,
                    detail=(
                        f"Handle '{handle}' matches the official verified {platform} "
                        f"account of {broker_name}."
                    ),
                )
            # Check for close misspelling (edit distance 1-2)
            if _similar(clean, official.lower()):
                return SocialCheckResult(
                    handle=handle,
                    platform=platform,
                    status="DOES_NOT_MATCH",
                    matched_broker=broker_name,
                    official_handle=official,
                    detail=(
                        f"Handle '{handle}' is SIMILAR but NOT identical to the official "
                        f"{broker_name} {platform} handle '@{official}'. "
                        f"This may be an impersonation attempt."
                    ),
                )

    return SocialCheckResult(
        handle=handle,
        platform=platform,
        status="UNKNOWN_ENTITY",
        detail=(
            f"Handle '{handle}' does not match any known official broker account. "
            f"Verify via the official website of the entity being claimed."
        ),
    )


def _similar(a: str, b: str) -> bool:
    """Simple edit-distance check — returns True if within 2 chars."""
    if abs(len(a) - len(b)) > 2:
        return False
    if a == b:
        return False
    # Count character differences
    diffs = sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))
    return 1 <= diffs <= 2
