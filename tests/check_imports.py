import json

from core.market_data import fetch_all_tickers, TICKERS
from core.news_client import fetch_global_news, TRUSTED_DOMAINS
from core.claude_client import chat, summarize_news, suggest_daily_theme, generate_note_from_chat
from core.prompts import MENTOR_SYSTEM, NEWS_SUMMARY_SYSTEM
from db.database import init_db, get_connection
from db.chat_repository import add_message, get_session_history, get_all_sessions, delete_session
from db.progress_repository import upsert_progress, get_all_progress, get_completion_summary
from db.notes_repository import add_note, get_all_notes, search_notes, delete_note

with open("curriculum/stages.json", encoding="utf-8") as f:
    stages = json.load(f)
    assert len(stages["stages"]) == 5

print("All imports OK")
print(f"  TICKERS: {list(TICKERS.keys())}")
print(f"  Trusted domains: {len(TRUSTED_DOMAINS)}")
print(f"  Stages loaded: {len(stages['stages'])}")
