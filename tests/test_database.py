"""
データベース層のユニットテスト。
pytest の tmp_path を使った一時ファイルDBで実行する（接続をまたぐテストに対応）。
"""

from pathlib import Path

import pytest

from db.database import get_connection, get_market_cache, init_db, upsert_market_cache
from db.chat_repository import add_message, delete_session, get_all_sessions, get_session_history
from db.notes_repository import (
    add_note,
    delete_note,
    get_all_notes,
    get_note,
    search_notes,
    update_note,
)
from db.progress_repository import (
    get_all_progress,
    get_completion_summary,
    get_progress,
    upsert_progress,
)


# ---------------------------------------------------------------------------
# Fixture: テストごとに独立した一時DBファイルを用意する
# ---------------------------------------------------------------------------

@pytest.fixture()
def db(tmp_path) -> Path:
    """テストごとに新しいDBファイルを作り、スキーマを初期化して返す。"""
    db_path = tmp_path / "test_mentor.db"
    init_db(db_path)
    return db_path


# ---------------------------------------------------------------------------
# database.py
# ---------------------------------------------------------------------------

class TestInitDb:
    def test_creates_tables(self, db):
        with get_connection(db) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert {"chat_history", "learning_progress", "notes", "market_cache"} <= tables

    def test_idempotent(self, db):
        init_db(db)  # 2回目も例外なし


class TestMarketCache:
    def test_upsert_and_get(self, db):
        upsert_market_cache("^N225", {"price": 38000.0}, db)
        result = get_market_cache("^N225", expire_minutes=30, db_path=db)
        assert result == {"price": 38000.0}

    def test_returns_none_for_missing_ticker(self, db):
        assert get_market_cache("MISSING", db_path=db) is None

    def test_upsert_overwrites_existing(self, db):
        upsert_market_cache("^N225", {"price": 1.0}, db)
        upsert_market_cache("^N225", {"price": 2.0}, db)
        result = get_market_cache("^N225", db_path=db)
        assert result == {"price": 2.0}

    def test_expired_cache_returns_none(self, db):
        upsert_market_cache("^N225", {"price": 38000.0}, db)
        result = get_market_cache("^N225", expire_minutes=0, db_path=db)
        assert result is None


# ---------------------------------------------------------------------------
# chat_repository.py
# ---------------------------------------------------------------------------

class TestAddMessage:
    def test_add_user_message(self, db):
        msg_id = add_message("sess1", "user", "PERとは何ですか？", db)
        assert isinstance(msg_id, int) and msg_id > 0

    def test_add_assistant_message(self, db):
        msg_id = add_message("sess1", "assistant", "PERとは株価収益率です。", db)
        assert msg_id > 0

    def test_invalid_role_raises(self, db):
        with pytest.raises(ValueError, match="Invalid role"):
            add_message("sess1", "system", "content", db)

    def test_empty_content_raises(self, db):
        with pytest.raises(ValueError, match="empty"):
            add_message("sess1", "user", "", db)

    def test_whitespace_content_raises(self, db):
        with pytest.raises(ValueError, match="empty"):
            add_message("sess1", "user", "   ", db)

    def test_empty_session_id_raises(self, db):
        with pytest.raises(ValueError):
            add_message("", "user", "content", db)

    def test_content_is_stripped(self, db):
        add_message("sess1", "user", "  hello  ", db)
        msgs = get_session_history("sess1", db_path=db)
        assert msgs[0].content == "hello"


class TestGetSessionHistory:
    def test_returns_messages_in_order(self, db):
        add_message("sess1", "user", "質問1", db)
        add_message("sess1", "assistant", "回答1", db)
        add_message("sess1", "user", "質問2", db)

        msgs = get_session_history("sess1", db_path=db)

        assert len(msgs) == 3
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"
        assert msgs[2].content == "質問2"

    def test_returns_empty_for_unknown_session(self, db):
        assert get_session_history("no_such_session", db_path=db) == []

    def test_limit_parameter(self, db):
        for i in range(10):
            add_message("sess1", "user", f"msg {i}", db)
        msgs = get_session_history("sess1", limit=3, db_path=db)
        assert len(msgs) == 3

    def test_sessions_are_isolated(self, db):
        add_message("sess_a", "user", "Aの質問", db)
        add_message("sess_b", "user", "Bの質問", db)
        assert len(get_session_history("sess_a", db_path=db)) == 1
        assert len(get_session_history("sess_b", db_path=db)) == 1


