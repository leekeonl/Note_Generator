"""
full_pipeline.py

End-to-end workflow:
    Inputs:
        - DevNotes.txt           (existing dev notes file, will be updated in-place)
        - patch_number           (e.g. "Patch10" or "Patch5.1") - user provided
        - checkinid.txt          (list of checkin IDs to include)
        - Notes.txt              (raw notes from devs)

    Output:
        - DevNotes.txt           (updated: new patch block inserted at top, just below Base Version)
        - DevNotes.YYYYMMDD_HHMMSS.bak.txt   (backup of DevNotes.txt before modification)
        - ReleaseNotes.txt       (regenerated from the updated DevNotes.txt)

This module is split into two phases so a preview can be shown before
anything is written to disk:

    build_preview()    Pure / read-only. Returns a PipelinePreview object
                       describing what *would* happen.
    commit_preview()   Side-effecting. Takes a PipelinePreview and actually
                       writes the files (with optional backup).
    run_full_pipeline() Thin wrapper that calls both, preserved for backward
                       compatibility with older callers.
"""

from dataclasses import dataclass, field
from pathlib import Path
from datetime import date, datetime
import re
import shutil

from notes_to_for_devnotes import build_for_devnotes_text
from ReleaseNotesCreatorv4 import build_release_notes_text

SEPARATOR = "--------------------------------------------------------------------------------"
BASE_VERSION_RE = re.compile(r'^\s*Base Version:\s*.+\s*$', re.IGNORECASE)
CHECKIN_RE = re.compile(r'^\s*Checkin ID:\s*(\S.*?)\s*$', re.IGNORECASE)


# =============================================================================
# Preview data class
# =============================================================================
@dataclass
class PipelinePreview:
    """
    Read-only description of what the pipeline would do.

    All file paths are resolved. Nothing has been written to disk yet -
    pass this object to commit_preview() to apply the changes.
    """
    devnotes_path: Path
    releasenotes_path: Path

    patch_label: str         # e.g. "Patch10"
    patch_date: str          # e.g. "5/17/2026"

    new_patch_block: str
    predicted_devnotes: str
    predicted_releasenotes: str

    requested_checkin_ids: list[str] = field(default_factory=list)
    included_checkin_ids: list[str] = field(default_factory=list)
    missing_checkin_ids: list[str] = field(default_factory=list)
    pr_to_checkins: dict[str, list[str]] = field(default_factory=dict)   # PR → list of checkin IDs it resolved to


# =============================================================================
# Internal helpers
# =============================================================================
def _format_today() -> str:
    today = date.today()
    return f"{today.month}/{today.day}/{today.year}"


def _build_new_patch_block(patch_number: str, for_devnotes_text: str) -> str:
    """
    Build the new patch block that will be prepended into DevNotes.txt.

    Example output:
        Patch10
        5/17/2026
        --------------------------------------------------------------------------------
        Checkin ID: ...
        ...
        --------------------------------------------------------------------------------
    """
    patch_number = patch_number.strip()
    date_str = _format_today()

    body = for_devnotes_text.rstrip()
    body_lines = body.splitlines()

    if not body_lines or body_lines[0].strip() != SEPARATOR:
        body = SEPARATOR + "\n" + body

    if not body.rstrip().endswith(SEPARATOR):
        body = body.rstrip() + "\n" + SEPARATOR

    return f"{patch_number}\n{date_str}\n{body}\n"


def _compose_updated_devnotes(original_text: str, new_patch_block: str) -> str:
    """
    Pure function: given current DevNotes contents and a new patch block,
    return what the updated DevNotes would be. Insertion point is right
    after the first 'Base Version:' line; if there's no such line, the
    block is prepended.
    """
    lines = original_text.splitlines(keepends=True)

    insert_idx = None
    for i, line in enumerate(lines):
        if BASE_VERSION_RE.match(line.rstrip("\n")):
            insert_idx = i + 1
            break

    if insert_idx is None:
        return new_patch_block + "\n" + original_text

    before = "".join(lines[:insert_idx])
    after = "".join(lines[insert_idx:])

    if not before.endswith("\n"):
        before += "\n"
    after_stripped = after.lstrip("\n")

    return (
        before
        + "\n"
        + new_patch_block.rstrip() + "\n"
        + "\n"
        + after_stripped
    )


