from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from db.database import get_connection

_VALID_ROLES = {"user", "assistant"}
_MAX_CONTENT_LENGTH = 20_000  # DB保存上限（UIの2000文字制限とは別）


@dataclass
class ChatMessage:
    id: int
    session_id: str
    role: str
    content: str
    created_at: datetime


def _validate_role(role: str) -> None:
    if role not in _VALID_ROLES:
        raise ValueError(f"Invalid role '{role}'. Must be one of {_VALID_ROLES}")


def _validate_content(content: str) -> None:
    if not content or not content.strip():
        raise ValueError("Content must not be empty")
    if len(content) > _MAX_CONTENT_LENGTH:
        raise ValueError(f"Content exceeds max length of {_MAX_CONTENT_LENGTH}")


def _row_to_message(row) -> ChatMessage:
    return ChatMessage(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def add_message(
    session_id: str,
    role: str,
    content: str,
    db_path: Optional[Path] = None,
) -> int:
    _validate_role(role)
    _validate_content(content)
    if not session_id or not session_id.strip():
        raise ValueError("session_id must not be empty")

    try:
        with get_connection(db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content.strip()),
            )
            new_id = cursor.lastrowid
        logger.debug("Added chat message id={} session={} role={}", new_id, session_id, role)
        return new_id
    except Exception as e:
        logger.error("Failed to add chat message: {}", e)
        raise


def get_session_history(
    session_id: str,
    limit: int = 100,
    db_path: Optional[Path] = None,
) -> list[ChatMessage]:
    if not session_id:
        return []
    try:
        with get_connection(db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, role, content, created_at
                FROM chat_history
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [_row_to_message(r) for r in rows]
    except Exception as e:
        logger.error("Failed to get session history: {}", e)
        return []


def get_all_sessions(db_path: Optional[Path] = None) -> list[str]:
    try:
        with get_connection(db_path) as conn:
            rows = conn.execute(
                """
                SELECT session_id
                FROM chat_history
                GROUP BY session_id
                ORDER BY MAX(created_at) DESC
                """
            ).fetchall()
        return [r["session_id"] for r in rows]
    except Exception as e:
        logger.error("Failed to get sessions: {}", e)
        return []


def delete_session(session_id: str, db_path: Optional[Path] = None) -> int:
    if not session_id:
        return 0
    try:
        with get_connection(db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM chat_history WHERE session_id = ?",
                (session_id,),
            )
            count = cursor.rowcount
        logger.info("Deleted {} messages for session {}", count, session_id)
        return count
    except Exception as e:
        logger.error("Failed to delete session {}: {}", session_id, e)
        raise
