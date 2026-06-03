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

# A patch header is now expected to span TWO lines:
#
#     Patch9             ← label only
#     8/8/2025           ← date on the next line
#     -------- (sep) --
#
# Earlier versions used a single-line "Patch9 8/8/2025" form. We support
# both, but the two-line form is what the real DevNotes files use.

# Matches a line containing ONLY a patch label (no other characters except
# leading/trailing whitespace).
PATCH_LABEL_LINE_RE = re.compile(
    r'^([A-Za-z]+\d+(?:\.\d+)?[A-Za-z0-9]*)\s*$'
)
# Matches a line containing ONLY a date.
DATE_LINE_RE = re.compile(
    r'^\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*$'
)
# Backward-compat: a single-line "Label date" form, if any older files use it.
PATCH_HEADER_RE = re.compile(
    r'^([A-Za-z]+\d+(?:\.\d+)?[A-Za-z0-9]*)\s+(\d{1,2}/\d{1,2}/\d{2,4})\s*$'
)


def _find_patch_header_at(lines: list[str], i: int) -> tuple[str, str, int] | None:
    """
    If `lines[i]` is the start of a patch header (either two-line or
    legacy single-line form), return (label, date, header_end_index_exclusive).

    Two-line form: label on line i, date on line i+1.
        header_end = i + 2

    Legacy single-line form: label and date together on line i.
        header_end = i + 1

    Returns None if `lines[i]` is not a patch header.
    """
    line = lines[i].rstrip()

    # Legacy single-line form first (more specific)
    m_single = PATCH_HEADER_RE.match(line)
    if m_single:
        return m_single.group(1), m_single.group(2), i + 1

    # Two-line form
    m_label = PATCH_LABEL_LINE_RE.match(line)
    if not m_label:
        return None
    # The label line must be followed by a date line for it to count as a
    # patch header. Otherwise it's just a label appearing inside body text.
    if i + 1 >= len(lines):
        return None
    m_date = DATE_LINE_RE.match(lines[i + 1].rstrip())
    if not m_date:
        return None
    return m_label.group(1), m_date.group(1), i + 2


def list_patch_labels(devnotes_path: str | Path) -> list[str]:
    """
    Return the labels of all patch blocks in the file, in the order they
    appear (top of file = first / most recent).

    Example: ["Patch3", "Patch2", "Patch1"]
    """
    text = _read(devnotes_path)
    lines = text.splitlines()
    labels: list[str] = []
    i = 0
    while i < len(lines):
        hit = _find_patch_header_at(lines, i)
        if hit:
            label, _date, next_i = hit
            labels.append(label)
            i = next_i
        else:
            i += 1
    return labels


def extract_patch_block(devnotes_path: str | Path, label: str) -> str | None:
    """
    Return the full text of the patch block with the given label, or None
    if not found.

    The returned text includes the patch header line(s), separator, all
    check-in blocks, and the trailing separator. It does NOT include
    leading or trailing blank lines.
    """
    text = _read(devnotes_path)
    lines = text.splitlines()

    start_idx: int | None = None
    end_idx: int | None = None

    i = 0
    while i < len(lines):
        hit = _find_patch_header_at(lines, i)
        if hit:
            hit_label, _date, next_i = hit
            if start_idx is None and hit_label == label:
                start_idx = i
                i = next_i
                continue
            if start_idx is not None:
                # Found the next patch header — our block ends here
                end_idx = i
                break
            i = next_i
        else:
            i += 1

    if start_idx is None:
        return None
    if end_idx is None:
        end_idx = len(lines)

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

    i = 0
    while i < len(lines):
        hit = _find_patch_header_at(lines, i)
        if hit:
            hit_label, _date, next_i = hit
            if start_idx is None and hit_label == label:
                start_idx = i
                i = next_i
                continue
            if start_idx is not None:
                end_idx = i
                break
            i = next_i
        else:
            i += 1

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
