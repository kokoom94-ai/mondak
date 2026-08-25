# -*- coding: utf-8 -*-
"""
제주관광 빅데이터 — 대상 데이터셋 구조 덤프
화면 설계에 필요한 필드·값 범위를 확인합니다. (저장 없음, 로그만)
"""
import json, ssl, re, time, urllib.request

URL="https://data.ijto.or.kr/api/dataPick/chart/renderChart.do"
CTX=ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
H={"Content-Type":"application/json; charset=UTF-8",
   "Accept":"application/json, text/javascript, */*; q=0.01",
   "X-Requested-With":"XMLHttpRequest",
   "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
   "Referer":"https://data.ijto.or.kr/","Origin":"https://data.ijto.or.kr"}

TARGET=[
 (17,"월별 입도 관광객"),(18,"일별 입도 관광객"),(19,"국가별 외국인 입도객"),
 (21,"통신사 지역별 방문객"),(23,"시도별 증감률"),(27,"읍면동별 소비금액"),
 (32,"카드 소비금액 합계"),(35,"월별 매출 관광객vs도민"),
 (39,"시간대별 패턴 관광객vs도민"),(41,"업종별 소비금액"),
 (48,"지역별 인기 장소"),(51,"읍면동별 도착 수"),(43,"제목없음"),
]

def call(sn, idx=0):
    b=json.dumps({"regSn":str(sn),"chartIndex":idx,
                  "searchDataBgnDt":"","searchDataEndDt":""}).encode()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(URL,data=b,method="POST",headers=H),
            timeout=20,context=CTX) as r:
            return json.loads(r.read().decode("utf-8","replace"))
    except Exception as e:
        return {"_err":str(e)}

def cap(l):
    m=re.search(r'text=\s*"([^"]+)"', l or ""); return m.group(1) if m else ""

for sn,label in TARGET:
    print("\n"+"="*66)
    print(f"regSn={sn}  {label}")
    print("="*66)
    d=call(sn)
    if "_err" in d: print("  오류:",d["_err"]); continue
    dd=d.get("data") or {}
    charts=dd.get("charts") or []
    print(f"  기간: {dd.get('dataBgnDt')} ~ {dd.get('dataEndDt')} | charts={len(charts)}")
    for ci,c in enumerate(charts):
        if not c or not c.get("data"): continue
        rows=c["data"]
        print(f"\n  --- chartIndex={ci} | 제목: {cap(c.get('layout',''))} | type={c.get('type')} ---")
        print(f"      행 수: {len(rows)}")
        if isinstance(rows,list) and rows and isinstance(rows[0],dict):
            keys=list(rows[0].keys())
            print(f"      필드({len(keys)}): {keys}")
            print("      샘플 2행:")
            for r in rows[:2]:
                print("       ", json.dumps(r,ensure_ascii=False)[:300])
            print("      마지막 행:")
            print("       ", json.dumps(rows[-1],ensure_ascii=False)[:300])
    time.sleep(0.3)
print("\n덤프 종료")
