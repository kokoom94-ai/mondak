# -*- coding: utf-8 -*-
"""
관광 AX 인사이트 수집기 — data/ax.json

무엇을 모으나
  정부부처·공공기관의 인공지능 전환(AX) 정책 추진상황과 타 지역 사례를 모은다.
  관광에 한정하지 않는다. 관광은 기반 사업이라 교통·복지·안전·행정·데이터 어느 쪽의
  AX 사례든 관광 정책 설계에 연결되기 때문이다.
  제주관광공사·제주도는 '보는 주체'이므로 수집 대상에서 뺀다.
  단순 공고(채용·입찰·모집)나 기관 메인페이지·데이터랩 화면은 정책이 아니므로 뺀다.

출처 (Gov.AX Insight 와 같은 구조)
  1차 : 대한민국 정책브리핑(korea.kr) — 전 부처 보도자료가 모여 있는 곳.
        기관 공식 도메인을 site: 로 긁으면 데이터랩 조회 화면·채용공고·기관 메인까지
        딸려 들어온다(실측: 182건 중 41%가 그런 것이었다). 정책브리핑은 보도자료만 있다.
  2차 : 각 기관 공식 채널 — 정책브리핑에 안 실리는 지역 관광기관 사례 보강용.

(구 설명 — 1단계 공식 채널 한정)
  · Google News RSS 에 site: 한정을 걸어 공식 도메인만 받는다.
    korea.kr(정책브리핑), .go.kr, 주요 공사·재단 공식 도메인.
  · 형식이 일정해 판정이 안정적이고, 홍보성 기사가 섞이지 않는다.
  2단계로 관광업계 언론을 넓힐 때는 AX_MEDIA_QUERIES 를 켜면 된다.

판정
  여기서는 수집·1차 선별만 한다. 기관·주제 분류는 llm_classify.py 가 맡는다.
  (규칙으로 "이 기사가 AX인가"를 판정하면 이슈체크에서 겪은 오분류가 반복된다)

원칙 — Gov.AX Insight 와 동일하게 지킨다
  · 원문 URL·발행일·출처를 반드시 보존한다
  · 본문 전체는 복제하지 않는다. 제목과 짧은 요약만
  · 확인되지 않는 것은 만들어 내지 않는다
"""
import os, re, json, html, ssl, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "data", "ax.json")

UA  = "Mozilla/5.0 (compatible; MondakBot/1.0; +https://kokoom94-ai.github.io/mondak/)"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

DAYS_BACK = 365   # 한 번에 받아올 범위. AX는 흐름을 보므로 넓게 잡는다
                  # (30일로 두었더니 첫 수집에서 1,277건 중 70%가 기간 밖으로 탈락했다)
KEEP_DAYS = 730   # 누적 보관 — AX는 흐름을 봐야 하므로 길게 둔다

