# -*- coding: utf-8 -*-
"""
제주관광 여론 수집기 — 네이버(뉴스·블로그·카페) + 구글뉴스 RSS
※ 스레드·유튜브는 토큰이 있을 때만 켜진다(없으면 조용히 건너뜀).
출처: 네이버 검색 오픈API, Google News RSS
"""
import os, re, sys, json, time, html, ssl, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

# 같은 폴더의 모듈을 찾도록 경로 추가 (어디서 실행하든 동작)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from issue_geo import EMD, SPOT, geo_hit
    from issue_classify import judge, ENGINE_VERSION
except Exception as e:
    print("모듈 로드 실패:", e)
    print("scripts/ 폴더에 issue_geo.py, issue_classify.py가 있는지 확인하세요.")
    raise

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "data", "issue.json")
HIST = os.path.join(HERE, "..", "data", "issue_history.json")

# ncloud API HUB (뉴스만 제공)
NAVER_ID     = os.environ.get("NAVER_ID", "").strip()
NAVER_SECRET = os.environ.get("NAVER_SECRET", "").strip()
# 네이버 개발자센터 오픈API (뉴스·블로그·카페 모두 제공, 하루 25,000회 무료)
NCID     = os.environ.get("NAVER_CLIENT_ID", "").strip()
NCSECRET = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
YOUTUBE_KEY  = os.environ.get("YOUTUBE_API_KEY", "").strip()
THREADS_TOKEN= os.environ.get("THREADS_ACCESS_TOKEN", "").strip()

CTX = ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
UA  = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"

# 수집 질의어 — 중립어 + 지역 조합
QUERIES = ["제주 여행", "제주도 여행", "제주 관광", "제주도 관광", "제주 관광정책",
           "제주 렌터카", "제주 숙소", "제주 맛집", "제주 물가", "제주 관광객"]
# 불만 탐지용 (블로그·카페·스레드) — 중립어로는 불만글이 검색에 잡히지 않는다.
# ※ 이 질의어로 모은 표본은 부정에 치우친다. 그래서 지수를 '부정 비중'이 아니라
#   '모인 불만 안에서의 분야 구성비'로 쓴다(index_calc.py 참고).
VOICE_EXTRA = ["제주 바가지", "제주 불친절", "제주 여행 실망", "제주 렌터카 불만",
               "제주 숙소 후기 별로", "제주 물가 비싸", "제주 여행 후회", "제주 관광지 불편",
               "제주 주차 불편", "제주 여행 다신"]
# 사건 탐지용 (뉴스 채널만) — 지역명 조합으로 놓치는 것 방지
NEWS_EXTRA = ["제주 사고", "제주 실종", "제주 화재", "제주 단속", "제주 관광 불편",
              "서귀포 사고", "제주 안전"]

DAYS_BACK = 21   # 한 번 실행에서 새로 받아올 범위
KEEP_DAYS = 60   # 누적 보관 기간 — 이보다 오래된 글만 버린다

def clean(s=""):
    s = re.sub(r"<[^>]+>", "", s or "")
    return html.unescape(s).strip()

