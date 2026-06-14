import os
import time
from dataclasses import dataclass
from typing import Optional

import anthropic
from loguru import logger

from core.prompts import (
    DAILY_THEME_SYSTEM,
    DAILY_THEME_USER_TEMPLATE,
    MENTOR_SYSTEM,
    NOTE_GENERATION_SYSTEM,
    NOTE_GENERATION_USER_TEMPLATE,
    NEWS_SUMMARY_SYSTEM,
    NEWS_SUMMARY_USER_TEMPLATE,
)

# --------------------------------------------------------------------------
# 定数
# --------------------------------------------------------------------------

_DEFAULT_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
_TIMEOUT_SECONDS = 30.0
_MAX_RETRIES = 2
_MAX_USER_INPUT_CHARS = 2_000   # セキュリティ方針：ユーザー入力の上限
_MAX_HISTORY_MESSAGES = 20      # 直近N件のみ送信（コスト・速度のバランス）
_DEFAULT_MAX_TOKENS = 1_024


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class ClaudeResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int


# --------------------------------------------------------------------------
# クライアント初期化
# --------------------------------------------------------------------------

def _build_client() -> Optional[anthropic.Anthropic]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY is not set.")
        return None
    try:
        return anthropic.Anthropic(
            api_key=api_key,
            timeout=_TIMEOUT_SECONDS,
            max_retries=_MAX_RETRIES,
        )
    except Exception as e:
        logger.error("Failed to initialize Anthropic client: {}", e)
        return None


# --------------------------------------------------------------------------
# 内部ユーティリティ
# --------------------------------------------------------------------------

def _sanitize(text: str, max_chars: int = _MAX_USER_INPUT_CHARS) -> str:
    """ユーザー入力の長さを制限する。"""
    return text[:max_chars]


def _call(
    client: anthropic.Anthropic,
    system: str,
    messages: list[dict],
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    model: str = _DEFAULT_MODEL,
) -> ClaudeResponse:
    """API呼び出しの共通処理。ライブラリのリトライ機能（max_retries=2）を利用。"""
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )

    content = response.content[0].text if response.content else ""
    if not content.strip():
        raise ValueError("Claude returned empty response")

    return ClaudeResponse(
        content=content,
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


def _error_response(reason: str) -> str:
    logger.error("Claude client error: {}", reason)
    return f"申し訳ありません。現在AIに接続できません。しばらくしてからもう一度お試しください。（{reason}）"


# --------------------------------------------------------------------------
# 公開API
# --------------------------------------------------------------------------

def chat(
    user_message: str,
    history: Optional[list[ChatMessage]] = None,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> str:
    """
    メンターチャット。会話履歴を含めてClaudeに送信する。

    Args:
        user_message: ユーザーの質問（最大2000文字に切り詰め）
        history: 過去の会話履歴（直近 _MAX_HISTORY_MESSAGES 件を使用）
        max_tokens: 生成するトークン数の上限

    Returns:
        Claudeの回答テキスト。エラー時はユーザー向けメッセージ。
    """
    client = _build_client()
    if client is None:
        return _error_response("APIキーが設定されていません")

    safe_input = _sanitize(user_message)
    if not safe_input.strip():
        return "質問を入力してください。"

    history = history or []
    recent = history[-_MAX_HISTORY_MESSAGES:]

    messages: list[dict] = [
        {"role": msg.role, "content": msg.content}
        for msg in recent
    ]
    messages.append({"role": "user", "content": safe_input})

    try:
        result = _call(client, MENTOR_SYSTEM, messages, max_tokens=max_tokens)
        logger.info(
            "chat() ok: input_tokens={} output_tokens={}",
            result.input_tokens, result.output_tokens,
        )
        return result.content
    except anthropic.APIConnectionError as e:
        return _error_response(f"接続エラー: {e}")
    except anthropic.RateLimitError:
        return _error_response("APIレート制限に達しました。少し待ってから再試行してください")
    except anthropic.APIStatusError as e:
        return _error_response(f"APIエラー (status={e.status_code})")
    except ValueError as e:
        return _error_response(str(e))
    except Exception as e:
        logger.exception("Unexpected error in chat()")
        return _error_response("予期しないエラーが発生しました")


def summarize_news(
    title: str,
    description: str,
    source: str,
    max_tokens: int = 512,
) -> str:
    """
    ニュース記事を初心者向けに要約する。

    Returns:
        要約テキスト。エラー時は空文字列。
    """
    client = _build_client()
    if client is None:
        return ""

    user_content = NEWS_SUMMARY_USER_TEMPLATE.format(
        title=_sanitize(title, 500),
        description=_sanitize(description, 1_000),
        source=_sanitize(source, 100),
    )

    try:
        result = _call(
            client,
            NEWS_SUMMARY_SYSTEM,
            [{"role": "user", "content": user_content}],
            max_tokens=max_tokens,
        )
        logger.info("summarize_news() ok: input_tokens={}", result.input_tokens)
        return result.content
    except Exception as e:
        logger.error("summarize_news() failed: {}", e)
        return ""


def suggest_daily_theme(
    progress_summary: str,
    market_summary: str,
    news_headlines: str,
    max_tokens: int = 768,
) -> str:
    """
    学習進捗と市場状況から今日の学習テーマを提案する。

    Returns:
        提案テキスト。エラー時はフォールバック文字列。
    """
    client = _build_client()
    if client is None:
        return "今日も引き続き基礎から学んでいきましょう。学習ロードマップのSTAGE 1から始めることをおすすめします。"

    user_content = DAILY_THEME_USER_TEMPLATE.format(
        progress_summary=_sanitize(progress_summary, 500),
        market_summary=_sanitize(market_summary, 300),
        news_headlines=_sanitize(news_headlines, 500),
    )

    try:
        result = _call(
            client,
            DAILY_THEME_SYSTEM,
            [{"role": "user", "content": user_content}],
            max_tokens=max_tokens,
        )
        logger.info("suggest_daily_theme() ok: input_tokens={}", result.input_tokens)
        return result.content
    except Exception as e:
        logger.error("suggest_daily_theme() failed: {}", e)
        return "今日も引き続き基礎から学んでいきましょう。学習ロードマップのSTAGE 1から始めることをおすすめします。"


def generate_note_from_chat(
    chat_history_text: str,
    max_tokens: int = 1_024,
) -> str:
    """
    チャット履歴から学習ノートを自動生成する。

    Args:
        chat_history_text: 「ユーザー: ...\nAI: ...\n」形式のチャット履歴テキスト

    Returns:
        ノートテキスト。エラー時は空文字列。
    """
    client = _build_client()
    if client is None:
        return ""

    user_content = NOTE_GENERATION_USER_TEMPLATE.format(
        chat_history=_sanitize(chat_history_text, 4_000),
    )

    try:
        result = _call(
            client,
            NOTE_GENERATION_SYSTEM,
            [{"role": "user", "content": user_content}],
            max_tokens=max_tokens,
        )
        logger.info("generate_note_from_chat() ok: input_tokens={}", result.input_tokens)
        return result.content
    except Exception as e:
        logger.error("generate_note_from_chat() failed: {}", e)
        return ""
