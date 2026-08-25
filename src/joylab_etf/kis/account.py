from __future__ import annotations

from typing import Any
import requests

from joylab_etf.kis.account_models import AccountPosition, AccountSummary


BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


class KISAccountAdapter:
    def __init__(self, client, settings):
        self.client = client
        self.settings = settings

    @property
    def tr_id(self) -> str:
        return "VTTC8434R" if self.settings.env == "paper" else "TTTC8434R"

    def get_balance(self) -> tuple[list[AccountPosition], AccountSummary]:
        url = f"{self.settings.base_url}{BALANCE_PATH}"

        params = {
            "CANO": self.settings.account_no,
            "ACNT_PRDT_CD": self.settings.account_product_code,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }

        self.client._throttle()

        response = requests.get(
            url,
            headers=self.client._auth_headers(self.tr_id),
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS 잔고 조회 실패: "
                f"msg_cd={data.get('msg_cd')} msg1={data.get('msg1')}"
            )

        positions: list[AccountPosition] = []

        for row in data.get("output1") or []:
            qty = _to_float(row.get("hldg_qty")) or 0.0

            # KIS는 당일 전량매도 잔고를 0으로 잠시 반환할 수 있음.
            # 실제 보유 포트폴리오에는 수량 0 종목을 제외.
            if qty <= 0:
                continue

            positions.append(
                AccountPosition(
                    symbol=str(row.get("pdno") or "").strip(),
                    name=str(row.get("prdt_name") or "").strip(),
                    quantity=qty,
                    sellable_quantity=_to_float(row.get("ord_psbl_qty")),
                    avg_price=_to_float(row.get("pchs_avg_pric")),
                    purchase_amount=_to_float(row.get("pchs_amt")),
                    current_price=_to_float(row.get("prpr")),
                    market_value=_to_float(row.get("evlu_amt")),
                    profit_loss=_to_float(row.get("evlu_pfls_amt")),
                    profit_loss_pct=_to_float(row.get("evlu_pfls_rt")),
                )
            )

        summary_row = (data.get("output2") or [{}])[0] if isinstance(data.get("output2"), list) else {}

        summary = AccountSummary(
            cash=_to_float(summary_row.get("dnca_tot_amt")),
            securities_value=_to_float(summary_row.get("scts_evlu_amt")),
            total_evaluation=_to_float(summary_row.get("tot_evlu_amt")),
            net_asset=_to_float(summary_row.get("nass_amt")),
            total_purchase_amount=_to_float(summary_row.get("pchs_amt_smtl_amt")),
            total_profit_loss=_to_float(summary_row.get("evlu_pfls_smtl_amt")),
        )

        return positions, summary
