from pathlib import Path
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from .config import settings
from .provider import MarketProvider
from .engine import evaluate,evaluate_ead

settings.validate_safety()
app=FastAPI(title="JoyLab KIS Realtime",version="0.2.1")
provider=MarketProvider()
STATIC=Path(__file__).parent/"static"
app.mount("/static",StaticFiles(directory=STATIC),name="static")

@app.get("/")
def home():return FileResponse(STATIC/"index.html")
@app.get("/api/health")
def health():return {"ok":True,"data_mode":settings.data_mode,"read_only":settings.read_only,"order_enabled":settings.order_enabled}
@app.get("/api/snapshot")
def snapshot():
    try:return provider.snapshot()
    except Exception as e:raise HTTPException(502,str(e))
@app.get("/api/decision")
def decision():
    try:return evaluate(provider.snapshot())
    except Exception as e:raise HTTPException(502,str(e))
@app.get("/api/ead-ranking")
def ead_ranking():
    try:return evaluate_ead(provider.snapshot())
    except Exception as e:raise HTTPException(502,str(e))
@app.get("/api/raw/flow/{ticker}")
def raw_flow(ticker:str):
    if settings.data_mode!="real" or provider.kis is None:return {"mode":"mock"}
    try:return provider.kis.investor_trend_estimate(ticker)
    except Exception as e:raise HTTPException(502,str(e))

if __name__=="__main__":uvicorn.run(app,host="127.0.0.1",port=8787)
