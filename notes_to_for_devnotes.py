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

# Patterns the user can put in checkinid.txt:
#   - Check-in version IDs   →  e.g. "0.1569", "0.4091" (digits.digits)
#   - PR numbers             →  e.g. "PR-157869", "PR-217458"
CHECKIN_ID_RE = re.compile(r'\b\d+\.\d+\b')
PR_RE         = re.compile(r'\bPR-\d+\b', re.IGNORECASE)

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
    requested_ids: list[str]                 = field(default_factory=list)  # All identifiers from checkinid.txt (checkin IDs + PR numbers, in input order)
    included_ids: list[str]                  = field(default_factory=list)  # Check-in IDs (numeric versions) actually included
    missing_ids: list[str]                   = field(default_factory=list)  # Identifiers from checkinid.txt that resolved to no check-in
    pr_to_checkins: dict[str, list[str]]     = field(default_factory=dict)  # Map of PR number → list of check-in IDs that contained it


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


def read_requested_items(checkinid_file: str) -> list[tuple[str, str]]:
    """
    Parse checkinid.txt and return a list of (kind, value) tuples preserving
    input order and uniqueness. Each entry is either:
        ("checkin", "0.4091")   — a check-in version identifier
        ("pr",      "PR-157869") — a PR number

    Both formats may appear on the same line or mixed across lines.

    Example input:
        0.1569
        PR-157869, PR-217458
        alice 0.4091

    Yields: ("checkin", "0.1569"), ("pr", "PR-157869"), ("pr", "PR-217458"),
            ("checkin", "0.4091")
    """
    text = Path(checkinid_file).read_text(encoding="utf-8", errors="ignore")

    # Collect all matches of both patterns with their positions, then walk
    # them in document order. PR is matched first to avoid the numeric part
    # of "PR-157869" being also matched by CHECKIN_ID_RE — but PR-157869
    # contains no period so it actually wouldn't, however we still strip PR
    # matches' spans from the text before scanning for check-in IDs to be safe.
    matches: list[tuple[int, str, str]] = []  # (position, kind, value)

    # Find PRs first
    pr_spans: list[tuple[int, int]] = []
    for m in PR_RE.finditer(text):
        # Canonicalize to uppercase "PR-" prefix
        matches.append((m.start(), "pr", "PR-" + m.group().split("-", 1)[1]))
        pr_spans.append(m.span())

    # Mask out PR spans so check-in regex doesn't pick up overlapping digits
    masked = list(text)
    for start, end in pr_spans:
        for i in range(start, end):
            masked[i] = " "
    masked_text = "".join(masked)

    for m in CHECKIN_ID_RE.finditer(masked_text):
        matches.append((m.start(), "checkin", m.group()))

    # Sort by position to preserve input order across mixed lines
    matches.sort(key=lambda t: t[0])

    seen: set[tuple[str, str]] = set()
    ordered: list[tuple[str, str]] = []
    for _, kind, value in matches:
        key = (kind, value)
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def _build_pr_to_checkin_map(notes_file: str) -> dict[str, list[str]]:
    """
    Pre-scan Notes.txt to build a mapping from PR number → list of check-in
    versions (e.g. "0.4091") that mention it.

    A single check-in can include multiple PRs, and the same PR can appear
    across multiple check-ins (e.g. one fix that landed in several merges).
    The returned mapping covers both cases.
    """
    lines = Path(notes_file).read_text(encoding="utf-8", errors="ignore").splitlines()
    mapping: dict[str, list[str]] = {}
    current_checkin: str | None = None

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("Checkin ID:"):
            m = CHECKIN_ID_RE.search(stripped)
            current_checkin = m.group() if m else None
            continue

        if current_checkin and stripped.startswith("PR Number(s):"):
            for prm in PR_RE.finditer(stripped):
                pr = "PR-" + prm.group().split("-", 1)[1]  # canonicalize case
                bucket = mapping.setdefault(pr, [])
                if current_checkin not in bucket:
                    bucket.append(current_checkin)

    return mapping


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
    requested identifiers were actually found in Notes.txt.

    checkinid.txt may contain a mix of:
        - Check-in version IDs (e.g. "0.4091")     →  match that check-in directly
        - PR numbers (e.g. "PR-157869")            →  match every check-in that lists this PR

    Identifiers that don't resolve to any check-in are reported in
    `result.missing_ids`.
    """
    # Parse user input — preserves original order so we can report it back
    requested_items = read_requested_items(checkinid_file)

    # Pre-scan Notes.txt to learn which PRs map to which check-ins
    pr_map = _build_pr_to_checkin_map(notes_file)

    # Resolve every requested item into one or more check-in IDs. Track the
    # request-order set of target check-ins, and remember which inputs
    # contributed nothing (= "missing").
    target_checkins: set[str] = set()
    pr_to_checkins_used: dict[str, list[str]] = {}
    missing: list[str] = []
    requested_display: list[str] = []  # original input order, as strings

    for kind, value in requested_items:
        requested_display.append(value)
        if kind == "checkin":
            target_checkins.add(value)
            # Whether this checkin actually exists in Notes.txt is determined
            # later when we walk the file; for now assume it does.
        else:  # kind == "pr"
            resolved = pr_map.get(value, [])
            if resolved:
                for cid in resolved:
                    target_checkins.add(cid)
                pr_to_checkins_used[value] = resolved
            else:
                # PR not found in any check-in
                missing.append(value)

    # Walk Notes.txt and capture matching check-in blocks (same as before,
    # but now matching against the resolved target_checkins set).
    lines = Path(notes_file).read_text(encoding="utf-8", errors="ignore").splitlines()
    found_checkins: set[str] = set()

    out: list[str] = []
    capture = False
    skip_auto = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("Checkin ID:"):
            ver = re.search(r"\d+\.\d+", stripped)
            if ver and ver.group() in target_checkins:
                capture = True
                skip_auto = False
                found_checkins.add(ver.group())
                out.append(line)
            else:
                capture = False
            continue

        if not capture:
            continue

        if AUTO_MERGE in line:
            skip_auto = True
            auto_merge_apps: list[str] = []
            continue

        if skip_auto:
            if stripped == SEPARATOR:
                if auto_merge_apps:
                    _replace_trailing_app_lines(out, auto_merge_apps)
                skip_auto = False
                out.append(SEPARATOR)
            elif APP_LINE_RE.match(line):
                auto_merge_apps.append(line)
            continue

        if stripped.startswith(REMOVE_HEADERS):
            continue

        m = INLINE_SECTION_RE.match(line)
        if m:
            out.append(f"[{m.group(1)}]")
            out.append("\t" + m.group(2))
            continue

        out.append(line)

    text = "\n".join(out).rstrip() + ("\n" if out else "")

    # Anything in target_checkins that we didn't actually see in Notes.txt is
    # also missing. For check-in inputs this means the user-provided ID
    # didn't exist; for PR inputs the map said it should exist but the walk
    # disagreed (edge case — possible if Notes.txt is malformed).
    for kind, value in requested_items:
        if kind == "checkin" and value not in found_checkins:
            if value not in missing:
                missing.append(value)

    included = sorted(found_checkins)

    return ForDevNotesResult(
        text=text,
        requested_ids=requested_display,
        included_ids=included,
        missing_ids=missing,
        pr_to_checkins=pr_to_checkins_used,
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
