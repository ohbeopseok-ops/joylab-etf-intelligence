"""KIS daily OHLC history -- used to compute standard technical levels
(e.g. moving averages) from real price data instead of hand-typed
numbers.

Verified live against KIS's own public reference
(koreainvestment/open-trading-api, examples_llm/domestic_stock/
inquire_daily_itemchartprice): endpoint
/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice,
TR FHKST03010100, output2 array with stck_bsop_date (business date,
YYYYMMDD) and stck_clpr (close price) among its fields. Max 100 records
per call.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import requests

from joylab_etf.kis.client import KISClient

DAILY_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
DAILY_PRICE_TR_ID = "FHKST03010100"


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


class DailyClose:
    __slots__ = ("business_date", "close")

    def __init__(self, business_date: str, close: float) -> None:
        self.business_date = business_date
        self.close = close


class KISDailyPriceAdapter:
    def __init__(self, client: KISClient):
        self.client = client

    def get_daily_closes(
        self,
        symbol: str,
        lookback_days: int = 60,
        market: str = "J",
        as_of: date | None = None,
    ) -> list[DailyClose]:
        """Most recent `lookback_days` CLOSED trading days, oldest first.

        Excludes today's row if the KIS response includes one for the
        currently-open session (its close would be the still-moving live
        price, not a settled daily close) -- callers computing a moving
        average must not silently mix a live price into a historical
        average.
        """
        today = as_of or date.today()
        # Trading days are a subset of calendar days; request a wide
        # enough calendar window to guarantee >= lookback_days rows
        # (weekends/holidays included), then trim to the tail.
        date_from = today - timedelta(days=int(lookback_days * 2.2) + 10)

        url = f"{self.client.settings.base_url}{DAILY_PRICE_PATH}"
        params = {
            "FID_COND_MRKT_DIV_CODE": market,
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": date_from.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": today.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0",
        }

        response = requests.get(
            url,
            headers=self.client._auth_headers(DAILY_PRICE_TR_ID),
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS 일별 시세 조회 실패: "
                f"msg_cd={data.get('msg_cd')} msg1={data.get('msg1')}"
            )

        rows = data.get("output2") or []
        if not isinstance(rows, list):
            raise RuntimeError("KIS 일별 시세 output2가 list 형식이 아닙니다.")

        closes: list[DailyClose] = []
        today_str = today.strftime("%Y%m%d")
        for row in rows:
            business_date = str(row.get("stck_bsop_date") or "").strip()
            close = _to_float(row.get("stck_clpr"))
            if not business_date or close is None:
                continue
            if business_date == today_str:
                continue
            closes.append(DailyClose(business_date=business_date, close=close))

        closes.sort(key=lambda c: c.business_date)
        if len(closes) < lookback_days:
            raise RuntimeError(
                f"KIS 일별 시세가 {lookback_days}거래일 미만입니다 "
                f"({len(closes)}건 수신)."
            )
        return closes[-lookback_days:]

    def get_simple_moving_average(
        self, symbol: str, days: int = 60, market: str = "J", as_of: date | None = None
    ) -> float:
        closes = self.get_daily_closes(symbol, lookback_days=days, market=market, as_of=as_of)
        return round(sum(c.close for c in closes) / len(closes), 2)
