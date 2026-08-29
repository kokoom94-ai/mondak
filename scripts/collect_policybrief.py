# -*- coding: utf-8 -*-
"""정부정책 브리핑 — 대한민국 정책브리핑(korea.kr) 정책뉴스를 모아 data/policybrief.json 으로.

정책브리핑 RSS는 2026-07-01 자로 중단됐다(저작권 등 권리 보호에 따른 제공방식 변경).
그래서 구글뉴스 색인을 통해 korea.kr 기사를 찾고, 리다이렉트를 원문 직링크로 되돌린다.
제목·발행일·원문 링크만 보관하고 본문은 저장하지 않는다.
"""
import html, json, os, re, ssl, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

OUT = os.path.join("data", "policybrief.json")
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
KEEP_DAYS = 60

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

# 정책브리핑의 정책뉴스에서 다루는 주제들
QUERIES = [
    "site:korea.kr 정책뉴스",
    "site:korea.kr 정부 발표",
    "site:korea.kr 국민 지원",
    "site:korea.kr 제도 개선",
    "site:korea.kr 지원금 신청",
    "site:korea.kr 민생",
    "site:korea.kr 관광",
    "site:korea.kr 지역 균형발전",
    "site:korea.kr 인공지능",
    "site:korea.kr 청년 정책",
]

RESOLVE_MAX = int(os.environ.get("PB_RESOLVE_MAX", "120"))


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def clean(t=""):
    t = html.unescape(t or "")
    t = re.sub(r"<[^>]*>", " ", t)
    t = re.sub(r"https?://\S+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def strip_tail(t=""):
    return re.sub(r"\s*[-|]\s*(대한민국 정책브리핑|정책브리핑|korea\.kr)\s*$", "", t or "").strip()


def google_news(q):
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q)
           + "&hl=ko&gl=KR&ceid=KR:ko")
    try:
        xml = fetch(url)
    except Exception as e:
        print("   ! " + q + ": " + str(e))
        return []
    out = []
    for m in re.finditer(r"<item>(.*?)</item>", xml, re.S):
        blk = m.group(1)
        def g(tag):
            mm = re.search(r"<" + tag + r"[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</" + tag + r">", blk, re.S)
            return (mm.group(1) if mm else "").strip()
        title = strip_tail(clean(g("title")))
        link = html.unescape(g("link")).strip()
        src = clean(g("source"))
        d = g("pubDate")
        date = ""
        mm = re.search(r"(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{4})", d)
        if mm:
            MON = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
                   "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
            date = str(mm.group(3)) + "-" + str(MON[mm.group(2)]).zfill(2) + "-" + str(int(mm.group(1))).zfill(2)
        if not title or not link: continue
        # 정책브리핑이 발행처인 것만
        if "정책브리핑" not in src and "korea.kr" not in link and "정책브리핑" not in title:
            if src and "korea" not in src.lower(): continue
        out.append({"title": title, "link": link, "date": date, "source": src or "대한민국 정책브리핑"})
    return out


# ── 구글뉴스 리다이렉트 → 원문 직링크 ──
def _gn_id(link):
    m = re.search(r"news\.google\.com/(?:rss/)?(?:articles|read)/([^?/]+)", link or "")
    return m.group(1) if m else None


def _gn_params(aid):
    try:
        page = fetch("https://news.google.com/rss/articles/" + aid)
    except Exception:
        return None
    m = re.search(r'data-p="([^"]+)"', page)
    if not m: return None
    try:
        data = json.loads(html.unescape(m.group(1)).replace("%.@.", '["garturlreq",'))
        return {"id": aid, "ts": data[-2], "sig": data[-1]}
    except Exception:
        return None


def _gn_decode(p):
    req_body = ('f.req=' + urllib.parse.quote(json.dumps([[[
        "Fbv4je",
        '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,'
        'null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"'
        + p["id"] + '",' + str(p["ts"]) + ',"' + p["sig"] + '"]']]]))).encode()
    req = urllib.request.Request(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute",
        data=req_body, headers={"User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    try:
        with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
            txt = r.read().decode("utf-8", "replace")
        row = json.loads(txt.split("\n\n")[1])[0]
        return json.loads(row[2])[1]
    except Exception:
        return None


def resolve(items):
    todo = [x for x in items if "news.google.com" in (x.get("link") or "") and not x.get("resolved")]
    todo = todo[:RESOLVE_MAX]
    if not todo:
        print("■ 직링크 해석 — 대상 없음"); return 0
    print("■ 직링크 해석 — " + str(len(todo)) + "건")
    ok = 0
    for x in todo:
        aid = _gn_id(x["link"])
        p = _gn_params(aid) if aid else None
        if p:
            u = _gn_decode(p)
            if u and u.startswith("http") and "news.google.com" not in u:
                x["gnews"] = x["link"]; x["link"] = u; x["resolved"] = True; ok += 1
        time.sleep(0.4)
    print("   해석 성공 " + str(ok) + " / " + str(len(todo)))
    return ok


def main():
    print("■ 수집 · 대한민국 정책브리핑 정책뉴스")
    print("   (정책브리핑 RSS는 2026-07-01 중단 — 구글뉴스 색인으로 찾습니다)")
    raw, seen = [], set()
    for q in QUERIES:
        got = google_news(q)
        new = 0
        for x in got:
            k = re.sub(r"\s+", "", x["title"])[:40]
            if not k or k in seen: continue
            seen.add(k); raw.append(x); new += 1
        print("   " + q.replace("site:korea.kr ", "") + ": " + str(new) + "건 (누적 " + str(len(raw)) + ")")
        time.sleep(0.5)

    # 기존 누적과 합친다
    prev = []
    if os.path.exists(OUT):
        try: prev = json.load(open(OUT, encoding="utf-8")).get("items", [])
        except Exception: prev = []
    cut = (NOW - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    merged = {}
    for x in prev + raw:
        if (x.get("date") or "") and x["date"] < cut: continue
        k = (x.get("gnews") or x.get("link") or x.get("title") or "").strip()
        if not k: continue
        if k in merged and merged[k].get("resolved") and not x.get("resolved"): continue
        merged[k] = x
    items = list(merged.values())
    items.sort(key=lambda x: x.get("date") or "", reverse=True)
    resolve(items)
    items.sort(key=lambda x: x.get("date") or "", reverse=True)

    os.makedirs("data", exist_ok=True)
    json.dump({"meta": {"updated": NOW.strftime("%Y-%m-%d %H:%M"),
                        "source": "대한민국 정책브리핑 (korea.kr) 정책뉴스",
                        "note": "정책브리핑 RSS 서비스는 2026-07-01 중단되어 검색 색인으로 수집합니다.",
                        "count": len(items),
                        "resolved": sum(1 for x in items if x.get("resolved"))},
               "items": items[:200]},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("")
    print("저장 " + str(len(items[:200])) + "건 · 직링크 "
          + str(sum(1 for x in items if x.get("resolved"))) + "건")
    print("→ " + OUT)


if __name__ == "__main__":
    main()
