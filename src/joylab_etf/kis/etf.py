from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from joylab_etf.kis.client_v011 import KISClient
from joylab_etf.kis.etf_models import ETFComponentSnapshot, ETFConstituent

KST = timezone(timedelta(hours=9))

ETF_COMPONENT_PATH = "/uapi/etfetn/v1/quotations/inquire-component-stock-price"
ETF_COMPONENT_TR_ID = "FHKST121600C0"


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    num = _to_float(value)
    return int(num) if num is not None else None


class KISETFAdapter:
    def __init__(self, client: KISClient):
        self.client = client

    def get_components(
        self,
        etf_symbol: str,
        market: str = "J",
        screen_code: str = "11216",
    ) -> ETFComponentSnapshot:
        url = f"{self.client.settings.base_url}{ETF_COMPONENT_PATH}"
        params = {
            "FID_COND_MRKT_DIV_CODE": market,
            "FID_INPUT_ISCD": etf_symbol,
            "FID_COND_SCR_DIV_CODE": screen_code,
        }

        self.client._throttle()

        response = requests.get(
            url,
            headers=self.client._auth_headers(ETF_COMPONENT_TR_ID),
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS ETF 구성종목 조회 실패: "
                f"msg_cd={data.get('msg_cd')} msg1={data.get('msg1')}"
            )

        raw_components = data.get("output2") or []
        if not isinstance(raw_components, list):
            raise RuntimeError("KIS ETF output2가 list 형식이 아닙니다.")

        constituents: list[ETFConstituent] = []

        for row in raw_components:
            symbol = str(row.get("stck_shrn_iscd") or "").strip()
            name = str(row.get("hts_kor_isnm") or "").strip()
            weight = _to_float(row.get("etf_cnfg_issu_rlim"))

            if not symbol or weight is None:
                continue

            constituents.append(
                ETFConstituent(
                    symbol=symbol,
                    name=name,
                    weight_pct=weight,
                    valuation_amount=_to_float(row.get("etf_vltn_amt")),
                    current_price=_to_int(row.get("stck_prpr")),
                )
            )

        if not constituents:
            raise RuntimeError("ETF 구성종목을 한 건도 정규화하지 못했습니다.")

        return ETFComponentSnapshot(
            etf_symbol=etf_symbol,
            timestamp=datetime.now(KST),
            constituents=constituents,
        )
