"""
FileSource — reads raw notes from a local Notes.txt-style file.

This is the source that mirrors the existing manual workflow: the user
selects a Notes.txt file from disk and we use its contents directly.
"""

from __future__ import annotations
from pathlib import Path
import re

from sources.base import NoteSource, FetchResult


CHECKIN_ID_RE = re.compile(r'\b\d+\.\d+\b')
PR_RE = re.compile(r'\bPR-\d+\b', re.IGNORECASE)


class FileSource(NoteSource):
    """
    Notes source backed by a local file.

    The file is read in its entirety; queries are matched against the
    Checkin ID / PR Number lines in the file to determine which check-ins
    are present. Notes content is returned as-is — the downstream parser
    handles all the filtering.
    """

    def __init__(self, path: str | Path, branch: str, priority: int = 100,
                 name: str | None = None):
        self.path = Path(path)
        super().__init__(
            name=name or f"file:{self.path.name}",
            branch=branch,
            priority=priority,
        )

    def fetch(self, queries):
        try:
            text = self.path.read_text(encoding="utf-8", errors="ignore")
        except (FileNotFoundError, OSError) as e:
            return FetchResult(
                text="",
                source_name=self.name,
                error=f"Could not read {self.path}: {e}",
                unmatched_queries=list(queries),
            )

        queries = list(queries)
        matched: dict[str, list[str]] = {}
        unmatched: list[str] = []

        # Build a quick index from the file: PR -> [checkin ids], and the
        # set of checkin ids present
        pr_to_checkins: dict[str, list[str]] = {}
        present_checkins: set[str] = set()
        current_checkin: str | None = None

        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("Checkin ID:"):
                m = CHECKIN_ID_RE.search(stripped)
                current_checkin = m.group() if m else None
                if current_checkin:
                    present_checkins.add(current_checkin)
            elif current_checkin and stripped.startswith("PR Number(s):"):
                for prm in PR_RE.finditer(stripped):
                    pr = "PR-" + prm.group().split("-", 1)[1]
                    pr_to_checkins.setdefault(pr, []).append(current_checkin)

        # Match each query
        for q in queries:
            if PR_RE.fullmatch(q):
                # Normalize case
                canonical = "PR-" + q.split("-", 1)[1]
                hits = pr_to_checkins.get(canonical, [])
                if hits:
                    matched[canonical] = hits
                else:
                    unmatched.append(q)
            elif CHECKIN_ID_RE.fullmatch(q):
                if q in present_checkins:
                    matched[q] = [q]
                else:
                    unmatched.append(q)
            else:
                unmatched.append(q)

        return FetchResult(
            text=text,
            matched_queries=matched,
            unmatched_queries=unmatched,
            source_name=self.name,
        )