class TestGetAllSessions:
    def test_lists_distinct_sessions(self, db):
        add_message("sess1", "user", "msg", db)
        add_message("sess2", "user", "msg", db)
        add_message("sess1", "user", "msg2", db)
        sessions = get_all_sessions(db)
        assert set(sessions) == {"sess1", "sess2"}

    def test_empty_when_no_messages(self, db):
        assert get_all_sessions(db) == []


class TestDeleteSession:
    def test_delete_removes_messages(self, db):
        add_message("sess1", "user", "msg", db)
        count = delete_session("sess1", db)
        assert count == 1
        assert get_session_history("sess1", db_path=db) == []

    def test_delete_nonexistent_session_returns_zero(self, db):
        assert delete_session("ghost", db) == 0


# ---------------------------------------------------------------------------
# progress_repository.py
# ---------------------------------------------------------------------------

class TestUpsertProgress:
    def test_insert_new_stage(self, db):
        upsert_progress("1-1", "not_started", db_path=db)
        rec = get_progress("1-1", db)
        assert rec is not None
        assert rec.status == "not_started"

    def test_update_existing_stage(self, db):
        upsert_progress("1-1", "not_started", db_path=db)
        upsert_progress("1-1", "in_progress", db_path=db)
        rec = get_progress("1-1", db)
        assert rec.status == "in_progress"

    def test_completed_sets_completed_at(self, db):
        upsert_progress("1-1", "completed", db_path=db)
        rec = get_progress("1-1", db)
        assert rec.completed_at is not None

    def test_not_completed_keeps_completed_at_none(self, db):
        upsert_progress("1-1", "not_started", db_path=db)
        rec = get_progress("1-1", db)
        assert rec.completed_at is None

    def test_invalid_status_raises(self, db):
        with pytest.raises(ValueError, match="Invalid status"):
            upsert_progress("1-1", "unknown", db_path=db)

    def test_empty_stage_id_raises(self, db):
        with pytest.raises(ValueError):
            upsert_progress("", "not_started", db_path=db)

    def test_quiz_score_exceeding_total_raises(self, db):
        with pytest.raises(ValueError):
            upsert_progress("1-1", "completed", quiz_score=4, quiz_total=3, db_path=db)

    def test_negative_quiz_score_raises(self, db):
        with pytest.raises(ValueError):
            upsert_progress("1-1", "completed", quiz_score=-1, quiz_total=3, db_path=db)

    def test_quiz_rate_computed_correctly(self, db):
        upsert_progress("1-1", "completed", quiz_score=2, quiz_total=3, db_path=db)
        rec = get_progress("1-1", db)
        assert rec.quiz_rate == pytest.approx(66.666, rel=1e-3)

    def test_quiz_rate_none_when_no_quiz(self, db):
        upsert_progress("1-1", "not_started", db_path=db)
        rec = get_progress("1-1", db)
        assert rec.quiz_rate is None


class TestGetProgress:
    def test_returns_none_for_unknown_stage(self, db):
        assert get_progress("9-9", db) is None


class TestGetAllProgress:
    def test_returns_all_records(self, db):
        upsert_progress("1-1", "completed", db_path=db)
        upsert_progress("1-2", "in_progress", db_path=db)
        records = get_all_progress(db)
        assert len(records) == 2

    def test_sorted_by_stage_id(self, db):
        upsert_progress("1-3", "not_started", db_path=db)
        upsert_progress("1-1", "not_started", db_path=db)
        upsert_progress("1-2", "not_started", db_path=db)
        records = get_all_progress(db)
        assert [r.stage_id for r in records] == ["1-1", "1-2", "1-3"]


