#!/usr/bin/env python3
"""몬딱 공고 수집기 — 도청·제주시·서귀포시 고시/공고 게시판을 긁어
공고 1건당 '직링크'를 확보, data/policies.json 생성. 표준 라이브러리만 사용."""
import json, re, ssl, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST=timezone(timedelta(hours=9)); NOW=datetime.now(KST)
OUT=Path(__file__).resolve().parent.parent/"data"/"policies.json"
UA={"User-Agent":"Mozilla/5.0 (mondak-collector)"}

BOARDS=[
 # (org, 목록 URL, 상세링크 판별 정규식, base)
 ("do","http://sido.jeju.go.kr/citynet/jsp/sap/SAPGosiBizProcess.do?command=searchList&flag=gosiGL&svp=Y",
  r'href="([^"]*searchDetail[^"]*)"',"http://sido.jeju.go.kr"),
 ("jeju","https://eminwon.jejusi.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp?not_ancmt_se_code=01,04&list_gubun=A",
  r'href="([^"]*OfrNotAncmtView[^"]*)"',"https://eminwon.jejusi.go.kr"),
 ("seog","https://seogwipo.go.kr/info/news/law/law.htm",
  r'href="([^"]*law\.htm\?[^"]*(?:act=view|seq=)[^"]*)"',"https://seogwipo.go.kr"),
]
RULES=[("welfare",r"복지|돌봄|어르신|노인|장애|아동|보육|의료|건강|바우처|지원금|생리대|임산부"),
 ("agri",r"감귤|농업|농가|어업|축산|수산|가뭄|저수|딸기|메밀|월동"),
 ("env",r"환경|에너지|재활용|일회용|탄소|정원|녹지|숲|생태|풍력"),
 ("youth",r"학교|학생|교육|청년|장학|평생학습|프로그램|수강"),
 ("tour",r"관광|축제|여행|올레|호텔|공연|문화"),
 ("ax",r"AI|인공지능|디지털|데이터|드론|ICT"),
 ("startup",r"창업|소상공인|기업|일자리|공공근로|채용|모집.*참여자|경제"),
 ("civic",r"안전|재난|훈련|점검|단속|민원|교통|주차|도로")]
WHO_RULES=[("이동약자·어르신",r"어르신|노인|장애|경로"),("육아·양육",r"임산부|아동|보육|육아|학부모"),
 ("청년·신혼",r"청년|신혼"),("농어업인",r"농가|농업|어업|축산"),("소상공인·창업",r"소상공인|창업|업소|기업")]
APPLY=r"모집|공모|신청|접수|지원사업|참여자|수강"

def fetch(url):
    ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
    req=urllib.request.Request(url,headers=UA)
    return urllib.request.urlopen(req,timeout=25,context=ctx).read().decode("utf-8","ignore")

def classify(t):
    for f,p in RULES:
        if re.search(p,t): return f
    return "civic"

def who_of(t):
    w=[k for k,p in WHO_RULES if re.search(p,t)]
    return w or ["모든 도민"]

def absolute(base,href):
    href=href.replace("&amp;","&")
    if href.startswith("http"): return href
    if href.startswith("/"): return base+href
    return base+"/"+href

def harvest(org,url,pat,base):
    html=fetch(url); out=[]
    # 제목: 링크 태그 내부 텍스트, 날짜: 근처 YYYY-MM-DD / YYYY.MM.DD
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',html,re.S|re.I):
        href,inner=m.group(1),re.sub(r"<[^>]+>","",m.group(2)).strip()
        if not re.search(pat,'href="'+href+'"'): continue
        if len(inner)<6: continue
        tail=html[m.end():m.end()+300]
        dm=re.search(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})",tail) or re.search(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})",inner)
        d=f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}" if dm else NOW.strftime("%Y-%m-%d")
        t=re.sub(r"\s+"," ",inner)[:90]
        out.append({"org":org,"f":classify(t),"d":d,"t":t,
            "s":"기관 공고 원문을 확인하세요. 제목 기반 자동 분류.","who":who_of(t),
            "due":"공고 원문 참조","amt":"공고 참조",
            "where":{"do":"도청","jeju":"제주시","seog":"서귀포시"}[org],
            "url":absolute(base,href),"apply":1 if re.search(APPLY,t) else 0})
    return out

def main():
    items=[]
    for org,url,pat,base in BOARDS:
        try:
            got=harvest(org,url,pat,base); print(org,len(got),"건")
            items+=got[:30]
        except Exception as e: print("skip",org,e)
    # 중복 제거 + 최근 21일
    seen=set(); uniq=[]
    cutoff=(NOW-timedelta(days=21)).strftime("%Y-%m-%d")
    for it in items:
        k=re.sub(r"\s+","",it["t"])[:40]
        if k in seen or it["d"]<cutoff: continue
        seen.add(k); uniq.append(it)
    uniq.sort(key=lambda x:x["d"],reverse=True)
    if not uniq: print("no notices; keeping previous"); return
    OUT.write_text(json.dumps({"meta":{"collected_at":NOW.strftime("%Y-%m-%d %H:%M KST"),
        "source":"도청 고시공고(citynet) · 제주시(eminwon) · 서귀포시 공고판 직크롤","count":len(uniq)},
        "items":uniq[:60]},ensure_ascii=False,indent=1),encoding="utf-8")
    print("wrote",OUT,len(uniq))

if __name__=="__main__": main()
