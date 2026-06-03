"""
Abstract base class for any source of developer check-in notes.

A NoteSource knows how to:
  - Identify itself (name, branch)
  - Fetch raw notes text given a query (PR numbers or check-in IDs)
  - Report priority (lower number = higher priority when merging)

The fetch() output is the same Notes.txt-style text that the rest of the
pipeline already knows how to parse.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class FetchResult:
    """Result of fetching notes from a single source for a set of queries."""
    text: str                                   # Raw Notes.txt-style text
    matched_queries: dict[str, list[str]] = field(default_factory=dict)
    # Map of "query value" → list of check-in IDs that matched. Used so the
    # priority merger and UI can show what each query resolved to in each source.
    unmatched_queries: list[str] = field(default_factory=list)
    # Queries that returned no results in this source.
    source_name: str = ""
    error: str | None = None
    # Non-None if the fetch failed. text/matched will be empty in that case.


class NoteSource:
    """
    A pluggable source of developer notes.

    Subclasses must implement fetch(). Everything else (priority comparison,
    name, branch label) is metadata used by the merger and UI.
    """

    def __init__(self, name: str, branch: str, priority: int = 100):
        self.name = name
        self.branch = branch
        self.priority = priority  # Lower = higher priority

    def fetch(self, queries: Iterable[str]) -> FetchResult:
        """
        Fetch raw notes text from this source for the given queries.

        Args:
            queries: Mixed iterable of check-in IDs ("0.4091") and PR numbers
                     ("PR-215320"). Subclasses decide how to interpret each.

        Returns:
            A FetchResult. On error, return a FetchResult with error set
            rather than raising — the merger should be able to fall back to
            other sources gracefully.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} branch={self.branch!r} priority={self.priority}>"
