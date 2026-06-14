from dotenv import load_dotenv

load_dotenv()

import uuid
from datetime import datetime

import streamlit as st

st.set_page_config(
    page_title="メンターチャット | AI投資メンター",
    page_icon="💬",
    layout="wide",
)

_MAX_INPUT_CHARS = 2_000
_DISCLAIMER_INLINE = (
    "⚠️ このチャットは **学習目的** のみです。"
    "AIの回答は投資アドバイスではありません。投資判断は自己責任で行ってください。"
)


@st.cache_resource
def _bootstrap():
    from core.logger import setup_logger
    from db.database import init_db
    setup_logger()
    init_db()


_bootstrap()


def _load_history(session_id: str):
    from db.chat_repository import get_session_history
    return get_session_history(session_id)


def _save_message(session_id: str, role: str, content: str):
    from db.chat_repository import add_message
    try:
        add_message(session_id, role, content)
    except Exception as e:
        st.toast(f"メッセージの保存に失敗しました: {e}", icon="⚠️")


def _get_sessions() -> list[str]:
    from db.chat_repository import get_all_sessions
    return get_all_sessions()


# ---- セッション初期化 ----
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "chat_initialized" not in st.session_state:
    st.session_state.chat_initialized = False

# ---- サイドバー: セッション管理 ----
with st.sidebar:
    st.markdown("### 💬 セッション管理")

    if st.button("➕ 新しい会話を開始", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.chat_initialized = False
        st.rerun()

    past_sessions = _get_sessions()
    current_id = st.session_state.session_id

    if past_sessions:
        st.markdown("**過去の会話**")
        for sid in past_sessions[:8]:
            label = f"📂 {sid[:8]}…"
            if sid == current_id:
                st.markdown(f"**▶ {label}** （現在）")
            else:
                if st.button(label, key=f"sess_{sid}", use_container_width=True):
                    st.session_state.session_id = sid
                    st.session_state.chat_initialized = False
                    st.rerun()

    st.divider()
    st.caption(_DISCLAIMER_INLINE)

# ---- メインUI ----
st.title("💬 メンターチャット")
st.info(_DISCLAIMER_INLINE, icon="⚠️")

session_id = st.session_state.session_id
history = _load_history(session_id)

# 会話履歴の表示
for msg in history:
    avatar = "🧑" if msg.role == "user" else "🤖"
    with st.chat_message(msg.role, avatar=avatar):
        st.markdown(msg.content)

# ウェルカムメッセージ（履歴が空の場合）
if not history:
    with st.chat_message("assistant", avatar="🤖"):
        st.markdown(
            "こんにちは！AI投資メンターです。\n\n"
            "投資・経済・市場について、どんなことでも質問してください。\n"
            "初心者向けに丁寧に解説します。\n\n"
            "**例えば…**\n"
            "- 「PERって何ですか？」\n"
            "- 「なぜ金利が上がると株価が下がるの？」\n"
            "- 「S&P500とは何ですか？」"
        )

# チャット入力
if prompt := st.chat_input(
    "投資・経済について質問してください…",
    max_chars=_MAX_INPUT_CHARS,
):
    # ユーザーメッセージ表示
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)
    _save_message(session_id, "user", prompt)

    # Claude に問い合わせ
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("考え中…"):
            from core.claude_client import ChatMessage as ClaudeMsg, chat as claude_chat

            claude_history = [
                ClaudeMsg(role=m.role, content=m.content) for m in history
            ]
            response = claude_chat(prompt, history=claude_history)

        st.markdown(response)
        _save_message(session_id, "assistant", response)

    st.rerun()

# ---- ノート生成 ----
if history:
    st.divider()
    col_note, col_del = st.columns([3, 1])

    with col_note:
        if st.button("📝 この会話からノートを生成", type="secondary"):
            history_text = "\n".join(
                f"{'ユーザー' if m.role == 'user' else 'AI'}: {m.content}"
                for m in history[-10:]
            )
            with st.spinner("ノートを生成中…"):
                from core.claude_client import generate_note_from_chat
                note_text = generate_note_from_chat(history_text)

            if note_text:
                # タイトルを1行目から抽出
                lines = note_text.strip().split("\n")
                title = lines[0].lstrip("#").strip() if lines else "チャットノート"
                title = title[:50] or "チャットノート"

                from db.notes_repository import add_note
                try:
                    note_id = add_note(
                        title=title,
                        content=note_text,
                        source="chat",
                        tags=["チャット", "自動生成"],
                    )
                    st.success(f"ノートを保存しました（📝 学習ノートページで確認できます）")
                except Exception as e:
                    st.error(f"ノートの保存に失敗しました: {e}")
            else:
                st.warning("ノートの生成に失敗しました。ANTHROPIC_API_KEY を確認してください。")

    with col_del:
        if st.button("🗑️ この会話を削除", type="secondary"):
            from db.chat_repository import delete_session
            delete_session(session_id)
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.chat_initialized = False
            st.rerun()

# ---- フッター ----
st.divider()
st.caption(
    "⚠️ **免責事項** | "
    "本アプリは投資教育・学習を目的としています。"
    "AIの解説は学習補助であり、投資アドバイスではありません。"
    "投資判断は必ずご自身の責任で行ってください。"
)
