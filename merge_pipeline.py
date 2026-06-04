"""
merge_pipeline.py — re-build an existing patch block by merging in new
check-ins fetched from a NoteSource (typically Phabricator).

Flow:
  1. extract the existing patch block from DevNotes
  2. parse its current check-in IDs
  3. given the new (already-fetched) Notes.txt-style text, parse its
     check-in IDs and build per-check-in text blocks
  4. detect duplicates (check-in IDs that appear both in the existing
     block and in the newly fetched text)
  5. apply the user's per-duplicate decisions (replace vs keep-existing)
  6. sort the union descending by check-in ID
  7. emit the rebuilt patch text
  8. splice it back into the DevNotes file (existing block removed,
     rebuilt block re-inserted at the same position)

Public API:
  detect_merge_conflicts(existing_ids, new_ids) -> list[str]
  build_merge_preview(...) -> MergePreview
  commit_merge_preview(preview, make_backup=True)
"""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field
from datetime import date
import re
import shutil

from devnotes_parser import (
    SEPARATOR, PATCH_HEADER_RE, CHECKIN_ID_RE,
    extract_patch_block, parse_patch_checkins, remove_patch_block,
    list_patch_labels,
    _find_patch_header_at,
)


@dataclass
class MergePreview:
    """Read-only description of a merge operation. Pass to commit_merge_preview."""
    devnotes_path: Path
    releasenotes_path: Path
    patch_label: str               # e.g. "Patch2" — the existing label
    patch_date: str                # date of the rebuilt block (today)

    rebuilt_patch_block: str       # the new text for the patch block
    predicted_devnotes: str        # full DevNotes content after the merge
    predicted_releasenotes: str    # full ReleaseNotes regenerated from above

    existing_checkin_ids: list[str] = field(default_factory=list)
    new_checkin_ids: list[str]      = field(default_factory=list)
    final_checkin_ids: list[str]    = field(default_factory=list)
    conflicts: list[str]            = field(default_factory=list)
    # The user's resolution: True = replace with new, False = keep existing
    resolutions: dict[str, bool]    = field(default_factory=dict)


def detect_merge_conflicts(
    existing_ids: list[str],
    new_ids: list[str],
) -> list[str]:
    """Return check-in IDs that appear in both lists, in `new_ids` order."""
    existing_set = set(existing_ids)
    return [cid for cid in new_ids if cid in existing_set]


def _split_into_checkin_blocks(notes_text: str) -> dict[str, str]:
    """
    Split a Notes.txt-style text into per-check-in text blocks.

    Each "block" is everything between SEPARATOR lines that contains a
    "Checkin ID: X.Y" header. Returns {checkin_id: block_text}.

    The block text does NOT include the surrounding SEPARATOR lines —
    those are added back at serialization time. This keeps the data model
    simple and avoids accidental double-separators when re-joining.
    """
    blocks: dict[str, str] = {}
    current_lines: list[str] = []
    current_id: str | None = None

    def _flush():
        nonlocal current_lines, current_id
        if current_id and current_lines:
            blocks[current_id] = "\n".join(current_lines).strip("\n")
        current_lines = []
        current_id = None

    for line in notes_text.splitlines():
        if line.rstrip() == SEPARATOR:
            _flush()
            continue
        current_lines.append(line)
        if current_id is None:
            stripped = line.strip()
            if stripped.startswith("Checkin ID:"):
                m = CHECKIN_ID_RE.search(stripped)
                if m:
                    current_id = m.group()
    _flush()

    return blocks


def _split_patch_into_checkin_blocks(patch_block_text: str) -> tuple[str, dict[str, str]]:
    """
    Split an existing patch block (with header) into:
        (header_text, {checkin_id: block_text})

    header_text is the patch label/date line(s), NOT including the first
    separator (which we'll re-emit when serializing). Works for both the
    two-line "Patch9\n8/8/2025" form and the legacy "Patch9 8/8/2025" form.
    """
    lines = patch_block_text.splitlines()
    header_lines: list[str] = []
    body_start = 0
    for i, line in enumerate(lines):
        if line.rstrip() == SEPARATOR:
            body_start = i
            break
        header_lines.append(line)
    body_text = "\n".join(lines[body_start:])
    blocks = _split_into_checkin_blocks(body_text)
    return "\n".join(header_lines), blocks


def _serialize_patch_block(header: str, blocks: dict[str, str], ordered_ids: list[str]) -> str:
    """Re-assemble a patch block from header + ordered check-in blocks."""
    out: list[str] = [header, SEPARATOR]
    for cid in ordered_ids:
        out.append(blocks[cid])
        out.append(SEPARATOR)
    return "\n".join(out)


def _format_today() -> str:
    today = date.today()
    return f"{today.month}/{today.day}/{today.year}"


def _checkin_sort_key(cid: str) -> tuple[int, int]:
    major, _, minor = cid.partition(".")
    try:
        return (int(major), int(minor))
    except ValueError:
        return (-1, -1)


