from dotenv import load_dotenv

load_dotenv()

import json
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="学習ロードマップ | AI投資メンター",
    page_icon="🗺️",
    layout="wide",
)

_STAGES_PATH = Path("curriculum/stages.json")
_STATUS_LABELS = {
    "not_started": "⬜ 未着手",
    "in_progress": "🔵 学習中",
    "completed":   "✅ 完了",
}
_STATUS_COLORS = {
    "not_started": "gray",
    "in_progress": "blue",
    "completed":   "green",
}


@st.cache_resource
def _bootstrap():
    from core.logger import setup_logger
    from db.database import init_db
    setup_logger()
    init_db()


_bootstrap()


@st.cache_data(show_spinner=False)
def _load_stages() -> dict:
    with open(_STAGES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_progress_map() -> dict:
    from db.progress_repository import get_all_progress
    return {p.stage_id: p for p in get_all_progress()}


def _overall_stats(progress_map: dict) -> tuple[int, int, int]:
    total = 25
    completed = sum(1 for p in progress_map.values() if p.status == "completed")
    in_progress = sum(1 for p in progress_map.values() if p.status == "in_progress")
    return total, completed, in_progress


# ---- UI ----
st.title("🗺️ 学習ロードマップ")
st.caption("5ステージ・25テーマの体系的カリキュラム。各テーマにミニクイズ3問付き。")

data = _load_stages()
progress_map = _load_progress_map()
total, completed, in_prog = _overall_stats(progress_map)

# === 進捗サマリー ===
st.subheader("📊 全体進捗")
col_a, col_b, col_c = st.columns(3)
col_a.metric("完了テーマ", f"{completed} / {total}")
col_b.metric("学習中", in_prog)
col_c.metric("達成率", f"{completed / total * 100:.0f}%")
st.progress(completed / total)

st.divider()

# === ステージ別 ===
st.subheader("📚 ステージ別カリキュラム")

for stage in data["stages"]:
    stage_id = stage["id"]
    stage_themes = stage["themes"]
    stage_completed = sum(
        1 for t in stage_themes
        if progress_map.get(t["id"]) and progress_map[t["id"]].status == "completed"
    )

    header = (
        f"**STAGE {stage_id}: {stage['title']}**"
        f"　{stage_completed}/{len(stage_themes)} 完了"
        f"　⏱️ 目安 {stage['estimated_weeks']}週間"
    )

    with st.expander(header, expanded=(stage_id == "1")):
        st.caption(stage["description"])
        st.markdown("---")

        for theme in stage_themes:
            theme_id = theme["id"]
            rec = progress_map.get(theme_id)
            current_status = rec.status if rec else "not_started"

            tcol1, tcol2 = st.columns([3, 1])
            with tcol1:
                st.markdown(f"**{theme_id}. {theme['title']}**")
                st.caption(theme["description"])

                if rec and rec.quiz_score is not None:
                    st.caption(
                        f"クイズ正答率: {rec.quiz_score}/{rec.quiz_total}問 "
                        f"({rec.quiz_rate:.0f}%)"
                    )

            with tcol2:
                new_status = st.selectbox(
                    "ステータス",
                    options=list(_STATUS_LABELS.keys()),
                    format_func=lambda s: _STATUS_LABELS[s],
                    index=list(_STATUS_LABELS.keys()).index(current_status),
                    key=f"status_{theme_id}",
                    label_visibility="collapsed",
                )
                if new_status != current_status:
                    from db.progress_repository import upsert_progress
                    upsert_progress(theme_id, new_status)
                    st.rerun()

            # クイズセクション
            quiz = theme.get("quiz", [])
            if quiz:
                quiz_result_key = f"quiz_result_{theme_id}"

                with st.expander(f"📝 ミニクイズ（{len(quiz)}問）", expanded=False):
                    if quiz_result_key in st.session_state:
                        # 結果表示
                        result = st.session_state[quiz_result_key]
                        score = result["score"]
                        details = result["details"]
                        st.markdown(f"### 結果: {score}/{len(quiz)} 問正解")
                        if score == len(quiz):
                            st.success("🎉 全問正解！素晴らしいです！")
                        elif score >= len(quiz) // 2:
                            st.info("👍 もう少し！復習してみましょう。")
                        else:
                            st.warning("📖 解説をよく読んで復習しましょう。")

                        for d in details:
                            icon = "✅" if d["correct"] else "❌"
                            st.markdown(f"**{icon} Q{d['num']}: {d['question']}**")
                            if not d["correct"]:
                                st.markdown(
                                    f"あなたの回答: ~~{d['user_answer']}~~  "
                                    f"→ 正解: **{d['correct_answer']}**"
                                )
                            with st.container():
                                st.caption(f"💡 {d['explanation']}")
                            st.markdown("---")

                        if st.button("🔄 もう一度挑戦", key=f"retry_{theme_id}"):
                            del st.session_state[quiz_result_key]
                            st.rerun()

                    else:
                        # クイズフォーム
                        with st.form(key=f"quiz_form_{theme_id}"):
                            user_answers = []
                            for qi, q in enumerate(quiz):
                                st.markdown(f"**Q{qi + 1}**: {q['question']}")
                                ans = st.radio(
                                    f"選択肢 Q{qi + 1}",
                                    options=q["choices"],
                                    index=None,
                                    key=f"radio_{theme_id}_{qi}",
                                    label_visibility="collapsed",
                                )
                                user_answers.append(ans)
                                st.markdown("")

                            submitted = st.form_submit_button("✅ 回答する", type="primary")

                        if submitted:
                            if any(a is None for a in user_answers):
                                st.warning("全問に回答してから提出してください。")
                            else:
                                score = 0
                                details = []
                                for qi, (q, ua) in enumerate(zip(quiz, user_answers)):
                                    correct_ans = q["choices"][q["correct_index"]]
                                    is_correct = ua == correct_ans
                                    if is_correct:
                                        score += 1
                                    details.append({
                                        "num": qi + 1,
                                        "question": q["question"],
                                        "user_answer": ua,
                                        "correct_answer": correct_ans,
                                        "explanation": q["explanation"],
                                        "correct": is_correct,
                                    })

                                st.session_state[quiz_result_key] = {
                                    "score": score,
                                    "details": details,
                                }

                                # 進捗を完了に更新
                                from db.progress_repository import upsert_progress
                                upsert_progress(
                                    theme_id,
                                    "completed",
                                    quiz_score=score,
                                    quiz_total=len(quiz),
                                )
                                st.rerun()

            st.markdown("　")  # テーマ間スペース

# ---- フッター ----
st.divider()
st.caption(
    "⚠️ **免責事項** | "
    "本アプリは投資教育・学習を目的としています。"
    "AIの解説は学習補助であり、投資アドバイスではありません。"
    "投資判断は必ずご自身の責任で行ってください。"
)
