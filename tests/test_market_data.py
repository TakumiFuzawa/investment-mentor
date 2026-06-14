"""
market_data.py のユニットテスト。
外部API（yfinance）はすべてモックし、ネットワーク不要で実行できる。
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from core.market_data import (
    TICKERS,
    TickerData,
    _is_cache_valid,
    _validate,
    clear_cache,
    fetch_all_tickers,
    fetch_ticker,
)


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _make_hist(prices: list[float]) -> pd.DataFrame:
    """Close 列を持つ最小限の DataFrame を生成する。"""
    return pd.DataFrame({"Close": prices})


def _make_ticker_mock(prices: list[float]) -> MagicMock:
    mock = MagicMock()
    mock.history.return_value = _make_hist(prices)
    return mock


# ---------------------------------------------------------------------------
# _validate
# ---------------------------------------------------------------------------

class TestValidate:
    def _base(self, price=100.0, prev=95.0):
        change = price - prev
        rate = change / prev * 100
        return TickerData(
            symbol="^N225", name="日経平均",
            price=price, prev_close=prev,
            change=change, change_rate=rate,
            fetched_at=datetime.now(),
        )

    def test_normal_data_has_no_warning(self):
        data = self._base()
        result = _validate(data)
        assert result.warning is None
        assert result.error is None

    def test_price_none_sets_error(self):
        data = TickerData(
            symbol="^N225", name="日経平均",
            price=None, prev_close=None, change=None, change_rate=None,
            fetched_at=datetime.now(),
        )
        result = _validate(data)
        assert result.error is not None

    def test_price_zero_sets_warning(self):
        data = self._base(price=0.0, prev=95.0)
        data.change = 0.0 - 95.0
        data.change_rate = -100.0
        result = _validate(data)
        assert result.warning is not None

    def test_price_negative_sets_warning(self):
        data = self._base(price=-1.0, prev=95.0)
        result = _validate(data)
        assert result.warning is not None

    def test_abnormal_change_over_30pct_sets_warning(self):
        data = self._base(price=131.0, prev=100.0)
        result = _validate(data)
        assert result.warning is not None
        assert "31" in result.warning or "%" in result.warning

    def test_change_exactly_30pct_no_warning(self):
        data = self._base(price=130.0, prev=100.0)
        result = _validate(data)
        assert result.warning is None


# ---------------------------------------------------------------------------
# fetch_ticker
# ---------------------------------------------------------------------------

class TestFetchTicker:
    def setup_method(self):
        clear_cache()

    @patch("core.market_data.yf.Ticker")
    def test_returns_valid_data(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _make_ticker_mock([38000.0, 38500.0])

        result = fetch_ticker("^N225")

        assert result.symbol == "^N225"
        assert result.name == "日経平均"
        assert result.price == pytest.approx(38500.0)
        assert result.prev_close == pytest.approx(38000.0)
        assert result.change == pytest.approx(500.0)
        assert result.error is None
        assert result.is_valid

    @patch("core.market_data.yf.Ticker")
    def test_returns_error_on_empty_history(self, mock_ticker_cls):
        mock = MagicMock()
        mock.history.return_value = pd.DataFrame()
        mock_ticker_cls.return_value = mock

        result = fetch_ticker("^N225")

        assert result.error is not None
        assert not result.is_valid

    @patch("core.market_data.yf.Ticker")
    def test_returns_error_on_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = RuntimeError("network error")

        result = fetch_ticker("^N225")

        assert result.error is not None
        assert not result.is_valid

    @patch("core.market_data.yf.Ticker")
    def test_cache_prevents_second_api_call(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _make_ticker_mock([100.0, 101.0])

        fetch_ticker("^GSPC")
        fetch_ticker("^GSPC")

        assert mock_ticker_cls.call_count == 1

    @patch("core.market_data.yf.Ticker")
    def test_unknown_symbol_uses_symbol_as_name(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _make_ticker_mock([100.0, 102.0])

        result = fetch_ticker("UNKNOWN")

        assert result.name == "UNKNOWN"

    @patch("core.market_data.yf.Ticker")
    def test_single_price_row_has_no_change(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _make_ticker_mock([38000.0])

        result = fetch_ticker("^N225")

        assert result.change is None
        assert result.change_rate is None


# ---------------------------------------------------------------------------
# fetch_all_tickers
# ---------------------------------------------------------------------------

class TestFetchAllTickers:
    def setup_method(self):
        clear_cache()

    @patch("core.market_data.yf.Ticker")
    def test_returns_all_four_tickers(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _make_ticker_mock([100.0, 101.0])

        results = fetch_all_tickers()

        assert len(results) == len(TICKERS)

    @patch("core.market_data.yf.Ticker")
    def test_symbols_match_tickers_dict(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _make_ticker_mock([100.0, 101.0])

        results = fetch_all_tickers()
        symbols = {r.symbol for r in results}

        assert symbols == set(TICKERS.keys())


# ---------------------------------------------------------------------------
# clear_cache / _is_cache_valid
# ---------------------------------------------------------------------------

class TestCache:
    def setup_method(self):
        clear_cache()

    def test_clear_cache_all(self):
        from core.market_data import _cache
        _cache["^N225"] = (MagicMock(), datetime.now())
        clear_cache()
        assert len(_cache) == 0

    def test_clear_cache_single_symbol(self):
        from core.market_data import _cache
        _cache["^N225"] = (MagicMock(), datetime.now())
        _cache["^GSPC"] = (MagicMock(), datetime.now())
        clear_cache("^N225")
        assert "^N225" not in _cache
        assert "^GSPC" in _cache

    def test_cache_valid_within_expire(self):
        assert _is_cache_valid(datetime.now()) is True

    def test_cache_invalid_after_expire(self):
        from datetime import timedelta
        old_time = datetime.now() - timedelta(minutes=60)
        assert _is_cache_valid(old_time) is False
