from dotenv import load_dotenv

load_dotenv()

import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="今日のブリーフィング | AI投資メンター",
    page_icon="📰",
    layout="wide",
)


@st.cache_resource
def _bootstrap():
    from core.logger import setup_logger
    from db.database import init_db
    setup_logger()
    init_db()


_bootstrap()

# ---- キャッシュ付きデータ取得 ----

@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_market():
    from core.market_data import fetch_all_tickers
    return fetch_all_tickers()


@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_news():
    from core.news_client import fetch_global_news
    return fetch_global_news(max_articles=3)


@st.cache_data(ttl=1800, show_spinner=False)
def _summarize(title: str, description: str, source: str) -> str:
    from core.claude_client import summarize_news
    return summarize_news(title, description, source)


@st.cache_data(ttl=21600, show_spinner=False)
def _daily_theme(progress_summary: str, market_summary: str, headlines: str) -> str:
    from core.claude_client import suggest_daily_theme
    return suggest_daily_theme(progress_summary, market_summary, headlines)


def _fmt_price(price: float, symbol: str) -> str:
    if symbol == "USDJPY=X":
        return f"¥{price:,.2f}"
    return f"{price:,.2f}"


def _progress_summary() -> str:
    try:
        from db.progress_repository import get_all_progress
        records = get_all_progress()
        completed = sum(1 for r in records if r.status == "completed")
        in_progress = sum(1 for r in records if r.status == "in_progress")
        if not records:
            return "まだ学習を開始していません。STAGE 1から始めましょう。"
        return f"全25テーマ中、完了: {completed}テーマ、学習中: {in_progress}テーマ"
    except Exception:
        return "進捗データなし"


# ---- UI ----

st.title("📰 今日のブリーフィング")
st.caption(f"更新: {datetime.now().strftime('%Y-%m-%d %H:%M')} ／ データは最大30分遅延")

if st.button("🔄 データを更新", type="secondary"):
    _fetch_market.clear()
    _fetch_news.clear()
    st.rerun()

st.divider()

# === 主要指数 ===
st.subheader("📊 主要指数")

with st.spinner("市場データを取得中…"):
    tickers = _fetch_market()

cols = st.columns(4)
market_lines = []
for col, ticker in zip(cols, tickers):
    with col:
        if ticker.is_valid:
            delta_val = f"{ticker.change_rate:+.2f}%" if ticker.change_rate is not None else None
            st.metric(
                label=ticker.name,
                value=_fmt_price(ticker.price, ticker.symbol),
                delta=delta_val,
            )
            market_lines.append(
                f"{ticker.name}: {_fmt_price(ticker.price, ticker.symbol)} ({delta_val or '±?%'})"
            )
            if ticker.warning:
                st.warning(f"⚠️ {ticker.warning}", icon="⚠️")
        else:
            st.metric(label=ticker.name, value="---")
            st.caption(f"🔴 {ticker.error or 'データ取得失敗'}")
            market_lines.append(f"{ticker.name}: 取得失敗")

market_summary = "\n".join(market_lines)

st.divider()

# === 経済ニュース ===
st.subheader("📡 経済ニュース（信頼ソース限定）")

with st.spinner("ニュースを取得中…"):
    articles = _fetch_news()

if not articles:
    st.warning(
        "ニュースを取得できませんでした。"
        "NEWS_API_KEY が設定されていないか、信頼ソースの記事が見つかりませんでした。",
        icon="⚠️",
    )
    headlines_text = "ニュース取得失敗"
else:
    headlines_text = "\n".join(f"・{a.title}" for a in articles)
    for i, article in enumerate(articles):
        with st.expander(f"**{article.title}**  —  {article.source_name}", expanded=(i == 0)):
            st.caption(f"出典: [{article.domain}]({article.url})  ／  {article.published_at[:10] if article.published_at else ''}")
            if article.description:
                st.markdown(f"_{article.description}_")

            st.markdown("**🤖 AI要約（学習目的）**")
            with st.spinner("要約生成中…"):
                summary = _summarize(article.title, article.description, article.source_name)
            if summary:
                st.markdown(summary)
            else:
                st.caption("要約を生成できませんでした（ANTHROPIC_API_KEY を確認してください）")

st.divider()

# === 今日の学習テーマ ===
st.subheader("🎯 今日の学習テーマ")

progress_text = _progress_summary()

with st.spinner("学習テーマを生成中…"):
    theme_text = _daily_theme(progress_text, market_summary, headlines_text)

if theme_text:
    st.markdown(theme_text)
else:
    st.info("学習テーマの生成には ANTHROPIC_API_KEY が必要です。ロードマップから学習を始めましょう。")

# ---- フッター ----
st.divider()
st.caption(
    "⚠️ **免責事項** | "
    "本アプリは投資教育・学習を目的としています。"
    "AIの解説は学習補助であり、投資アドバイスではありません。"
    "表示される市場データは最大15〜30分の遅延があります。"
    "投資判断は必ずご自身の責任で行ってください。"
)
