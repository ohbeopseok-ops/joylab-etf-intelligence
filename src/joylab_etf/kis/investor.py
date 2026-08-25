from __future__ import annotations

from typing import Any

import requests

from joylab_etf.kis.client import KISClient
from joylab_etf.kis.investor_models import InvestorFlowSnapshot

# Verified against KIS Open Trading API reference examples_llm/domestic_stock/inquire_investor:
# [국내주식] 기본시세 > 주식현재가 투자자[v1_국내주식-012]
INVESTOR_PATH = "/uapi/domestic-stock/v1/quotations/inquire-investor"
INVESTOR_TR_ID = "FHKST01010900"


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).replace(",", ""))
    except ValueError:
        return None


class KISInvestorAdapter:
    """개인/외국인/기관계 순매수 조회. 연기금 개별 구분은 KIS API에 없다 (추측 금지)."""

    def __init__(self, client: KISClient):
        self.client = client

    def get_investor_flow(
        self,
        symbol: str,
        market: str = "J",
    ) -> list[InvestorFlowSnapshot]:
        url = f"{self.client.settings.base_url}{INVESTOR_PATH}"
        params = {
            "FID_COND_MRKT_DIV_CODE": market,
            "FID_INPUT_ISCD": symbol,
        }

        response = requests.get(
            url,
            headers=self.client._auth_headers(INVESTOR_TR_ID),
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS 투자자 매매동향 조회 실패: "
                f"msg_cd={data.get('msg_cd')} msg1={data.get('msg1')}"
            )

        rows = data.get("output") or []
        if not isinstance(rows, list):
            raise RuntimeError("KIS 투자자 매매동향 output이 list 형식이 아닙니다.")

        snapshots: list[InvestorFlowSnapshot] = []
        for row in rows:
            business_date = str(row.get("stck_bsop_date") or "").strip()
            individual = _to_int(row.get("prsn_ntby_qty"))
            foreign = _to_int(row.get("frgn_ntby_qty"))
            institution = _to_int(row.get("orgn_ntby_qty"))

            if not business_date or individual is None or foreign is None or institution is None:
                continue

            snapshots.append(
                InvestorFlowSnapshot(
                    symbol=symbol,
                    business_date=business_date,
                    individual_net_buy_qty=individual,
                    foreign_net_buy_qty=foreign,
                    institution_net_buy_qty=institution,
                )
            )

        if not snapshots:
            raise RuntimeError("투자자 매매동향을 한 건도 정규화하지 못했습니다.")

        return snapshots
