from __future__ import annotations

from fastapi import FastAPI, HTTPException

from joylab_etf.config_v014 import Settings
from joylab_etf.kis.client import KISClient
from joylab_etf.kis.investor_flow_intraday import KISIntradayInvestorFlowAdapter
from joylab_etf.kis.program_trade import KISProgramTradeAdapter

app = FastAPI(
    title="JoyLab Market Gateway",
    version="0.1.7",
    description="Read-only KIS market data gateway for JoyLab PC/mobile clients.",
)


def _build_clients():
    settings = Settings.from_env()
    client = KISClient(settings)
    return (
        client,
        KISIntradayInvestorFlowAdapter(client),
        KISProgramTradeAdapter(client),
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "joylab-market-gateway", "read_only": True}


@app.get("/v1/market/{symbol}/quote")
def quote(symbol: str):
    client, _, _ = _build_clients()
    try:
        data = client.get_domestic_quote(symbol.zfill(6))
        return data.model_dump(mode="json")
    except Exception as exc:  # preserve KIS error in detail during development
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/v1/market/{symbol}/investor-flow")
def investor_flow(symbol: str, name: str | None = None, market_index_code: str = "0001"):
    _, flow_adapter, _ = _build_clients()
    try:
        data = flow_adapter.get_symbol(
            symbol.zfill(6),
            name=name,
            market_index_code=market_index_code,
        )
        return data.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/v1/market/{symbol}/program-trade")
def program_trade(symbol: str, market: str = "J"):
    _, _, program_adapter = _build_clients()
    try:
        data = program_adapter.get_latest(symbol.zfill(6), market=market)
        return data.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/v1/market/{symbol}/snapshot")
def snapshot(symbol: str, name: str | None = None, market_index_code: str = "0001", market: str = "J"):
    client, flow_adapter, program_adapter = _build_clients()
    try:
        quote_data = client.get_domestic_quote(symbol.zfill(6))
        flow_data = flow_adapter.get_symbol(
            symbol.zfill(6),
            name=name,
            market_index_code=market_index_code,
        )
        program_data = program_adapter.get_latest(symbol.zfill(6), market=market)
        return {
            "symbol": symbol.zfill(6),
            "quote": quote_data.model_dump(mode="json"),
            "investor_flow": flow_data.model_dump(mode="json"),
            "program_trade": program_data.model_dump(mode="json"),
            "read_only": True,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
