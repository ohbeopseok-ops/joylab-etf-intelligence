from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from joylab_etf.kis.client import KISClient
from joylab_etf.kis.investor_flow_models import (
    FlowStatus,
    InvestorFlowSnapshot,
    SignalConfidence,
)

KST = timezone(timedelta(hours=9))


class KISIntradayInvestorFlowAdapter:
    """KIS 국내기관/외국인 매매종목 가집계 adapter.

    API: /uapi/domestic-stock/v1/quotations/foreign-institution-total
    TR : FHPTJ04400000

    주의:
    - 본 API는 장중 가집계이며 틱 단위 실시간 수급이 아니다.
    - 외국인/기관 갱신 시각은 KIS 운영 상황에 따라 ±10분 정도 차이가 날 수 있다.
    - 종목이 응답 목록에 없다고 순매수 0으로 해석하지 않는다.
    """

    API_PATH = "/uapi/domestic-stock/v1/quotations/foreign-institution-total"
    TR_ID = "FHPTJ04400000"

    def __init__(self, client: KISClient):
        self.client = client

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(float(str(value).replace(",", "")))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _first(row: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row and row[key] not in (None, ""):
                return row[key]
        return None

    def fetch_rows(
        self,
        *,
        market_index_code: str = "0001",
        sort_by_amount: bool = True,
        net_buy: bool = True,
        investor_type: str = "0",
    ) -> list[dict[str, Any]]:
        url = f"{self.client.settings.base_url}{self.API_PATH}"
        params = {
            "FID_COND_MRKT_DIV_CODE": "V",
            "FID_COND_SCR_DIV_CODE": "16449",
            "FID_INPUT_ISCD": market_index_code,
            "FID_DIV_CLS_CODE": "1" if sort_by_amount else "0",
            "FID_RANK_SORT_CLS_CODE": "0" if net_buy else "1",
            "FID_ETC_CLS_CODE": investor_type,
        }

        response = requests.get(
            url,
            headers=self.client._auth_headers(self.TR_ID),
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS investor flow 조회 실패: msg_cd={data.get('msg_cd')} "
                f"msg1={data.get('msg1')}"
            )

        output = data.get("output") or []
        if not isinstance(output, list):
            raise RuntimeError("KIS investor flow output 형식이 list가 아닙니다.")
        return output

    def get_symbol(
        self,
        symbol: str,
        *,
        name: str | None = None,
        market_index_code: str = "0001",
    ) -> InvestorFlowSnapshot:
        observed_at = datetime.now(KST)

        # 전체 투자자 기준 순매수 상위/순매도 상위를 모두 확인해야
        # 순매도 종목이 누락되는 것을 막을 수 있다.
        rows: list[dict[str, Any]] = []
        rows.extend(
            self.fetch_rows(
                market_index_code=market_index_code,
                sort_by_amount=True,
                net_buy=True,
                investor_type="0",
            )
        )
        rows.extend(
            self.fetch_rows(
                market_index_code=market_index_code,
                sort_by_amount=True,
                net_buy=False,
                investor_type="0",
            )
        )

        symbol_keys = ("mksc_shrn_iscd", "stck_shrn_iscd", "pdno", "code")
        row = next(
            (
                item
                for item in rows
                if str(self._first(item, *symbol_keys) or "").zfill(6) == symbol.zfill(6)
            ),
            None,
        )

        if row is None:
            return InvestorFlowSnapshot(
                symbol=symbol,
                name=name,
                status=FlowStatus.UNAVAILABLE,
                confidence=SignalConfidence.NONE,
                source_tr_id=self.TR_ID,
                observed_at=observed_at,
            )

        return InvestorFlowSnapshot(
            symbol=symbol,
            name=name or self._first(row, "hts_kor_isnm", "prdt_name"),
            foreign_net_buy_qty=self._to_int(
                self._first(row, "frgn_ntby_qty", "frgn_ntby_qtty", "frgn_ntby_qty2")
            ),
            foreign_net_buy_amount=self._to_int(
                self._first(row, "frgn_ntby_tr_pbmn", "frgn_ntby_amt", "frgn_ntby_amount")
            ),
            institution_net_buy_qty=self._to_int(
                self._first(row, "orgn_ntby_qty", "orgn_ntby_qtty", "orgn_ntby_qty2")
            ),
            institution_net_buy_amount=self._to_int(
                self._first(row, "orgn_ntby_tr_pbmn", "orgn_ntby_amt", "orgn_ntby_amount")
            ),
            status=FlowStatus.ESTIMATED,
            confidence=SignalConfidence.PRIMARY,
            source_tr_id=self.TR_ID,
            observed_at=observed_at,
        )
