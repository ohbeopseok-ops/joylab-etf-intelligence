from __future__ import annotations

from typing import Any

from joylab_etf.kis.buying_power_models import BuyingPower

PATH = "/uapi/domestic-stock/v1/trading/inquire-psbl-order"


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


class KISBuyingPowerAdapter:
    def __init__(self, client, settings):
        self.client = client
        self.settings = settings

    @property
    def tr_id(self) -> str:
        return "VTTC8908R" if self.settings.env == "paper" else "TTTC8908R"

    def inquire(
        self,
        symbol: str,
        reference_price: float,
        include_cma: bool = False,
        include_overseas: bool = False,
    ) -> BuyingPower:
        url = f"{self.settings.base_url}{PATH}"

        params = {
            "CANO": self.settings.account_no,
            "ACNT_PRDT_CD": self.settings.account_product_code,
            "PDNO": symbol,
            "ORD_UNPR": str(int(reference_price)),
            "ORD_DVSN": "01",  # 시장가: 증거금율 반영한 가능수량 조회
            "CMA_EVLU_AMT_ICLD_YN": "Y" if include_cma else "N",
            "OVRS_ICLD_YN": "Y" if include_overseas else "N",
        }

        response = self.client.authorized_get(
            url=url,
            tr_id=self.tr_id,
            params=params,
            retry_on_expired_token=True,
        )

        if not response.ok:
            raise RuntimeError(
                f"KIS Buying Power HTTP {response.status_code}: "
                f"{response.text[:800]}"
            )

        data: dict[str, Any] = response.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS 매수가능조회 실패: "
                f"msg_cd={data.get('msg_cd')} msg1={data.get('msg1')}"
            )

        output = data.get("output") or {}

        return BuyingPower(
            symbol=symbol,
            reference_price=reference_price,
            order_possible_cash=_to_float(output.get("ord_psbl_cash")),
            no_credit_buy_amount=_to_float(output.get("nrcvb_buy_amt")),
            no_credit_buy_qty=_to_float(output.get("nrcvb_buy_qty")),
            max_buy_amount=_to_float(output.get("max_buy_amt")),
            max_buy_qty=_to_float(output.get("max_buy_qty")),
            calc_price=_to_float(output.get("psbl_qty_calc_unpr")),
        )