def fetch(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")

# ── 네이버 검색 — 두 경로 지원
#    (1) 개발자센터 오픈API : 뉴스·블로그·카페 전부. 우선 사용
#    (2) ncloud API HUB     : 뉴스만. (1)이 없을 때 사용
NAVER_EP = {"news":"news", "blog":"blog", "cafe":"cafearticle"}
HUB_BASE = "https://naverapihub.apigw.ntruss.com/search/v1"
DEV_BASE = "https://openapi.naver.com/v1/search"

def naver(channel, query, display=100, start=1):
    ep = NAVER_EP[channel]
    qs = urllib.parse.urlencode({"query": query, "display": display,
                                 "start": start, "sort": "date"})
    tries = []
    if NCID and NCSECRET:
        tries.append(("개발자센터", f"{DEV_BASE}/{ep}.json?{qs}",
                      {"X-Naver-Client-Id": NCID, "X-Naver-Client-Secret": NCSECRET}))
    if NAVER_ID and NAVER_SECRET:
        tries.append(("API HUB", f"{HUB_BASE}/{ep}?{qs}",
                      {"x-ncp-apigw-api-key-id": NAVER_ID, "x-ncp-apigw-api-key": NAVER_SECRET}))
    if not tries: return []
    last=None
    for label, url, hdr in tries:
        try:
            d = json.loads(fetch(url, hdr)); break
        except Exception as e:
            last=f"{label}: {e}"; d=None
    if d is None:
        print(f"   ! naver/{channel} '{query}': {last}"); return []
    out=[]
    for it in d.get("items", []):
        pub = it.get("pubDate") or it.get("postdate") or ""
        ts=None
        if pub:
            try: ts = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %z")
            except Exception:
                try: ts = datetime.strptime(pub, "%Y%m%d").replace(tzinfo=KST)
                except Exception: ts=None
        out.append({"title": clean(it.get("title")), "description": clean(it.get("description")),
                    "link": it.get("originallink") or it.get("link"),
                    "date": ts.astimezone(KST).strftime("%Y-%m-%d") if ts else None,
                    "channel": channel, "query": query})
    return out

# ── 구글 뉴스 RSS
def google_news(query):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
    try: xml = fetch(url)
    except Exception as e:
        print(f"   ! gnews '{query}': {e}"); return []
    out=[]
    for m in re.finditer(r"<item>(.*?)</item>", xml, re.S):
        b=m.group(1)
        g=lambda tag: (re.search(rf"<{tag}>(.*?)</{tag}>", b, re.S) or [None,""])[1]
        pub=g("pubDate"); ts=None
        if pub:
            try: ts=datetime.strptime(clean(pub), "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
            except Exception: ts=None
        out.append({"title": clean(g("title")), "description": clean(g("description"))[:300],
                    "link": clean(g("link")),
                    "date": ts.astimezone(KST).strftime("%Y-%m-%d") if ts else None,
                    "channel": "news", "query": query})
    return out

# ── 스레드 (토큰 있을 때만)
def threads(query):
    if not THREADS_TOKEN: return []
    url = "https://graph.threads.net/v1.0/keyword_search?" + urllib.parse.urlencode(
        {"q": query, "search_type": "TOP", "fields": "id,text,timestamp,permalink",
         "access_token": THREADS_TOKEN})
    try: d=json.loads(fetch(url))
    except Exception as e:
        print(f"   ! threads '{query}': {e}"); return []
    out=[]
    for it in d.get("data", []):
        txt=(it.get("text") or "").strip()
        if not txt: continue
        ts=it.get("timestamp","")[:10]
        out.append({"title": txt[:80], "description": txt, "link": it.get("permalink"),
                    "date": ts or None, "channel": "threads", "query": query})
    return out

# ── 유튜브 (키 있을 때만)
def youtube(query):
    if not YOUTUBE_KEY: return []
    url = "https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(
        {"part":"snippet","q":query,"type":"video","order":"date","maxResults":25,
         "regionCode":"KR","relevanceLanguage":"ko","key":YOUTUBE_KEY})
    try: d=json.loads(fetch(url))
    except Exception as e:
        print(f"   ! youtube '{query}': {e}"); return []
    out=[]
    for it in d.get("items", []):
        sn=it.get("snippet",{})
        out.append({"title": clean(sn.get("title")), "description": clean(sn.get("description")),
                    "link": f"https://www.youtube.com/watch?v={it['id'].get('videoId','')}",
                    "date": (sn.get("publishedAt") or "")[:10],
                    "channel": "youtube", "query": query})
    return out

def probe_channels():
    """API HUB에서 어떤 채널이 열려 있는지 먼저 확인한다."""
    ok=[]
    for ch in ("news","blog","cafe"):
        r=naver(ch,"제주",display=1)
        if r: ok.append(ch); print(f"   {ch:5s} 사용 가능")
        else: print(f"   {ch:5s} 응답 없음 — 이후 건너뜀")
        time.sleep(0.2)
    return ok

def collect():
    cutoff = (NOW - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
    raw=[]
    print("■ 채널 점검")
    CH = probe_channels()
    if not CH:
        print("   사용 가능한 네이버 채널이 없습니다. 구글뉴스만으로 진행합니다.")
    print("■ 네이버")
    for q in QUERIES:
        for ch in CH:
            r=naver(ch,q); raw+=r
            print(f"   {ch:5s} '{q}': {len(r)}건"); time.sleep(0.15)
    print("■ 불만 보강 질의 (블로그·카페)")
    for q in VOICE_EXTRA:
        got=0
        for ch in ("blog","cafe"):
            if ch not in CH: continue
            r=naver(ch,q,display=50); raw+=r; got+=len(r); time.sleep(0.15)
        print(f"   '{q}': {got}건")
    print("■ 뉴스 보강 질의")
    for q in NEWS_EXTRA:
        r=naver("news",q) if "news" in CH else []; raw+=r
        g=google_news(q); raw+=g
        print(f"   news '{q}': 네이버 {len(r)} / 구글 {len(g)}"); time.sleep(0.2)
    print("■ 구글뉴스")
    for q in QUERIES[:5]:
        g=google_news(q); raw+=g
        print(f"   '{q}': {len(g)}건"); time.sleep(0.2)
    if THREADS_TOKEN:
        print("■ 스레드")
        for q in ["제주","제주도","제주여행","제주 여행 후기","제주 렌터카","제주 물가"]:
            r=threads(q); raw+=r; print(f"   '{q}': {len(r)}건"); time.sleep(0.3)
    else:
        print("■ 스레드 — 토큰 없음, 건너뜀")
    if YOUTUBE_KEY:
        print("■ 유튜브")
        for q in QUERIES[:4]:
            r=youtube(q); raw+=r; print(f"   '{q}': {len(r)}건"); time.sleep(0.3)
    else:
        print("■ 유튜브 — 키 없음, 건너뜀")

    # 중복 제거 + 기간 필터
    seen={}
    for it in raw:
        k=(it.get("link") or it.get("title") or "").strip()
        if not k: continue
        if it.get("date") and it["date"] < cutoff: continue
        if k not in seen: seen[k]=it
    return list(seen.values())

def main():
    print("=== 제주관광 여론 수집 ===")
    print("개발자센터(블로그·카페):", "설정됨" if (NCID and NCSECRET) else "없음",
          "| API HUB(뉴스):", "설정됨" if (NAVER_ID and NAVER_SECRET) else "없음",
          "| THREADS:", "설정됨" if THREADS_TOKEN else "없음",
          "| YOUTUBE:", "설정됨" if YOUTUBE_KEY else "없음")
    if not ((NCID and NCSECRET) or (NAVER_ID and NAVER_SECRET)):
        print("\n네이버 키가 없습니다. Secrets에 NAVER_CLIENT_ID/NAVER_CLIENT_SECRET"
              " 또는 NAVER_ID/NAVER_SECRET을 등록하세요.")
        raise SystemExit(1)
    if not (NCID and NCSECRET):
        print("  ※ 개발자센터 키가 없어 블로그·카페는 수집되지 않습니다.")
    print(f"수집 시작 · 엔진 {ENGINE_VERSION} · 기준 {NOW:%Y-%m-%d %H:%M} KST\n")
    items = collect()
    print(f"\n원본 {len(items)}건 (중복·기간 제거 후)\n")

    kept=[]; dropped={}
    for it in items:
        r = judge(it)
        if not r["keep"]:
            key=f"{r['stage']}·{r['why']}"
            dropped[key]=dropped.get(key,0)+1
            continue
        it.update({k:r.get(k) for k in ("type","category","nature","track","policy",
                                        "sentiment","strength","neg","pos","reasons","pending","rel_why")})
        kept.append(it)

    print("■ 제외 사유")
    for k,v in sorted(dropped.items(), key=lambda x:-x[1]):
        print(f"   {v:5d}  {k}")
    print(f"\n■ 채택 {len(kept)}건")
    from collections import Counter
    print("   감성:", dict(Counter(x["sentiment"] for x in kept)))
    print("   유형:", dict(Counter(x["type"] for x in kept)))
    print("   채널:", dict(Counter(x["channel"] for x in kept)))
    print("   분류:", dict(Counter(x["category"] for x in kept if x["category"])))

    # ── 누적 병합
    # 네이버 검색 API는 최신순 일부만 돌려주므로, 매 실행마다 덮어쓰면 과거가 남지 않는다.
    # (실측: 21일치라 해도 최근 이틀이 전체의 62%를 차지했다)
    # 기존 파일과 링크 기준으로 합쳐야 월 단위 비교가 실제로 가능해진다.
    prev=[]
    if os.path.exists(OUT):
        try: prev=json.load(open(OUT,encoding="utf-8")).get("items",[])
        except Exception: prev=[]
    keep_cut=(NOW - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    merged={}
    for it in prev + kept:                      # 새 판정 결과가 옛 것을 덮어쓴다
        k=(it.get("link") or it.get("title") or "").strip()
        if not k: continue
        if it.get("date") and it["date"] < keep_cut: continue
        merged[k]=it
    allitems=sorted(merged.values(), key=lambda x: x.get("date") or "", reverse=True)
    print(f"■ 누적  기존 {len(prev)} + 신규 {len(kept)} → 병합 {len(allitems)}건 (보관 {KEEP_DAYS}일)")

    out={"meta":{"updated":NOW.strftime("%Y-%m-%d %H:%M"),"engine":ENGINE_VERSION,
                 "collected":len(items),"kept":len(kept),"stored":len(allitems),
                 "days":DAYS_BACK,"keep_days":KEEP_DAYS,
                 "source":"네이버 검색 오픈API · Google News RSS",
                 "disclaimer":"공개된 게시물을 수집해 규칙으로 분류한 참고자료입니다. 원인 해석이나 위험도 판단은 하지 않습니다."},
         "dropped":dropped,"items":allitems}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n저장:", os.path.relpath(OUT))

if __name__ == "__main__":
    main()