class TestGetCompletionSummary:
    def test_empty_returns_zeros(self, db):
        summary = get_completion_summary(db)
        assert summary == {"total": 0, "completed": 0, "in_progress": 0}

    def test_counts_correctly(self, db):
        upsert_progress("1-1", "completed", db_path=db)
        upsert_progress("1-2", "in_progress", db_path=db)
        upsert_progress("1-3", "not_started", db_path=db)
        summary = get_completion_summary(db)
        assert summary["total"] == 3
        assert summary["completed"] == 1
        assert summary["in_progress"] == 1


# ---------------------------------------------------------------------------
# notes_repository.py
# ---------------------------------------------------------------------------

class TestAddNote:
    def test_add_manual_note(self, db):
        note_id = add_note("テストタイトル", "テスト内容", source="manual", db_path=db)
        assert note_id > 0

    def test_add_chat_note_with_tags(self, db):
        note_id = add_note("PERとは", "株価収益率の解説", source="chat",
                           tags=["PER", "指標"], db_path=db)
        note = get_note(note_id, db)
        assert note.tags == ["PER", "指標"]

    def test_empty_title_raises(self, db):
        with pytest.raises(ValueError, match="empty"):
            add_note("", "content", db_path=db)

    def test_empty_content_raises(self, db):
        with pytest.raises(ValueError, match="empty"):
            add_note("title", "", db_path=db)

    def test_invalid_source_raises(self, db):
        with pytest.raises(ValueError, match="Invalid source"):
            add_note("title", "content", source="web", db_path=db)

    def test_none_source_allowed(self, db):
        note_id = add_note("title", "content", source=None, db_path=db)
        note = get_note(note_id, db)
        assert note.source is None

    def test_tags_default_to_empty_list(self, db):
        note_id = add_note("title", "content", db_path=db)
        note = get_note(note_id, db)
        assert note.tags == []


class TestGetNote:
    def test_returns_none_for_missing_id(self, db):
        assert get_note(9999, db) is None


class TestGetAllNotes:
    def test_returns_all(self, db):
        add_note("A", "content A", db_path=db)
        add_note("B", "content B", db_path=db)
        notes = get_all_notes(db_path=db)
        assert len(notes) == 2

    def test_filter_by_source(self, db):
        add_note("A", "content", source="chat", db_path=db)
        add_note("B", "content", source="manual", db_path=db)
        chat_notes = get_all_notes(source="chat", db_path=db)
        assert len(chat_notes) == 1
        assert chat_notes[0].title == "A"


class TestSearchNotes:
    def test_finds_by_title(self, db):
        add_note("PER入門", "株価収益率とは", db_path=db)
        add_note("PBR入門", "株価純資産倍率とは", db_path=db)
        results = search_notes("PER", db)
        assert len(results) == 1
        assert results[0].title == "PER入門"

    def test_finds_by_content(self, db):
        add_note("指標まとめ", "PERとPBRの違いを解説", db_path=db)
        results = search_notes("PBRの違い", db)
        assert len(results) == 1

    def test_empty_keyword_returns_empty(self, db):
        add_note("title", "content", db_path=db)
        assert search_notes("", db) == []


class TestUpdateNote:
    def test_update_title(self, db):
        note_id = add_note("旧タイトル", "content", db_path=db)
        update_note(note_id, title="新タイトル", db_path=db)
        note = get_note(note_id, db)
        assert note.title == "新タイトル"

    def test_update_tags(self, db):
        note_id = add_note("title", "content", tags=["A"], db_path=db)
        update_note(note_id, tags=["A", "B"], db_path=db)
        note = get_note(note_id, db)
        assert note.tags == ["A", "B"]

    def test_returns_false_for_missing_note(self, db):
        assert update_note(9999, title="new", db_path=db) is False

    def test_returns_false_when_nothing_to_update(self, db):
        note_id = add_note("title", "content", db_path=db)
        assert update_note(note_id, db_path=db) is False


class TestDeleteNote:
    def test_delete_existing_note(self, db):
        note_id = add_note("title", "content", db_path=db)
        assert delete_note(note_id, db) is True
        assert get_note(note_id, db) is None

    def test_delete_nonexistent_note_returns_false(self, db):
        assert delete_note(9999, db) is False