# ── 기관 ────────────────────────────────────────────────
# name  : 화면 표기
# domain: site: 한정에 쓸 도메인
# tag   : 축 분류 (부처 / 공사 / 지자체 / 지역관광 / 유관)
ORGS = [
 {"name":"문화체육관광부",   "domain":"mcst.go.kr",          "tag":"부처",   "q":"문화체육관광부"},
 {"name":"한국관광공사",     "domain":"knto.or.kr",          "tag":"공사",   "q":"한국관광공사"},
 {"name":"한국관광공사",     "domain":"visitkorea.or.kr",    "tag":"공사",   "q":"한국관광공사"},
 {"name":"경기관광공사",     "domain":"ggtour.or.kr",        "tag":"지역관광","q":"경기관광공사"},
 {"name":"부산관광공사",     "domain":"bto.or.kr",           "tag":"지역관광","q":"부산관광공사"},
 {"name":"부산관광공사",     "domain":"visitbusan.net",      "tag":"지역관광","q":"부산관광공사"},
 {"name":"인천관광공사",     "domain":"ito.or.kr",           "tag":"지역관광","q":"인천관광공사"},
 {"name":"경상북도문화관광공사","domain":"gyeongbuk.go.kr",    "tag":"지역관광","q":"경북문화관광공사"},
 {"name":"전남관광재단",     "domain":"jntour.or.kr",        "tag":"지역관광","q":"전남관광재단"},
 {"name":"충남문화관광재단", "domain":"cctf.or.kr",          "tag":"지역관광","q":"충남관광재단"},
 {"name":"강원관광재단",     "domain":"gwto.or.kr",          "tag":"지역관광","q":"강원관광재단"},
 {"name":"경북문화관광공사", "domain":"gcto.co.kr",          "tag":"지역관광","q":"경북문화관광공사"},
 {"name":"서울관광재단",     "domain":"sto.or.kr",           "tag":"지역관광","q":"서울관광재단"},
 {"name":"한국문화정보원",   "domain":"kcisa.kr",            "tag":"유관",   "q":"한국문화정보원"},
 {"name":"한국문화관광연구원","domain":"kcti.re.kr",         "tag":"유관",   "q":"한국문화관광연구원"},
 {"name":"한국지능정보사회진흥원","domain":"nia.or.kr",       "tag":"유관",   "q":"한국지능정보사회진흥원"},
 {"name":"정보통신산업진흥원","domain":"nipa.kr",             "tag":"유관",   "q":"정보통신산업진흥원"},
 {"name":"행정안전부",       "domain":"mois.go.kr",          "tag":"부처",   "q":"행정안전부"},
 {"name":"과학기술정보통신부","domain":"msit.go.kr",          "tag":"부처",   "q":"과학기술정보통신부"},
 {"name":"국토교통부",       "domain":"molit.go.kr",         "tag":"부처",   "q":"국토교통부"},
]

# ── AX 키워드 ───────────────────────────────────────────
# 1순위 : 이 말이 제목·요약에 있으면 AX 후보
AX_KEYWORDS = [
 "인공지능","AI","A.I","AX","에이아이","생성형","챗봇","챗GPT","ChatGPT",
 "LLM","머신러닝","딥러닝","알고리즘","디지털 전환","DX","데이터 기반",
 "빅데이터","스마트관광","지능형","자동화","디지털트윈","메타버스",
 "추천 시스템","개인화","초개인화","AI 에이전트","에이전트",
]
# '데이터'만 있으면 약한 신호 — AI 계열 낱말이 함께 있어야 인정
AX_WEAK = ["데이터","플랫폼","디지털"]

# ── 검색 질의어 ─────────────────────────────────────────
# 기관 × AX 축으로 조합해 생성한다
# 1차 — 대한민국 정책브리핑. 전 부처 보도자료가 모여 있어 잡음이 거의 없다.
BRIEFING_QUERIES = [
 # AX 전반
 'site:korea.kr 인공지능 전환', 'site:korea.kr AI 도입', 'site:korea.kr 생성형 AI',
 'site:korea.kr AI 에이전트', 'site:korea.kr 공공 AI', 'site:korea.kr 디지털 전환',
 'site:korea.kr AI 서비스 구축', 'site:korea.kr 데이터 플랫폼 구축',
 'site:korea.kr AI 정부', 'site:korea.kr 챗봇 도입',
 # 관광·문화 (가중 영역)
 'site:korea.kr 관광 인공지능', 'site:korea.kr 관광 AI', 'site:korea.kr 스마트관광',
 'site:korea.kr 문화체육관광부 인공지능', 'site:korea.kr 관광 빅데이터',
]

AX_TOPIC_QUERIES = [
 # 공공 AX 전반
 "공공기관 인공지능 도입", "지자체 AI 서비스", "행정 인공지능 전환",
 "공공 생성형 AI", "AI 에이전트 공공", "공공 데이터 플랫폼 구축",
 # 관광·문화
 "관광 인공지능", "관광 AI", "스마트관광", "관광 빅데이터", "관광 챗봇",
 # 관광과 맞닿는 인접 영역
 "교통 인공지능 서비스", "재난 안전 인공지능", "다국어 통역 인공지능",
 "문화시설 인공지능", "지역 소멸 대응 데이터",
]
# 2단계 — 관광업계 언론까지 넓힐 때 켠다 (site 한정 없음)
AX_MEDIA_QUERIES = [
 "여행업계 인공지능", "호텔 인공지능", "항공 인공지능", "여행 플랫폼 AI",
]
USE_MEDIA = os.environ.get("AX_USE_MEDIA", "") == "1"

