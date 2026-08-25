# -*- coding: utf-8 -*-
"""
소비 계열 최신 데이터 탐색
- searchDataBgnDt/EndDt 에 값을 넣으면 더 최신이 오는지 확인
- 대상: 41(업종별) · 35(카드매출) · 27(읍면동소비) · 32(소비합계)
"""
import json, ssl, re, time, urllib.request

URL="https://data.ijto.or.kr/api/dataPick/chart/renderChart.do"
CTX=ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
H={"Content-Type":"application/json; charset=UTF-8","Accept":"application/json, */*",
   "X-Requested-With":"XMLHttpRequest",
   "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
   "Referer":"https://data.ijto.or.kr/","Origin":"https://data.ijto.or.kr"}

def call(sn, bgn="", end="", idx=0, timeout=15):
    b=json.dumps({"regSn":str(sn),"chartIndex":idx,
                  "searchDataBgnDt":bgn,"searchDataEndDt":end}).encode()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(URL,data=b,method="POST",headers=H),
            timeout=timeout,context=CTX) as r:
            return json.loads(r.read().decode("utf-8","replace"))
    except Exception as e:
        return {"_err":str(e)}

def cap(l):
    m=re.search(r'text=\s*"([^"]+)"', l or "")
    return re.sub(r'\s+',' ',m.group(1)).strip() if m else ""

def first(d):
    dd=(d or {}).get("data") or {}
    for c in dd.get("charts") or []:
        if c and c.get("data"): return c, dd
    return None, dd

TARGET=[(41,"업종별 소비"),(35,"카드매출 관광객vs도민"),
        (27,"읍면동별 소비금액"),(32,"카드 소비금액 합계"),(39,"시간대별 패턴")]

for sn,label in TARGET:
    print("\n"+"="*64)
    print(f"regSn={sn}  {label}")
    print("="*64)

    # ① 기본 호출 (파라미터 없음)
    c,dd=first(call(sn))
    if not c:
        print("  ❌ 데이터 없음"); continue
    base_b, base_e = dd.get("dataBgnDt"), dd.get("dataEndDt")
    rows=c["data"]
    print(f"  [기본]     기간 {base_b} ~ {base_e} · {len(rows)}행")
    print(f"             제목 {cap(c.get('layout',''))}")
    if rows and isinstance(rows[0],dict):
        ks=list(rows[0].keys())
        print(f"             필드 {ks[:6]}")
        # 날짜형 필드가 있으면 실제 최신값
        dk=next((k for k in ks if k in ("dateVal","groupVal")), None)
        if dk:
            vals=[str(r.get(dk)) for r in rows]
            print(f"             {dk} 범위: {vals[0]} ~ {vals[-1]}")

    # ② 최신 기간을 명시해서 재요청
    for bgn,end in [("202601","202612"),("202506","202606"),("202401","202612")]:
        d2=call(sn,bgn,end)
        c2,dd2=first(d2)
        if "_err" in d2:
            print(f"  [{bgn}~{end}] 오류 {d2['_err'][:40]}"); continue
        if not c2:
            print(f"  [{bgn}~{end}] 데이터 없음"); continue
        nb,ne=dd2.get("dataBgnDt"),dd2.get("dataEndDt")
        mark=" ★ 더 최신!" if (ne and base_e and str(ne)>str(base_e)) else ""
        print(f"  [{bgn}~{end}] → {nb} ~ {ne} · {len(c2['data'])}행{mark}")
        time.sleep(0.3)
print("\n탐색 종료")
