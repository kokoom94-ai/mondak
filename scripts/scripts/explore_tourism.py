# -*- coding: utf-8 -*-
"""제주관광 빅데이터 플랫폼 — 응답 구조 탐색"""
import json, ssl, re, time, urllib.request

URL = "https://data.ijto.or.kr/api/dataPick/chart/renderChart.do"
CTX = ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
H = {
 "Content-Type":"application/json; charset=UTF-8",
 "Accept":"application/json, text/javascript, */*; q=0.01",
 "X-Requested-With":"XMLHttpRequest",
 "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
 "Referer":"https://data.ijto.or.kr/","Origin":"https://data.ijto.or.kr",
}

def call(regSn, idx=0, timeout=20):
    body=json.dumps({"regSn":str(regSn),"chartIndex":idx,
                     "searchDataBgnDt":"","searchDataEndDt":""}).encode()
    req=urllib.request.Request(URL,data=body,method="POST",headers=H)
    try:
        with urllib.request.urlopen(req,timeout=timeout,context=CTX) as r:
            return json.loads(r.read().decode("utf-8","replace"))
    except Exception as e:
        return {"_err":str(e)}

def caption(layout):
    m=re.search(r'text=\s*"([^"]+)"', layout or "")
    return m.group(1) if m else ""

def walk(o, path="", depth=0, out=None):
    if out is None: out=[]
    if depth>6: return out
    if isinstance(o,dict):
        for k,v in o.items():
            walk(v, f"{path}.{k}", depth+1, out)
    elif isinstance(o,list):
        if o and all(isinstance(x,(int,float)) for x in o if x is not None):
            out.append((path,"숫자배열",len(o),o[:5]))
        elif o and isinstance(o[0],dict):
            out.append((path,"객체배열",len(o),list(o[0].keys())[:10]))
            walk(o[0], f"{path}[0]", depth+1, out)
        else:
            for i,x in enumerate(o[:2]): walk(x, f"{path}[{i}]", depth+1, out)
    return out

print("="*60); print("1) regSn=17 응답 구조 해부"); print("="*60)
d=call(17)
if "_err" in d: print("오류:",d["_err"])
else:
    charts=(d.get("data") or {}).get("charts") or []
    print("charts 개수:",len(charts))
    for i,c in enumerate(charts):
        if not c: print(f"  [{i}] null"); continue
        print(f"\n  [{i}] 키: {list(c.keys())}")
        for k,v in c.items():
            t=type(v).__name__
            if isinstance(v,str):
                extra = f"  제목='{caption(v)}'" if 'layout' in k.lower() else ""
                print(f"      {k}: str({len(v)}자){extra}")
            elif isinstance(v,(list,dict)):
                print(f"      {k}: {t}(len={len(v)})")
            else:
                print(f"      {k}: {t} = {v}")
        print("\n  * 숫자/객체 배열 위치")
        for p,kind,n,sample in walk(c):
            print(f"      {p:38s} {kind} n={n} {str(sample)[:80]}")

print("\n"+"="*60); print("2) regSn 1~60 데이터셋 목록"); print("="*60)
found=[]
for sn in range(1,61):
    r=call(sn,timeout=12)
    if "_err" in r: print(f"  {sn:3d}: 오류 {r['_err'][:40]}"); continue
    ch=(r.get("data") or {}).get("charts") or []
    live=[c for c in ch if c]
    if live:
        caps=[caption(c.get("layout","")) for c in live]
        caps=[c for c in caps if c]
        found.append((sn,caps))
        print(f"  OK {sn:3d}: 차트 {len(live)}개 — {' / '.join(caps[:3])}")
    time.sleep(0.25)
print(f"\n유효 데이터셋: {len(found)}개")
