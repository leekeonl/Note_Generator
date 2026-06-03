"""
Branch detector — extracts the upstream branch token from a DevNotes file.

The first line of a DevNotes file looks like:

    Base Version: 1.8.4-SP33-B7-Release

This module extracts the branch token ("SP33") so the auto-generate page
knows which branch to query first in Phabricator (with Development as the
ultimate fallback).
"""

from __future__ import annotations
from pathlib import Path
import re


# Match common branch token patterns inside a Base Version string. The
# pattern accepts SP followed by digits (SP33, SP35), or other letter+digit
# combinations that match typical release branch naming.
BRANCH_TOKEN_RE = re.compile(r'\b([A-Z]{2,}\d+(?:[A-Z]+\d*)?)\b')

# The base version line itself
BASE_VERSION_LINE_RE = re.compile(r'^\s*Base\s+Version\s*:\s*(.+?)\s*$', re.IGNORECASE)


def extract_branch_from_devnotes(devnotes_path: str | Path) -> str | None:
    """
    Read the DevNotes file and return the detected branch token, or None
    if no Base Version line is present (or no token could be extracted).

    Example:
        "Base Version: 1.8.4-SP33-B7-Release"  →  "SP33"
        "Base Version: 1.8.4-SP35-HF14"        →  "SP35"  (first match wins)
    """
    path = Path(devnotes_path)
    try:
        # Only need to scan the first few lines — Base Version is always on top
        with path.open(encoding="utf-8", errors="ignore") as f:
            for _ in range(5):
                line = f.readline()
                if not line:
                    break
                token = extract_branch_from_text(line)
                if token:
                    return token
    except (FileNotFoundError, OSError):
        return None
    return None


def extract_branch_from_text(text: str) -> str | None:
    """
    Extract a branch token from a single line of text (or any short string).

    Returns None if the text doesn't look like a Base Version line, or if
    no token of the expected form is present.
    """
    match = BASE_VERSION_LINE_RE.match(text)
    if not match:
        return None
    version_string = match.group(1)
    token_match = BRANCH_TOKEN_RE.search(version_string)
    return token_match.group(1) if token_match else None
