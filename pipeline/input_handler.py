"""
SANGYAN — Input Handler (Step 1)
Accepts: image upload (base64), text paste, URL, social handle.
Detects input type automatically.
"""

import base64
import re
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class InputType(str, Enum):
    SCREENSHOT = "screenshot"
    TEXT = "text"
    URL = "url"
    HANDLE = "handle"


class SangyanInput(BaseModel):
    input_type: InputType
    content: str  # base64 for image, raw text, URL, or @handle


class ProcessedInput(BaseModel):
    input_type: InputType
    raw_text: str                  # text extracted or provided
    image_bytes: Optional[bytes] = None
    url: Optional[str] = None
    handle: Optional[str] = None
    original_content: str = ""


URL_PATTERN = re.compile(
    r'^https?://'
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
    r'localhost|'
    r'\d{1,3}(?:\.\d{1,3}){3})'
    r'(?::\d+)?'
    r'(?:/?|[/?]\S+)$',
    re.IGNORECASE
)

HANDLE_PATTERN = re.compile(r'^@?[\w.]+$')
TGME_PATTERN = re.compile(r'^(https?://)?(t\.me|telegram\.me)/\S+', re.IGNORECASE)


def detect_input_type(content: str) -> InputType:
    """Auto-detect input type from content string."""
    stripped = content.strip()

    # Check if it's a base64-encoded image
    try:
        # Remove data URI prefix if present
        b64 = stripped.split(",", 1)[-1] if "," in stripped else stripped
        decoded = base64.b64decode(b64, validate=True)
        # Quick magic byte check for JPEG/PNG/WEBP/GIF
        if (decoded[:2] == b'\xff\xd8' or       # JPEG
                decoded[:4] in (b'\x89PNG', b'GIF8', b'RIFF') or  # PNG/GIF/WEBP
                decoded[:4] == b'\x89PNG'):
            return InputType.SCREENSHOT
    except Exception:
        pass

    # Check for Telegram URL
    if TGME_PATTERN.match(stripped):
        return InputType.URL

    # Check for URL
    if URL_PATTERN.match(stripped):
        return InputType.URL

    # Check for social handle (short, no spaces, starts with @ or looks like one)
    if len(stripped) < 50 and " " not in stripped and (
            stripped.startswith("@") or HANDLE_PATTERN.match(stripped)
    ):
        return InputType.HANDLE

    # Default to text
    return InputType.TEXT


def process_input(raw_input: SangyanInput) -> ProcessedInput:
    """
    Convert a SangyanInput into a ProcessedInput suitable for the pipeline.
    For images, image_bytes is set so the OCR engine can consume it.
    For text/URL/handle, raw_text is set directly.
    """
    content = raw_input.content.strip()

    if raw_input.input_type == InputType.SCREENSHOT:
        # Decode base64 image
        b64 = content.split(",", 1)[-1] if "," in content else content
        image_bytes = base64.b64decode(b64)
        return ProcessedInput(
            input_type=InputType.SCREENSHOT,
            raw_text="",          # to be filled by OCR engine
            image_bytes=image_bytes,
            original_content=content,
        )

    elif raw_input.input_type == InputType.URL:
        return ProcessedInput(
            input_type=InputType.URL,
            raw_text=content,
            url=content,
            original_content=content,
        )

    elif raw_input.input_type == InputType.HANDLE:
        handle = content if content.startswith("@") else f"@{content}"
        return ProcessedInput(
            input_type=InputType.HANDLE,
            raw_text=content,
            handle=handle,
            original_content=content,
        )

    else:  # TEXT
        return ProcessedInput(
            input_type=InputType.TEXT,
            raw_text=content,
            original_content=content,
        )
