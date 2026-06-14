from dotenv import load_dotenv

load_dotenv()

import streamlit as st

st.set_page_config(
    page_title="AI投資メンター",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def _bootstrap():
    from core.logger import setup_logger
    from db.database import init_db
    setup_logger()
    init_db()


_bootstrap()

# ---- サイドバー共通情報 ----
with st.sidebar:
    st.markdown("## 📈 AI投資メンター")
    st.caption("スキマ時間30分で投資知識を積み上げる")
    st.divider()
    st.markdown(
        "**ページ案内**\n"
        "- 📰 今日のブリーフィング\n"
        "- 💬 メンターチャット\n"
        "- 🗺️ 学習ロードマップ\n"
        "- 📝 学習ノート"
    )
    st.divider()
    st.caption("⚠️ 学習目的のみ。投資判断は自己責任で。")

# ---- ホーム ----
st.title("📈 AI投資メンター")
st.markdown("**スキマ時間30分で投資知識を体系的に積み上げる、あなた専用の学習パートナー。**")

st.divider()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("### 📰")
    st.markdown("**今日のブリーフィング**")
    st.caption("市場状況・ニュース・今日の学習テーマを確認")
with col2:
    st.markdown("### 💬")
    st.markdown("**メンターチャット**")
    st.caption("投資・経済について何でもAIに質問")
with col3:
    st.markdown("### 🗺️")
    st.markdown("**学習ロードマップ**")
    st.caption("5ステージ・25テーマの体系的カリキュラム")
with col4:
    st.markdown("### 📝")
    st.markdown("**学習ノート**")
    st.caption("学んだことを記録して後から振り返る")

st.divider()
st.info(
    "👈 左のサイドバーからページを選択してください。"
    "初めての方は **📰 今日のブリーフィング** から始めることをおすすめします。"
)

st.divider()
st.caption(
    "⚠️ **免責事項** | "
    "本アプリは投資教育・学習を目的としています。"
    "AIの解説は学習補助であり、投資アドバイスではありません。"
    "表示される市場データは最大15〜30分の遅延があります。"
    "投資判断は必ずご自身の責任で行ってください。"
)
