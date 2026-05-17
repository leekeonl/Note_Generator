from pathlib import Path
from dataclasses import dataclass, field
import re

SEPARATOR = "--------------------------------------------------------------------------------"
REMOVE_HEADERS = (
    "Developer:",
    "Timestamp:",
    "Release Notes Needed:",
    "Review Needed:",
    "CE Review Needed:",
    "Software Categories:",
)
AUTO_MERGE = "[Auto Merge Wizard]"


@dataclass
class ForDevNotesResult:
    """Result of building For_DevNotes content in memory."""
    text: str                                = ""    # The cleaned For_DevNotes content
    requested_ids: list[str]                 = field(default_factory=list)  # All IDs from checkinid.txt
    included_ids: list[str]                  = field(default_factory=list)  # IDs that were found in Notes.txt
    missing_ids: list[str]                   = field(default_factory=list)  # IDs in checkinid.txt but NOT in Notes.txt


def read_checkin_ids(checkinid_file: str) -> set[str]:
    text = Path(checkinid_file).read_text(encoding="utf-8", errors="ignore")
    return set(re.findall(r"\d+\.\d+", text))


def read_checkin_ids_ordered(checkinid_file: str) -> list[str]:
    """Same as read_checkin_ids but preserves order and uniqueness."""
    text = Path(checkinid_file).read_text(encoding="utf-8", errors="ignore")
    seen: set[str] = set()
    ordered: list[str] = []
    for m in re.finditer(r"\d+\.\d+", text):
        v = m.group()
        if v not in seen:
            seen.add(v)
            ordered.append(v)
    return ordered


def build_for_devnotes_text(
    checkinid_file: str,
    notes_file: str,
) -> ForDevNotesResult:
    """
    Build the For_DevNotes-style filtered text in memory and report which
    requested check-in IDs were actually found in Notes.txt vs. missing.
    """
    requested = read_checkin_ids_ordered(checkinid_file)
    requested_set = set(requested)
    found: set[str] = set()

    lines = Path(notes_file).read_text(encoding="utf-8", errors="ignore").splitlines()

    out: list[str] = []
    capture = False
    skip_auto = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("Checkin ID:"):
            ver = re.search(r"\d+\.\d+", stripped)
            if ver and ver.group() in requested_set:
                capture = True
                skip_auto = False
                found.add(ver.group())
                out.append(line)
            else:
                capture = False
            continue

        if not capture:
            continue

        if AUTO_MERGE in line:
            skip_auto = True
            continue

        if skip_auto:
            if stripped == SEPARATOR:
                skip_auto = False
                out.append(SEPARATOR)
            continue

        if stripped.startswith(REMOVE_HEADERS):
            continue

        out.append(line)

    text = "\n".join(out).rstrip() + ("\n" if out else "")

    # Preserve requested-order for reporting
    included = [i for i in requested if i in found]
    missing = [i for i in requested if i not in found]

    return ForDevNotesResult(
        text=text,
        requested_ids=requested,
        included_ids=included,
        missing_ids=missing,
    )


def generate_for_devnotes(checkinid_file: str, notes_file: str, output_file) -> ForDevNotesResult:
    """
    File-based wrapper. Kept for backward compatibility with existing UI code
    and external callers. Returns the same ForDevNotesResult for callers that
    want to inspect included/missing IDs.
    """
    result = build_for_devnotes_text(checkinid_file, notes_file)
    Path(output_file).write_text(result.text, encoding="utf-8")
    return result
