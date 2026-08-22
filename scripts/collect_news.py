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
GOOGLE_QUERIES=["제주도 when:14d","제주도청 OR 제주도의회 when:14d","제주 관광 when:14d",
 "제주 (AI OR 스타트업) when:14d","제주 (복지 OR 돌봄) when:14d",
 "제주 (감귤 OR 농업 OR 어업) when:14d","제주 (환경 OR 에너지) when:14d","제주 (사고 OR 폭우 OR 안전) when:14d"]

RULES=[
 ("정치/행정",r"도정|시정|도지사|시장|도의회|의회|의원|조례|예산안|인사청문|청문회|간담회|시민사회|시위|집회|외교|국민의힘|더불어민주당|민주당|당협|선거|공천|위성곤|오영훈|이상봉|4·3|4\.3|위령제|추념|행정체제|도청|공무원|위촉|감사원|국정감사|행정사무감사|정기인사|인사 발표|인사 단행|이사관|국장|서기관|승진|발탁|사장 후보|공사 사장|예결위|녹색당|시민단체|서명운동|칼럼|사설|기자상|여성가족|성평등|청렴|교부금|교총|국비|현판식|파트너십|협약|MOU|기부|고향사랑|이장|공청회|주민자치"),
 ("복지/사회서비스",r"복지|돌봄|어르신|노인|장애|취약계층|아동|보육|의료급여|건강보험|국민연금|바우처|사회보장|지역사회보장|요양|한부모|기초생활|자립|나눔|한끼|경로|장수|저소득|치매|헌혈|사례관리|고령자|반려동물|예방접종|심폐소생술|자선|기부금|복지위생"),
 ("1차산업",r"감귤|만감류|한라봉|천혜향|농가|농업|어업|어민|축산|한우|흑우|월동무|당근|메밀|딸기|가뭄|조업|수산|양식|품종|노지|비닐하우스|유리온실|재배|과수|출하|어가|밭작물|농산물|귀농|귀촌|농지|직불금|양돈|마사회|구제역|백신|풋귤|유제품|농단협|경관보전|국립공원|마을만들기|제주마|밭담"),
 ("신산업/AX",r"AI|인공지능|AX|디지털|데이터센터|빅데이터|UAM|드론|우주|위성|발사체|ICT|클라우드|바이오|바이오헬스|반도체|로봇|모빌리티|과기원|스타링크|신소재|R&D|연구개발|첨단|블록체인|메타버스"),
 ("환경/에너지",r"환경|에너지|탄소|재활용|일회용|다회용|정원도시|그린수소|풍력|태양광|재생에너지|신재생|생태|기후위기|친환경|탄소중립|용천수|유수율|난방전기화|히트펌프|자연자원|해양도립공원"),
 ("교육/청년",r"학교|학생|교육청|교육감|늘봄|고교학점제|장학|대학교|청소년|입시|교사|학부모|유치원|대학병원|제주대|학폭|공교육|도서관|연구센터|수료식|중등교육"),
 ("문화/관광/스포츠",r"관광|여행|크루즈|올레길|축제|페스티벌|공연|전시|문화|미술|박물관|콘서트|영화|호텔|리조트|방문객|워케이션|면세|MICE|스포츠|체육|선수|경기|리그|마라톤|대회|감독|구단|제주SK|아시안게임|올림픽|월드컵|비엔날레|음악제|리사이틀|신화|문인협회|신인문학상|국가유산|관아|만장굴|비자림|테라피|그림책|개인전|명상|항공좌석|항공편|항공사|항공이동권|e스포츠|피아니스트|바이올린|화가|래퍼|가볼 만한|여정|힐링|설문대할망|열쇠|해녀|잠녀|무형유산|유네스코"),
 ("창업/경제",r"스타트업|창업|수출|기업|경제|투자|고용|일자리|소상공인|상권|매출|벤처|자영업|은행|주가|증시|액면분할|상의|상공회의소|가맹|이자카야|소비|인구|4만명|돌파|펫패스|무신사"),
 ("안전/민원행정",r"태풍|호우|폭우|폭염|지진|화재|침수|재난|안전|특보|경보|구조|해경|119|민방위|단속|민원|점검|교통사고|붕괴|누수|정전|날씨|소나기|무더위|열대야|온열질환|식중독|을지연습|소방|횡단보도|신호등|실종|수색|물에 빠져|숨져|심정지|입적|난투극|흉기|최저기온|기온|더위"),
 ("사건사고/기타",r"사건|사고|체포|구속|기소|검찰|경찰|법원|판결|재판|연예|방송|드라마|아이돌|배우|가수|출연|절도|폭행|음주운전|마약|나혼자산다|나혼산|차예련|이찬원|톡파원|예능|시청률|벌금|의혹|고발|은폐|허위"),
]
# 제주 관련성: 이 중 하나는 제목에 있어야 함 (제주 정치인·주요인물 포함)
JEJU=r"제주|서귀포|한라|탐라|올레|우도|추자|마라도|성산|중문|애월|조천|한림|대정|구좌|표선|남원|안덕|곶자왈|해녀|감귤|도의회|도정|도지사|제주시|JDC|제주관광|도내|도민|위성곤|오영훈|이상봉|문성유|김광수|4·3|4\.3|위령제|섯알오름|다랑쉬"
# 타지역 기사: 타지역 지명 있고 제주 실질 키워드 없으면 무조건 제외 (PDF: 타지역 기사 무조건 제외)
OTHER_REGION=r"울산|부산|대구|인천|광주|대전|세종|수원|성남|용인|고양|창원|청주|천안|전주|포항|김해|경기|강원|충청|충북|충남|전라|전북|전남|경상|경북|경남|영덕|울릉|통영|여수|목포|속초|강릉"
# 강한 제주 신호: 타지역 단어가 함께 있을 때는 이게 있어야만 제주 기사로 인정 (해녀·감귤 등 약한 신호로는 타지역 못 이김)
JEJU_STRONG=r"제주|서귀포|한라|탐라|애월|조천|한림|대정|구좌|표선|남원|안덕|성산|중문|우도|추자|마라도|곶자왈|도의회|도정|도지사|JDC|위성곤|오영훈|이상봉|4·3|4\.3|섯알오름"
# 사명 속 '제주'는 관련성 증거로 안 침 — 진짜 제주 키워드가 따로 있어야 통과
BRAND=r"제주항공|제주은행|제주유나이티드|제주드림타워"
def jeju_ok(t):
    clean=re.sub(BRAND,"",t)
    if re.search(OTHER_REGION,t):
        return bool(re.search(JEJU_STRONG,clean))  # 타지역 있으면 강한 제주신호 필수
    return bool(re.search(JEJU, clean))
