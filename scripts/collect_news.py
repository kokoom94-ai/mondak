#!/usr/bin/env python3
"""몬딱 새소식 수집기 v3 — 제주 관련성 필터 + 매체수 집계 수정판.
v2 버그 수정: (1)동일제목을 군집 前 삭제해 매체수가 못 늘던 문제 (2)무관 기사 유입 (3)한국어 제목 군집 정밀도"""
import json, re, ssl, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET
from pathlib import Path

KST=timezone(timedelta(hours=9)); NOW=datetime.now(KST)
OUT=Path(__file__).resolve().parent.parent/"data"/"news.json"

LOCAL_FEEDS=[("헤드라인제주","https://www.headlinejeju.co.kr/rss/allArticle.xml"),
 ("뉴스제주","https://www.newsjeju.net/rss/allArticle.xml"),
 ("제주의소리","https://www.jejusori.net/rss/allArticle.xml"),
 ("뉴스N제주","https://newsnjeju.com/rss/allArticle.xml"),
 ("제주일보","https://www.jejunews.com/rss/allArticle.xml")]
GOOGLE_QUERIES=["제주도 when:7d","제주도청 OR 제주도의회 when:7d","제주 관광 when:7d",
 "제주 (AI OR 스타트업) when:7d","제주 (복지 OR 돌봄) when:7d",
 "제주 (감귤 OR 농업 OR 어업) when:7d","제주 (환경 OR 에너지) when:7d","제주 (사고 OR 폭우 OR 안전) when:7d"]

RULES=[("안전/민원행정",r"태풍|호우|폭우|폭염|지진|화재|침수|사고|재난|안전|특보|경보|구조|해경|119|민방위|단속|민원|점검"),
 ("복지/사회보험",r"복지|돌봄|어르신|노인|장애|취약|아동|보육|의료급여|건강보험|국민연금|바우처|지원금|장수"),
 ("1차산업",r"감귤|만감류|한라봉|농가|농업|어업|어민|해녀|축산|한우|월동|당근|메밀|딸기|가뭄|조업|수산|양식|품종|노지|하우스|재배|과수|출하|묘"),
 ("환경/에너지",r"환경|에너지|탄소|재활용|일회용|다회용|정원도시|그린수소|풍력|태양광|생태|곶자왈|오름"),
 ("교육/청년",r"학교|학생|교육|청년|늘봄|학점제|IB|장학|대학|청소년"),
 ("문화/관광",r"관광|여행|크루즈|올레|축제|페스티벌|공연|전시|문화|미술|박물관|콘서트|영화|호텔|리조트|방문객|워케이션|면세|MICE"),
 ("신산업/AX",r"AI|인공지능|디지털|데이터|UAM|드론|우주|ICT|클라우드|바이오"),
 ("스타트업/경제",r"스타트업|창업|수출|기업|경제|투자|고용|일자리|소상공인|상권"),
 ("행정",r"도정|도청|도지사|도의회|의원|조례|예산|행정|공무원|인사청문|감사|위촉|읍면동|4·3|제주시|서귀포")]
# 제주 관련성: 이 중 하나는 제목에 있어야 함
JEJU=r"제주|서귀포|한라|탐라|올레|우도|추자|마라도|성산|중문|애월|조천|한림|대정|구좌|표선|남원|안덕|곶자왈|오름|해녀|감귤|도의회|도정|도지사|제주시|JDC|제주관광|도내|도민"
# 오탐: 이름만 '제주'인 전국뉴스 / 스포츠·연예·부고류
EXCLUDE=r"프로야구|프로축구|프로농구|배구|골프|K리그|KBO|연예|아이돌|드라마|\[부고\]|\[인사\]|\[동정\]|로또|^\[?(오늘|내일)?\s*날씨"
# 사명 속 '제주'는 관련성 증거로 안 침 — 진짜 제주 키워드가 따로 있어야 통과
BRAND=r"제주항공|제주은행|제주유나이티드|제주드림타워"
def jeju_ok(t): return bool(re.search(JEJU, re.sub(BRAND,"",t)))

def classify(t):
    for s,p in RULES:
        if re.search(p,t): return s
    return "기타"

def fetch(url,timeout=20):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (mondak)"})
    with urllib.request.urlopen(req,timeout=timeout,context=ssl.create_default_context()) as r:
        return r.read()

def norm(t):
    """군집용 정규화: 매체명 꼬리·괄호·따옴표·기호 제거"""
    t=re.sub(r"\s*-\s*[^-]{2,20}$","",t)          # " - 매체명" 꼬리
    t=re.sub(r"[\[\(][^\]\)]{1,12}[\]\)]","",t)   # [단독][속보](종합)
    t=re.sub(r"[\"'“”‘’…·,.:;!?~—\-\s]","",t)
    return t

def bigrams(t):
    n=norm(t); return {n[i:i+2] for i in range(len(n)-1)} if len(n)>1 else {n}

def parse_rss(xml_bytes, force_src=None):
    items=[]
    for it in ET.fromstring(xml_bytes).iter("item"):
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
        if not title or re.search(EXCLUDE,title): continue
        items.append({"t":title,"link":link,"src":src,"d":d})
    return items


