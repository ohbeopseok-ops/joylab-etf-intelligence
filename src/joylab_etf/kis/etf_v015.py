from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

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
    value = _to_float(value)
    return int(value) if value is not None else None


class KISETFAdapter:
    def __init__(self, client):
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

        response = self.client.authorized_get(
            url=url,
            tr_id=ETF_COMPONENT_TR_ID,
            params=params,
            retry_on_expired_token=True,
        )

        if not response.ok:
            raise RuntimeError(
                f"KIS ETF Component HTTP {response.status_code}: "
                f"{response.text[:800]}"
            )

        data: dict[str, Any] = response.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS ETF 구성종목 조회 실패: "
                f"msg_cd={data.get('msg_cd')} msg1={data.get('msg1')}"
            )

        constituents: list[ETFConstituent] = []

        for row in data.get("output2") or []:
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