# 수집 단계 하드 제외: 완전 무관한 전국 스포츠·부고류 (분류 대상 아닌 것만)
EXCLUDE=r"프로야구|KBO리그|\[부고\]|\[동정\]|로또"
def classify(t):
    # 선처리: 순서 규칙으로 오분류되는 강한 신호 먼저 잡기
    if re.search(r"해녀|잠녀",t): return "문화/관광/스포츠"     # 해녀=문화유산 (학교/졸업식보다 우선)
    if re.search(r"소방|화재|폭발|산불",t): return "안전/민원행정"  # 소방·화재 (다문화의 '문화'보다 우선)
    for s,p in RULES:
        if re.search(p,t): return s
    return "사건사고/기타"  # 미분류는 사건사고/기타로 흡수 (별도 '기타' 없앰)

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
            u="https://naverapihub.apigw.ntruss.com/search/v1/news?display=100&sort=date&query="+urllib.parse.quote(q)
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
    # 누적: 직전 결과를 합산해 14일 창 안에서 매체수·기사수가 줄지 않게 함
    try:
        for pv in json.loads(OUT.read_text()).get("items",[]):
            lk=pv.get("link","")
            if not lk or lk in seen_links: continue
            seen_links.add(lk)
            all_items.append({"t":pv["t"],"link":lk,"src":pv.get("src",""),"d":pv.get("d"),
                              "direct":True,"outlets_prev":pv.get("outlets",[])})
        print("이전 누적",len(all_items),"건 병합")
    except Exception: pass
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
    cutoff=(NOW-timedelta(days=14)).strftime("%Y-%m-%d")
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
            for s2 in i.get("outlets_prev",[]):
                if s2 and s2 not in outlets: outlets.append(s2)
        rep["outlets"]=outlets[:8]; rep["n"]=max(len(outlets),1)
        rep["sec"]=classify(rep["t"]); rep.pop("direct",None)
        out.append(rep)
    out.sort(key=lambda x:(x["d"] or "0000",x["n"]), reverse=True)  # 최신→매체수 순
    out=out[:400]
    if not out: print("no items; keeping previous"); return
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({"meta":{"collected_at":NOW.strftime("%Y-%m-%d %H:%M KST"),
        "window_days":14,"cadence":"3h","source":"지역 언론 RSS 5곳(직링크)+Google News — 사안별 보도 매체수 집계","count":len(out)},
        "items":out},ensure_ascii=False,indent=1),encoding="utf-8")
    top=out[0]; print("wrote",len(out),"items · top:",top["n"],"개사 —",top["t"][:40])

if __name__=="__main__": main()
