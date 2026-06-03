"""
devnotes_parser.py — read existing patch blocks from a DevNotes.txt file.

DevNotes.txt structure:

    Base Version: 1.8.4-SP33-B7-Release

    Patch2 6/2/2026
    --------------------------------------------------------------------------------
    Checkin ID: 0.2626
    ...
    --------------------------------------------------------------------------------
    Checkin ID: 0.2625
    ...
    --------------------------------------------------------------------------------

    Patch1 5/15/2026
    --------------------------------------------------------------------------------
    Checkin ID: 0.2500
    ...

A "patch block" starts with a header line that matches our patch label
pattern (e.g. "Patch2 6/2/2026") and continues until the next patch header
or end of file. Inside, check-ins are separated by 80-dash separator lines.

This module exposes:
    list_patch_labels(devnotes_path)     → list of patch labels in the file
    extract_patch_block(devnotes_path, label) → full text of one patch block
    parse_patch_checkins(patch_text)     → list of check-in IDs in the block
"""

from __future__ import annotations
from pathlib import Path
import re


SEPARATOR = "-" * 80
CHECKIN_ID_RE = re.compile(r'\b\d+\.\d+\b')

# A patch header looks like:    Patch10 6/2/2026
#                              LabPatch3 5/15/2026
#                              HomeMade5.1 4/1/2026
PATCH_HEADER_RE = re.compile(
    r'^([A-Za-z]+\d+(?:\.\d+)?[A-Za-z0-9]*)\s+(\d{1,2}/\d{1,2}/\d{2,4})\s*$'
)


def list_patch_labels(devnotes_path: str | Path) -> list[str]:
    """
    Return the labels of all patch blocks in the file, in the order they
    appear (top of file = first / most recent).

    Example: ["Patch3", "Patch2", "Patch1"]
    """
    text = _read(devnotes_path)
    labels: list[str] = []
    for line in text.splitlines():
        m = PATCH_HEADER_RE.match(line.rstrip())
        if m:
            labels.append(m.group(1))
    return labels


def extract_patch_block(devnotes_path: str | Path, label: str) -> str | None:
    """
    Return the full text of the patch block with the given label, or None
    if not found.

    The returned text includes the patch header line, separator, all
    check-in blocks, and the trailing separator. It does NOT include
    leading or trailing blank lines.
    """
    text = _read(devnotes_path)
    lines = text.splitlines()

    start_idx: int | None = None
    end_idx: int | None = None

    for i, line in enumerate(lines):
        m = PATCH_HEADER_RE.match(line.rstrip())
        if m:
            if start_idx is None and m.group(1) == label:
                start_idx = i
                continue
            # We found the next patch header — that marks the end of our block
            if start_idx is not None:
                end_idx = i
                break

    if start_idx is None:
        return None

    if end_idx is None:
        end_idx = len(lines)

    # Trim trailing blank lines from the slice
    block_lines = lines[start_idx:end_idx]
    while block_lines and not block_lines[-1].strip():
        block_lines.pop()

    return "\n".join(block_lines)


def parse_patch_checkins(patch_text: str) -> list[str]:
    """
    Return the list of check-in IDs that appear inside a patch block, in
    the order they appear.

    Example: ["0.2626", "0.2625", "0.2611"]
    """
    out: list[str] = []
    for line in patch_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Checkin ID:"):
            m = CHECKIN_ID_RE.search(stripped)
            if m:
                out.append(m.group())
    return out


def remove_patch_block(devnotes_path: str | Path, label: str) -> str:
    """
    Return the full DevNotes text with the specified patch block removed.
    Used by the merge flow before re-inserting a rebuilt block.

    If the label isn't found, the original text is returned unchanged.
    """
    text = _read(devnotes_path)
    lines = text.splitlines()

    start_idx: int | None = None
    end_idx: int | None = None

    for i, line in enumerate(lines):
        m = PATCH_HEADER_RE.match(line.rstrip())
        if m:
            if start_idx is None and m.group(1) == label:
                start_idx = i
                continue
            if start_idx is not None:
                end_idx = i
                break

    if start_idx is None:
        return text

    if end_idx is None:
        end_idx = len(lines)

    # Also consume blank lines immediately after the block so we don't leave
    # an extra gap.
    while end_idx < len(lines) and not lines[end_idx].strip():
        end_idx += 1

    new_lines = lines[:start_idx] + lines[end_idx:]
    return "\n".join(new_lines)


def _read(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")