def _normalize_new_notes(new_notes_text: str) -> str:
    """
    Apply the same normalization the new-patch pipeline applies, so the
    merge flow gets identical output (Auto-Merge handled, internal headers
    stripped, inline section headers split, etc.).

    notes_to_for_devnotes.build_for_devnotes_text is file-based, so we
    write the inputs to temp files and read the output back. Slightly
    wasteful but it guarantees both flows go through the exact same code.
    """
    import tempfile
    import os
    from notes_to_for_devnotes import build_for_devnotes_text, CHECKIN_ID_RE

    # Extract every check-in ID present in the new notes — those are the
    # ones we want to keep when normalizing. Otherwise the filter step
    # would drop everything.
    checkin_ids = sorted(set(CHECKIN_ID_RE.findall(new_notes_text)))
    if not checkin_ids:
        return new_notes_text  # nothing to normalize

    notes_tmp = None
    checkinid_tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".txt", delete=False,
            prefix="merge_notes_") as tmp:
            tmp.write(new_notes_text)
            notes_tmp = tmp.name
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".txt", delete=False,
            prefix="merge_checkinid_") as tmp:
            tmp.write("\n".join(checkin_ids))
            checkinid_tmp = tmp.name

        result = build_for_devnotes_text(checkinid_tmp, notes_tmp)
        return result.text
    finally:
        for p in (notes_tmp, checkinid_tmp):
            if p:
                try: os.unlink(p)
                except OSError: pass


def build_merge_preview(
    devnotes_file: str,
    releasenotes_file: str,
    patch_label: str,
    new_notes_text: str,
    resolutions: dict[str, bool] | None = None,
) -> MergePreview:
    """
    Build a preview of merging `new_notes_text` (Notes.txt-style) into
    the existing patch block labelled `patch_label` inside `devnotes_file`.

    `resolutions` maps check-in ID → True (replace with new) or False
    (keep existing). Any conflicts not listed default to True (replace).
    On the first call, callers typically pass None to *discover* what the
    conflicts are; then prompt the user; then call again with the chosen
    resolutions.
    """
    resolutions = dict(resolutions or {})

    devnotes_path = Path(devnotes_file)
    releasenotes_path = Path(releasenotes_file)

    # 1. Extract existing patch block
    existing_block = extract_patch_block(devnotes_path, patch_label)
    if existing_block is None:
        raise ValueError(
            f"Could not find patch block {patch_label!r} in {devnotes_path}.\n"
            f"Available labels: {list_patch_labels(devnotes_path)}"
        )

    header_text, existing_blocks = _split_patch_into_checkin_blocks(existing_block)
    existing_ids = list(existing_blocks.keys())

    # 2. Normalize the newly-fetched notes through the same pipeline the
    # new-patch flow uses. This handles:
    #   - Auto-Merge Wizard app-list replacement (old apps → new apps)
    #   - Stripping internal-only headers (Developer:, Timestamp:, etc.)
    #   - Inline section header normalization
    # Without this step the merge preview would show raw Phabricator output
    # with old app versions still listed above the Auto-Merge block.
    normalized_new_notes = _normalize_new_notes(new_notes_text)

    # 3. Parse new check-in blocks
    new_blocks = _split_into_checkin_blocks(normalized_new_notes)
    new_ids = list(new_blocks.keys())

    # 4. Detect conflicts and decide per-id which version to keep
    conflicts = detect_merge_conflicts(existing_ids, new_ids)
    merged_blocks: dict[str, str] = {}

    # start with existing (unconflicted) blocks
    for cid, block in existing_blocks.items():
        if cid in conflicts:
            # Defer; we'll decide based on resolutions
            continue
        merged_blocks[cid] = block

    # add new (unconflicted) blocks
    for cid, block in new_blocks.items():
        if cid in conflicts:
            continue
        merged_blocks[cid] = block

    # handle conflicts based on user resolutions (default = replace)
    for cid in conflicts:
        replace = resolutions.get(cid, True)
        merged_blocks[cid] = new_blocks[cid] if replace else existing_blocks[cid]

    # 4. Sort final IDs descending by check-in number
    final_ids = sorted(merged_blocks.keys(), key=_checkin_sort_key, reverse=True)

    # 5. Update the header to today's date (keep label as-is). Use the
    # two-line form ("Patch9\n8/8/2025") to match the rest of the file.
    today_str = _format_today()
    new_header = f"{patch_label}\n{today_str}"

    rebuilt_block = _serialize_patch_block(new_header, merged_blocks, final_ids)

    # 6. Splice into DevNotes — remove old block, insert rebuilt block in place
    devnotes_text_without = remove_patch_block(devnotes_path, patch_label)
    predicted_devnotes = _splice_patch_back(
        devnotes_text_without,
        rebuilt_block,
        patch_label,
        original_devnotes_path=devnotes_path,
    )

    # 7. Regenerate ReleaseNotes from the predicted DevNotes
    predicted_releasenotes = _generate_release_from_devnotes(predicted_devnotes)

    return MergePreview(
        devnotes_path=devnotes_path,
        releasenotes_path=releasenotes_path,
        patch_label=patch_label,
        patch_date=today_str,
        rebuilt_patch_block=rebuilt_block,
        predicted_devnotes=predicted_devnotes,
        predicted_releasenotes=predicted_releasenotes,
        existing_checkin_ids=existing_ids,
        new_checkin_ids=new_ids,
        final_checkin_ids=final_ids,
        conflicts=conflicts,
        resolutions=resolutions,
    )


