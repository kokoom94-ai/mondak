# -*- coding: utf-8 -*-
"""
관광 AX 인사이트 수집기 — data/ax.json

무엇을 모으나
  관광 분야의 인공지능 전환(AX) 관련 보도자료·발표를 모은다.
  목적은 "타 기관은 무엇을 하고 있고, 제주관광공사는 어디에 있나"를 보는 것.

출처 (1단계 — 공식 채널 한정)
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

DAYS_BACK = 30    # 한 번에 새로 받아올 범위
KEEP_DAYS = 730   # 누적 보관 — AX는 흐름을 봐야 하므로 길게 둔다

# ── 기관 ────────────────────────────────────────────────
# name  : 화면 표기
# domain: site: 한정에 쓸 도메인
# tag   : 축 분류 (부처 / 공사 / 지자체 / 지역관광 / 유관)
ORGS = [
 {"name":"문화체육관광부",   "domain":"mcst.go.kr",          "tag":"부처",   "q":"문화체육관광부"},
 {"name":"한국관광공사",     "domain":"knto.or.kr",          "tag":"공사",   "q":"한국관광공사"},
 {"name":"한국관광공사",     "domain":"visitkorea.or.kr",    "tag":"공사",   "q":"한국관광공사"},
 {"name":"제주특별자치도",   "domain":"jeju.go.kr",          "tag":"지자체", "q":"제주특별자치도"},
 {"name":"제주관광공사",     "domain":"ijto.or.kr",          "tag":"우리",   "q":"제주관광공사"},
 {"name":"경기관광공사",     "domain":"ggtour.or.kr",        "tag":"지역관광","q":"경기관광공사"},
 {"name":"부산관광공사",     "domain":"bto.or.kr",           "tag":"지역관광","q":"부산관광공사"},
 {"name":"인천관광공사",     "domain":"ito.or.kr",           "tag":"지역관광","q":"인천관광공사"},
 {"name":"강원관광재단",     "domain":"gwto.or.kr",          "tag":"지역관광","q":"강원관광재단"},
 {"name":"경북문화관광공사", "domain":"gcto.co.kr",          "tag":"지역관광","q":"경북문화관광공사"},
 {"name":"서울관광재단",     "domain":"sto.or.kr",           "tag":"지역관광","q":"서울관광재단"},
 {"name":"한국문화정보원",   "domain":"kcisa.kr",            "tag":"유관",   "q":"한국문화정보원"},
 {"name":"한국문화관광연구원","domain":"kcti.re.kr",         "tag":"유관",   "q":"한국문화관광연구원"},
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
AX_TOPIC_QUERIES = [
 "관광 인공지능", "관광 AI", "관광 AX", "관광 디지털 전환",
 "여행 인공지능", "스마트관광", "관광 빅데이터", "관광 챗봇",
 "관광 데이터 플랫폼", "관광 생성형 AI",
]
# 2단계 — 관광업계 언론까지 넓힐 때 켠다 (site 한정 없음)
AX_MEDIA_QUERIES = [
 "여행업계 인공지능", "호텔 인공지능", "항공 인공지능", "여행 플랫폼 AI",
]
USE_MEDIA = os.environ.get("AX_USE_MEDIA", "") == "1"

# 공식 도메인 화이트리스트 — 이 밖의 링크는 1단계에서 버린다
OFFICIAL_SUFFIX = (".go.kr", ".or.kr", "korea.kr", ".re.kr")


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
        src = clean((re.search(r"<source[^>]*>(.*?)</source>", b, re.S) or [None, ""])[1])
        out.append({"title": clean(g("title")),
                    "description": clean(g("description"))[:300],
                    "link": clean(g("link")),
                    "date": ts.astimezone(KST).strftime("%Y-%m-%d") if ts else None,
                    "source": src, "query": query})
    return out


def is_official(link):
    try:
        host = urllib.parse.urlparse(link).netloc.lower()
    except Exception:
        return False
    return any(host.endswith(s) or s in host for s in OFFICIAL_SUFFIX)


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
            ("국토교통부","부처"),("중소벤처기업부","부처"),("해양수산부","부처")]

def guess_org(link, title, body=""):
    """기관 추정. 최종 확정은 LLM이 한다. 못 찾으면 None을 두고 넘긴다."""
    host = ""
    try: host = urllib.parse.urlparse(link).netloc.lower()
    except Exception: pass
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
    print("■ 기관별 공식 채널")
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
        title = x.get("title") or ""
        body  = x.get("description") or ""

        if not USE_MEDIA and not is_official(link):
            drop("공식 채널 아님"); continue
        score, hits = ax_score(title, body)
        if score == 0:
            drop("AX 신호 없음"); continue
        if not is_tourism(title, body):
            drop("관광 맥락 없음"); continue

        org, tag = guess_org(link, title, body)
        kept.append({**x,
                     "org": org, "org_tag": tag,
                     "ax_rank": "제목" if score == 2 else "밀접",
                     "ax_hits": hits,
                     "official": is_official(link)})

    # ── 누적 병합 (이슈체크와 같은 방식)
    prev = []
    if os.path.exists(OUT):
        try: prev = json.load(open(OUT, encoding="utf-8")).get("items", [])
        except Exception: prev = []
    keep_cut = (NOW - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    merged = {}
    for it in prev + kept:
        k = (it.get("link") or it.get("title") or "").strip()
        if not k: continue
        if it.get("date") and it["date"] < keep_cut: continue
        merged[k] = it
    allitems = sorted(merged.values(), key=lambda x: x.get("date") or "", reverse=True)

    out = {"meta": {"updated": NOW.strftime("%Y-%m-%d %H:%M"),
                    "engine": "ax-v1-20260826",
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
