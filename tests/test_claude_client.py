"""
claude_client.py のユニットテスト。
Anthropic API はすべてモックし、ネットワーク不要で実行できる。
"""

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from core.claude_client import (
    ChatMessage,
    ClaudeResponse,
    _sanitize,
    chat,
    generate_note_from_chat,
    suggest_daily_theme,
    summarize_news,
)


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _make_response(text: str = "テスト回答です。") -> MagicMock:
    """anthropic.messages.create() の戻り値を模倣するモックを生成する。"""
    content_block = MagicMock()
    content_block.text = text

    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 50

    response = MagicMock()
    response.content = [content_block]
    response.model = "claude-sonnet-4-20250514"
    response.usage = usage
    return response


def _make_client_mock(response_text: str = "テスト回答です。") -> MagicMock:
    """anthropic.Anthropic クライアントのモックを生成する。"""
    client = MagicMock(spec=anthropic.Anthropic)
    client.messages.create.return_value = _make_response(response_text)
    return client


# ---------------------------------------------------------------------------
# _sanitize
# ---------------------------------------------------------------------------

class TestSanitize:
    def test_short_text_unchanged(self):
        assert _sanitize("hello", 100) == "hello"

    def test_truncates_to_max_chars(self):
        text = "a" * 3000
        result = _sanitize(text, 2000)
        assert len(result) == 2000

    def test_empty_string(self):
        assert _sanitize("", 2000) == ""

    def test_exactly_at_limit_unchanged(self):
        text = "a" * 2000
        assert _sanitize(text, 2000) == text


# ---------------------------------------------------------------------------
# chat()
# ---------------------------------------------------------------------------

class TestChat:
    @patch("core.claude_client._build_client")
    def test_returns_response_text(self, mock_build):
        mock_build.return_value = _make_client_mock("PERとは株価収益率です。")

        result = chat("PERとは何ですか？")

        assert "PERとは株価収益率" in result

    @patch("core.claude_client._build_client")
    def test_returns_error_message_when_no_client(self, mock_build):
        mock_build.return_value = None

        result = chat("PERとは何ですか？")

        assert "APIキーが設定されていません" in result

    @patch("core.claude_client._build_client")
    def test_empty_user_message_returns_prompt(self, mock_build):
        mock_build.return_value = _make_client_mock()

        result = chat("   ")

        assert "入力してください" in result
        mock_build.return_value.messages.create.assert_not_called()

    @patch("core.claude_client._build_client")
    def test_history_is_included_in_messages(self, mock_build):
        client_mock = _make_client_mock()
        mock_build.return_value = client_mock

        history = [
            ChatMessage(role="user", content="前の質問"),
            ChatMessage(role="assistant", content="前の回答"),
        ]
        chat("新しい質問", history=history)

        call_args = client_mock.messages.create.call_args
        messages = call_args.kwargs["messages"]
        # 履歴2件 + 新規1件 = 3件
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "前の質問"
        assert messages[-1]["content"] == "新しい質問"

    @patch("core.claude_client._build_client")
    def test_history_is_limited_to_max(self, mock_build):
        client_mock = _make_client_mock()
        mock_build.return_value = client_mock

        # 30件の履歴（上限 _MAX_HISTORY_MESSAGES=20 を超える）
        history = [
            ChatMessage(role="user" if i % 2 == 0 else "assistant", content=f"msg {i}")
            for i in range(30)
        ]
        chat("新しい質問", history=history)

        call_args = client_mock.messages.create.call_args
        messages = call_args.kwargs["messages"]
        # 20件 + 新規1件 = 21件
        assert len(messages) == 21

    @patch("core.claude_client._build_client")
    def test_user_input_is_sanitized(self, mock_build):
        client_mock = _make_client_mock()
        mock_build.return_value = client_mock

        long_input = "a" * 5000
        chat(long_input)

        call_args = client_mock.messages.create.call_args
        messages = call_args.kwargs["messages"]
        user_content = messages[-1]["content"]
        assert len(user_content) == 2000

    @patch("core.claude_client._build_client")
    def test_returns_error_on_api_connection_error(self, mock_build):
        client_mock = MagicMock(spec=anthropic.Anthropic)
        client_mock.messages.create.side_effect = anthropic.APIConnectionError(
            request=MagicMock()
        )
        mock_build.return_value = client_mock

        result = chat("質問")

        assert "接続エラー" in result

    @patch("core.claude_client._build_client")
    def test_returns_error_on_rate_limit(self, mock_build):
        client_mock = MagicMock(spec=anthropic.Anthropic)
        client_mock.messages.create.side_effect = anthropic.RateLimitError(
            message="rate limit", response=MagicMock(), body={}
        )
        mock_build.return_value = client_mock

        result = chat("質問")

        assert "レート制限" in result

    @patch("core.claude_client._build_client")
    def test_returns_error_on_api_status_error(self, mock_build):
        client_mock = MagicMock(spec=anthropic.Anthropic)
        client_mock.messages.create.side_effect = anthropic.APIStatusError(
            message="bad request",
            response=MagicMock(),
            body={},
        )
        mock_build.return_value = client_mock

        result = chat("質問")

        assert "APIエラー" in result

    @patch("core.claude_client._build_client")
    def test_returns_error_on_empty_response(self, mock_build):
        client_mock = _make_client_mock("")
        mock_build.return_value = client_mock

        result = chat("質問")

        assert "現在AIに接続できません" in result

    @patch("core.claude_client._build_client")
    def test_system_prompt_contains_disclaimer(self, mock_build):
        client_mock = _make_client_mock()
        mock_build.return_value = client_mock

        chat("質問")

        call_args = client_mock.messages.create.call_args
        system = call_args.kwargs["system"]
        assert "学習目的" in system
        assert "投資アドバイス" in system


