# -*- coding: utf-8 -*-
"""제주행사모음 — 비짓제주 축제 목록에서 받아 data/festival.json으로.

경로: api.visitjeju.net/api/contents/list  (축제 목록 화면이 실제로 쓰는 것)
공개 API(/vsjApi/)에는 축제 기간이 없어서 이쪽을 쓴다. 키는 필요 없다.

2026-01 ~ 2027-01 을 월별로 순회해 전량을 받는다.
새 축제가 올라오거나 기간이 바뀌면 다음 실행에서 자동 반영된다.
"""
import json, os, re, ssl, sys, time, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://api.visitjeju.net/api/contents/list"
OUT  = os.path.join("data", "festival.json")
SEED = os.path.join("data", "festival_seed.json")

KST   = timezone(timedelta(hours=9))
NOW   = datetime.now(KST)
TODAY = NOW.strftime("%Y-%m-%d")

# 표시 범위 — 사용자 확정
MONTHS = [(2026, m) for m in range(1, 13)] + [(2027, 1)]
RANGE_FROM, RANGE_TO = "2026-01-01", "2027-01-31"

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA  = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
PROBE = "--probe" in sys.argv


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko", "Referer": "https://www.visitjeju.net/kr/festival/list"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def call(year, month, page=1, state="all"):
    q = {"_siteId": "jejuavj", "locale": "kr", "device": "pc",
         "sorting": "likecnt desc", "year": year, "month": f"{month:02d}",
         "festivalcontents": "y", "contentscd": "c5",
         "pageSize": 100, "page": page, "state": state}
    try:
        return json.loads(fetch(BASE + "?" + urllib.parse.urlencode(q)))
    except Exception as e:
        print("   ! " + str(year) + "-" + str(month) + " p" + str(page) + ": " + str(e))
        return {}


# ── 값 꺼내기 ────────────────────────────────────────────
def flatten(o, prefix=""):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flatten(v, prefix + "." + k if prefix else k))
    elif isinstance(o, list):
        for i, v in enumerate(o[:3]):
            out.update(flatten(v, prefix + "[" + str(i) + "]"))
    else:
        out[prefix] = o
    return out


def pick(item, *names, default=""):
    flat = flatten(item)
    low = {k.lower(): v for k, v in flat.items()}
    for n in names:
        n = n.lower()
        for k, v in low.items():
            if k == n or k.endswith("." + n):
                if isinstance(v, str) and v.strip(): return v.strip()
                if isinstance(v, (int, float)): return v
    return default


DATE_RX = re.compile(r"(20\d{2})[-./]?(\d{2})[-./]?(\d{2})")
# 사진 경로·등록시각이 기간으로 오인되던 문제 — 그런 필드는 건너뛴다
SKIP = ("photo", "img", "thumbnail", "path", "url", "seo", "reg", "mod", "upd", "cre")


def as_date(v):
    if not isinstance(v, str): return None
    m = DATE_RX.search(v)
    if not m: return None
    y, mo, d = m.groups()
    if not ("2020" <= y <= "2030" and "01" <= mo <= "12" and "01" <= d <= "31"): return None
    return y + "-" + mo + "-" + d


def pick_period(item):
    """기간. 먼저 이름이 맞는 필드를 보고, 없으면 날짜꼴 값을 훑는다."""
    s = pick(item, "startdate", "startDate", "sdate", "fstvlstartdate", "startymd", default="")
    e = pick(item, "enddate", "endDate", "edate", "fstvlenddate", "endymd", default="")
    sd, ed = as_date(str(s)), as_date(str(e))
    if sd: return sd, (ed or sd)
    found = []
    for path, v in flatten(item).items():
        if any(w in path.lower() for w in SKIP): continue
        d = as_date(v)
        if d: found.append(d)
    if not found: return None, None
    found.sort()
    return found[0], found[-1]


def status_of(sd, ed):
    if not sd: return "기간미상"
    e = ed or sd
    if TODAY < sd: return "예정"
    if TODAY > e:  return "종료"
    return "진행중"


def clean_title(t):
    t = unicodedata.normalize("NFKC", str(t or ""))
    t = re.sub(r"제?\s*\d+\s*회", "", t)
    t = re.sub(r"20\d{2}\s*(년도?)?", "", t)
    t = re.sub(r"[()\[\]<>「」『』·,\-~—:!?'\"’“”]", "", t)
    return re.sub(r"\s+", "", t).strip()


# ── 수집 ─────────────────────────────────────────────────
def collect():
    seen, out = set(), []
    for y, m in MONTHS:
        page, got_m = 1, 0
        while page <= 12:
            d = call(y, m, page)
            items = d.get("items") or d.get("list") or d.get("resultList") or []
            if isinstance(d.get("data"), dict):
                items = items or d["data"].get("items") or d["data"].get("list") or []
            if not items: break
            for x in items:
                cid = str(pick(x, "contentsid", "contentsId", "cid", default="")).strip()
                key = cid or clean_title(pick(x, "title", default=""))
                if not key or key in seen: continue
                seen.add(key); out.append(x); got_m += 1
            total = d.get("totalCount") or d.get("total") or 0
            if len(items) < 100: break
            page += 1
            time.sleep(0.5)
        print("   " + str(y) + "-" + str(m).zfill(2) + ": " + str(got_m) + "건 (누적 " + str(len(out)) + ")")
        time.sleep(0.6)
    return out


