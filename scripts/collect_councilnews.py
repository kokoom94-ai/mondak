# -*- coding: utf-8 -*-
"""제주도의회 관련 보도 — 의원별로 모아 data/councilnews.json 으로.

news.json은 최근 2주치만 보관해 7월 기사가 없다.
그래서 도의회 보도만 따로, 시작일부터 누적해 모은다.

환경변수: NAVER_CLIENT_ID / NAVER_CLIENT_SECRET  (없으면 구글뉴스만 사용)
"""
import html, json, os, re, ssl, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

OUT   = os.path.join("data", "councilnews.json")
FROM  = os.environ.get("CN_FROM", "2026-07-01")     # 이 날짜부터 모은다
KST   = timezone(timedelta(hours=9))
NOW   = datetime.now(KST)

NID   = os.environ.get("NAVER_CLIENT_ID", "").strip()
NSEC  = os.environ.get("NAVER_CLIENT_SECRET", "").strip()

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA  = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

# 제13대 제주도의회 의원 45명
MEMBERS = ["한권","박호형","김기환","한동수","정민구","김황국","강성의","박안수","김봉현",
           "양영수","강정범","양영식","강철남","양경호","이경심","송창권","이남근","장정훈",
           "강봉직","강동우","김덕홍","김승준","강충룡","오은초","김대진","강명균","임정은",
           "이경철","송영훈","양홍식","하성용","한동훈","박지은","임혜주","정다운","고석준",
           "장희순","오경남","강영아","김효","김태현","이정한","박왕철","김경애","김혜지"]

COMMON_Q = ["제주도의회", "제주특별자치도의회", "제주도의회 의원", "제주도의회 상임위",
            "제주도의회 임시회", "제주도의회 정례회", "제주도의회 행정사무감사"]


def fetch(url, headers=None, timeout=20):
    h = {"User-Agent": UA}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def clean(t=""):
    t = html.unescape(t or "")
    t = re.sub(r"<[^>]*>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


MON = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
       "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}


def rfc_date(d):
    m = re.search(r"(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{4})", d or "")
    if not m: return ""
    return m.group(3) + "-" + str(MON[m.group(2)]).zfill(2) + "-" + m.group(1).zfill(2)


def naver(q, display=100, start=1):
    if not (NID and NSEC): return []
    url = ("https://openapi.naver.com/v1/search/news.json?query="
           + urllib.parse.quote(q) + "&display=" + str(display)
           + "&start=" + str(start) + "&sort=date")
    try:
        d = json.loads(fetch(url, {"X-Naver-Client-Id": NID,
                                   "X-Naver-Client-Secret": NSEC}))
    except Exception as e:
        print("   ! 네이버 " + q + ": " + str(e))
        return []
    out = []
    for it in d.get("items", []):
        out.append({"t": clean(it.get("title")),
                    "desc": clean(it.get("description"))[:180],
                    "link": (it.get("originallink") or it.get("link") or "").strip(),
                    "d": rfc_date(it.get("pubDate")),
                    "src": "네이버"})
    return out


def gnews(q):
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:180d")
           + "&hl=ko&gl=KR&ceid=KR:ko")
    try:
        xml = fetch(url)
    except Exception as e:
        print("   ! 구글 " + q + ": " + str(e))
        return []
    out = []
    for m in re.finditer(r"<item>(.*?)</item>", xml, re.S):
        blk = m.group(1)
        def g(tag):
            mm = re.search(r"<" + tag + r"[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</" + tag + r">", blk, re.S)
            return (mm.group(1) if mm else "").strip()
        out.append({"t": clean(g("title")), "desc": "",
                    "link": html.unescape(g("link")).strip(),
                    "d": rfc_date(g("pubDate")), "src": clean(g("source")) or "구글뉴스"})
    return out


# 도의회 기사인지 — 제목·본문에 도의회 표기가 있어야 한다
IS_COUNCIL = re.compile(r"제주\s?도의회|제주특별자치도의회|도의회")


def main():
    print("■ 제주도의회 보도 수집 — " + FROM + " 이후")
    print("   네이버 " + ("사용" if (NID and NSEC) else "미설정(구글만)"))

    raw = []
    # ① 공통 검색어
    for q in COMMON_Q:
        got = naver(q) + gnews(q)
        raw += got
        print("   [공통] " + q + ": " + str(len(got)) + "건")
        time.sleep(0.3)
    # ② 의원별
    for i, name in enumerate(MEMBERS, 1):
        q = "제주도의회 " + name
        got = naver(q, display=50) + gnews(q)
        raw += got
        if i % 10 == 0:
            print("   [의원] " + str(i) + "/" + str(len(MEMBERS)) + " · 누적 " + str(len(raw)))
        time.sleep(0.3)

    # 기존 누적과 합친다
    prev = []
    if os.path.exists(OUT):
        try: prev = json.load(open(OUT, encoding="utf-8")).get("items", [])
        except Exception: prev = []

    merged = {}
    for x in prev + raw:
        t = (x.get("t") or "").strip()
        if not t or not IS_COUNCIL.search(t + " " + (x.get("desc") or "")): continue
        d = x.get("d") or ""
        if d and d < FROM: continue
        if d and d > NOW.strftime("%Y-%m-%d"): continue
        key = re.sub(r"[^가-힣A-Za-z0-9]", "", t)[:45]
        if not key: continue
        old = merged.get(key)
        # 원문 직링크(네이버 originallink)를 우선 보관
        if old and "news.google.com" not in (old.get("link") or ""): continue
        merged[key] = {"t": t, "link": x.get("link") or "", "d": d,
                       "src": x.get("src") or "", "desc": (x.get("desc") or "")[:150]}

    items = list(merged.values())
    # 의원 태깅
    for x in items:
        blob = x["t"] + " " + x.get("desc", "")
        who = [n for n in MEMBERS if n in blob]
        x["who"] = who
    items.sort(key=lambda x: x.get("d") or "", reverse=True)

    os.makedirs("data", exist_ok=True)
    by = {}
    for x in items:
        if x["who"]:
            for n in x["who"]: by[n] = by.get(n, 0) + 1
        else:
            by["공통"] = by.get("공통", 0) + 1

    json.dump({"meta": {"updated": NOW.strftime("%Y-%m-%d %H:%M"),
                        "from": FROM, "count": len(items),
                        "members": MEMBERS,
                        "source": "네이버 뉴스검색 · 구글뉴스"},
               "items": items[:1200]},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("")
    print("저장 " + str(len(items[:1200])) + "건")
    print("의원별: " + str(dict(sorted(by.items(), key=lambda x: -x[1])[:12])))
    print("→ " + OUT)


if __name__ == "__main__":
    main()
