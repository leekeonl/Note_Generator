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

# App-list line: matches lines like "[ Lam300Host ]  AppName (version info)"
# These show up under [Internal Notes] and again under [Auto Merge Wizard].
# When the Auto-Merge block contains app-list lines, we replace the existing
# ones above (which point at the source check-in's version) with the
# Auto-Merge versions (which point at the actual merged version).
APP_LINE_RE = re.compile(r'^\s*\[\s*[^\]]+\s*\]\s+\S.*\(.+\)\s*$')

# Known section headers that may appear in dev notes. Only these are
# normalized when found inline; arbitrary bracketed text in body content
# (e.g. "[ CVS ]", "[ Lam2300_V3\Install\... ]") is left alone.
KNOWN_SECTIONS = (
    "Issue Description",
    "Feature Description",
    "Solution",
    "Root Cause",
    "Internal Notes",
)

# Match a known section header that has content on the same line, e.g.
#   [Issue Description] EDA returns "Not Enough Memory"...
# Captures: (1) the section header in canonical form, (2) the inline content.
INLINE_SECTION_RE = re.compile(
    r'^\s*\[\s*(' + "|".join(re.escape(s) for s in KNOWN_SECTIONS) + r')\s*\]\s+(\S.*)$',
    re.IGNORECASE,
)


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


def _replace_trailing_app_lines(buffer: list[str], replacements: list[str]) -> None:
    """
    Walk backwards from the end of `buffer`, find the contiguous tail of
    app-list lines (interleaved with blank lines), remove them, and append
    `replacements` in their place.

    Buffer state before:
        [Internal Notes]
        Tested on S4 PM5 with PR owner.
        Look at attachments...
        <blank>
        [ Lam300Host ]  ... (LeeNi6 0.111)        ← old apps
        [ Lam300PMC ]   ... (LeeNi6 1.7.9.991)    ← old apps

    Buffer state after, with replacements applied:
        [Internal Notes]
        Tested on S4 PM5 with PR owner.
        Look at attachments...
        <blank>
        [ Lam300Host ]  ... (LeeNi6 [184 SP35 HF] 0.108.1)        ← new apps
        [ Lam300PMC ]   ... (LeeNi6 [184 SP35 HF] 1.7.9.972.11)   ← new apps

    Descriptive prose (e.g. "Tested on S4 PM5...") is preserved — only the
    trailing app-list lines are swapped.
    """
    # Walk back through trailing blank lines + app-list lines, marking where
    # the swap region begins. Stop the moment we hit a non-blank,
    # non-app-list line (that's body prose we want to keep).
    i = len(buffer)
    while i > 0:
        prev = buffer[i - 1]
        if prev.strip() == "" or APP_LINE_RE.match(prev):
            i -= 1
        else:
            break

    # Within the marked region [i, len(buffer)), keep blank-line spacing
    # but drop the app-list lines themselves before appending replacements.
    tail = buffer[i:]
    del buffer[i:]
    # Preserve any blank lines that came before the first app line, so the
    # spacing between body prose and the app list is unchanged.
    for line in tail:
        if APP_LINE_RE.match(line):
            break
        buffer.append(line)
    buffer.extend(replacements)


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
            auto_merge_apps: list[str] = []   # collect app-list lines from this AM block
            continue

        if skip_auto:
            if stripped == SEPARATOR:
                # End of Auto-Merge block. If it contained app-list lines, use
                # them to replace the existing app-list lines at the tail of
                # our output buffer (which came from above the AM marker).
                if auto_merge_apps:
                    _replace_trailing_app_lines(out, auto_merge_apps)
                skip_auto = False
                out.append(SEPARATOR)
            elif APP_LINE_RE.match(line):
                auto_merge_apps.append(line)
            # otherwise (blank line, descriptive text, etc.) — discard
            continue

        if stripped.startswith(REMOVE_HEADERS):
            continue

        # Normalize inline section headers:  [Section] content  →  [Section]\n\tcontent
        # Only known section names are touched, so arbitrary bracketed text
        # in body content (e.g. "[ CVS ]") is preserved as-is.
        m = INLINE_SECTION_RE.match(line)
        if m:
            out.append(f"[{m.group(1)}]")    # canonicalized section header
            out.append("\t" + m.group(2))    # the content, indented with a tab
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
