from __future__ import annotations
import threading,time
import requests
from .config import settings
from .models import FlowSnapshot

_LOCK=threading.Lock()

class KISClient:
    def __init__(self):
        self.base=settings.base_url; self.s=requests.Session(); self.token=None; self.exp=0.0
    def auth(self,force=False):
        with _LOCK:
            if not force and self.token and self.exp>time.time()+60:return self.token
            r=self.s.post(self.base+"/oauth2/tokenP",json={"grant_type":"client_credentials","appkey":settings.app_key,"appsecret":settings.app_secret},timeout=10)
            r.raise_for_status(); d=r.json(); self.token=d["access_token"]; self.exp=time.time()+int(d.get("expires_in",82800)); return self.token
    def _get(self,path,tr_id,params):
        h={"authorization":f"Bearer {self.auth()}","appkey":settings.app_key,"appsecret":settings.app_secret,"tr_id":tr_id}
        r=self.s.get(self.base+path,headers=h,params=params,timeout=10); r.raise_for_status(); d=r.json()
        if d.get("rt_cd")!="0": raise RuntimeError(f"KIS {d.get('msg_cd')}: {d.get('msg1')}")
        return d
    def current_price(self,ticker):
        return self._get("/uapi/domestic-stock/v1/quotations/inquire-price","FHKST01010100",{"FID_COND_MRKT_DIV_CODE":"J","FID_INPUT_ISCD":ticker}).get("output",{})
    def kospi_index(self):
        return self._get("/uapi/domestic-stock/v1/quotations/inquire-index-price","FHPUP02100000",{"FID_COND_MRKT_DIV_CODE":"U","FID_INPUT_ISCD":"0001"}).get("output",{})
    def investor_trend_estimate(self,ticker):
        return self._get("/uapi/domestic-stock/v1/quotations/investor-trend-estimate","HHPTJ04160200",{"MKSC_SHRN_ISCD":ticker})
    @staticmethod
    def parse_price(o):
        n=lambda k: float(str(o.get(k,0)).replace(",","") or 0)
        price=int(n("stck_prpr")); pct=n("prdy_ctrt"); vol=int(n("acml_vol")) if o.get("acml_vol") else None
        high=int(n("stck_hgpr")) if o.get("stck_hgpr") else None
        draw=round((price/high-1)*100,2) if high and high>0 else None
        return price,pct,vol,high,draw
    @staticmethod
    def parse_index(o):
        def f(keys):
            for k in keys:
                if o.get(k) not in (None,""): return float(str(o[k]).replace(",",""))
            return 0.0
        return f(["bstp_nmix_prpr","stck_prpr"]),f(["bstp_nmix_prdy_ctrt","prdy_ctrt"])
    @staticmethod
    def parse_flow(d):
        rows=d.get("output2") or d.get("output") or []
        if isinstance(rows,dict):rows=[rows]
        if not rows:return FlowSnapshot()
        r=rows[-1]
        def gi(keys):
            for k in keys:
                v=r.get(k)
                if v not in (None,""):
                    try:return int(float(str(v).replace(",","")))
                    except:pass
            return None
        f=gi(["frgn_ntby_qty","frgn_estm_ntby_qty","frgn_ntby_tr_pbmn"])
        i=gi(["orgn_ntby_qty","orgn_estm_ntby_qty","orgn_ntby_tr_pbmn"])
        t=str(r.get("stck_cntg_hour") or r.get("bsop_hour_gb") or "") or None
        return FlowSnapshot(foreign_net_qty=f,institution_net_qty=i,source_time=t,confidence="MEDIUM" if f is not None or i is not None else "UNKNOWN")