def _splice_patch_back(
    devnotes_without_block: str,
    rebuilt_block: str,
    patch_label: str,
    original_devnotes_path: Path,
) -> str:
    """
    Re-insert the rebuilt patch block in the same position it was before
    (identified by the original file's patch ordering).

    Strategy: find where the patch *would have been* by looking at the
    label that came right before it in the original file. If no patch
    came before (i.e. our block was the very first one), insert after the
    Base Version line.
    """
    # Find what label came directly before patch_label in the original file
    original_labels = list_patch_labels(original_devnotes_path)
    try:
        idx = original_labels.index(patch_label)
    except ValueError:
        # Patch label not in original file — shouldn't happen since we already
        # extracted it, but fall back to appending at the end of Base Version
        idx = 0
    label_before = original_labels[idx - 1] if idx > 0 else None

    out_lines = devnotes_without_block.splitlines()
    insert_at: int

    if label_before is None:
        # Insert right after the Base Version header line (or at top)
        insert_at = 0
        for i, line in enumerate(out_lines):
            if line.strip().startswith("Base Version:"):
                insert_at = i + 1
                break
        # Skip any immediately-following blank lines (we'll add our own)
        while insert_at < len(out_lines) and not out_lines[insert_at].strip():
            insert_at += 1
    else:
        # Insert immediately after `label_before`'s block.
        # Walk the lines using the two-line-aware header detector.
        insert_at = len(out_lines)
        in_target_block = False
        i = 0
        while i < len(out_lines):
            hit = _find_patch_header_at(out_lines, i)
            if hit:
                hit_label, _date, next_i = hit
                if hit_label == label_before:
                    in_target_block = True
                    i = next_i
                    continue
                if in_target_block:
                    insert_at = i
                    break
                i = next_i
            else:
                i += 1

    # Build the spliced result with appropriate spacing around our block
    before = out_lines[:insert_at]
    after = out_lines[insert_at:]

    # Trim trailing blanks from `before` so we control spacing
    while before and not before[-1].strip():
        before.pop()
    # Trim leading blanks from `after` for the same reason
    while after and not after[0].strip():
        after.pop(0)

    pieces: list[str] = []
    if before:
        pieces.append("\n".join(before))
    pieces.append(rebuilt_block)
    if after:
        pieces.append("\n".join(after))

    return "\n\n".join(pieces) + "\n"


def _generate_release_from_devnotes(devnotes_text: str) -> str:
    """
    Run the same transformation that ReleaseNotesCreatorv4.process_dev_notes
    would, but on a string rather than a file. We do this by writing the
    text to a temp file and calling the existing module.
    """
    import tempfile
    from ReleaseNotesCreatorv4 import process_dev_notes

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix="_DevNotes.txt", delete=False,
        prefix="merge_preview_",
    ) as tf:
        tf.write(devnotes_text)
        in_path = tf.name

    out_path = in_path.replace("_DevNotes.txt", "_ReleaseNotes.txt")
    try:
        process_dev_notes(in_path, out_path)
        return Path(out_path).read_text(encoding="utf-8", errors="ignore")
    finally:
        for p in (in_path, out_path):
            try: Path(p).unlink()
            except OSError: pass


def commit_merge_preview(
    preview: MergePreview,
    make_backup: bool = True,
) -> tuple[Path, Path, Path | None]:
    """
    Apply a MergePreview to disk:
      - write predicted_devnotes to preview.devnotes_path
      - write predicted_releasenotes to preview.releasenotes_path
      - optionally create a timestamped backup of the original DevNotes

    Returns: (devnotes_path, releasenotes_path, backup_path_or_None)
    """
    backup_path: Path | None = None
    if make_backup and preview.devnotes_path.exists():
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = preview.devnotes_path.with_name(
            f"{preview.devnotes_path.stem}.{ts}.bak{preview.devnotes_path.suffix}"
        )
        shutil.copy2(preview.devnotes_path, backup_path)

    preview.devnotes_path.write_text(preview.predicted_devnotes, encoding="utf-8")
    preview.releasenotes_path.write_text(preview.predicted_releasenotes, encoding="utf-8")

    return preview.devnotes_path, preview.releasenotes_path, backup_path
