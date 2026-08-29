# -*- coding: utf-8 -*-
"""나라장터 제주 입찰공고 — 조달청 입찰공고정보서비스에서 받아 data/bids.json 으로.

환경변수: GOV24_KEY (data.go.kr 인증키. 나라장터 서비스도 같은 키를 쓴다)

응답 필드 이름을 확신할 수 없으므로 스스로 찾아낸다.
필드가 어긋나면 첫 항목 원문을 로그에 찍으니, 그걸 보고 바로 고칠 수 있다.
"""
import json, os, re, ssl, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

KEY  = os.environ.get("GOV24_KEY", "").strip()
BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"
OUT  = os.path.join("data", "bids.json")

KST  = timezone(timedelta(hours=9))
NOW  = datetime.now(KST)
DAYS = int(os.environ.get("BID_DAYS", "30"))     # 최근 며칠분
ROWS = 100
PROBE = "--probe" in sys.argv

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA  = "Mozilla/5.0 (compatible; MondakBot/1.0; +https://kokoom94-ai.github.io/mondak/)"

# 공고 종류별 조회 경로 — 물품·용역·공사·외자
KINDS = [("용역", "getBidPblancListInfoServcPPSSrch"),
         ("물품", "getBidPblancListInfoThngPPSSrch"),
         ("공사", "getBidPblancListInfoCnstwkPPSSrch")]


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def call(op, page, bgn, end):
    q = {"serviceKey": KEY, "pageNo": page, "numOfRows": ROWS, "type": "json",
         "inqryDiv": "1", "inqryBgnDt": bgn, "inqryEndDt": end}
    url = BASE + "/" + op + "?" + urllib.parse.urlencode(q, safe="%")
    try:
        txt = fetch(url)
    except Exception as e:
        print("   ! " + op + " p" + str(page) + ": " + str(e))
        return None
    if txt.lstrip().startswith("<"):
        m = re.search(r"<returnAuthMsg>([^<]*)</returnAuthMsg>|<errMsg>([^<]*)</errMsg>", txt)
        print("   ! XML 응답: " + (m.group(0) if m else txt[:160].replace("\n", " ")))
        return None
    try:
        return json.loads(txt)
    except Exception:
        print("   ! JSON 아님: " + txt[:160].replace("\n", " "))
        return None


def rows_of(d):
    """응답에서 목록을 찾는다. 감싸는 이름이 무엇이든 가장 큰 dict 배열을 쓴다."""
    if not d: return []
    best = []
    def walk(o):
        nonlocal best
        if isinstance(o, list):
            if o and isinstance(o[0], dict) and len(o) > len(best): best = o
            for v in o[:5]: walk(v)
        elif isinstance(o, dict):
            for v in o.values(): walk(v)
    walk(d)
    return best


def pick(r, *names, default=""):
    low = {str(k).lower(): v for k, v in r.items()}
    for n in names:
        v = low.get(n.lower())
        if v not in (None, "", "null"): return str(v).strip()
    return default


def to_date(v):
    m = re.search(r"(20\d{2})[-./]?(\d{2})[-./]?(\d{2})", str(v or ""))
    return m.group(1) + "-" + m.group(2) + "-" + m.group(3) if m else ""


def to_won(v):
    try:
        n = int(float(str(v).replace(",", "")))
        return n if n > 0 else None
    except Exception:
        return None


# 제주 판별 — 지역명이 기관명·지역제한·공고명 어디에 있어도 잡는다
JEJU = re.compile(r"제주|서귀포|한라|탐라|우도|추자|성산|애월|한림|표선|남원|대정|안덕|조천|구좌|한경")


def normalize(rows, kind):
    out = []
    for r in rows:
        if not isinstance(r, dict): continue
        title = pick(r, "bidNtceNm", "ntceNm", "공고명")
        if not title: continue
        org  = pick(r, "dminsttNm", "ntceInsttNm", "수요기관명", "발주기관")
        rgn  = pick(r, "prtcptLmtRgnNm", "rgnLmtBidLocplcJdgmBssCd", "지역제한")
        blob = title + " " + org + " " + rgn
        if not JEJU.search(blob): continue
        no   = pick(r, "bidNtceNo", "공고번호")
        ord_ = pick(r, "bidNtceOrd", "차수", default="00")
        link = pick(r, "bidNtceDtlUrl", "bidNtceUrl")
        if not link and no:
            link = ("https://www.g2b.go.kr/ep/invitation/publish/bidInfoDtl.do"
                    "?bidno=" + no + "&bidseq=" + ord_)
        out.append({
            "no": no, "kind": kind, "title": title,
            "org": org or pick(r, "ntceInsttNm"),
            "region": rgn,
            "posted": to_date(pick(r, "bidNtceDt", "rgstDt", "공고일시")),
            "close":  to_date(pick(r, "bidClseDt", "opengDt", "입찰마감일시")),
            "price":  to_won(pick(r, "presmptPrce", "asignBdgtAmt", "추정가격")),
            "method": pick(r, "cntrctCnclsMthdNm", "bidMethdNm"),
            "link": link,
        })
    return out


def main():
    if not KEY:
        print("GOV24_KEY 미설정 — Settings→Secrets→Actions에 등록 필요"); return

    end = NOW.strftime("%Y%m%d") + "2359"
    bgn = (NOW - timedelta(days=DAYS)).strftime("%Y%m%d") + "0000"
    print("■ 나라장터 제주 입찰공고 — " + bgn[:8] + " ~ " + end[:8])

    all_items, shown = [], False
    for kind, op in KINDS:
        got = 0
        for page in range(1, 21):
            d = call(op, page, bgn, end)
            rows = rows_of(d)
            if PROBE and rows and not shown:
                shown = True
                print("")
                print("[probe] 첫 항목 원문:")
                print(json.dumps(rows[0], ensure_ascii=False, indent=1)[:1600])
                return
            if not rows: break
            picked = normalize(rows, kind)
            all_items += picked
            got += len(picked)
            if len(rows) < ROWS: break
            time.sleep(0.4)
        print("   " + kind + ": 제주 " + str(got) + "건")
        time.sleep(0.5)

    # 같은 공고번호는 한 건으로 본다(종류가 겹쳐 들어오는 경우가 있다). 마감 임박순.
    seen, items = set(), []
    for x in all_items:
        k = x["no"] or (x["title"] + x["org"])
        if k in seen: continue
        seen.add(k); items.append(x)
    today = NOW.strftime("%Y-%m-%d")
    items.sort(key=lambda x: (x["close"] < today, x["close"] or "9999"))

    os.makedirs("data", exist_ok=True)
    json.dump({"meta": {"updated": NOW.strftime("%Y-%m-%d %H:%M"),
                        "source": "조달청 나라장터 입찰공고정보서비스 (공공데이터포털)",
                        "period": bgn[:8] + "~" + end[:8],
                        "count": len(items)},
               "items": items[:300]},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    import collections
    live = [x for x in items if x["close"] >= today]
    print("")
    print("저장 " + str(len(items[:300])) + "건 · 마감 전 " + str(len(live)) + "건")
    print("종류: " + str(dict(collections.Counter(x["kind"] for x in items))))
    print("→ " + OUT)


if __name__ == "__main__":
    main()
