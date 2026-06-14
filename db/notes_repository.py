import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from db.database import get_connection

_VALID_SOURCES = {"chat", "manual"}
_MAX_TITLE_LENGTH = 200
_MAX_CONTENT_LENGTH = 50_000
_MAX_TAGS = 20


@dataclass
class Note:
    id: int
    title: str
    content: str
    source: Optional[str]
    tags: list[str]
    created_at: datetime
    updated_at: datetime


def _validate_title(title: str) -> None:
    if not title or not title.strip():
        raise ValueError("title must not be empty")
    if len(title) > _MAX_TITLE_LENGTH:
        raise ValueError(f"title exceeds max length of {_MAX_TITLE_LENGTH}")


def _validate_content(content: str) -> None:
    if not content or not content.strip():
        raise ValueError("content must not be empty")
    if len(content) > _MAX_CONTENT_LENGTH:
        raise ValueError(f"content exceeds max length of {_MAX_CONTENT_LENGTH}")


def _validate_source(source: Optional[str]) -> None:
    if source is not None and source not in _VALID_SOURCES:
        raise ValueError(f"Invalid source '{source}'. Must be one of {_VALID_SOURCES} or None")


def _validate_tags(tags: list[str]) -> None:
    if len(tags) > _MAX_TAGS:
        raise ValueError(f"Too many tags (max {_MAX_TAGS})")
    for tag in tags:
        if not isinstance(tag, str) or not tag.strip():
            raise ValueError("Each tag must be a non-empty string")


def _row_to_note(row) -> Note:
    tags_raw = row["tags"] or "[]"
    try:
        tags = json.loads(tags_raw)
    except json.JSONDecodeError:
        tags = []
    return Note(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        source=row["source"],
        tags=tags,
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )


def add_note(
    title: str,
    content: str,
    source: Optional[str] = None,
    tags: Optional[list[str]] = None,
    db_path: Optional[Path] = None,
) -> int:
    tags = tags or []
    _validate_title(title)
    _validate_content(content)
    _validate_source(source)
    _validate_tags(tags)

    tags_json = json.dumps(tags, ensure_ascii=False)
    try:
        with get_connection(db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO notes (title, content, source, tags)
                VALUES (?, ?, ?, ?)
                """,
                (title.strip(), content.strip(), source, tags_json),
            )
            new_id = cursor.lastrowid
        logger.debug("Added note id={} source={}", new_id, source)
        return new_id
    except Exception as e:
        logger.error("Failed to add note: {}", e)
        raise


def get_note(note_id: int, db_path: Optional[Path] = None) -> Optional[Note]:
    try:
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM notes WHERE id = ?", (note_id,)
            ).fetchone()
        return _row_to_note(row) if row else None
    except Exception as e:
        logger.error("Failed to get note {}: {}", note_id, e)
        return None


def get_all_notes(
    source: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> list[Note]:
    try:
        with get_connection(db_path) as conn:
            if source:
                rows = conn.execute(
                    "SELECT * FROM notes WHERE source = ? ORDER BY created_at DESC",
                    (source,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM notes ORDER BY created_at DESC"
                ).fetchall()
        return [_row_to_note(r) for r in rows]
    except Exception as e:
        logger.error("Failed to get notes: {}", e)
        return []


def search_notes(keyword: str, db_path: Optional[Path] = None) -> list[Note]:
    if not keyword or not keyword.strip():
        return []
    pattern = f"%{keyword.strip()}%"
    try:
        with get_connection(db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM notes
                WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                ORDER BY updated_at DESC
                """,
                (pattern, pattern, pattern),
            ).fetchall()
        return [_row_to_note(r) for r in rows]
    except Exception as e:
        logger.error("Failed to search notes: {}", e)
        return []


def update_note(
    note_id: int,
    title: Optional[str] = None,
    content: Optional[str] = None,
    tags: Optional[list[str]] = None,
    db_path: Optional[Path] = None,
) -> bool:
    if title is None and content is None and tags is None:
        return False

    existing = get_note(note_id, db_path)
    if existing is None:
        return False

    new_title = title.strip() if title is not None else existing.title
    new_content = content.strip() if content is not None else existing.content
    new_tags = tags if tags is not None else existing.tags

    _validate_title(new_title)
    _validate_content(new_content)
    _validate_tags(new_tags)

    tags_json = json.dumps(new_tags, ensure_ascii=False)
    try:
        with get_connection(db_path) as conn:
            conn.execute(
                """
                UPDATE notes
                SET title = ?, content = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_title, new_content, tags_json, note_id),
            )
        logger.debug("Updated note id={}", note_id)
        return True
    except Exception as e:
        logger.error("Failed to update note {}: {}", note_id, e)
        raise


def delete_note(note_id: int, db_path: Optional[Path] = None) -> bool:
    try:
        with get_connection(db_path) as conn:
            cursor = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug("Deleted note id={}", note_id)
        return deleted
    except Exception as e:
        logger.error("Failed to delete note {}: {}", note_id, e)
        raise
