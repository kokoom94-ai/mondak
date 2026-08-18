#!/usr/bin/env python3
"""몬딱 새소식 수집기 v2 — 지역 언론 RSS(기사 직링크) + Google News RSS(전체 매체수 집계).
표준 라이브러리만 사용. GitHub Actions에서 하루 3회 실행 → data/news.json"""
import json, re, ssl, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET
from pathlib import Path

KST=timezone(timedelta(hours=9)); NOW=datetime.now(KST)
OUT=Path(__file__).resolve().parent.parent/"data"/"news.json"

# 지역 언론 RSS (엔디소프트 계열 표준 경로) — 실패 시 자동 스킵
LOCAL_FEEDS=[
 ("헤드라인제주","https://www.headlinejeju.co.kr/rss/allArticle.xml"),
 ("뉴스제주","https://www.newsjeju.net/rss/allArticle.xml"),
 ("제주의소리","https://www.jejusori.net/rss/allArticle.xml"),
 ("뉴스N제주","https://newsnjeju.com/rss/allArticle.xml"),
 ("제주일보","https://www.jejunews.com/rss/allArticle.xml"),
]
GOOGLE_QUERIES=["제주 when:7d","제주도청 OR 제주도의회 when:7d","제주 관광 when:7d",
 "제주 (AI OR 스타트업 OR 디지털) when:7d","제주 (복지 OR 돌봄) when:7d",
 "제주 (감귤 OR 농업 OR 어업) when:7d","제주 (환경 OR 에너지) when:7d","제주 (사고 OR 안전 OR 폭우) when:7d"]

RULES=[
 ("안전/민원행정", r"태풍|호우|폭우|폭염|지진|화재|침수|사고|재난|안전|특보|경보|구조|해경|119|민방위|을지|단속|민원|점검"),
 ("복지/사회보험", r"복지|돌봄|어르신|노인|장애|취약|아동|보육|의료급여|건강보험|국민연금|바우처|지원금|장수|유니버설"),
 ("1차산업", r"감귤|농가|농업|어업|어민|해녀|축산|축협|월동채소|당근|메밀|딸기|저수조|가뭄.*농|조업|수산"),
 ("환경/에너지", r"환경|에너지|탄소|재활용|일회용|다회용|순환경제|정원도시|친환경|그린수소|풍력|태양광|생태"),
 ("교육/청년", r"학교|학생|교육|청년|늘봄|학점제|IB|장학|대학|진로|청소년"),
 ("관광", r"관광|여행|크루즈|올레|축제|호텔|리조트|항공.*환승|방문객|워케이션|면세|MICE"),
 ("신산업/AX", r"AI|인공지능|디지털|데이터|UAM|드론|우주|ICT|클라우드|반도체|바이오|디지털트윈"),
 ("스타트업/경제", r"스타트업|창업|수출|기업|경제|투자|고용|일자리|소상공인|상권"),
 ("행정", r"도정|도청|도지사|도의회|의원|조례|예산|행정|공무원|인사청문|감사|위촉|읍면동|4·3"),
]
EXCLUDE=r"^\[?(오늘|내일) 날씨|로또|K리그|프로축구|프로야구|연예|\[포토\]|\(포토\)"

def classify(t):
    for s,p in RULES:
        if re.search(p,t): return s
    return "기타"

def fetch(url,timeout=20):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (mondak-collector)"})
    with urllib.request.urlopen(req,timeout=timeout,context=ssl.create_default_context()) as r:
        return r.read()

def parse_rss(xml_bytes, force_src=None):
    items=[]
    root=ET.fromstring(xml_bytes)
    for it in root.iter("item"):
        title=(it.findtext("title") or "").strip()
        link=(it.findtext("link") or "").strip()
        pub=it.findtext("pubDate")
        src_el=it.find("source"); src=(src_el.text or "").strip() if src_el is not None else ""
        if force_src: src=force_src
        elif src and title.endswith(" - "+src): title=title[:-(len(src)+3)].strip()
        elif " - " in title and not src: title,_,src=title.rpartition(" - ")
        d=None
        if pub:
            try: d=parsedate_to_datetime(pub).astimezone(KST).strftime("%Y-%m-%d")
            except Exception: pass
        if title and not re.search(EXCLUDE,title):
            items.append({"t":title,"link":link,"src":src,"d":d})
    return items

def toks(t):
    t=re.sub(r"[\[\]()<>'\"…·,.:;!?~—-]"," ",t)
    return {w for w in t.split() if len(w)>=2}

def main():
    seen=set(); all_items=[]
    for name,url in LOCAL_FEEDS:                       # 1) 지역지: 직링크·정확한 발행일
        try:
            for it in parse_rss(fetch(url), force_src=name):
                if "제주" not in it["t"] and name not in ("헤드라인제주","제주의소리"): pass
                k=re.sub(r"\s+","",it["t"])[:40]
                if k in seen: continue
                seen.add(k); it["direct"]=True; all_items.append(it)
        except Exception as e: print("skip local",name,e)
    for q in GOOGLE_QUERIES:                           # 2) 구글뉴스: 매체수 폭 확장
        try:
            u="https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=ko&gl=KR&ceid=KR:ko"
            for it in parse_rss(fetch(u)):
                k=re.sub(r"\s+","",it["t"])[:40]
                if k in seen: continue
                seen.add(k); it["direct"]=False; all_items.append(it)
        except Exception as e: print("skip google",q,e)
    cutoff=(NOW-timedelta(days=7)).strftime("%Y-%m-%d")
    all_items=[i for i in all_items if not i["d"] or i["d"]>=cutoff]
    clusters=[]                                        # 3) 사안 군집 → 매체 수
    for it in all_items:
        tk=toks(it["t"]); placed=False
        for cl in clusters:
            j=len(tk&cl["tk"])/(len(tk|cl["tk"]) or 1)
            if j>=0.45: cl["items"].append(it); cl["tk"]|=tk; placed=True; break
        if not placed: clusters.append({"tk":set(tk),"items":[it]})
    out=[]
    for cl in clusters:
        direct=[i for i in cl["items"] if i.get("direct")]
        rep=dict(max(direct or cl["items"], key=lambda x:len(x["t"])))  # 직링크 우선
        outlets=[]
        for i in cl["items"]:
            s=(i.get("src") or "").strip()
            if s and s not in outlets: outlets.append(s)
        rep["outlets"]=outlets[:6]; rep["n"]=max(len(outlets),1)
        rep["sec"]=classify(rep["t"]); rep.pop("direct",None)
        out.append(rep)
    out.sort(key=lambda x:(x["d"] or "0000"), reverse=True)
    out=out[:100]
    if not out: print("no items; keeping previous"); return
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({"meta":{
        "collected_at":NOW.strftime("%Y-%m-%d %H:%M KST"),"window_days":7,
        "source":"지역 언론 RSS 5곳 (기사 직링크) + Google News (매체수 집계)","count":len(out)},
        "items":out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote",OUT,len(out),"items")

if __name__=="__main__": main()