# 공식 도메인 화이트리스트 — 이 밖의 링크는 1단계에서 버린다
OFFICIAL_SUFFIX = (".go.kr", ".or.kr", "korea.kr", ".re.kr")

# 우리 자신은 벤치마킹 대상이 아니다. 도메인·표기 어느 쪽으로 걸려도 뺀다.
SELF_DOMAINS = ("ijto.or.kr", "visitjeju.net", "jeju.go.kr")
SELF_NAMES   = ("제주관광공사", "제주특별자치도", "제주도청", "제주관광빅데이터플랫폼")

# 정책이 아닌 것 — 단순 공고·기관 메인·데이터 조회 화면
NOISE_RX = [
 r"채용|합격자|면접|임용|모집\s?공고|입찰|낙찰|계약\s?체결|견적",
 r"공고\s*$|공고문|공고\s?-|입찰공고|재공고",
 r"수요조사|만족도\s?조사|설문",
 r"빅데이터\s?플랫폼|데이터랩|통계\s?조회|현황\s?조회",
 r"^[가-힣A-Za-z\s]{2,20}\s?-\s?[가-힣A-Za-z\s]{2,20}$",   # "강원관광재단 - 강원관광재단" 류
 r"설명회\s?개최\s?알림|협조\s?요청|알림마당\s?\|\s?공지사항",
 r"주간|월간|연간\s?보고서\s?목록|자료실\s*$",
 r"선정\s?결과\s?발표|선정결과\s?발표|결과\s?발표\s*(\||$|-)",
 r"\|\s?공지사항\s?\||공지사항\s*(-|$)",
 r"\(목록\)|목록\s*(-|$)|카드뉴스|강좌\s?소개|e배움터",
 r"안내\s*(\||$|-)|접수\s?기간|신청\s?안내",
]

# 정책 '추진'이 아니라 지원사업 절차에 가까운 말 — 단독으로는 정책 신호로 보지 않는다
PROCEDURAL = ["공모 선정", "선정 결과", "지원 규모", "접수", "신청", "모집 안내"]

def is_self(x, title, body=""):
    dom = (x.get("source_domain") or "").lower()
    if any(d in dom for d in SELF_DOMAINS): return True
    q = x.get("query") or ""
    if any(d in q for d in SELF_DOMAINS): return True
    return any(n in (title or "") for n in SELF_NAMES)

def is_noise(title):
    t = (title or "").strip()
    return any(re.search(p, t) for p in NOISE_RX)


def clean(s=""):
    s = re.sub(r"<[^>]+>", "", s or "")
    return html.unescape(s).strip()


