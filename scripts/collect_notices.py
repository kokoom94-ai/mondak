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
if "%" in KEY: KEY=urllib.parse.unquote(KEY)   # Encoding 키 입력 시 자동 변환
BASE="https://api.odcloud.kr/api/gov24/v3/serviceList"

RULES=[
 ("agri",r"감귤|만감류|농업|농가|어업|축산|수산|귀농|비료|임업|화훼|낙농|한우|흑우|양식|종서|종구|과수|감자|수확|여성농업인|직불|어가|농작물|원지정비|한라봉|천혜향|가축|밭작물|월동무|영농"),
 ("welfare",r"복지|돌봄|어르신|노인|장애|장애인|정신질환|정신건강|질환|중증|난치|재활|취약계층|저소득|기초생활|한부모|조손|아동|보육|의료|건강|바우처|생리대|임산부|수당|급여|요양|보훈|기초연금|고엽제|참전|유공자|해녀|위탁|자립정착|틀니|보청기"),
 ("housing",r"주거|전세|임차|월세|주택|재형저축|자산형성|내집|보증금"),
 ("job",r"공공근로|일자리|취업|직업훈련|근로자\s*모집|채용|구직|일경험|고용촉진"),
 ("youth",r"학교|학생|교육|청년|장학|평생학습|대학생"),
 ("startup",r"창업|소상공인|기업|경제|소득증대|자영업|상권|판로"),
 ("tour",r"관광|축제|문화|공연|예술|미술|음악|스포츠|체육|선수|경기|생활체육|운동"),
 ("env",r"환경|에너지|재활용|전기차|탄소|신재생|친환경"),
 ("ax",r"AI|인공지능|디지털|데이터|정보화|바이오|빅데이터")]
# 장비·시설지원 특별 판정 (RULES보다 먼저 적용)
EQUIP_STRONG=r"암반제거|경작지\s*정비|배수로|관정|기반정비|농로|용수로|객토|경지정리|토양개량"  # 작물명 있어도 무조건 장비
EQUIP_WEAK=r"농기계|기계화|저온저장고|범용\s*장비"  # 작물명 없을 때만 장비
CROP=r"감귤|만감류|화훼|낙농|한우|흑우|양식|종서|종구|과수|감자|농작물|원지정비|한라봉|천혜향|밭작물|가축"
def classify_field(blob):
    if re.search(EQUIP_STRONG,blob): return "equip"
    if re.search(EQUIP_WEAK,blob) and not re.search(CROP,blob): return "equip"
    return next((f for f,p in RULES if re.search(p,blob)),"welfare")
WHO=[("이동약자·어르신",r"어르신|노인|장애|경로"),("육아·양육",r"임산부|출산|아동|보육|육아|한부모"),
 ("청년·신혼",r"청년|신혼|대학생"),("농어업인",r"농업|농가|어업|축산|귀농"),
 ("소상공인·창업",r"소상공인|창업|기업|자영업")]

def call(page):
    q={"serviceKey":KEY,"page":page,"perPage":100,
       "cond[소관기관명::LIKE]":"제주"}
    url=BASE+"?"+urllib.parse.urlencode(q)
    ctx=ssl.create_default_context()
    hdr={"User-Agent":"mondak","Authorization":"Infuser "+KEY}
    with urllib.request.urlopen(urllib.request.Request(url,headers=hdr),timeout=30,context=ctx) as r:
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
        print("API ERR",repr(e))
        if "401" in str(e): print("→ 점검: (1)키 활성화 대기 최대 1시간 (2)Decoding 키인지 (3)활용신청한 API의 End Point가 api.odcloud.kr/api/gov24 인지")
        return
    items=[]
    for r in rows:
        sid=str(r.get("서비스ID") or r.get("서비스아이디") or "").strip()
        t=str(r.get("서비스명","")).strip()
        if not sid or not t: continue
        org=str(r.get("소관기관명",""))
        summary=str(r.get("서비스목적요약") or r.get("서비스목적") or "")[:120]
        due=str(r.get("신청기한") or "상시/공고 참조").strip()[:60]
        # 소관기관명으로 층위 판별 (읍면동 > 행정시 > 도청 순, 세부기관 우선)
        if re.search(r"(읍|면|동)\s*$|주민센터|행정복지센터",org): dept="eup"
        elif "서귀포" in org: dept="seog"
        elif "제주시" in org: dept="jeju"
        elif re.search(r"교육|학교",org): dept="do"
        else: dept="do"
        blob=t+" "+summary
        f=classify_field(blob)
        w=[k for k,p in WHO if re.search(p,blob)] or ["모든 도민"]
        items.append({"org":dept,"f":f,"d":NOW.strftime("%Y-%m-%d"),"t":t,
            "s":summary or "정부24 상세페이지에서 지원내용·신청방법을 확인하세요.",
            "who":w,"due":due,"amt":str(r.get("지원내용",""))[:80] or "상세 참조",
            "where":org or "제주특별자치도",
            "url":str(r.get("상세조회URL") or "").strip() or f"https://www.gov.kr/portal/rcvfvrSvc/dtlEx/{sid}","apply":1})
    if not items:
        print("0건 — 응답 샘플:",json.dumps(rows[:1],ensure_ascii=False)[:800]); return
    seen=set(); uniq=[x for x in items if not (x["t"] in seen or seen.add(x["t"]))]
    OUT.write_text(json.dumps({"meta":{"collected_at":NOW.strftime("%Y-%m-%d %H:%M KST"),
        "source":"정부24 공공서비스 개방 API (공공데이터포털) — 서비스별 정부24 직링크","count":len(uniq)},
        "items":uniq[:80]},ensure_ascii=False,indent=1),encoding="utf-8")
    print("wrote",len(uniq),"items")

if __name__=="__main__": main()
