# -*- coding: utf-8 -*-
"""
제주관광 빅데이터 — 읍면동 방문객 수집 (regSn=21)
출처: 제주관광 빅데이터 서비스 플랫폼 (제주관광공사)
"""
import json, ssl, re, os, time, urllib.request

URL="https://data.ijto.or.kr/api/dataPick/chart/renderChart.do"
CTX=ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
H={"Content-Type":"application/json; charset=UTF-8",
   "Accept":"application/json, text/javascript, */*; q=0.01",
   "X-Requested-With":"XMLHttpRequest",
   "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
   "Referer":"https://data.ijto.or.kr/","Origin":"https://data.ijto.or.kr"}
HERE=os.path.dirname(os.path.abspath(__file__))
OUT=os.path.join(HERE,"..","data","tourism.json")

def call(sn, idx=0):
    b=json.dumps({"regSn":str(sn),"chartIndex":idx,
                  "searchDataBgnDt":"","searchDataEndDt":""}).encode()
    with urllib.request.urlopen(
        urllib.request.Request(URL,data=b,method="POST",headers=H),
        timeout=20,context=CTX) as r:
        return json.loads(r.read().decode("utf-8","replace"))

def cap(l):
    m=re.search(r'text=\s*"([^"]+)"', l or ""); return m.group(1) if m else ""

def first_data(d):
    for c in (d.get("data") or {}).get("charts") or []:
        if c and c.get("data"): return c
    return None

out={"meta":{"updated":time.strftime("%Y-%m-%d"),
     "source":"제주관광 빅데이터 서비스 플랫폼 (제주관광공사)",
     "disclaimer":"공개 통계를 정리한 참고자료이며 원인 해석은 포함하지 않습니다."}}

# ── 읍면동 방문객 (regSn=21)
print("읍면동 방문객 수집…")
d=call(21); c=first_data(d)
if not c: print("  데이터 없음"); raise SystemExit(1)
dd=d.get("data") or {}
rows=c["data"]
items=[]
for r in rows:
    nm=(r.get("groupVal") or "").strip()
    if not nm: continue
    items.append({
      "name":nm,
      "native":r.get("nativeVal") or 0,
      "native_yoy":r.get("nativeVal_yoy"),
      "native_mom":r.get("nativeVal_mom"),
      "foreign":r.get("foreignVal") or 0,
      "foreign_yoy":r.get("foreignVal_yoy"),
      "foreign_mom":r.get("foreignVal_mom"),
      "native_share":r.get("nativeVal_share"),
      "foreign_share":r.get("foreignVal_share"),
    })
items.sort(key=lambda x:-x["native"])
for i,x in enumerate(items,1): x["rank"]=i

# ── 자동 판정 (계산만, 원인 없음)
def f(v): return v if isinstance(v,(int,float)) else None
flags=[]
for x in items:
    ny,fy=f(x["native_yoy"]),f(x["foreign_yoy"])
    tags=[]
    if ny is not None and fy is not None:
        if ny<0 and fy>0: tags.append("엇갈림·내국인↓외국인↑")
        elif ny>0 and fy<0: tags.append("엇갈림·내국인↑외국인↓")
    if ny is not None and abs(ny)>=20: tags.append(("급증" if ny>0 else "급감")+"·내국인")
    if fy is not None and abs(fy)>=30: tags.append(("급증" if fy>0 else "급감")+"·외국인")
    # 외국인 비중이 평균보다 뚜렷이 높은 곳
    tot=x["native"]+x["foreign"]
    x["foreign_ratio"]=round(x["foreign"]/tot*100,2) if tot else 0
    x["flags"]=tags
    if tags: flags.append({"name":x["name"],"tags":tags,"native_yoy":ny,"foreign_yoy":fy})

avg_fr=round(sum(x["foreign_ratio"] for x in items)/len(items),2)
intl=sorted([x for x in items if x["foreign_ratio"]>=avg_fr*2],
            key=lambda z:-z["foreign_ratio"])[:5]

out["emd"]={"month":dd.get("dataBgnDt"),"title":cap(c.get("layout","")),
  "count":len(items),"avg_foreign_ratio":avg_fr,
  "items":items,
  "alerts":flags[:12],
  "intl_spots":[{"name":x["name"],"ratio":x["foreign_ratio"],
                 "foreign":x["foreign"],"native":x["native"]} for x in intl]}

os.makedirs(os.path.dirname(OUT),exist_ok=True)
json.dump(out,open(OUT,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print(f"  {len(items)}개 읍면동 | 판정 {len(flags)}건 | 외국인비중 평균 {avg_fr}%")
print("저장:",os.path.relpath(OUT))