def normalize(raw):
    out, nodate = [], 0
    for x in raw:
        title = str(pick(x, "title", default="")).strip()
        if not title: continue
        sd, ed = pick_period(x)
        if not sd: nodate += 1
        cid = str(pick(x, "contentsid", "contentsId", "cid", default="")).strip()
        lat = pick(x, "latitude", "lat", default=None)
        lng = pick(x, "longitude", "lng", default=None)
        try: lat = float(lat) if lat not in ("", None) else None
        except Exception: lat = None
        try: lng = float(lng) if lng not in ("", None) else None
        except Exception: lng = None
        out.append({
            "id": cid or clean_title(title),
            "title": title,
            "start": sd, "end": ed or sd,
            "status": status_of(sd, ed),
            "region": str(pick(x, "region2cd.label", "region2", "region1cd.label", default="")).strip(),
            "addr": str(pick(x, "roadaddress", "address", default="")).strip(),
            "lat": lat, "lng": lng,
            "intro": str(pick(x, "introduction", "intro", default="")).strip()[:180],
            "tag": str(pick(x, "tag", "alltag", default="")).strip()[:120],
            "img": str(pick(x, "thumbnailpath", "imgpath", default="")).strip(),
            "phone": str(pick(x, "phoneno", "phone", default="")).strip(),
            "link": ("https://www.visitjeju.net/kr/detail/view?contentsid=" + cid) if cid else "",
            "source": "비짓제주",
        })
    if nodate: print("   ! 기간 없는 항목 " + str(nodate) + "건")
    return out


def merge_seed(api_items):
    """수기 시드는 보조 — API에 아직 없는 행사만 채운다 (유형·주최도 보강)."""
    try:
        seed = json.load(open(SEED, encoding="utf-8"))["items"]
    except Exception:
        print("■ 시드 없음 — API 수집분만 사용"); return api_items

    idx = {}
    for x in api_items:
        k = clean_title(x["title"])
        if k: idx.setdefault(k, x)

    def find(key):
        if key in idx: return idx[key]
        for k, v in idx.items():
            if len(key) >= 5 and (key in k or k in key): return v
        return None

    add, enrich_n = 0, 0
    for s in seed:
        a = find(s["key"])
        if a:                                   # 이미 API에 있다 — 빈 칸만 채운다
            if not a.get("tag") and s.get("kind"): a["tag"] = s["kind"]; enrich_n += 1
            if not a.get("addr") and s.get("place"): a["addr"] = s["place"]
            if not a.get("region") and s.get("region"): a["region"] = s["region"]
            if not a.get("start") and s.get("start"):
                a["start"], a["end"] = s["start"], s["end"]
                a["status"] = status_of(s["start"], s["end"]); enrich_n += 1
            continue
        api_items.append({                      # API에 없는 행사 — 시드에서 가져온다
            "id": s["key"], "title": s["title"],
            "start": s["start"], "end": s["end"],
            "status": status_of(s["start"], s["end"]),
            "region": s.get("region", ""), "addr": s.get("place", ""),
            "lat": None, "lng": None, "intro": "", "tag": s.get("kind", ""),
            "img": "", "phone": "", "link": "", "source": "통합일정",
        })
        add += 1
    print("■ 시드 보완 — API에 없던 행사 " + str(add) + "건 추가 · 빈 칸 보강 " + str(enrich_n) + "건")
    return api_items


def in_range(it):
    s, e = it.get("start"), it.get("end")
    if not s: return True
    return not (e < RANGE_FROM or s > RANGE_TO)


def main():
    print("■ 수집 · " + BASE)
    raw = collect()
    if not raw:
        print("수집 0건 — 중단합니다 (기존 파일 보존)"); return

    if PROBE:
        print("")
        print("[probe] 첫 항목 전체 필드")
        for k, v in sorted(flatten(raw[0]).items()):
            print("   " + k.ljust(34) + " = " + str(v)[:70])
        return

    items = normalize(raw)
    items = merge_seed(items)
    items = [x for x in items if in_range(x)]
    order = {"진행중": 0, "예정": 1, "기간미상": 2, "종료": 3}
    items.sort(key=lambda x: (order.get(x["status"], 9), x.get("start") or "9999"))

    by_status, by_region = {}, {}
    for x in items:
        by_status[x["status"]] = by_status.get(x["status"], 0) + 1
        r = x["region"] or "미상"
        by_region[r] = by_region.get(r, 0) + 1

    os.makedirs("data", exist_ok=True)
    json.dump({"meta": {"updated": NOW.strftime("%Y-%m-%d %H:%M"),
                        "source": "비짓제주 축제와 행사 (제주관광공사) + 2026 통합일정",
                        "range": [RANGE_FROM, RANGE_TO],
                        "count": len(items), "by_status": by_status},
               "items": items},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("")
    print("저장 " + str(len(items)) + "건 · " + str(by_status))
    print("지역: " + str(dict(sorted(by_region.items(), key=lambda x: -x[1])[:12])))
    print("→ " + OUT)


if __name__ == "__main__":
    main()
