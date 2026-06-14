from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from db.database import get_connection

_VALID_STATUSES = {"not_started", "in_progress", "completed"}


@dataclass
class ProgressRecord:
    id: int
    stage_id: str
    status: str
    quiz_score: Optional[int]
    quiz_total: Optional[int]
    completed_at: Optional[datetime]
    updated_at: datetime

    @property
    def quiz_rate(self) -> Optional[float]:
        if self.quiz_score is None or not self.quiz_total:
            return None
        return self.quiz_score / self.quiz_total * 100


def _validate_status(status: str) -> None:
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {_VALID_STATUSES}")


def _validate_stage_id(stage_id: str) -> None:
    if not stage_id or not stage_id.strip():
        raise ValueError("stage_id must not be empty")


def _validate_quiz(score: Optional[int], total: Optional[int]) -> None:
    if score is None and total is None:
        return
    if score is not None and score < 0:
        raise ValueError("quiz_score must not be negative")
    if total is not None and total <= 0:
        raise ValueError("quiz_total must be positive")
    if score is not None and total is not None and score > total:
        raise ValueError("quiz_score must not exceed quiz_total")


def _row_to_record(row) -> ProgressRecord:
    return ProgressRecord(
        id=row["id"],
        stage_id=row["stage_id"],
        status=row["status"],
        quiz_score=row["quiz_score"],
        quiz_total=row["quiz_total"],
        completed_at=(
            datetime.fromisoformat(str(row["completed_at"]))
            if row["completed_at"]
            else None
        ),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )


def upsert_progress(
    stage_id: str,
    status: str,
    quiz_score: Optional[int] = None,
    quiz_total: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> None:
    _validate_stage_id(stage_id)
    _validate_status(status)
    _validate_quiz(quiz_score, quiz_total)

    completed_at = (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "completed" else None
    )

    try:
        with get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO learning_progress
                    (stage_id, status, quiz_score, quiz_total, completed_at, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(stage_id) DO UPDATE SET
                    status       = excluded.status,
                    quiz_score   = excluded.quiz_score,
                    quiz_total   = excluded.quiz_total,
                    completed_at = CASE
                        WHEN excluded.status = 'completed' THEN excluded.completed_at
                        ELSE learning_progress.completed_at
                    END,
                    updated_at   = CURRENT_TIMESTAMP
                """,
                (stage_id, status, quiz_score, quiz_total, completed_at),
            )
        logger.debug("Upserted progress stage_id={} status={}", stage_id, status)
    except Exception as e:
        logger.error("Failed to upsert progress for {}: {}", stage_id, e)
        raise


def get_progress(
    stage_id: str,
    db_path: Optional[Path] = None,
) -> Optional[ProgressRecord]:
    try:
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM learning_progress WHERE stage_id = ?",
                (stage_id,),
            ).fetchone()
        return _row_to_record(row) if row else None
    except Exception as e:
        logger.error("Failed to get progress for {}: {}", stage_id, e)
        return None


def get_all_progress(db_path: Optional[Path] = None) -> list[ProgressRecord]:
    try:
        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM learning_progress ORDER BY stage_id ASC"
            ).fetchall()
        return [_row_to_record(r) for r in rows]
    except Exception as e:
        logger.error("Failed to get all progress: {}", e)
        return []


def get_completion_summary(db_path: Optional[Path] = None) -> dict:
    try:
        with get_connection(db_path) as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*)                                        AS total,
                    SUM(CASE WHEN status='completed' THEN 1 END)   AS completed,
                    SUM(CASE WHEN status='in_progress' THEN 1 END) AS in_progress
                FROM learning_progress
                """
            ).fetchone()
        return {
            "total": row["total"] or 0,
            "completed": row["completed"] or 0,
            "in_progress": row["in_progress"] or 0,
        }
    except Exception as e:
        logger.error("Failed to get completion summary: {}", e)
        return {"total": 0, "completed": 0, "in_progress": 0}
