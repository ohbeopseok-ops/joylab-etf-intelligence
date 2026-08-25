from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from joylab_etf.kis.client import KISClient
from joylab_etf.kis.index_models import IndexQuote

# Verified live against KIS: /uapi/domestic-stock/v1/quotations/inquire-price
# (used for stocks, TR FHKST01010100) rejects FID_COND_MRKT_DIV_CODE="U" with
# OPSQ2001. This dedicated index endpoint is the correct one --
# [국내주식] 업종/기타 > 국내업종 현재지수[v1_국내주식-063].
INDEX_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-index-price"
INDEX_PRICE_TR_ID = "FHPUP02100000"

KOSPI = "0001"
KOSDAQ = "1001"
KOSPI200 = "2001"

KST = timezone(timedelta(hours=9))


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


class KISIndexAdapter:
    def __init__(self, client: KISClient):
        self.client = client

    def get_index_price(self, index_code: str = KOSPI, market: str = "U") -> IndexQuote:
        url = f"{self.client.settings.base_url}{INDEX_PRICE_PATH}"
        params = {
            "FID_COND_MRKT_DIV_CODE": market,
            "FID_INPUT_ISCD": index_code,
        }

        response = requests.get(
            url,
            headers=self.client._auth_headers(INDEX_PRICE_TR_ID),
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS 지수 현재가 조회 실패: "
                f"msg_cd={data.get('msg_cd')} msg1={data.get('msg1')}"
            )

        output = data.get("output") or {}
        change_pct = _to_float(output.get("bstp_nmix_prdy_ctrt"))
        if change_pct is None:
            raise RuntimeError("지수 등락률(bstp_nmix_prdy_ctrt)이 응답에 없습니다.")

        return IndexQuote(
            index_code=index_code,
            price=_to_float(output.get("bstp_nmix_prpr")),
            change_pct=change_pct,
            timestamp=datetime.now(KST),
        )
