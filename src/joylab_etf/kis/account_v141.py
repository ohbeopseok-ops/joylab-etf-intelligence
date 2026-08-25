from __future__ import annotations

import os
from typing import Any
import requests

from joylab_etf.kis.client_v141 import KISClient
from joylab_etf.kis.account_models import (
    AccountBalanceSnapshot,
    AccountPosition,
    AccountSummary,
)
from joylab_etf.kis.http_utils import safe_kis_error

BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


class KISAccountAdapter:
    def __init__(self, client: KISClient):
        self.client = client
        self.account_no = os.getenv("KIS_ACCOUNT_NO", "").strip()
        self.product_code = os.getenv("KIS_ACCOUNT_PRODUCT_CODE", "01").strip()

        if not self.account_no:
            raise RuntimeError("KIS_ACCOUNT_NO가 비어 있습니다.")

        if len(self.account_no) != 8 or not self.account_no.isdigit():
            raise RuntimeError("KIS_ACCOUNT_NO는 숫자 8자리여야 합니다.")

        if len(self.product_code) != 2:
            raise RuntimeError("KIS_ACCOUNT_PRODUCT_CODE는 2자리여야 합니다.")

    @property
    def tr_id(self) -> str:
        return "VTTC8434R" if self.client.settings.env == "paper" else "TTTC8434R"

    def get_balance(self, max_pages: int = 10) -> AccountBalanceSnapshot:
        url = f"{self.client.settings.base_url}{BALANCE_PATH}"

        fk100 = ""
        nk100 = ""
        tr_cont = ""
        positions: list[AccountPosition] = []
        summary: AccountSummary | None = None
        pages = 0

        while pages < max_pages:
            params = {
                "CANO": self.account_no,
                "ACNT_PRDT_CD": self.product_code,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": fk100,
                "CTX_AREA_NK100": nk100,
            }

            headers = self.client._auth_headers(self.tr_id)
            if tr_cont:
                headers["tr_cont"] = tr_cont

            self.client._throttle()
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=15,
            )

            if not response.ok:
                raise safe_kis_error(
                    response,
                    f"KIS 잔고조회 실패 env={self.client.settings.env}",
                )

            data: dict[str, Any] = response.json()

            if data.get("rt_cd") != "0":
                raise RuntimeError(
                    f"KIS 잔고조회 실패 env={self.client.settings.env}: "
                    f"msg_cd={data.get('msg_cd')} msg1={data.get('msg1')}"
                )

            pages += 1

            for row in data.get("output1") or []:
                qty = _num(row.get("hldg_qty")) or 0.0
                if qty <= 0:
                    continue

                positions.append(
                    AccountPosition(
                        symbol=str(row.get("pdno") or "").strip(),
                        name=str(row.get("prdt_name") or "").strip(),
                        quantity=qty,
                        orderable_quantity=_num(row.get("ord_psbl_qty")),
                        avg_price=_num(row.get("pchs_avg_pric")),
                        current_price=_num(row.get("prpr")),
                        purchase_amount=_num(row.get("pchs_amt")),
                        market_value=_num(row.get("evlu_amt")),
                        profit_loss=_num(row.get("evlu_pfls_amt")),
                        profit_loss_pct=_num(row.get("evlu_pfls_rt")),
                    )
                )

            output2 = data.get("output2") or []
            if output2 and summary is None:
                row = output2[0]
                summary = AccountSummary(
                    deposit_total=_num(row.get("dnca_tot_amt")),
                    securities_value=_num(row.get("scts_evlu_amt")),
                    total_evaluation=_num(row.get("tot_evlu_amt")),
                    net_asset=_num(row.get("nass_amt")),
                    purchase_total=_num(row.get("pchs_amt_smtl_amt")),
                    evaluation_total=_num(row.get("evlu_amt_smtl_amt")),
                    profit_loss_total=_num(row.get("evlu_pfls_smtl_amt")),
                )

            next_tr_cont = (response.headers.get("tr_cont") or "").strip()
            fk100 = str(data.get("ctx_area_fk100") or "").strip()
            nk100 = str(data.get("ctx_area_nk100") or "").strip()

            if next_tr_cont not in {"M", "F"}:
                break

            tr_cont = "N"

        deduped = {p.symbol: p for p in positions if p.symbol}

        return AccountBalanceSnapshot(
            positions=list(deduped.values()),
            summary=summary,
            pages=pages,
        )
