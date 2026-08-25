from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from joylab_etf.config_v014 import Settings as AccountSettings
from joylab_etf.intelligence.portfolio_gate import evaluate_portfolio_gate
from joylab_etf.intelligence.portfolio_gate_models import GateInput, GateResult, PortfolioGatePolicy
from joylab_etf.intelligence.true_exposure_v015 import TrueExposureReport, build_true_exposure_report
from joylab_etf.kis.account import KISAccountAdapter
from joylab_etf.kis.buying_power import KISBuyingPowerAdapter
from joylab_etf.kis.client_v0142 import KISClient as AccountClient
from joylab_etf.kis.etf_v015 import KISETFAdapter


class PortfolioDataUnavailable(Exception):
    """KIS_ACCOUNT_NO/PRODUCT_CODE not configured. Callers must show UNKNOWN,
    never fall back to a guessed 0 or an invented balance."""


def load_etf_and_cluster_membership(
    instruments_path: Path, ai_power_path: Path
) -> tuple[set[str], dict[str, str]]:
    """ETF symbol set + {member_symbol: cluster_name}.

    Only "semiconductor" has a cap in portfolio_policy.json today, so that
    is the only cluster_name callers can pass to evaluate_portfolio_gate
    without inventing a policy value.
    """
    instruments = json.loads(instruments_path.read_text(encoding="utf-8"))
    ai_power = json.loads(ai_power_path.read_text(encoding="utf-8"))

    etf_symbols = set(instruments.get("etfs", []))
    etf_symbols |= {etf["symbol"] for etf in ai_power.get("etfs", [])}

    cluster_membership: dict[str, str] = {}
    for cluster_name, symbols in instruments.get("clusters", {}).items():
        for symbol in symbols:
            cluster_membership[symbol] = cluster_name
    for cluster_name, symbols in ai_power.get("clusters", {}).items():
        for symbol in symbols:
            cluster_membership.setdefault(symbol, cluster_name)

    return etf_symbols, cluster_membership


class PortfolioStateProvider:
    """Real KIS account balance + True Exposure + Portfolio Gate, reused by
    both scripts/analyst.py's CLI path and the Telegram assistant.

    Every public method raises PortfolioDataUnavailable if the account env
    vars are unset, rather than defaulting to 0/empty -- an unconfigured
    account is UNKNOWN, not "no position".
    """

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self._settings: AccountSettings | None = None
        self._client: AccountClient | None = None
        self._etf_symbols: set[str] | None = None
        self._cluster_membership: dict[str, str] | None = None
        self._policy: PortfolioGatePolicy | None = None

    def _ensure(self) -> None:
        if self._settings is not None:
            return
        try:
            self._settings = AccountSettings.from_env()
        except Exception as exc:
            raise PortfolioDataUnavailable(str(exc)) from exc
        self._client = AccountClient(self._settings)
        self._etf_symbols, self._cluster_membership = load_etf_and_cluster_membership(
            self.config_dir / "instruments.json",
            self.config_dir / "ai_power_universe.json",
        )
        self._policy = PortfolioGatePolicy(
            **json.loads((self.config_dir / "portfolio_policy.json").read_text(encoding="utf-8"))
        )

    def get_exposure_report(self) -> tuple[TrueExposureReport, list[Any], Any]:
        """(report, positions, account_summary). One live KIS balance call."""
        self._ensure()
        assert self._client is not None and self._settings is not None
        account = KISAccountAdapter(self._client, self._settings)
        positions, summary = account.get_balance()

        etf_adapter = KISETFAdapter(self._client)
        etf_snapshots: dict[str, Any] = {}
        assert self._etf_symbols is not None
        for position in positions:
            if position.symbol in self._etf_symbols and position.quantity > 0:
                etf_snapshots[position.symbol] = etf_adapter.get_components(position.symbol)

        assert self._cluster_membership is not None
        semiconductor_symbols = {
            symbol
            for symbol, cluster in self._cluster_membership.items()
            if cluster == "semiconductor"
        }
        report = build_true_exposure_report(
            positions=positions,
            etf_snapshots=etf_snapshots,
            semiconductor_symbols=semiconductor_symbols,
            total_account_evaluation=summary.total_evaluation,
        )
        return report, positions, summary

    def get_buying_power(self, symbol: str, reference_price: float) -> Any:
        """KIS no-credit buyable amount/qty for `symbol` at `reference_price`.
        Symbol/price-dependent -- there is no single account-wide "orderable
        amount" per CLAUDE.md (dnca_tot_amt is explicitly not authoritative)."""
        self._ensure()
        assert self._client is not None and self._settings is not None
        buying_power = KISBuyingPowerAdapter(self._client, self._settings)
        return buying_power.inquire(symbol=symbol, reference_price=reference_price)

    def get_gate_result(self, symbol: str, name: str, current_price: float) -> GateResult | None:
        """Real Portfolio Gate for `symbol`. None if its cluster has no
        configured cap (e.g. power_equipment) -- never invents one."""
        self._ensure()
        assert self._cluster_membership is not None and self._policy is not None
        cluster_name = self._cluster_membership.get(symbol)
        if cluster_name != "semiconductor":
            return None

        report, _positions, summary = self.get_exposure_report()
        if summary.total_evaluation is None:
            return None

        target_row = next((row for row in report.rows if row.symbol == symbol), None)
        direct_value = target_row.direct_value if target_row else 0.0
        indirect_value = target_row.indirect_value if target_row else 0.0
        true_exposure_value = target_row.total_value if target_row else 0.0

        assert self._client is not None and self._settings is not None
        buying_power = KISBuyingPowerAdapter(self._client, self._settings)
        bp = buying_power.inquire(symbol=symbol, reference_price=current_price)

        gate_input = GateInput(
            symbol=symbol,
            name=name,
            current_price=current_price,
            direct_value=direct_value,
            indirect_value=indirect_value,
            true_exposure_value=true_exposure_value,
            total_account_value=summary.total_evaluation,
            securities_value=report.securities_value,
            cluster_name=cluster_name,
            cluster_value=report.semiconductor_value,
            kis_buyable_qty=int(bp.no_credit_buy_qty or 0),
            kis_buyable_amount=bp.no_credit_buy_amount or 0.0,
        )
        return evaluate_portfolio_gate(gate_input, self._policy)
