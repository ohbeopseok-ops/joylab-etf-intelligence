from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from joylab_etf.kis.client import KISClient
from joylab_etf.kis.investor_flow_models import ProgramTradeSnapshot

KST = timezone(timedelta(hours=9))


class KISProgramTradeAdapter:
    """종목별 프로그램매매추이(체결) 보조 신호 adapter.

    API: /uapi/domestic-stock/v1/quotations/program-trade-by-stock
    TR : FHPPG04650101

    이 값은 외국인 순매수의 대체값이 아니다.
    장중 외국인/기관 가집계가 아직 갱신되지 않았거나 stale일 때
    방향성 확인용 auxiliary signal로만 사용한다.
    """

    API_PATH = "/uapi/domestic-stock/v1/quotations/program-trade-by-stock"
    TR_ID = "FHPPG04650101"

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

    def get_latest(self, symbol: str, market: str = "J") -> ProgramTradeSnapshot:
        url = f"{self.client.settings.base_url}{self.API_PATH}"
        params = {
            "FID_COND_MRKT_DIV_CODE": market,
            "FID_INPUT_ISCD": symbol,
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
                f"KIS program trade 조회 실패: msg_cd={data.get('msg_cd')} "
                f"msg1={data.get('msg1')}"
            )

        output = data.get("output") or []
        if isinstance(output, dict):
            rows = [output]
        elif isinstance(output, list):
            rows = output
        else:
            rows = []

        observed_at = datetime.now(KST)
        if not rows:
            return ProgramTradeSnapshot(
                symbol=symbol,
                observed_at=observed_at,
            )

        row = rows[0]
        return ProgramTradeSnapshot(
            symbol=symbol,
            program_net_buy_qty=self._to_int(
                self._first(
                    row,
                    "whol_smtn_ntby_qty",
                    "prgm_ntby_qty",
                    "ntby_qty",
                )
            ),
            program_net_buy_amount=self._to_int(
                self._first(
                    row,
                    "whol_smtn_ntby_tr_pbmn",
                    "prgm_ntby_amt",
                    "ntby_tr_pbmn",
                )
            ),
            observed_at=observed_at,
        )
