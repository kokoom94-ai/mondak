# -*- coding: utf-8 -*-
"""제주행사모음 — 비짓제주 관광정보 OPEN API에서 축제·행사를 받아 data/festival.json으로.

키는 코드에 넣지 않는다. 환경변수 VISITJEJU_KEY(=GitHub Secret)로만 받는다.

이 수집기는 '스스로 찾아내는' 방식이다.
  · 축제 카테고리 코드(c1~c9 중 무엇인지)를 라벨로 판별한다
  · 날짜 필드 이름을 모르므로, 값이 날짜꼴인 필드를 전부 훑어 시작·종료일을 뽑는다
API 규격이 조금 달라도 로그에 무엇을 봤는지 남기므로 다음 실행에서 바로 고칠 수 있다.
"""
import json, os, re, ssl, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

KEY  = os.environ.get("VISITJEJU_KEY", "").strip()
BASE = "https://api.visitjeju.net/vsjApi/contents/searchList"
OUT  = os.path.join("data", "festival.json")

KST  = timezone(timedelta(hours=9))
NOW  = datetime.now(KST)
TODAY = NOW.strftime("%Y-%m-%d")

# 표시 범위 — 2026-01-01 ~ 2027-01-31 (사용자 확정)
RANGE_FROM = "2026-01-01"
RANGE_TO   = "2027-01-31"

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA  = "Mozilla/5.0 (compatible; MondakBot/1.0; +https://kokoom94-ai.github.io/mondak/)"

PROBE = "--probe" in sys.argv      # 탐색 결과만 출력하고 저장하지 않음


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def call(category, page=1):
    q = {"apiKey": KEY, "locale": "kr", "page": page, "category": category}
    try:
        return json.loads(fetch(BASE + "?" + urllib.parse.urlencode(q)))
    except Exception as e:
        print(f"   ! {category} p{page}: {e}")
        return {}


# ── 날짜 뽑기 ────────────────────────────────────────────
DATE_RX = re.compile(r"(20\d{2})[-./]?(\d{2})[-./]?(\d{2})")

def as_date(v):
    """문자열에서 YYYY-MM-DD를 뽑는다. 20260801 / 2026.08.01 / 2026-08-01 모두 처리."""
    if not isinstance(v, str): return None
    m = DATE_RX.search(v)
    if not m: return None
    y, mo, d = m.groups()
    if not ("2020" <= y <= "2030" and "01" <= mo <= "12" and "01" <= d <= "31"): return None
    return f"{y}-{mo}-{d}"


def flatten(o, prefix=""):
    """중첩 dict를 '경로: 값' 쌍으로 편다. API가 {value,label} 꼴을 많이 쓴다."""
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(o, list):
        for i, v in enumerate(o[:3]):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = o
    return out


def pick_dates(item):
    """항목 전체를 훑어 날짜꼴 값을 모으고, 가장 이른/늦은 것을 기간으로 삼는다.
    필드명이 startDate·sDate·fstvlStartDate 무엇이든 걸린다."""
    flat = flatten(item)
    found = []
    for path, v in flat.items():
        d = as_date(v)
        if d: found.append((path, d))
    if not found: return None, None, []
    ds = sorted(d for _, d in found)
    return ds[0], ds[-1], found


def pick(item, *names, default=""):
    flat = flatten(item)
    low = {k.lower(): v for k, v in flat.items()}
    for n in names:
        for k, v in low.items():
            if k == n.lower() or k.endswith("." + n.lower()):
                if isinstance(v, str) and v.strip(): return v.strip()
                if isinstance(v, (int, float)): return v
    return default


def status_of(sd, ed):
    """진행 중 / 예정 / 종료"""
    if not sd: return "미정"
    e = ed or sd
    if TODAY < sd:  return "예정"
    if TODAY > e:   return "종료"
    return "진행중"


# ── 1단계 · 축제 카테고리 찾기 ───────────────────────────
def find_festival_category():
    """c1~c9를 한 페이지씩 불러 라벨을 본다. '축제'나 '행사'가 들어간 코드를 고른다."""
    print("■ 카테고리 탐색")
    hit, seen = None, {}
    for i in range(1, 10):
        code = f"c{i}"
        d = call(code, 1)
        items = d.get("items") or []
        if not items:
            print(f"   {code}: (없음)"); time.sleep(0.3); continue
        labels = {}
        for x in items[:20]:
            lb = pick(x, "label", "contentscd.label", "cl", default="")
            if lb: labels[lb] = labels.get(lb, 0) + 1
        top = max(labels, key=labels.get) if labels else "?"
        total = d.get("totalCount") or d.get("resultCount") or len(items)
        seen[code] = (top, total)
        print(f"   {code}: {top} · 총 {total}건")
        if hit is None and ("축제" in top or "행사" in top or "이벤트" in top):
            hit = code
        time.sleep(0.3)
    if hit:
        print(f"   → 축제 카테고리: {hit} ({seen[hit][0]})")
    else:
        print("   → 라벨로 못 찾음. 날짜 필드가 있는 카테고리로 재판정한다")
        for code, (lb, _) in seen.items():
            d = call(code, 1)
            for x in (d.get("items") or [])[:5]:
                sd, ed, _f = pick_dates(x)
                if sd and ed and sd != ed:      # 기간이 있는 콘텐츠 = 행사
                    hit = code; print(f"   → {code}({lb})에 기간 필드 발견 — 축제로 판단"); break
            if hit: break
            time.sleep(0.3)
    return hit, seen


