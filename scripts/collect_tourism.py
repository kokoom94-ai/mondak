# -*- coding: utf-8 -*-
"""
제주관광 빅데이터 수집 — 읍면동(21) · 카드매출(35) · 시간대(39)
출처: 제주관광 빅데이터 서비스 플랫폼 (제주관광공사)
※ 계산만 하고 원인 해석은 하지 않습니다.
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
    for a in (1,2):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(URL,data=b,method="POST",headers=H),
                timeout=15,context=CTX) as r:
                return json.loads(r.read().decode("utf-8","replace"))
        except Exception as e:
            if a==2: print(f"  ! regSn={sn} 실패: {e}"); return None
            time.sleep(1.5)

def cap(l):
    m=re.search(r'text=\s*"([^"]+)"', l or "")
    return re.sub(r'\s+',' ',m.group(1)).strip() if m else ""

def first(d):
    if not d: return None,None
    dd=d.get("data") or {}
    for c in dd.get("charts") or []:
        if c and c.get("data"): return c,dd
    return None,dd

def num(v): return v if isinstance(v,(int,float)) else None

out={"meta":{"updated":time.strftime("%Y-%m-%d"),
     "source":"제주관광 빅데이터 서비스 플랫폼 (제주관광공사)",
     "disclaimer":"공개 통계를 계산해 정리한 참고자료입니다. 원인 해석은 포함하지 않습니다."}}

# ══ ① 읍면동 방문객 (21) ══
print("① 읍면동 방문객")
c,dd=first(call(21))
if c:
    items=[]
    for r in c["data"]:
        nm=(r.get("groupVal") or "").strip()
        if not nm: continue
        n,f=r.get("nativeVal") or 0, r.get("foreignVal") or 0
        items.append({"name":nm,"native":n,"foreign":f,
          "native_yoy":num(r.get("nativeVal_yoy")),"native_mom":num(r.get("nativeVal_mom")),
          "foreign_yoy":num(r.get("foreignVal_yoy")),"foreign_mom":num(r.get("foreignVal_mom")),
          "foreign_ratio":round(f/(n+f)*100,2) if (n+f) else 0})
    items.sort(key=lambda x:-x["native"])
    for i,x in enumerate(items,1): x["rank"]=i
    # ── 편차 기반 판정: 43곳 평균에서 얼마나 벗어났나(표준편차 배수)
    import statistics as _st
    NY=[x["native_yoy"] for x in items if isinstance(x["native_yoy"],(int,float))]
    FY=[x["foreign_yoy"] for x in items if isinstance(x["foreign_yoy"],(int,float))]
    mn=_st.mean(NY) if NY else 0; sdn=_st.pstdev(NY) if len(NY)>1 else 0
    mf=_st.mean(FY) if FY else 0; sdf=_st.pstdev(FY) if len(FY)>1 else 0
    Z=1.5   # 이 배수 이상 벗어나면 이례
    alerts=[]
    for x in items:
        ny,fy=x["native_yoy"],x["foreign_yoy"]; t=[]
        zn = (ny-mn)/sdn if (isinstance(ny,(int,float)) and sdn) else 0
        zf = (fy-mf)/sdf if (isinstance(fy,(int,float)) and sdf) else 0
        x["z_native"]=round(zn,2); x["z_foreign"]=round(zf,2)
        if abs(zn)>=Z: t.append(("내국인 크게 늘어남" if zn>0 else "내국인 크게 줄어듦"))
        if abs(zf)>=Z: t.append(("외국인 크게 늘어남" if zf>0 else "외국인 덜 늘어남"))
        x["flags"]=t
        if t: alerts.append({"name":x["name"],"tags":t,
          "native_yoy":ny,"native_mom":x["native_mom"],
          "foreign_yoy":fy,"foreign_mom":x["foreign_mom"],
          "z_native":round(zn,2),"z_foreign":round(zf,2),
          "z_max":round(max(abs(zn),abs(zf)),2)})
    alerts.sort(key=lambda a:-a["z_max"])
    # 전체 분포 요약(화면에서 "평균은 이렇다"를 말하기 위해)
    dist={"native":{"mean":round(mn,1),"sd":round(sdn,1),"min":round(min(NY),1) if NY else None,"max":round(max(NY),1) if NY else None},
          "foreign":{"mean":round(mf,1),"sd":round(sdf,1),"min":round(min(FY),1) if FY else None,"max":round(max(FY),1) if FY else None},
          "z":Z}
    avg=round(sum(x["foreign_ratio"] for x in items)/len(items),2)
    intl=sorted([x for x in items if x["foreign_ratio"]>=avg*2],key=lambda z:-z["foreign_ratio"])[:5]
    out["emd"]={"month":dd.get("dataBgnDt"),"count":len(items),"avg_foreign_ratio":avg,
      "items":items,"alerts":alerts,"dist":dist,
      "intl_spots":[{"name":x["name"],"ratio":x["foreign_ratio"],
                     "foreign":x["foreign"],"native":x["native"]} for x in intl]}
    print(f"   {len(items)}곳 · 판정 {len(alerts)}건")

# ══ ② 카드매출 관광객vs도민 (35) ══
print("② 카드매출 관광객vs도민")
c,dd=first(call(35))
if c:
    KT,KD="내국인 관광객","도민"
    rows=[]
    for r in c["data"]:
        t,d=r.get(KT) or 0, r.get(KD) or 0
        rows.append({"date":r.get("dateVal"),"tourist":t,"local":d,
          "tourist_share":num(r.get(KT+"_share")),"local_share":num(r.get(KD+"_share")),
          "tourist_yoy":num(r.get(KT+"_yoy")),"local_yoy":num(r.get(KD+"_yoy"))})
    rows.sort(key=lambda x:x["date"])
    fst,lst=rows[0],rows[-1]
    out["card"]={"period":f"{fst['date']}~{lst['date']}","latest":lst["date"],
      "items":rows,
      "trend":{"share_first":fst["tourist_share"],"share_last":lst["tourist_share"],
               "share_delta":round((lst["tourist_share"] or 0)-(fst["tourist_share"] or 0),1)}}
    print(f"   {len(rows)}개월 · 관광객비중 {fst['tourist_share']}%→{lst['tourist_share']}%")

# ══ ③ 시간대별 (39) ══
print("③ 시간대별 소비 패턴")
c,dd=first(call(39))
if c:
    KT,KD="내국인 관광객","도민"
    hrs=[]
    for r in c["data"]:
        g=r.get("groupVal")
        hrs.append({"hour":int(g) if str(g).isdigit() else g,
          "tourist":r.get(KT) or 0,"local":r.get(KD) or 0,
          "tourist_share":num(r.get(KT+"_share"))})
    hrs.sort(key=lambda x:x["hour"] if isinstance(x["hour"],int) else 99)
    valid=[x for x in hrs if isinstance(x["tourist_share"],(int,float))]
    hi=max(valid,key=lambda x:x["tourist_share"]) if valid else None
    lo=min(valid,key=lambda x:x["tourist_share"]) if valid else None
    tmax=max(hrs,key=lambda x:x["tourist"]); lmax=max(hrs,key=lambda x:x["local"])
    out["hourly"]={"month":dd.get("dataBgnDt"),"items":hrs,
      "peak_tourist":tmax["hour"],"peak_local":lmax["hour"],
      "share_high":{"hour":hi["hour"],"share":hi["tourist_share"]} if hi else None,
      "share_low":{"hour":lo["hour"],"share":lo["tourist_share"]} if lo else None}
    print(f"   24시간 · 관광객피크 {tmax['hour']}시 / 도민피크 {lmax['hour']}시")


# ══ ④ 업종별 소비 (41) ══
print("④ 업종별 소비")
c,dd=first(call(41))
if c:
    # 값 필드명 자동 탐지 (sumVal / 소비금액 / value 등)
    keys=list(c["data"][0].keys()) if c["data"] else []
    print("   필드:", keys[:8])
    VK=next((k for k in keys
             if k not in ("groupVal","dateVal")
             and not k.endswith(("_share","_mom","_yoy","_mom_sum","_yoy_sum"))), None)
    print("   값 필드:", VK)
    rows=[]
    for r in c["data"]:
        g=(r.get("groupVal") or "").strip()
        if not g: continue
        rows.append({"name":g,
          "value":(r.get(VK) or 0) if VK else 0,
          "share":num(r.get((VK or "")+"_share")),
          "yoy":num(r.get((VK or "")+"_yoy")),
          "mom":num(r.get((VK or "")+"_mom"))})
    rows.sort(key=lambda x:-(x["value"] or 0))
    out["industry"]={"month":dd.get("dataBgnDt"),"count":len(rows),"items":rows}
    print(f"   {len(rows)}개 업종")

# ══ ⑤ 계절 격차 (17 월별 입도) ══
print("⑤ 계절 격차")
c,dd=first(call(17))
if c:
    ms=[]
    for r in c["data"]:
        d_=r.get("domesticVal") or 0; f_=r.get("foreignVal") or 0
        ms.append({"date":r.get("dateVal"),"domestic":d_,"foreign":f_,"total":d_+f_,
                   "domestic_yoy":num(r.get("domesticVal_yoy")),
                   "foreign_yoy":num(r.get("foreignVal_yoy"))})
    ms.sort(key=lambda x:x["date"])
    hi=max(ms,key=lambda x:x["total"]); lo=min(ms,key=lambda x:x["total"])
    out["monthly"]={"period":f"{ms[0]['date']}~{ms[-1]['date']}","items":ms,
      "peak":{"month":hi["date"],"total":hi["total"]},
      "low":{"month":lo["date"],"total":lo["total"]},
      "gap_ratio":round(hi["total"]/lo["total"],2) if lo["total"] else None}
    print(f"   최성수기 {hi['date']} {hi['total']:,} / 최비수기 {lo['date']} {lo['total']:,}")


# ══ ⑥ 항공 운항 (50) — 국내선·국제선 회복률 ══
print("⑥ 항공 운항")
c,dd=first(call(50))
if c:
    rows=c["data"]
    keys=list(rows[0].keys()) if rows else []
    print("   필드:", keys[:10])
    # 국내/국제 필드명 자동 탐지
    dom_k=next((k for k in keys if ("국내" in k) and not k.endswith(("_share","_mom","_yoy","_mom_sum","_yoy_sum"))), None)
    int_k=next((k for k in keys if ("국제" in k) and not k.endswith(("_share","_mom","_yoy","_mom_sum","_yoy_sum"))), None)
    date_k=next((k for k in keys if k in ("dateVal","groupVal")), keys[0] if keys else None)
    items=[]
    for r in rows:
        it={"date":r.get(date_k)}
        if dom_k: it["domestic"]=r.get(dom_k) or 0; it["domestic_yoy"]=num(r.get(dom_k+"_yoy"))
        if int_k: it["intl"]=r.get(int_k) or 0; it["intl_yoy"]=num(r.get(int_k+"_yoy"))
        if not dom_k and not int_k:
            # 구분 없이 단일 값
            vk=next((k for k in keys if k!=date_k and isinstance(r.get(k),(int,float))), None)
            if vk: it["total"]=r.get(vk) or 0; it["total_yoy"]=num(r.get(vk+"_yoy"))
        items.append(it)
    items.sort(key=lambda x:str(x.get("date")))
    out["air"]={"period":f"{dd.get('dataBgnDt')}~{dd.get('dataEndDt')}",
      "title":cap(c.get("layout","")),
      "field_domestic":dom_k,"field_intl":int_k,
      "items":items}
    print(f"   {len(items)}건 · 국내={dom_k} 국제={int_k}")

# ══ ⑦ 여객선 (52) ══
print("⑦ 여객선")
c,dd=first(call(52))
if c:
    rows=c["data"]; keys=list(rows[0].keys()) if rows else []
    date_k=next((k for k in keys if k in ("dateVal","groupVal")), keys[0] if keys else None)
    vk=next((k for k in keys if k!=date_k and not k.endswith(("_share","_mom","_yoy","_mom_sum","_yoy_sum"))), None)
    its=[{"date":r.get(date_k),"value":r.get(vk) or 0,"yoy":num(r.get((vk or "")+"_yoy"))} for r in rows]
    its.sort(key=lambda x:str(x["date"]))
    out["ship"]={"period":f"{dd.get('dataBgnDt')}~{dd.get('dataEndDt')}",
      "title":cap(c.get("layout","")),"field":vk,"items":its}
    print(f"   {len(its)}건 · 값필드={vk}")


# ══ ⑧ 일별 입도객 (18) ══
print("⑧ 일별 입도객")
c,dd=first(call(18))
if c:
    rows=[]
    for r in c["data"]:
        rows.append({"date":r.get("dateVal"),
          "kor":r.get("visitorKor") or 0,"forgn":r.get("visitorFor") or 0,
          "total":r.get("Total") or ((r.get("visitorKor") or 0)+(r.get("visitorFor") or 0)),
          "kor_yoy":num(r.get("visitorKor_yoy")),"forgn_yoy":num(r.get("visitorFor_yoy")),
          "total_yoy":num(r.get("Total_yoy"))})
    rows.sort(key=lambda x:str(x["date"]))
    out["daily"]={"period":f"{dd.get('dataBgnDt')}~{dd.get('dataEndDt')}","items":rows}
    print(f"   {len(rows)}일치 · 최신 {rows[-1]['date']} 합계 {rows[-1]['total']:,}명")

os.makedirs(os.path.dirname(OUT),exist_ok=True)
json.dump(out,open(OUT,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("저장:",os.path.relpath(OUT))
