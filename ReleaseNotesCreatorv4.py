"""
ReleaseNotesCreatorv3.py

Reads DevNotes.txt and generates ReleaseNotes.txt with:

  1) Copies ONLY the first "Base Version: ..." line to the TOP of ReleaseNotes.txt.
  2) Preserves patch headers and dates (e.g., LabPatch3, 5/11/2026).
  3) Preserves the exact separator line(s) made of hyphens (e.g., "--------------------------------------------------------------------------------")
     in the SAME places they appear in the patch block.
  4) For each check-in block, keeps ONLY:
        [Issue Description]
        [Feature Description]
     while always keeping:
        Checkin ID:
        PR Number(s):
        Comments:

This matches the formatting style seen in your DevNotes/ReleaseNotes examples.
"""

import re
from pathlib import Path
from typing import List, Optional

# --- Regex patterns ---
BASE_VERSION_RE = re.compile(r'^\s*Base Version:\s*.+\s*$', re.IGNORECASE)
# Patch header: one or more letters followed by a number (integer or decimal),
# optionally with extra alphanumeric suffix. Matches Patch12, LabPatch3,
# HomeMade5, Patch5.1, LabPatch3.2, etc.
PATCH_RE = re.compile(r'^\s*[A-Za-z]+\d+(?:\.\d+)?\w*\s*$')
DATE_RE = re.compile(r'^\s*\d{1,2}/\d{1,2}/\d{4}\s*$')                  # 5/11/2026
SEP_RE = re.compile(r'^\s*-{5,}\s*$')                                  # "-----" or longer

CHECKIN_RE = re.compile(r'^\s*Checkin ID:\s*.*$', re.IGNORECASE)
PR_RE = re.compile(r'^\s*PR Number\(s\):\s*.*$', re.IGNORECASE)
COMMENTS_RE = re.compile(r'^\s*Comments:\s*$', re.IGNORECASE)

SECTION_RE = re.compile(r'^\s*\[(.+?)\]\s*$')  # [Issue Description], [Solution], etc.

KEEP_SECTIONS = {"Issue Description", "Feature Description"}


def extract_base_version_line(lines_no_nl: List[str]) -> Optional[str]:
    """Return the first exact 'Base Version: ...' line (without trailing newline) or None."""
    for line in lines_no_nl:
        if BASE_VERSION_RE.match(line):
            return line
    return None


def is_patch_header(line: str) -> bool:
    return bool(PATCH_RE.match(line.strip()))


def collect_patch_block(lines_no_nl: List[str], start_idx: int) -> (List[str], int):
    """
    Collect a patch block starting at start_idx (which is a patch header line).
    Stops when the next patch header is found or EOF.
    Returns (patch_block_lines, next_index).
    """
    block = []
    i = start_idx
    n = len(lines_no_nl)
    while i < n:
        if i != start_idx and is_patch_header(lines_no_nl[i]):
            break
        block.append(lines_no_nl[i])
        i += 1
    return block, i