def _predict_releasenotes(updated_devnotes_text: str) -> str:
    """
    Generate ReleaseNotes from predicted DevNotes contents, fully in memory.
    """
    return build_release_notes_text(updated_devnotes_text)


def _extract_checkin_ids_from_block(text: str) -> list[str]:
    """Return all 'Checkin ID: <id>' values found in `text`, in order."""
    ids = []
    for line in text.splitlines():
        m = CHECKIN_RE.match(line)
        if m:
            ids.append(m.group(1).strip())
    return ids


def _backup_devnotes(devnotes_path: Path) -> Path:
    """
    Create a timestamped backup of DevNotes.txt next to it. Multiple runs
    in the same day produce distinct backups (timestamp resolution: 1 sec),
    so previous backups are never overwritten.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{devnotes_path.stem}.{timestamp}.bak{devnotes_path.suffix}"
    backup_path = devnotes_path.with_name(backup_name)
    shutil.copy2(devnotes_path, backup_path)
    return backup_path


# =============================================================================
# Public API
# =============================================================================
def build_preview(
    devnotes_file: str,
    patch_number: str,
    checkinid_file: str,
    notes_file: str,
) -> PipelinePreview:
    """
    Compute everything the pipeline would do, without touching the user's
    filesystem (temp files used internally are cleaned up). Pass the result
    to commit_preview() to apply the changes.

    Raises:
        FileNotFoundError, ValueError - same conditions as run_full_pipeline().
    """
    devnotes_path = Path(devnotes_file)
    if not devnotes_path.exists():
        raise FileNotFoundError(f"DevNotes file not found: {devnotes_path}")

    if not patch_number or not patch_number.strip():
        raise ValueError("Patch number is required (e.g. 'Patch10').")

    fd_result = build_for_devnotes_text(checkinid_file, notes_file)
    if not fd_result.text.strip():
        raise ValueError(
            "No check-ins matched. Verify that IDs in checkinid.txt also "
            "appear in Notes.txt."
        )

    patch_label = patch_number.strip()
    patch_date = _format_today()
    new_patch_block = _build_new_patch_block(patch_label, fd_result.text)

    original_devnotes = devnotes_path.read_text(encoding="utf-8", errors="ignore")
    predicted_devnotes = _compose_updated_devnotes(original_devnotes, new_patch_block)
    predicted_releasenotes = _predict_releasenotes(predicted_devnotes)

    # Check-in analysis: included IDs are the full "name version" strings as
    # they appear in the new patch block; missing IDs come from the
    # ForDevNotesResult (requested but not found in Notes.txt).
    included = _extract_checkin_ids_from_block(new_patch_block)

    releasenotes_path = devnotes_path.parent / "ReleaseNotes.txt"

    return PipelinePreview(
        devnotes_path=devnotes_path,
        releasenotes_path=releasenotes_path,
        patch_label=patch_label,
        patch_date=patch_date,
        new_patch_block=new_patch_block,
        predicted_devnotes=predicted_devnotes,
        predicted_releasenotes=predicted_releasenotes,
        requested_checkin_ids=fd_result.requested_ids,
        included_checkin_ids=included,
        missing_checkin_ids=fd_result.missing_ids,
        pr_to_checkins=fd_result.pr_to_checkins,
    )


def commit_preview(
    preview: PipelinePreview,
    make_backup: bool = True,
) -> tuple[Path, Path, Path | None]:
    """
    Actually write the predicted DevNotes and ReleaseNotes to disk, optionally
    backing up the existing DevNotes first.

    Returns:
        (devnotes_path, releasenotes_path, backup_path_or_None)
    """
    backup_path: Path | None = None
    if make_backup and preview.devnotes_path.exists():
        backup_path = _backup_devnotes(preview.devnotes_path)

    preview.devnotes_path.write_text(preview.predicted_devnotes, encoding="utf-8")
    preview.releasenotes_path.write_text(preview.predicted_releasenotes, encoding="utf-8")

    return preview.devnotes_path, preview.releasenotes_path, backup_path


def run_full_pipeline(
    devnotes_file: str,
    patch_number: str,
    checkinid_file: str,
    notes_file: str,
    make_backup: bool = True,
) -> tuple[Path, Path, Path | None]:
    """
    Backward-compatible one-shot entry point. Equivalent to:
        commit_preview(build_preview(...), make_backup=...)
    """
    preview = build_preview(devnotes_file, patch_number, checkinid_file, notes_file)
    return commit_preview(preview, make_backup=make_backup)
