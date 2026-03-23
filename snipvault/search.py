"""Full-text search: SQLite FTS5 on title+tags+content with fuzzy matching."""

import json
import re
from datetime import datetime
from typing import Optional

from .vault import Vault


def _fts5_escape(query: str) -> str:
    """Escape special FTS5 characters and build a search query."""
    # Remove FTS5 special chars except quotes and *
    cleaned = re.sub(r'[^\w\s"*]', " ", query)
    tokens = cleaned.split()
    if not tokens:
        return '""'
    # Add prefix matching wildcard for partial matches
    parts = []
    for t in tokens:
        if not t.startswith('"'):
            parts.append(f"{t}*")
        else:
            parts.append(t)
    return " OR ".join(parts)


def search_snippets(
    vault: Vault,
    query: str,
    language: Optional[str] = None,
    tags: Optional[list[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Search snippets using FTS5 full-text search.

    Args:
        vault: Vault instance
        query: Search query string
        language: Filter by programming language
        tags: Filter by tags (AND logic)
        date_from: ISO date string lower bound
        date_to: ISO date string upper bound
        limit: Max results

    Returns:
        List of matching snippets (with decrypted content) ranked by relevance.
    """
    fts_query = _fts5_escape(query)

    sql = """
        SELECT s.*, snippets_fts.rank
        FROM snippets_fts
        JOIN snippets s ON s.id = snippets_fts.rowid
        WHERE snippets_fts MATCH ?
    """
    params: list = [fts_query]

    if language:
        sql += " AND s.language = ?"
        params.append(language)

    if tags:
        for tag in tags:
            sql += " AND s.tags LIKE ?"
            params.append(f'%"{tag}"%')

    if date_from:
        sql += " AND s.created_at >= ?"
        params.append(date_from)

    if date_to:
        sql += " AND s.created_at <= ?"
        params.append(date_to)

    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    rows = vault.conn.execute(sql, params).fetchall()
    results = []
    for r in rows:
        results.append(vault._row_to_dict(r))
    return results


def fuzzy_search(
    vault: Vault,
    query: str,
    threshold: float = 0.4,
    limit: int = 20,
) -> list[dict]:
    """Fuzzy search using trigram similarity on titles.

    Falls back to LIKE-based matching when FTS5 doesn't find results.
    """
    # First try FTS5
    fts_results = search_snippets(vault, query, limit=limit)
    if fts_results:
        return fts_results

    # Fall back to LIKE-based fuzzy matching
    pattern = f"%{'%'.join(query.lower())}%"
    rows = vault.conn.execute(
        """SELECT * FROM snippets
           WHERE LOWER(title) LIKE ? OR LOWER(tags) LIKE ?
           ORDER BY updated_at DESC LIMIT ?""",
        (pattern, pattern, limit),
    ).fetchall()

    results = []
    for r in rows:
        score = _similarity(query.lower(), r["title"].lower())
        if score >= threshold:
            entry = vault._row_to_dict(r)
            entry["_score"] = round(score, 3)
            results.append(entry)

    results.sort(key=lambda x: x.get("_score", 0), reverse=True)
    return results


def _similarity(a: str, b: str) -> float:
    """Simple trigram similarity between two strings."""
    if not a or not b:
        return 0.0
    tri_a = set(_trigrams(a))
    tri_b = set(_trigrams(b))
    if not tri_a or not tri_b:
        return 0.0
    intersection = tri_a & tri_b
    union = tri_a | tri_b
    return len(intersection) / len(union)


def _trigrams(s: str) -> list[str]:
    """Generate character trigrams."""
    padded = f"  {s} "
    return [padded[i : i + 3] for i in range(len(padded) - 2)]