def process_checkin_block(checkin_lines: List[str]) -> List[str]:
    """
    Given lines belonging to a single check-in (starting with 'Checkin ID:'),
    return output lines that keep:
      - Checkin ID / PR Number(s) / Comments:
      - only [Issue Description] and [Feature Description] sections and their body lines
    """
    out = []

    # 1) Always keep these header lines if present (in original order)
    #    We'll scan from top until we hit the first [Section] header.
    i = 0
    n = len(checkin_lines)
    while i < n:
        line = checkin_lines[i]
        if SECTION_RE.match(line):
            break
        # preserve separator lines too if any appear inside (rare, but safe)
        if CHECKIN_RE.match(line) or PR_RE.match(line) or COMMENTS_RE.match(line) or SEP_RE.match(line):
            out.append(line)
        i += 1

    # 2) Now parse sections; output only kept ones
    current_section = None
    buffer = []  # collect body lines for current_section

    def flush_section():
        nonlocal current_section, buffer, out
        if current_section in KEEP_SECTIONS:
            out.append(f"[{current_section}]")
            out.extend(buffer)
        # reset
        current_section = None
        buffer = []

    while i < n:
        line = checkin_lines[i]

        # If we hit a separator line, treat it as boundary: flush any section and output separator.
        if SEP_RE.match(line):
            flush_section()
            out.append(line)
            i += 1
            continue

        m = SECTION_RE.match(line)
        if m:
            # new section starts: flush previous
            flush_section()
            current_section = m.group(1).strip()
            buffer = []
            i += 1
            continue

        # regular body line
        if current_section is not None:
            buffer.append(line)

        i += 1

    # flush last section
    flush_section()

    # Trim extra trailing blank lines (but do NOT remove trailing separator lines)
    while out and out[-1].strip() == "":
        # stop trimming if the previous line is a separator; keep formatting stable
        if len(out) >= 2 and SEP_RE.match(out[-2]):
            break
        out.pop()

    return out


def build_release_notes(lines_no_nl: List[str]) -> List[str]:
    """
    Build release notes body from DevNotes lines (no newlines).
    Preserves:
      - patch header/date lines
      - separator lines made of hyphens
    Filters check-ins to keep only Issue/Feature sections.
    """
    out = []
    i = 0
    n = len(lines_no_nl)

    while i < n:
        line = lines_no_nl[i]

        # Skip base version in body (we place it at the very top separately)
        if BASE_VERSION_RE.match(line):
            i += 1
            continue

        if is_patch_header(line):
            patch_block, next_i = collect_patch_block(lines_no_nl, i)

            # Walk the patch block sequentially, preserving separators and headers.
            j = 0
            m = len(patch_block)

            # 1) output patch header and any non-checkin lines until first Checkin ID
            while j < m and not CHECKIN_RE.match(patch_block[j]):
                # preserve patch title, date, separator lines, and blank lines exactly
                out.append(patch_block[j])
                j += 1

            # 2) process each check-in chunk split by "Checkin ID:" lines
            while j < m:
                if not CHECKIN_RE.match(patch_block[j]):
                    # If unexpected line appears, preserve if it's a separator/blank; else skip.
                    if SEP_RE.match(patch_block[j]) or patch_block[j].strip() == "":
                        out.append(patch_block[j])
                    j += 1
                    continue

                # collect one check-in block: from this Checkin ID until next Checkin ID OR end of patch
                k = j
                j += 1
                while j < m and not CHECKIN_RE.match(patch_block[j]):
                    j += 1
                checkin_lines = patch_block[k:j]

                # filter the check-in
                out.extend(process_checkin_block(checkin_lines))

            i = next_i
            continue

        # If outside a patch block: ignore (except you can preserve stray separators if desired)
        i += 1

    # Remove trailing blank lines at end
    while out and out[-1].strip() == "":
        out.pop()

    return out


def build_release_notes_text(devnotes_text: str) -> str:
    """
    Build the ReleaseNotes text from DevNotes text content (in memory).
    Same logic as process_dev_notes() but doesn't touch the filesystem.
    """
    lines_no_nl = devnotes_text.splitlines()
    base_version = extract_base_version_line(lines_no_nl)
    body_lines = build_release_notes(lines_no_nl)

    parts: list[str] = []
    if base_version:
        parts.append(base_version + "\n\n")
    parts.extend(line + "\n" for line in body_lines)
    return "".join(parts)


def process_dev_notes(input_file: str = "DevNotes.txt", output_file: str = "ReleaseNotes.txt") -> None:
    input_path = Path(input_file)
    output_path = Path(output_file)

    raw = input_path.read_text(encoding="utf-8", errors="ignore")
    text = build_release_notes_text(raw)
    output_path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    process_dev_notes("DevNotes.txt", "ReleaseNotes.txt")