import os
NAVER_ID=os.environ.get("NAVER_ID","").strip(); NAVER_SECRET=os.environ.get("NAVER_SECRET","").strip()  # NAVER API HUB(ncloud)
DOMAP={"headlinejeju.co.kr":"헤드라인제주","newsjeju.net":"뉴스제주","jejusori.net":"제주의소리",
 "newsnjeju.com":"뉴스N제주","jejunews.com":"제주일보","jejudomin.co.kr":"제주도민일보","jejuilbo.net":"제주新보",
 "yna.co.kr":"연합뉴스","news1.kr":"뉴스1","newsis.com":"뉴시스","joongang.co.kr":"중앙일보","chosun.com":"조선일보",
 "donga.com":"동아일보","hani.co.kr":"한겨레","khan.co.kr":"경향신문","kbs.co.kr":"KBS","imnews.imbc.com":"MBC",
 "sbs.co.kr":"SBS","jtbc.co.kr":"JTBC","ytn.co.kr":"YTN","mk.co.kr":"매일경제","hankyung.com":"한국경제",
 "jibs.co.kr":"JIBS","kctvjeju.com":"KCTV제주방송","ihalla.com":"한라일보"}
def naver_news():
    if not (NAVER_ID and NAVER_SECRET): print("naver(API HUB): 키 미설정, 건너뜀"); return []
    out=[]
    for q in ("제주","제주도청 OR 제주도의회","제주 관광","제주 감귤 OR 농업","제주 축제"):
        try:
            u="https://naverapihub.apigw.ntruss.com/search/v1/news.json?display=100&sort=date&query="+urllib.parse.quote(q)
            req=urllib.request.Request(u,headers={"x-ncp-apigw-api-key-id":NAVER_ID,"x-ncp-apigw-api-key":NAVER_SECRET})
            with urllib.request.urlopen(req,timeout=20,context=ssl.create_default_context()) as r:
                j=json.loads(r.read().decode("utf-8"))
            for it in j.get("items",[]):
                t=re.sub(r"<[^>]+>","",it.get("title","")).replace("&quot;",'"').replace("&amp;","&").replace("&lt;","<").replace("&gt;",">").strip()
                link=(it.get("originallink") or it.get("link") or "").strip()
                if not t or not link or re.search(EXCLUDE,t) or not jeju_ok(t): continue
                d=None
                try: d=parsedate_to_datetime(it["pubDate"]).astimezone(KST).strftime("%Y-%m-%d")
                except Exception: pass
                dom=re.sub(r"^www\.","",urllib.parse.urlparse(link).netloc)
                src=DOMAP.get(dom) or DOMAP.get(".".join(dom.split(".")[-2:])) or dom
                out.append({"t":t,"link":link,"src":src,"d":d,"direct":True})
        except Exception as e: print("skip naver",q,repr(e))
    print("naver:",len(out),"건")
    return out

def main():
    all_items=[]; seen_links=set()
    for name,url in LOCAL_FEEDS:
        try:
            for it in parse_rss(fetch(url), force_src=name):
                # 지역지: 제주 키워드 있거나 8분야로 분류되면 유지(제목에 '제주' 없어도 도내 기사)
                if not jeju_ok(it["t"]) and classify(it["t"])=="기타": continue
                if it["link"] in seen_links: continue
                seen_links.add(it["link"]); it["direct"]=True; all_items.append(it)
        except Exception as e: print("skip local",name,e)
    for it in naver_news():                              # 네이버: 원문 직링크·매체 폭
        if it["link"] in seen_links: continue
        seen_links.add(it["link"]); all_items.append(it)
    for q in GOOGLE_QUERIES:
        try:
            u="https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=ko&gl=KR&ceid=KR:ko"
            for it in parse_rss(fetch(u)):
                if not jeju_ok(it["t"]): continue   # 구글발: 사명 제외하고 제주 키워드 필수
                if it["link"] in seen_links: continue
                seen_links.add(it["link"]); it["direct"]=False; all_items.append(it)
        except Exception as e: print("skip google",q,e)
    cutoff=(NOW-timedelta(days=7)).strftime("%Y-%m-%d")
    all_items=[i for i in all_items if not i["d"] or i["d"]>=cutoff]
    today=NOW.strftime("%Y-%m-%d")
    for i in all_items:
        if not i["d"]: i["d"]=today
    print("수집",len(all_items),"건")
    clusters=[]
    for it in all_items:
        bg=bigrams(it["t"]); nk=norm(it["t"])[:30]; placed=False
        for cl in clusters:
            if nk and nk==cl["nk"]:                       # 동일 제목 → 즉시 병합(매체수 집계 핵심)
                cl["items"].append(it); placed=True; break
            j=len(bg&cl["bg"])/(len(bg|cl["bg"]) or 1)    # 대표 제목과만 비교(군집 비대 방지)
            if j>=0.30: cl["items"].append(it); placed=True; break
        if not placed: clusters.append({"bg":bg,"nk":nk,"items":[it]})
    out=[]
    for cl in clusters:
        direct=[i for i in cl["items"] if i.get("direct")]
        rep=dict(max(direct or cl["items"], key=lambda x:len(x["t"])))
        outlets=[]
        for i in cl["items"]:
            s=(i.get("src") or "").strip()
            if s and s not in outlets: outlets.append(s)
        rep["outlets"]=outlets[:8]; rep["n"]=max(len(outlets),1)
        rep["sec"]=classify(rep["t"]); rep.pop("direct",None)
        out.append(rep)
    out.sort(key=lambda x:(x["d"] or "0000",x["n"]), reverse=True)  # 최신→매체수 순
    out=out[:100]
    if not out: print("no items; keeping previous"); return
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({"meta":{"collected_at":NOW.strftime("%Y-%m-%d %H:%M KST"),
        "window_days":7,"source":"지역 언론 RSS 5곳(직링크)+Google News — 사안별 보도 매체수 집계","count":len(out)},
        "items":out},ensure_ascii=False,indent=1),encoding="utf-8")
    top=out[0]; print("wrote",len(out),"items · top:",top["n"],"개사 —",top["t"][:40])

if __name__=="__main__": main()
