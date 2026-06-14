from dotenv import load_dotenv

load_dotenv()

import streamlit as st

st.set_page_config(
    page_title="学習ノート | AI投資メンター",
    page_icon="📝",
    layout="wide",
)


@st.cache_resource
def _bootstrap():
    from core.logger import setup_logger
    from db.database import init_db
    setup_logger()
    init_db()


_bootstrap()


def _get_notes(keyword: str = "", source: str = "all"):
    from db.notes_repository import get_all_notes, search_notes
    if keyword.strip():
        notes = search_notes(keyword)
    else:
        src = None if source == "all" else source
        notes = get_all_notes(source=src)
    return notes


def _format_date(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def _source_badge(source) -> str:
    return {"chat": "🤖 自動生成", "manual": "✏️ 手動"}.get(source or "", "📄 その他")


# ---- UI ----
st.title("📝 学習ノート")
st.caption("チャットから自動生成されたノートと、手動で追加したメモを管理します。")

tab_list, tab_add, tab_ai = st.tabs(["📋 ノート一覧", "✏️ ノートを追加", "🤖 チャットから生成"])

# ==============================
# Tab 1: ノート一覧
# ==============================
with tab_list:
    col_search, col_filter = st.columns([3, 1])
    with col_search:
        keyword = st.text_input("🔍 キーワード検索", placeholder="例: PER、金利、分散投資…")
    with col_filter:
        source_filter = st.selectbox(
            "絞り込み",
            options=["all", "chat", "manual"],
            format_func=lambda s: {"all": "すべて", "chat": "🤖 自動生成", "manual": "✏️ 手動"}[s],
        )

    notes = _get_notes(keyword, source_filter)

    if not notes:
        st.info(
            "ノートがまだありません。\n\n"
            "「✏️ ノートを追加」タブで手動追加するか、"
            "メンターチャットで会話後に「📝 ノートを生成」ボタンを使ってください。"
        )
    else:
        st.caption(f"{len(notes)} 件のノートが見つかりました")

        for note in notes:
            with st.container(border=True):
                head_col, badge_col, date_col = st.columns([4, 1, 1])
                with head_col:
                    st.markdown(f"**{note.title}**")
                with badge_col:
                    st.caption(_source_badge(note.source))
                with date_col:
                    st.caption(_format_date(note.updated_at))

                if note.tags:
                    tags_str = "　".join(f"`{t}`" for t in note.tags)
                    st.markdown(tags_str)

                # 本文プレビュー（最大200文字）
                preview = note.content[:200].replace("\n", " ")
                if len(note.content) > 200:
                    preview += "…"
                st.caption(preview)

                detail_col, del_col = st.columns([5, 1])
                with detail_col:
                    if st.button("詳細を見る", key=f"detail_{note.id}"):
                        st.session_state[f"show_note_{note.id}"] = True

                with del_col:
                    if st.button("削除", key=f"del_{note.id}", type="secondary"):
                        from db.notes_repository import delete_note
                        delete_note(note.id)
                        st.toast("ノートを削除しました")
                        st.rerun()

                # 詳細展開
                if st.session_state.get(f"show_note_{note.id}"):
                    with st.expander("📄 ノート全文", expanded=True):
                        st.markdown(note.content)
                        if st.button("閉じる", key=f"close_{note.id}"):
                            del st.session_state[f"show_note_{note.id}"]
                            st.rerun()

# ==============================
# Tab 2: ノートを追加
# ==============================
with tab_add:
    st.markdown("### ✏️ 新しいノートを追加")

    with st.form("add_note_form", clear_on_submit=True):
        title = st.text_input("タイトル *", placeholder="例: PERの基本的な見方", max_chars=200)
        content = st.text_area(
            "内容 *",
            placeholder="学んだことを自由に書いてください…",
            height=250,
        )
        tags_input = st.text_input(
            "タグ（カンマ区切り）",
            placeholder="例: PER, バリュエーション, 株式",
        )
        submitted = st.form_submit_button("💾 保存する", type="primary")

    if submitted:
        if not title.strip():
            st.error("タイトルを入力してください。")
        elif not content.strip():
            st.error("内容を入力してください。")
        else:
            tags = [t.strip() for t in tags_input.split(",") if t.strip()] if tags_input else []
            try:
                from db.notes_repository import add_note
                add_note(title=title.strip(), content=content.strip(), source="manual", tags=tags)
                st.success("✅ ノートを保存しました！「📋 ノート一覧」タブで確認できます。")
            except Exception as e:
                st.error(f"保存に失敗しました: {e}")

# ==============================
# Tab 3: チャットから生成
# ==============================
with tab_ai:
    st.markdown("### 🤖 チャット履歴からノートを自動生成")
    st.info(
        "メンターチャットの会話を選んで、AIが自動的に学習ノートを作成します。\n"
        "チャットページの「📝 ノートを生成」ボタンからも同じことができます。",
        icon="💡",
    )

    from db.chat_repository import get_all_sessions, get_session_history

    sessions = get_all_sessions()
    if not sessions:
        st.warning("チャット履歴がまだありません。まずメンターチャットで会話してください。")
    else:
        selected_session = st.selectbox(
            "会話セッションを選択",
            options=sessions,
            format_func=lambda s: f"📂 {s[:8]}… ({s})",
        )

        if selected_session:
            history = get_session_history(selected_session, limit=20)
            if history:
                st.caption(f"{len(history)} 件のメッセージ")
                with st.expander("会話プレビュー", expanded=False):
                    for m in history[-6:]:
                        label = "👤 あなた" if m.role == "user" else "🤖 AI"
                        st.markdown(f"**{label}**: {m.content[:100]}{'…' if len(m.content) > 100 else ''}")

                if st.button("🤖 ノートを生成する", type="primary"):
                    history_text = "\n".join(
                        f"{'ユーザー' if m.role == 'user' else 'AI'}: {m.content}"
                        for m in history
                    )
                    with st.spinner("AIがノートを生成中… (10〜30秒かかることがあります)"):
                        from core.claude_client import generate_note_from_chat
                        note_text = generate_note_from_chat(history_text)

                    if note_text:
                        lines = note_text.strip().split("\n")
                        title = lines[0].lstrip("#").strip()[:50] or "チャットノート"
                        try:
                            from db.notes_repository import add_note
                            note_id = add_note(
                                title=title,
                                content=note_text,
                                source="chat",
                                tags=["チャット", "自動生成"],
                            )
                            st.success("✅ ノートを保存しました！「📋 ノート一覧」で確認できます。")
                            st.markdown("---")
                            st.markdown("**生成されたノート**")
                            st.markdown(note_text)
                        except Exception as e:
                            st.error(f"ノートの保存に失敗しました: {e}")
                    else:
                        st.warning(
                            "ノートの生成に失敗しました。"
                            "ANTHROPIC_API_KEY が正しく設定されているか確認してください。"
                        )

# ---- フッター ----
st.divider()
st.caption(
    "⚠️ **免責事項** | "
    "本アプリは投資教育・学習を目的としています。"
    "AIの解説は学習補助であり、投資アドバイスではありません。"
    "投資判断は必ずご自身の責任で行ってください。"
)
