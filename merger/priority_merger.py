"""
Priority merger — combines results from multiple NoteSources using
'ultimate fallback' semantics.

Strategy:
  1. Sort sources by priority (lower number = higher priority).
  2. Try the first source with all queries.
  3. If it returns ZERO matched queries (or only an error), fall back to
     the next source. Repeat until one source returns at least one match,
     or all sources are exhausted.
  4. The chosen source is the sole contributor of notes.

This is intentionally simpler than 'per-query fallback' (where some PRs
might come from one source and others from another). The simpler model is
predictable: every note in this run came from the same branch, so users
can reason about it as a single coherent release.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable

from sources.base import NoteSource, FetchResult


@dataclass
class MergedResult:
    """Final output after walking the priority chain."""
    text: str = ""
    chosen_source: str | None = None   # Name of the source that produced the output
    chosen_branch: str | None = None   # Branch label of the chosen source
    matched_queries: dict[str, list[str]] = field(default_factory=dict)
    unmatched_queries: list[str] = field(default_factory=list)
    # Per-source diagnostics for the UI: shows what was tried and why each
    # source did/didn't win. Always populated, even on success.
    attempts: list[dict] = field(default_factory=list)


def merge_with_priority_fallback(
    sources: Iterable[NoteSource],
    queries: Iterable[str],
) -> MergedResult:
    """
    Try each source in priority order until one returns at least one match.

    Args:
        sources: Iterable of NoteSource instances.
        queries: Iterable of query strings (check-in IDs and/or PR numbers).

    Returns:
        A MergedResult populated from the first successful source, or empty
        if every source returned nothing.
    """
    sorted_sources = sorted(sources, key=lambda s: s.priority)
    queries = list(queries)

    attempts: list[dict] = []

    for src in sorted_sources:
        result: FetchResult = src.fetch(queries)
        attempt_record = {
            "source": src.name,
            "branch": src.branch,
            "priority": src.priority,
            "matched_count": len(result.matched_queries),
            "unmatched_count": len(result.unmatched_queries),
            "error": result.error,
        }
        attempts.append(attempt_record)

        # Skip sources that errored out
        if result.error:
            continue

        # Skip sources that matched nothing
        if not result.matched_queries:
            continue

        # First source with matches wins — return immediately
        return MergedResult(
            text=result.text,
            chosen_source=src.name,
            chosen_branch=src.branch,
            matched_queries=dict(result.matched_queries),
            unmatched_queries=list(result.unmatched_queries),
            attempts=attempts,
        )

    # Nothing matched anywhere
    return MergedResult(
        text="",
        chosen_source=None,
        chosen_branch=None,
        matched_queries={},
        unmatched_queries=queries,
        attempts=attempts,
    )
