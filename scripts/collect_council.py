#!/usr/bin/env python3
"""제주특별자치도의회 의안정보 수집 — 국회도서관 지방의정포털(CLIK) Open API.
bill.do를 searchType=RASMBLY_NM(지방의회명)으로 조회 → 제주 의안 최신순 → data/council.json
Secret: CLIK_KEY (지방의정포털 인증키)
출처표시: '국회도서관 CLIK 공공데이터' (약관 제10조 준수)
"""
import json, os, ssl, urllib.parse, urllib.request, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9)); NOW = datetime.now(KST)
OUT = Path(__file__).resolve().parent.parent / "data" / "council.json"
KEY = os.environ.get("CLIK_KEY", "").strip()
BASE = "https://clik.nanet.go.kr/openapi/bill.do"
COUNCIL = "제주특별자치도의회"
LIST_COUNT = 100
MAX_PAGES = 3          # 최근 의안 위주 (100*3=최대 300건 훑음)
KEEP = 120             # 저장할 최근 의안 수
SEARCH_TYPES = ["RASMBLY_NM", "ALL"]  # RASMBLY_NM 우선, 안되면 ALL로 폴백

def get(url, tries=3):
    ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
    last=None
    for i in range(tries):
        try:
            raw=urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (mondak)"}),timeout=25,context=ctx).read()
            return raw.decode("utf-8","ignore")
        except Exception as e:
            last=e; time.sleep(2)
    raise last

def parse(txt):
    try: j=json.loads(txt)
    except Exception: return None
    if isinstance(j,list): j = j[0] if j else {}   # bill.do는 [ {...} ] 배열로 감싸옴
    return j

def dt(v):
    v=str(v or "")
    if len(v)>=8 and v[:8].isdigit() and v[:8]!="19700101":
        return f"{v[:4]}-{v[4:6]}-{v[6:8]}"
    return ""

def fetch_pages(stype):
    """한 searchType으로 페이지 순회. (items, rasmbly_id, ok) 반환"""
    items=[]; seen=set(); rid=None; ok=False; dbg=True
    for pg in range(MAX_PAGES):
        q={"key":KEY,"type":"json","displayType":"list","startCount":pg*LIST_COUNT,
           "listCount":LIST_COUNT,"searchType":stype,"searchKeyword":COUNCIL}
        url=BASE+"?"+urllib.parse.urlencode(q)
        try: j=parse(get(url))
        except Exception as e:
            print(f"  [{stype}] p{pg} 요청 실패:", e); break
        if not j:
            print(f"  [{stype}] p{pg} 파싱 실패"); break
        code=j.get("RESULT_CODE"); msg=j.get("RESULT_MESSAGE")
        total=j.get("TOTAL_COUNT","?"); lst=j.get("LIST") or []
        print(f"  [{stype}] p{pg}: code={code} total={total} rows={len(lst)}")
        if code!="SUCCESS":
            print(f"  ⚠ [{stype}] 오류: {msg}"); break
        ok=True
        if dbg and lst:
            print("  ★ 첫 행:", json.dumps(lst[0], ensure_ascii=False)[:400]); dbg=False
        if not lst: break
        for it in lst:
            r=it.get("ROW") or it
            nm=(r.get("RASMBLY_NM") or "").strip()
            if COUNCIL not in nm: continue          # 제주도의회만 정확히
            if not rid: rid=r.get("RASMBLY_ID")
            docid=(r.get("DOCID") or "").strip()
            if not docid or docid in seen: continue
            seen.add(docid)
            items.append({
                "t": (r.get("BI_SJ") or "").strip(),
                "kind": (r.get("BI_KND_NM") or "").strip(),
                "status": (r.get("CL_STD_NM") or "").strip(),
                "no": (r.get("BI_NO") or "").strip(),
                "proposer": (r.get("PROPSR") or "").strip(),
                "date": dt(r.get("ITNC_DE")),
                "numpr": (r.get("RASMBLY_NUMPR") or "").strip(),
                "url": "https://clik.nanet.go.kr/potal/search/searchView.do?collection=assemblybill&DOCID="+urllib.parse.quote(docid),
            })
        time.sleep(0.3)
        if len(lst)<LIST_COUNT: break
    return items, rid, ok

def main():
    if not KEY:
        print("CLIK_KEY 미설정 — 지방의정포털 인증키를 Secrets에 등록"); return
    items=[]; rid=None
    for stype in SEARCH_TYPES:
        items, rid, ok = fetch_pages(stype)
        if items:                       # 이 searchType으로 제주 의안을 얻었으면 끝
            print(f"  → searchType={stype} 성공 ({len(items)}건)")
            break
        if not ok:                      # 오류로 실패했으면 다음 searchType 시도
            continue

    if not items:
        print("제주 의안 0건 — 위 로그의 code/오류 확인 필요"); return

    items.sort(key=lambda x: x["date"], reverse=True)
    items = items[:KEEP]

    by_status={}; by_kind={}
    for x in items:
        if x["status"]: by_status[x["status"]]=by_status.get(x["status"],0)+1
        if x["kind"]: by_kind[x["kind"]]=by_kind.get(x["kind"],0)+1

    out={"meta":{"collected_at":NOW.strftime("%Y-%m-%d %H:%M KST"),
        "council":COUNCIL,"rasmbly_id":rid,"count":len(items),
        "by_status":by_status,"by_kind":by_kind,
        "source":"국회도서관 CLIK 공공데이터"},
        "items":items}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding="utf-8")
    print(f"wrote {len(items)}건 · 상태:{by_status} · 종류:{by_kind}")

if __name__=="__main__": main()