# ── 2단계 · 수집 ─────────────────────────────────────────
def collect(cat):
    print(f"■ 수집 · category={cat}")
    items, page, seen_ids = [], 1, set()
    while page <= 60:
        d = call(cat, page)
        got = d.get("items") or []
        if not got: break
        for x in got:
            cid = pick(x, "contentsid", "contentsId", "cid", default="")
            if cid and cid in seen_ids: continue
            if cid: seen_ids.add(cid)
            items.append(x)
        pc = d.get("pageCount") or 0
        print(f"   p{page}: {len(got)}건 (누적 {len(items)})")
        if pc and page >= pc: break
        page += 1
        time.sleep(0.35)
    return items


def normalize(raw):
    """화면이 쓰는 모양으로 정리."""
    out, no_date = [], 0
    for x in raw:
        title = str(pick(x, "title", default="")).strip()
        if not title: continue
        sd, ed, found = pick_dates(x)
        if not sd: no_date += 1
        region = str(pick(x, "region2cd.label", "region2", "region1cd.label", default="")).strip()
        addr   = str(pick(x, "roadaddress", "address", default="")).strip()
        lat    = pick(x, "latitude", "lat", default=None)
        lng    = pick(x, "longitude", "lng", default=None)
        try: lat = float(lat) if lat not in ("", None) else None
        except Exception: lat = None
        try: lng = float(lng) if lng not in ("", None) else None
        except Exception: lng = None
        cid = str(pick(x, "contentsid", "contentsId", "cid", default="")).strip()
        out.append({
            "id": cid or title,
            "title": title,
            "start": sd, "end": ed or sd,
            "status": status_of(sd, ed),
            "region": region,
            "addr": addr,
            "lat": lat, "lng": lng,
            "intro": str(pick(x, "introduction", "intro", default="")).strip()[:180],
            "tag": str(pick(x, "tag", "tags", default="")).strip()[:120],
            "img": str(pick(x, "thumbnailpath", "photoid", "imgpath", default="")).strip(),
            "phone": str(pick(x, "phoneno", "phone", default="")).strip(),
            "link": f"https://www.visitjeju.net/kr/detail/view?contentsid={cid}" if cid else "",
            "source": "비짓제주",
        })
    if no_date:
        print(f"   ! 날짜를 못 찾은 항목 {no_date}건 — 기간 미정으로 둔다")
    return out


def in_range(it):
    s, e = it.get("start"), it.get("end")
    if not s: return True                      # 기간 미정은 일단 남긴다
    return not (e < RANGE_FROM or s > RANGE_TO)


def main():
    if not KEY:
        print("VISITJEJU_KEY 미설정 — GitHub Secret에 등록하세요"); return
    cat, seen = find_festival_category()
    if not cat:
        print("축제 카테고리를 찾지 못했습니다. 위 라벨 목록을 보고 코드를 지정해 주세요."); return
    if PROBE:
        print("\n[probe] 저장하지 않고 종료합니다.")
        d = call(cat, 1)
        sample = (d.get("items") or [None])[0]
        if sample:
            print("\n샘플 항목의 전체 필드:")
            for k, v in sorted(flatten(sample).items()):
                print(f"   {k} = {str(v)[:70]}")
        return

    raw = collect(cat)
    items = normalize(raw)
    items = [x for x in items if in_range(x)]
    order = {"진행중": 0, "예정": 1, "미정": 2, "종료": 3}
    items.sort(key=lambda x: (order.get(x["status"], 9), x.get("start") or "9999"))

    by_status, by_region = {}, {}
    for x in items:
        by_status[x["status"]] = by_status.get(x["status"], 0) + 1
        r = x["region"] or "미상"
        by_region[r] = by_region.get(r, 0) + 1

    os.makedirs("data", exist_ok=True)
    json.dump({"meta": {"updated": NOW.strftime("%Y-%m-%d %H:%M"),
                        "source": "비짓제주 관광정보 OPEN API (제주관광공사)",
                        "category": cat, "range": [RANGE_FROM, RANGE_TO],
                        "count": len(items), "by_status": by_status},
               "items": items},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\n저장 {len(items)}건 · {by_status}")
    print(f"지역: {dict(sorted(by_region.items(), key=lambda x: -x[1])[:12])}")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
