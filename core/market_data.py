import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf
from loguru import logger

TICKERS: dict[str, str] = {
    "^N225": "日経平均",
    "^GSPC": "S&P500",
    "USDJPY=X": "ドル円",
    "^IXIC": "NASDAQ",
}

_CACHE_EXPIRE_MINUTES = int(os.getenv("CACHE_EXPIRE_MINUTES", "30"))
_ABNORMAL_CHANGE_THRESHOLD = 30.0  # ±30% で異常警告

# セッション内インメモリキャッシュ（SQLite永続化はPhase 2-3で統合）
_cache: dict[str, tuple["TickerData", datetime]] = {}


@dataclass
class TickerData:
    symbol: str
    name: str
    price: Optional[float]
    prev_close: Optional[float]
    change: Optional[float]
    change_rate: Optional[float]  # %単位
    fetched_at: datetime
    warning: Optional[str] = None
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.error is None and self.price is not None


def _validate(data: TickerData) -> TickerData:
    if data.price is None:
        data.error = "価格データを取得できませんでした"
        return data

    if data.price <= 0:
        data.warning = f"異常な価格値（{data.price}）を検出しました"
        logger.warning("Abnormal price for {}: {}", data.symbol, data.price)
        return data

    if data.change_rate is not None and abs(data.change_rate) > _ABNORMAL_CHANGE_THRESHOLD:
        data.warning = (
            f"異常な変動（{data.change_rate:+.2f}%）を検出しました。"
            "データの正確性をご確認ください。"
        )
        logger.warning(
            "Abnormal change rate for {}: {:.2f}%", data.symbol, data.change_rate
        )

    return data


def _is_cache_valid(cached_at: datetime) -> bool:
    return datetime.now() - cached_at < timedelta(minutes=_CACHE_EXPIRE_MINUTES)


def fetch_ticker(symbol: str) -> TickerData:
    name = TICKERS.get(symbol, symbol)
    now = datetime.now()

    if symbol in _cache:
        cached_data, cached_at = _cache[symbol]
        if _is_cache_valid(cached_at):
            elapsed = (now - cached_at).total_seconds() / 60
            logger.debug("Cache hit for {} ({:.1f} min old)", symbol, elapsed)
            return cached_data

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")

        if hist is None or hist.empty:
            logger.warning("No history data returned for {}", symbol)
            return TickerData(
                symbol=symbol, name=name,
                price=None, prev_close=None, change=None, change_rate=None,
                fetched_at=now, error="データを取得できませんでした",
            )

        price = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else None
        change = price - prev_close if prev_close is not None else None
        change_rate = (change / prev_close * 100) if (change is not None and prev_close) else None

        result = TickerData(
            symbol=symbol, name=name,
            price=price, prev_close=prev_close,
            change=change, change_rate=change_rate,
            fetched_at=now,
        )
        result = _validate(result)

        _cache[symbol] = (result, now)
        logger.info("Fetched {}: price={:.4f}", symbol, price)
        return result

    except Exception as e:
        logger.error("Failed to fetch ticker {}: {}", symbol, e)
        return TickerData(
            symbol=symbol, name=name,
            price=None, prev_close=None, change=None, change_rate=None,
            fetched_at=now, error="データを取得できませんでした",
        )


def fetch_all_tickers() -> list[TickerData]:
    results = []
    for symbol in TICKERS:
        results.append(fetch_ticker(symbol))
    return results


def clear_cache(symbol: Optional[str] = None) -> None:
    if symbol:
        _cache.pop(symbol, None)
    else:
        _cache.clear()
    logger.debug("Cache cleared (symbol={})", symbol or "ALL")
