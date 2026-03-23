"""Encrypted vault: SQLite + AES-256-GCM encryption."""

import os
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .crypto import encrypt, decrypt

DEFAULT_VAULT_DIR = Path.home() / ".snipvault"
DEFAULT_DB_NAME = "vault.db"


def _get_db_path() -> Path:
    vault_dir = Path(os.environ.get("SNIPVAULT_DIR", str(DEFAULT_VAULT_DIR)))
    vault_dir.mkdir(parents=True, exist_ok=True)
    return vault_dir / DEFAULT_DB_NAME


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and FTS5."""
    path = db_path or _get_db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Initialize the vault database schema."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS snippets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS snippets_fts USING fts5(
            title, content, tags, language,
            content='snippets',
            content_rowid='id',
            tokenize='porter unicode61'
        );

        CREATE TRIGGER IF NOT EXISTS snippets_ai AFTER INSERT ON snippets BEGIN
            INSERT INTO snippets_fts(rowid, title, content, tags, language)
            VALUES (new.id, new.title, new.content, new.tags, new.language);
        END;

        CREATE TRIGGER IF NOT EXISTS snippets_ad AFTER DELETE ON snippets BEGIN
            INSERT INTO snippets_fts(snippets_fts, rowid, title, content, tags, language)
            VALUES ('delete', old.id, old.title, old.content, old.tags, old.language);
        END;

        CREATE TRIGGER IF NOT EXISTS snippets_au AFTER UPDATE ON snippets BEGIN
            INSERT INTO snippets_fts(snippets_fts, rowid, title, content, tags, language)
            VALUES ('delete', old.id, old.title, old.content, old.tags, old.language);
            INSERT INTO snippets_fts(rowid, title, content, tags, language)
            VALUES (new.id, new.title, new.content, new.tags, new.language);
        END;
    """)
    conn.commit()


class Vault:
    """Encrypted snippet vault backed by SQLite."""

    def __init__(self, passphrase: str, db_path: Optional[Path] = None):
        self.passphrase = passphrase
        self.conn = get_connection(db_path)
        init_db(self.conn)

    def close(self):
        self.conn.close()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add(
        self,
        title: str,
        content: str,
        language: str = "",
        tags: Optional[list[str]] = None,
    ) -> int:
        """Add an encrypted snippet. Returns the snippet ID."""
        now = self._now()
        encrypted_content = encrypt(content, self.passphrase)
        tags_json = json.dumps(tags or [])
        cursor = self.conn.execute(
            """INSERT INTO snippets (title, content, language, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (title, encrypted_content, language, tags_json, now, now),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get(self, snippet_id: int) -> Optional[dict]:
        """Get a snippet by ID, decrypting its content."""
        row = self.conn.execute(
            "SELECT * FROM snippets WHERE id = ?", (snippet_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_all(
        self,
        language: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """List snippets with optional filters. Content not decrypted for speed."""
        query = "SELECT id, title, language, tags, created_at, updated_at FROM snippets WHERE 1=1"
        params: list = []
        if language:
            query += " AND language = ?"
            params.append(language)
        if tag:
            query += " AND tags LIKE ?"
            params.append(f'%"{tag}"%')
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "language": r["language"],
                "tags": json.loads(r["tags"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def update(
        self,
        snippet_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        language: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> bool:
        """Update a snippet. Returns True if found."""
        existing = self.conn.execute(
            "SELECT * FROM snippets WHERE id = ?", (snippet_id,)
        ).fetchone()
        if not existing:
            return False
        now = self._now()
        new_title = title if title is not None else existing["title"]
        new_content = (
            encrypt(content, self.passphrase)
            if content is not None
            else existing["content"]
        )
        new_language = language if language is not None else existing["language"]
        new_tags = json.dumps(tags) if tags is not None else existing["tags"]
        self.conn.execute(
            """UPDATE snippets SET title=?, content=?, language=?, tags=?, updated_at=?
               WHERE id=?""",
            (new_title, new_content, new_language, new_tags, now, snippet_id),
        )
        self.conn.commit()
        return True

    def delete(self, snippet_id: int) -> bool:
        """Delete a snippet. Returns True if found."""
        cursor = self.conn.execute(
            "DELETE FROM snippets WHERE id = ?", (snippet_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def export_all(self) -> list[dict]:
        """Export all snippets with decrypted content."""
        rows = self.conn.execute(
            "SELECT * FROM snippets ORDER BY id"
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def import_snippets(self, snippets: list[dict]) -> int:
        """Import snippets. Returns count imported."""
        count = 0
        for s in snippets:
            self.add(
                title=s["title"],
                content=s["content"],
                language=s.get("language", ""),
                tags=s.get("tags", []),
            )
            count += 1
        return count

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """Convert a DB row to dict with decrypted content."""
        try:
            content = decrypt(row["content"], self.passphrase)
        except Exception:
            content = "[decryption failed - wrong passphrase?]"
        return {
            "id": row["id"],
            "title": row["title"],
            "content": content,
            "language": row["language"],
            "tags": json.loads(row["tags"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