# ---------------------------------------------------------------------------
# summarize_news()
# ---------------------------------------------------------------------------

class TestSummarizeNews:
    @patch("core.claude_client._build_client")
    def test_returns_summary_text(self, mock_build):
        mock_build.return_value = _make_client_mock("日銀が金利を引き上げました。")

        result = summarize_news("日銀利上げ", "概要テキスト", "nikkei.com")

        assert "日銀" in result

    @patch("core.claude_client._build_client")
    def test_returns_empty_when_no_client(self, mock_build):
        mock_build.return_value = None

        result = summarize_news("タイトル", "概要", "source")

        assert result == ""

    @patch("core.claude_client._build_client")
    def test_returns_empty_on_exception(self, mock_build):
        client_mock = MagicMock(spec=anthropic.Anthropic)
        client_mock.messages.create.side_effect = RuntimeError("network error")
        mock_build.return_value = client_mock

        result = summarize_news("タイトル", "概要", "source")

        assert result == ""

    @patch("core.claude_client._build_client")
    def test_inputs_are_sanitized(self, mock_build):
        client_mock = _make_client_mock()
        mock_build.return_value = client_mock

        summarize_news("a" * 1000, "b" * 2000, "c" * 200)

        call_args = client_mock.messages.create.call_args
        user_content = call_args.kwargs["messages"][0]["content"]
        # 各フィールドがそれぞれの上限内に収まっていること
        assert len(user_content) < 3000  # 500+1000+100 より短い


# ---------------------------------------------------------------------------
# suggest_daily_theme()
# ---------------------------------------------------------------------------

class TestSuggestDailyTheme:
    @patch("core.claude_client._build_client")
    def test_returns_theme_text(self, mock_build):
        mock_build.return_value = _make_client_mock("## 今日の学習テーマ\nPERの読み方")

        result = suggest_daily_theme("進捗なし", "日経38000円", "特になし")

        assert "テーマ" in result

    @patch("core.claude_client._build_client")
    def test_returns_fallback_when_no_client(self, mock_build):
        mock_build.return_value = None

        result = suggest_daily_theme("", "", "")

        assert "STAGE 1" in result
        assert len(result) > 0

    @patch("core.claude_client._build_client")
    def test_returns_fallback_on_exception(self, mock_build):
        client_mock = MagicMock(spec=anthropic.Anthropic)
        client_mock.messages.create.side_effect = RuntimeError("error")
        mock_build.return_value = client_mock

        result = suggest_daily_theme("", "", "")

        assert "STAGE 1" in result


# ---------------------------------------------------------------------------
# generate_note_from_chat()
# ---------------------------------------------------------------------------

class TestGenerateNoteFromChat:
    @patch("core.claude_client._build_client")
    def test_returns_note_text(self, mock_build):
        mock_build.return_value = _make_client_mock("## PERとは\n株価収益率のことです。")

        result = generate_note_from_chat("ユーザー: PERとは？\nAI: 株価収益率です。")

        assert len(result) > 0

    @patch("core.claude_client._build_client")
    def test_returns_empty_when_no_client(self, mock_build):
        mock_build.return_value = None

        result = generate_note_from_chat("チャット履歴")

        assert result == ""

    @patch("core.claude_client._build_client")
    def test_returns_empty_on_exception(self, mock_build):
        client_mock = MagicMock(spec=anthropic.Anthropic)
        client_mock.messages.create.side_effect = RuntimeError("error")
        mock_build.return_value = client_mock

        result = generate_note_from_chat("チャット履歴")

        assert result == ""

    @patch("core.claude_client._build_client")
    def test_long_chat_history_is_truncated(self, mock_build):
        client_mock = _make_client_mock()
        mock_build.return_value = client_mock

        long_history = "チャット内容\n" * 1000
        generate_note_from_chat(long_history)

        call_args = client_mock.messages.create.call_args
        user_content = call_args.kwargs["messages"][0]["content"]
        assert len(user_content) < len(long_history) + 100  # テンプレート分を考慮


# ---------------------------------------------------------------------------
# プロンプトの内容チェック（prompts.py との整合）
# ---------------------------------------------------------------------------

class TestPromptContents:
    def test_mentor_system_prohibits_investment_advice(self):
        from core.prompts import MENTOR_SYSTEM
        assert "投資アドバイス" in MENTOR_SYSTEM
        assert "銘柄推奨" in MENTOR_SYSTEM

    def test_mentor_system_requires_disclaimer(self):
        from core.prompts import MENTOR_SYSTEM
        assert "学習目的" in MENTOR_SYSTEM

    def test_mentor_system_mentions_next_step(self):
        from core.prompts import MENTOR_SYSTEM
        assert "次に学ぶべきこと" in MENTOR_SYSTEM

    def test_news_summary_template_has_placeholders(self):
        from core.prompts import NEWS_SUMMARY_USER_TEMPLATE
        formatted = NEWS_SUMMARY_USER_TEMPLATE.format(
            title="テスト", description="概要", source="reuters.com"
        )
        assert "テスト" in formatted
        assert "reuters.com" in formatted

    def test_daily_theme_template_has_placeholders(self):
        from core.prompts import DAILY_THEME_USER_TEMPLATE
        formatted = DAILY_THEME_USER_TEMPLATE.format(
            progress_summary="完了0件",
            market_summary="日経38000円",
            news_headlines="特になし",
        )
        assert "完了0件" in formatted

    def test_note_generation_template_has_placeholder(self):
        from core.prompts import NOTE_GENERATION_USER_TEMPLATE
        formatted = NOTE_GENERATION_USER_TEMPLATE.format(chat_history="テスト履歴")
        assert "テスト履歴" in formatted
