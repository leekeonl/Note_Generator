"""
Branch detector — extracts the upstream branch token from a DevNotes file.

The first line of a DevNotes file looks like:

    Base Version: 1.8.4-SP37-HF4E-Release

This module extracts the branch token ("SP37") so the Auto-Generate page
knows which real git branch to page in Bitbucket (commits/<branch>).

ETCH variant
------------
Some base versions carry an etch hotfix marker, e.g.:

    Base Version: 1.8.4-SP37-HF4E-Release
                          ^^^^  ^^^^
                          SP37  HF4E  (the trailing "E" == ETCH)

Those check-ins do NOT live on the plain "SP37" branch. They live on a
dedicated "SP37ETCH" branch in the Bitbucket mirror. So when the etch
marker is present we remap the SP token:  SP37  ->  SP37ETCH.

Plain (non-etch) base versions keep their existing behaviour untouched.
"""

from __future__ import annotations
from pathlib import Path
import re


# General branch token: SP followed by digits, optionally with a trailing
# letter+digit chunk (handles SP35, SP18SM, etc.). First match wins.
BRANCH_TOKEN_RE = re.compile(r'\b([A-Z]{2,}\d+(?:[A-Z]+\d*)?)\b')

# The Base Version line itself.
BASE_VERSION_LINE_RE = re.compile(r'^\s*Base\s+Version\s*:\s*(.+?)\s*$', re.IGNORECASE)

# ETCH marker inside a base version. Two accepted spellings:
#   - a hotfix token ending in E:  HF4E, HF14E, HF10E
#   - the literal word ETCH
ETCH_MARKER_RE = re.compile(r'\bHF\d+E\b|\bETCH\b', re.IGNORECASE)

# The bare "SP<number>" prefix we append ETCH to.
SP_NUMBER_RE = re.compile(r'(SP\d+)', re.IGNORECASE)


def extract_branch_from_devnotes(devnotes_path: str | Path) -> str | None:
    """
    Read the DevNotes file and return the detected branch token, or None
    if no Base Version line is present (or no token could be extracted).

    Example:
        "Base Version: 1.8.4-SP35-B7-Release"    ->  "SP35"
        "Base Version: 1.8.4-SP37-HF4E-Release"  ->  "SP37ETCH"
    """
    path = Path(devnotes_path)
    try:
        # Base Version is always at the top; only scan the first few lines.
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

    Returns None if the text isn't a Base Version line, or if no token of
    the expected form is present.

    ETCH handling: when the base version carries an etch marker (e.g. the
    "HF4E" in "1.8.4-SP37-HF4E-Release"), the plain SP token is remapped to
    its dedicated etch branch ("SP37" -> "SP37ETCH").
    """
    match = BASE_VERSION_LINE_RE.match(text)
    if not match:
        return None
    version_string = match.group(1)

    token_match = BRANCH_TOKEN_RE.search(version_string)
    if not token_match:
        return None
    token = token_match.group(1)

    # Remap to the etch branch when the etch marker is present.
    if ETCH_MARKER_RE.search(version_string):
        sp_match = SP_NUMBER_RE.match(token)
        if sp_match:
            return f"{sp_match.group(1).upper()}ETCH"

    return token
