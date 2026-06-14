"""
news_client.py のユニットテスト。
外部API（NewsAPI）はすべてモックし、ネットワーク不要で実行できる。
"""

from unittest.mock import MagicMock, patch

import pytest

from core.news_client import (
    TRUSTED_DOMAINS,
    NewsArticle,
    _extract_domain,
    _is_trusted,
    fetch_news,
)


# ---------------------------------------------------------------------------
# _extract_domain
# ---------------------------------------------------------------------------

class TestExtractDomain:
    def test_standard_url(self):
        assert _extract_domain("https://www.reuters.com/article/abc") == "reuters.com"

    def test_url_without_www(self):
        assert _extract_domain("https://reuters.com/article/abc") == "reuters.com"

    def test_subdomain(self):
        assert _extract_domain("https://jp.reuters.com/article/abc") == "jp.reuters.com"

    def test_nikkei_url(self):
        assert _extract_domain("https://www.nikkei.com/article/xyz") == "nikkei.com"

    def test_empty_url_returns_empty(self):
        assert _extract_domain("") == ""

    def test_malformed_url_returns_empty(self):
        assert _extract_domain("not-a-url") == ""


# ---------------------------------------------------------------------------
# _is_trusted
# ---------------------------------------------------------------------------

class TestIsTrusted:
    @pytest.mark.parametrize("domain", list(TRUSTED_DOMAINS))
    def test_all_trusted_domains_pass(self, domain):
        assert _is_trusted(domain) is True

    def test_subdomain_of_trusted_passes(self):
        assert _is_trusted("jp.reuters.com") is True
        assert _is_trusted("markets.bloomberg.com") is True

    def test_untrusted_domain_fails(self):
        assert _is_trusted("example.com") is False
        assert _is_trusted("fake-news-site.net") is False

    def test_partial_match_does_not_pass(self):
        # "reuters.com.evil.com" はサブドメインではない
        assert _is_trusted("reuters.com.evil.com") is False


# ---------------------------------------------------------------------------
# fetch_news
# ---------------------------------------------------------------------------

def _make_raw_article(url: str, title: str = "Test Title") -> dict:
    return {
        "title": title,
        "description": "Some description",
        "url": url,
        "source": {"name": "Test Source"},
        "publishedAt": "2026-06-13T00:00:00Z",
    }


def _make_newsapi_response(articles: list[dict]) -> dict:
    return {"status": "ok", "totalResults": len(articles), "articles": articles}


class TestFetchNews:
    @patch("core.news_client._build_client")
    def test_returns_empty_when_no_api_key(self, mock_build):
        mock_build.return_value = None

        result = fetch_news()

        assert result == []

    @patch("core.news_client._build_client")
    def test_filters_untrusted_sources(self, mock_build):
        client = MagicMock()
        client.get_everything.return_value = _make_newsapi_response([
            _make_raw_article("https://www.reuters.com/article/1", "Reuters article"),
            _make_raw_article("https://www.fake-news.com/article/2", "Fake article"),
        ])
        mock_build.return_value = client

        results = fetch_news(max_articles=10)

        assert len(results) == 1
        assert results[0].domain == "reuters.com"

    @patch("core.news_client._build_client")
    def test_limits_to_max_articles(self, mock_build):
        client = MagicMock()
        client.get_everything.return_value = _make_newsapi_response([
            _make_raw_article(f"https://www.reuters.com/article/{i}", f"Article {i}")
            for i in range(10)
        ])
        mock_build.return_value = client

        results = fetch_news(max_articles=3)

        assert len(results) <= 3

    @patch("core.news_client._build_client")
    def test_returns_news_article_dataclass(self, mock_build):
        client = MagicMock()
        client.get_everything.return_value = _make_newsapi_response([
            _make_raw_article("https://www.reuters.com/article/1", "Reuters Title"),
        ])
        mock_build.return_value = client

        results = fetch_news(max_articles=5)

        assert len(results) == 1
        article = results[0]
        assert isinstance(article, NewsArticle)
        assert article.title == "Reuters Title"
        assert article.domain == "reuters.com"

    @patch("core.news_client._build_client")
    def test_skips_articles_with_empty_title(self, mock_build):
        client = MagicMock()
        client.get_everything.return_value = _make_newsapi_response([
            {"title": "", "url": "https://reuters.com/a", "description": "d",
             "source": {"name": "Reuters"}, "publishedAt": "2026-06-13T00:00:00Z"},
            _make_raw_article("https://reuters.com/b", "Valid Title"),
        ])
        mock_build.return_value = client

        results = fetch_news(max_articles=5)

        assert len(results) == 1
        assert results[0].title == "Valid Title"

    @patch("core.news_client._build_client")
    def test_returns_empty_on_api_error(self, mock_build):
        client = MagicMock()
        client.get_everything.side_effect = RuntimeError("API error")
        mock_build.return_value = client

        results = fetch_news()

        assert results == []

    @patch("core.news_client._build_client")
    def test_returns_empty_on_non_ok_status(self, mock_build):
        client = MagicMock()
        client.get_everything.return_value = {"status": "error", "articles": []}
        mock_build.return_value = client

        results = fetch_news()

        assert results == []

    @patch("core.news_client._build_client")
    def test_bloomberg_subdomain_is_trusted(self, mock_build):
        client = MagicMock()
        client.get_everything.return_value = _make_newsapi_response([
            _make_raw_article("https://markets.bloomberg.com/article/1", "Bloomberg"),
        ])
        mock_build.return_value = client

        results = fetch_news(max_articles=5)

        assert len(results) == 1
        assert results[0].domain == "markets.bloomberg.com"
