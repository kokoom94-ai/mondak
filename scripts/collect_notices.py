#!/usr/bin/env python3
"""몬딱 지원서비스 수집기 v3 — 정부24 공공서비스 개방 API(공공데이터포털).
해외IP 차단 없는 공식 API. 제주 관련 서비스만 추려 직링크와 함께 data/policies.json 생성.
필요 환경변수: GOV24_KEY (data.go.kr 인증키, 디코딩키 권장)"""
import json, os, re, ssl, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST=timezone(timedelta(hours=9)); NOW=datetime.now(KST)
OUT=Path(__file__).resolve().parent.parent/"data"/"policies.json"
KEY=os.environ.get("GOV24_KEY","").strip()
BASE="https://api.odcloud.kr/api/gov24/v3/serviceList"

RULES=[("welfare",r"복지|돌봄|어르신|노인|장애|아동|보육|의료|건강|바우처|지원금|생리대|임산부|수당|급여"),
 ("agri",r"감귤|농업|농가|어업|축산|수산|귀농|비료"),
 ("env",r"환경|에너지|재활용|전기차|탄소|신재생"),
 ("youth",r"학교|학생|교육|청년|장학|평생학습"),
 ("tour",r"관광|축제|문화|공연"),
 ("ax",r"AI|인공지능|디지털|데이터|정보화"),
 ("startup",r"창업|소상공인|기업|일자리|취업|고용|경제"),
 ("civic",r"안전|재난|민원|교통|주거|법률")]
WHO=[("이동약자·어르신",r"어르신|노인|장애|경로"),("육아·양육",r"임산부|출산|아동|보육|육아|한부모"),
 ("청년·신혼",r"청년|신혼|대학생"),("농어업인",r"농업|농가|어업|축산|귀농"),
 ("소상공인·창업",r"소상공인|창업|기업|자영업")]

def call(page):
    q={"serviceKey":KEY,"page":page,"perPage":100,
       "cond[소관기관명::LIKE]":"제주"}
    url=BASE+"?"+urllib.parse.urlencode(q)
    ctx=ssl.create_default_context()
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"mondak"}),timeout=30,context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    if not KEY:
        print("GOV24_KEY 미설정 — Settings→Secrets→Actions에 등록 필요"); return
    rows=[]
    try:
        for pg in (1,2,3):
            j=call(pg); data=j.get("data",[])
            rows+=data
            print("page",pg,":",len(data),"건 (총",j.get("totalCount"),")")
            if len(data)<100: break
    except Exception as e:
        print("API ERR",repr(e)); return
    items=[]
    for r in rows:
        sid=str(r.get("서비스ID") or r.get("서비스아이디") or "").strip()
        t=str(r.get("서비스명","")).strip()
        if not sid or not t: continue
        org=str(r.get("소관기관명",""))
        summary=str(r.get("서비스목적요약") or r.get("서비스목적") or "")[:120]
        due=str(r.get("신청기한") or "상시/공고 참조").strip()[:60]
        dept="jeju" if "제주시" in org else ("seog" if "서귀포" in org else "do")
        blob=t+" "+summary
        f=next((f for f,p in RULES if re.search(p,blob)),"welfare")
        w=[k for k,p in WHO if re.search(p,blob)] or ["모든 도민"]
        items.append({"org":dept,"f":f,"d":NOW.strftime("%Y-%m-%d"),"t":t,
            "s":summary or "정부24 상세페이지에서 지원내용·신청방법을 확인하세요.",
            "who":w,"due":due,"amt":str(r.get("지원내용",""))[:80] or "상세 참조",
            "where":org or "제주특별자치도",
            "url":f"https://www.gov.kr/portal/rcvfvrSvc/dtlEx/{sid}","apply":1})
    if not items:
        print("0건 — 응답 샘플:",json.dumps(rows[:1],ensure_ascii=False)[:800]); return
    seen=set(); uniq=[x for x in items if not (x["t"] in seen or seen.add(x["t"]))]
    OUT.write_text(json.dumps({"meta":{"collected_at":NOW.strftime("%Y-%m-%d %H:%M KST"),
        "source":"정부24 공공서비스 개방 API (공공데이터포털) — 서비스별 정부24 직링크","count":len(uniq)},
        "items":uniq[:80]},ensure_ascii=False,indent=1),encoding="utf-8")
    print("wrote",len(uniq),"items")

if __name__=="__main__": main()
