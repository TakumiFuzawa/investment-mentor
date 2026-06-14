import os
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse
from typing import Optional

from loguru import logger

TRUSTED_DOMAINS: set[str] = {
    # 主要メディア（有料プランで取得可能）
    "reuters.com",
    "bloomberg.com",
    "nikkei.com",
    "boj.or.jp",
    "mof.go.jp",
    "federalreserve.gov",
    # 無料プランで取得可能な信頼できる金融・経済ニュースソース
    "finance.yahoo.com",
    "wsj.com",
    "ft.com",
    "cnbc.com",
    "marketwatch.com",
    "forbes.com",
    "businessinsider.com",
    "financialpost.com",
    "apnews.com",
    "economist.com",
    "barrons.com",
    "thestreet.com",
    "investopedia.com",
    "morningstar.com",
    "seekingalpha.com",
    "economictimes.indiatimes.com",
}

_MAX_ARTICLES = 3
_FETCH_PAGE_SIZE = 20  # 信頼ソースでフィルタ後に3本残るよう多めに取得


@dataclass
class NewsArticle:
    title: str
    description: str
    url: str
    source_name: str
    published_at: str
    domain: str


def _extract_domain(url: str) -> str:
    try:
        hostname = urlparse(url).hostname or ""
        # "www." プレフィックスを除去
        return hostname.removeprefix("www.")
    except Exception:
        return ""


def _is_trusted(domain: str) -> bool:
    # 完全一致 or サブドメインを許容（例: jp.reuters.com）
    if domain in TRUSTED_DOMAINS:
        return True
    for trusted in TRUSTED_DOMAINS:
        if domain.endswith("." + trusted):
            return True
    return False


def _build_client():
    """newsapi.NewsApiClient を遅延生成する。APIキー未設定時は None を返す。"""
    api_key = os.getenv("NEWS_API_KEY", "").strip()
    if not api_key:
        logger.warning("NEWS_API_KEY is not set. News fetch will be skipped.")
        return None
    try:
        from newsapi import NewsApiClient  # type: ignore
        return NewsApiClient(api_key=api_key)
    except ImportError:
        logger.error("newsapi-python is not installed.")
        return None
    except Exception as e:
        logger.error("Failed to initialize NewsApiClient: {}", e)
        return None


def fetch_news(
    query: str = "economy OR stock market OR 日経 OR 経済",
    language: str = "en",
    max_articles: int = _MAX_ARTICLES,
) -> list[NewsArticle]:
    client = _build_client()
    if client is None:
        return []

    try:
        response = client.get_everything(
            q=query,
            language=language,
            sort_by="publishedAt",
            page_size=_FETCH_PAGE_SIZE,
        )
    except Exception as e:
        logger.error("NewsAPI request failed: {}", e)
        return []

    if response.get("status") != "ok":
        logger.error("NewsAPI returned non-ok status: {}", response.get("status"))
        return []

    raw_articles: list[dict] = response.get("articles", [])
    articles: list[NewsArticle] = []

    for raw in raw_articles:
        url: str = raw.get("url", "")
        domain = _extract_domain(url)

        if not _is_trusted(domain):
            logger.debug("Filtered out untrusted domain: {}", domain)
            continue

        title: str = raw.get("title") or ""
        description: str = raw.get("description") or ""
        source_name: str = (raw.get("source") or {}).get("name", domain)
        published_at: str = raw.get("publishedAt", "")

        if not title or not url:
            continue

        articles.append(
            NewsArticle(
                title=title,
                description=description,
                url=url,
                source_name=source_name,
                published_at=published_at,
                domain=domain,
            )
        )

        if len(articles) >= max_articles:
            break

    logger.info(
        "Fetched {} trusted articles (from {} total candidates)",
        len(articles),
        len(raw_articles),
    )
    return articles


def fetch_jp_news(max_articles: int = _MAX_ARTICLES) -> list[NewsArticle]:
    """日本語経済ニュース（日経・日銀・財務省向け）"""
    return fetch_news(
        query="日経 OR 日本銀行 OR 財務省 OR 株価 OR 経済",
        language="jp",
        max_articles=max_articles,
    )


def fetch_global_news(max_articles: int = _MAX_ARTICLES) -> list[NewsArticle]:
    """英語グローバル経済ニュース"""
    return fetch_news(
        query="stock market OR economy OR interest rate OR inflation",
        language="en",
        max_articles=max_articles,
    )