def fetch(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def google_news(query):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
    try:
        xml = fetch(url)
    except Exception as e:
        print(f"   ! gnews '{query}': {e}")
        return []
    out = []
    for m in re.finditer(r"<item>(.*?)</item>", xml, re.S):
        b = m.group(1)
        g = lambda tag: (re.search(rf"<{tag}>(.*?)</{tag}>", b, re.S) or [None, ""])[1]
        pub = clean(g("pubDate")); ts = None
        if pub:
            for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
                try:
                    ts = datetime.strptime(pub, fmt)
                    if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
                    break
                except Exception:
                    ts = None
        # link 는 news.google.com 리다이렉트 주소라 발행처를 알 수 없다.
        # RSS 의 <source url="https://www.mcst.go.kr">문화체육관광부</source> 를 쓴다.
        sm = re.search(r'<source([^>]*)>(.*?)</source>', b, re.S)
        src = clean(sm.group(2)) if sm else ""
        surl = ""
        if sm:
            um = re.search(r'url="([^"]+)"', sm.group(1))
            if um: surl = um.group(1)
        sdom = ""
        if surl:
            try: sdom = urllib.parse.urlparse(surl).netloc.lower()
            except Exception: sdom = ""
        out.append({"title": clean(g("title")),
                    "description": clean(g("description"))[:300],
                    "link": clean(g("link")),
                    "date": ts.astimezone(KST).strftime("%Y-%m-%d") if ts else None,
                    "source": src, "source_url": surl, "source_domain": sdom,
                    "query": query})
    return out


def is_official(x):
    """
    구글 뉴스 RSS 의 link 는 news.google.com 리다이렉트라 발행처를 담지 않는다.
    (첫 수집에서 날짜를 통과한 376건이 전부 여기서 탈락했다)
    발행처 도메인을 우선 보고, 없으면 site: 질의로 받아온 것인지로 판단한다.
    """
    dom = (x.get("source_domain") or "").lower()
    if dom:
        return any(dom.endswith(sfx) or sfx in dom for sfx in OFFICIAL_SUFFIX)
    q = x.get("query") or ""
    if q.startswith("site:"):          # 질의 자체가 공식 도메인 한정이었다
        return True
    link = x.get("link") or ""
    try: host = urllib.parse.urlparse(link).netloc.lower()
    except Exception: return False
    if "news.google.com" in host: return False
    return any(host.endswith(sfx) or sfx in host for sfx in OFFICIAL_SUFFIX)


def ax_score(title, body=""):
    """AX 관련도. 0이면 후보 아님."""
    t = f"{title} {body}"
    tl = t.lower()
    hits = [w for w in AX_KEYWORDS if (w.lower() in tl if w.isascii() else w in t)]
    if hits:
        # 제목에 있으면 1순위
        strong = [w for w in hits if (w.lower() in title.lower() if w.isascii() else w in title)]
        return (2 if strong else 1), hits[:5]
    weak = [w for w in AX_WEAK if w in t]
    return 0, weak


TOURISM_W = ["관광","여행","관광객","방문객","여행객","숙박","호텔","축제","관광지",
             "MICE","마이스","크루즈","항공","면세","체류","답사","투어"]

def is_tourism(title, body=""):
    # 제목에 있으면 확실. 제목에 없고 본문에만 있으면 스치듯 언급일 수 있어
    # 관광 낱말이 둘 이상 나올 때만 인정한다.
    if any(w in title for w in TOURISM_W): return True
    hits = sum(1 for w in TOURISM_W if w in (body or ""))
    return hits >= 2

def _is_tourism_legacy(title, body=""):
    t = f"{title} {body}"
    return any(w in t for w in
               ["관광","여행","관광객","방문객","여행객","숙박","호텔","축제","관광지",
                "MICE","마이스","크루즈","항공","면세","체류","답사","투어","콘텐츠관광"])


# korea.kr / 정책브리핑은 전 부처 공용 포털이다.
# 도메인으로 기관을 찍으면 과기정통부 기사가 문체부로 잡힌다. 본문 표기를 먼저 본다.
SHARED_HOST = ("korea.kr",)
# 본문에서 잡아낼 부처 표기 (관광 소관 밖이어도 기관축에 올려 둔다)
MINISTRY = [("문화체육관광부","부처"),("문체부","부처"),("과학기술정보통신부","부처"),
            ("과기정통부","부처"),("행정안전부","부처"),("행안부","부처"),
            ("국토교통부","부처"),("국토부","부처"),("중소벤처기업부","부처"),("중기부","부처"),
            ("해양수산부","부처"),("해수부","부처"),("환경부","부처"),("농림축산식품부","부처"),
            ("산업통상자원부","부처"),("기획재정부","부처"),("고용노동부","부처"),
            ("국가유산청","부처"),("문화재청","부처"),("산림청","부처"),
            ("한국관광공사","공사"),("한국문화관광연구원","유관"),("한국문화정보원","유관"),
            ("인천광역시","지역관광"),("부산광역시","지역관광"),("서울특별시","지역관광"),
            ("경기도","지역관광"),("강원특별자치도","지역관광"),("전라남도","지역관광"),
            ("경상북도","지역관광"),("충청남도","지역관광"),("용인특례시","지역관광"),
            ("인천시","지역관광"),("부산시","지역관광"),("서울시","지역관광"),
            ("대구시","지역관광"),("광주시","지역관광"),("대전시","지역관광"),
            ("울산시","지역관광"),("세종시","지역관광"),("강원도","지역관광"),
            ("전남도","지역관광"),("경북도","지역관광"),("충남도","지역관광"),
            ("전북특별자치도","지역관광"),("경상남도","지역관광")]

# 정책 추진·사례로 볼 수 있는 신호
POLICY_RX = [
 r"추진|시행|도입|구축|개발|운영\s?(개시|시작)|착수|출시|개통|오픈",
 r"확대|고도화|개편|전환|혁신|시범|실증|실증사업",
 r"협약|업무협약|MOU|맞손|공동\s?(추진|개발)",
 r"지원\s?(사업|한다|나서)|육성|투자|예산\s?(투입|편성)",
 r"발표|공개|선보|소개|계획\s?(수립|발표)|전략|로드맵|기본계획",
 r"성과|효과|늘었|증가|달성|기록|첫\s?|최초|최대",
 r"서비스|플랫폼\s?(구축|개편|출시)|시스템\s?(구축|도입)",
 r"공모|선정(됐|되|한다)|우수\s?사례|시범\s?사업",
]

def has_policy_signal(title, body=""):
    t = f"{title} {body}"
    if not any(re.search(p, t) for p in POLICY_RX): return False
    # 절차 안내만 있고 실제 추진 내용이 없으면 정책 사례로 보지 않는다
    if any(w in (title or "") for w in PROCEDURAL):
        strong = [r"도입|구축|개발|시행|출시|개통|운영\s?개시|고도화|전환|실증",
                  r"협약|MOU|성과|효과|첫\s?|최초|전략|로드맵|기본계획"]
        return any(re.search(p, title or "") for p in strong)
    return True

def guess_org(x, title, body=""):
    """기관 추정. 최종 확정은 LLM이 한다. 못 찾으면 None을 두고 넘긴다."""
    host = (x.get("source_domain") or "").lower()
    if not host:
        try: host = urllib.parse.urlparse(x.get("link") or "").netloc.lower()
        except Exception: host = ""
        if "news.google.com" in host: host = ""
    if not host:
        q = x.get("query") or ""                 # site:mcst.go.kr (...) 형태
        m = re.match(r"site:([^\s)]+)", q)
        if m: host = m.group(1).lower()
    t = f"{title} {body}"
    shared = any(h in host for h in SHARED_HOST)
    if not shared:
        for o in ORGS:
            if o["domain"] in host: return o["name"], o["tag"]
    for o in ORGS:                      # 본문 표기 우선
        if o["q"] in t: return o["name"], o["tag"]
    for name, tag in MINISTRY:
        if name in t:
            return ("문화체육관광부" if name == "문체부" else
                    "과학기술정보통신부" if name == "과기정통부" else
                    "행정안전부" if name == "행안부" else name), tag
    return None, None


def collect():
    raw = []
    print("■ 1차 · 대한민국 정책브리핑")
    for q in BRIEFING_QUERIES:
        r = google_news(q)
        for x in r: x["src_tier"] = "정책브리핑"
        raw += r
        print(f"   '{q.replace('site:korea.kr ','')}': {len(r)}건")
        time.sleep(0.4)

    print("■ 2차 · 기관별 공식 채널")
    for o in ORGS:
        q = f'site:{o["domain"]} (인공지능 OR AI OR 디지털전환 OR 데이터)'
        r = google_news(q)
        for x in r: x["org_hint"] = o["name"]
        raw += r
        print(f"   {o['name']:14s} ({o['domain']:22s}) {len(r)}건")
        time.sleep(0.4)

    print("■ 주제 질의")
    for q in AX_TOPIC_QUERIES:
        r = google_news(q); raw += r
        print(f"   '{q}': {len(r)}건")
        time.sleep(0.4)

    if USE_MEDIA:
        print("■ 관광업계 언론 (2단계)")
        for q in AX_MEDIA_QUERIES:
            r = google_news(q); raw += r
            print(f"   '{q}': {len(r)}건")
            time.sleep(0.4)
    return raw


def main():
    raw = collect()
    cut = (NOW - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")

    kept, dropped = [], {}
    seen = set()
    def drop(why): dropped[why] = dropped.get(why, 0) + 1

    for x in raw:
        link = (x.get("link") or "").strip()
        if not link or link in seen:
            drop("중복"); continue
        seen.add(link)
        if x.get("date") and x["date"] < cut:
            drop("기간 밖"); continue
        if not x.get("date"):
            x["date"] = NOW.strftime("%Y-%m-%d")   # 날짜 불명은 수집일로 둔다
        title = x.get("title") or ""
        body  = x.get("description") or ""

        if not USE_MEDIA and not is_official(x):
            drop("공식 채널 아님"); continue
        if is_self(x, title, body):
            drop("제주 기관(보는 주체)"); continue
        if is_noise(title):
            drop("공고·기관페이지"); continue
        score, hits = ax_score(title, body)
        if score == 0:
            drop("AX 신호 없음"); continue
        # 관광 여부는 더 이상 채택 조건이 아니다. 분류용 표시로만 남긴다.
        tour = is_tourism(title, body)
        if not has_policy_signal(title, body):
            drop("정책·사례 신호 없음"); continue

        org, tag = guess_org(x, title, body)
        kept.append({**x,
                     "org": org, "org_tag": tag, "tourism": tour,
                     "ax_rank": "제목" if score == 2 else "밀접",
                     "ax_hits": hits,
                     "official": is_official(x)})

    # ── 누적 병합 (이슈체크와 같은 방식)
    prev = []
    if os.path.exists(OUT):
        try: prev = json.load(open(OUT, encoding="utf-8")).get("items", [])
        except Exception: prev = []
    keep_cut = (NOW - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    # 엔진이 바뀌면 누적된 옛 항목을 버린다.
    # 관광AX는 선별 규칙이 크게 달라져 옛 판정을 그대로 두면 화면이 섞인다.
    ENG = "ax-v4-20260826"
    kept_old = [it for it in prev if it.get("engine") == ENG]
    if len(prev) != len(kept_old):
        print(f"■ 엔진 변경 — 옛 판정 {len(prev)-len(kept_old)}건 폐기 후 재수집분으로 대체")
    for it in kept: it["engine"] = ENG

    merged = {}
    for it in kept_old + kept:
        k = (it.get("link") or it.get("title") or "").strip()
        if not k: continue
        if it.get("date") and it["date"] < keep_cut: continue
        merged[k] = it
    allitems = sorted(merged.values(), key=lambda x: x.get("date") or "", reverse=True)

    out = {"meta": {"updated": NOW.strftime("%Y-%m-%d %H:%M"),
                    "engine": "ax-v4-20260826",
                    "collected": len(raw), "kept": len(kept), "stored": len(allitems),
                    "days": DAYS_BACK, "keep_days": KEEP_DAYS,
                    "stage": "2단계(업계 언론 포함)" if USE_MEDIA else "1단계(공식 채널)",
                    "source": "Google News RSS · 공식 도메인 한정",
                    "disclaimer": "공개된 보도자료를 수집해 분류한 참고자료입니다. "
                                  "원문·발행일·출처를 함께 표기하며, 확인되지 않은 내용은 생성하지 않습니다."},
           "orgs": ORGS, "dropped": dropped, "items": allitems}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    from collections import Counter
    print(f"\n수집 {len(raw)} → 채택 {len(kept)} → 누적 저장 {len(allitems)}건")
    print("  제외:", dict(sorted(dropped.items(), key=lambda x: -x[1])))
    print("  기관:", dict(Counter(x.get("org") for x in allitems).most_common(8)))
    print("  등급:", dict(Counter(x.get("ax_rank") for x in allitems)))
    print("저장:", os.path.relpath(OUT))


if __name__ == "__main__":
    main()
