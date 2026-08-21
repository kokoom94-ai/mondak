#!/usr/bin/env python3
"""제주특별자치도의회 의안정보 수집 — 국회도서관 지방의정포털(CLIK) Open API.

전략(3단):
  1) ID 자동탐색: 여러 키워드로 bill.do를 조회, 응답행의 RASMBLY_NM에서
     '제주특별자치도의회'를 찾아 RASMBLY_ID 확보.
  2) rasmblyId 정조회: 찾은 ID를 rasmblyId 파라미터로 넣어 제주 의안만 수집.
  3) 폴백 전국스캔: ID를 못 찾으면 여러 페이지를 넓게 훑으며 RASMBLY_NM으로 제주만 필터.

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
KEEP = 150                       # 저장할 최근 의안 수
SCAN_PAGES = 30                  # 폴백 전국스캔 최대 페이지(30*100=3000건 훑음)
PROBE_KEYWORDS = ["제주특별자치도의회", "제주특별자치도", "제주"]
DIAG_ONLY = os.environ.get("COUNCIL_DIAG", "").strip() == "1"  # 진단만 하고 종료

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
    if isinstance(j,list): j = j[0] if j else {}   # bill.do는 [ {...} ] 배열로 감쌀 수 있음
    return j

def dt(v):
    v=str(v or "")
    if len(v)>=8 and v[:8].isdigit() and v[:8]!="19700101":
        return f"{v[:4]}-{v[4:6]}-{v[6:8]}"
    return ""

def rows_of(j):
    lst = j.get("LIST") or []
    out=[]
    for it in lst:
        out.append(it.get("ROW") or it)
    return out

def call(params):
    """단일 호출 → (code, msg, total, rows[])"""
    q={"key":KEY,"type":"json","displayType":"list","listCount":LIST_COUNT}
    q.update(params)
    url=BASE+"?"+urllib.parse.urlencode(q)
    try: j=parse(get(url))
    except Exception as e:
        return "REQFAIL", str(e), "?", []
    if not j: return "PARSEFAIL","",("?"),[]
    return j.get("RESULT_CODE"), j.get("RESULT_MESSAGE"), j.get("TOTAL_COUNT","?"), rows_of(j)

# ── 1단계: 제주 RASMBLY_ID 자동탐색 ──────────────────────────────
def discover_rid():
    for kw in PROBE_KEYWORDS:
        for stype in ("ALL","BI_SJ"):
            code,msg,total,rows = call({"startCount":0,"searchType":stype,"searchKeyword":kw})
            print(f"  [probe kw='{kw}' type={stype}] code={code} total={total} rows={len(rows)}")
            if code!="SUCCESS" or not rows: 
                continue
            # ── 진단: 첫 행의 전체 필드 구조를 그대로 출력 ──
            if rows:
                print("  [진단] 첫 행 전체 필드:", json.dumps(rows[0], ensure_ascii=False)[:600])
                print("  [진단] 필드 키 목록:", list(rows[0].keys()))
            # ── 진단: BI_SJ(제목)에 '제주'가 든 행을 찾아 그 RASMBLY_ID/필드 확인 ──
            for r in rows:
                sj=(r.get("BI_SJ") or "")
                if "제주" in sj:
                    print("  [진단★] 제목에 '제주' 포함 행 발견:")
                    print("         BI_SJ:", sj[:60])
                    print("         RASMBLY_ID:", r.get("RASMBLY_ID"))
                    print("         RASMBLY_NM:", r.get("RASMBLY_NM"))
                    print("         전체:", json.dumps(r, ensure_ascii=False)[:500])
                    break
            for r in rows:
                nm=(r.get("RASMBLY_NM") or "").strip()
                if COUNCIL in nm:
                    rid=(r.get("RASMBLY_ID") or "").strip()
                    if rid:
                        print(f"  ✔ 제주 RASMBLY_ID 발견: {rid} (from kw='{kw}')")
                        return rid
            time.sleep(0.3)
    print("  ✖ 자동탐색으로 제주 ID 못 찾음")
    return None

def norm(r):
    docid=(r.get("DOCID") or "").strip()
    return {
        "t": (r.get("BI_SJ") or "").strip(),
        "kind": (r.get("BI_KND_NM") or "").strip(),
        "status": (r.get("CL_STD_NM") or "").strip(),
        "no": (r.get("BI_NO") or "").strip(),
        "proposer": (r.get("PROPSR") or "").strip(),
        "date": dt(r.get("ITNC_DE")),
        "numpr": (r.get("RASMBLY_NUMPR") or "").strip(),
        "url": "https://clik.nanet.go.kr/potal/search/searchView.do?collection=assemblybill&DOCID="+urllib.parse.quote(docid),
        "_docid": docid,
    }

# ── 2단계: rasmblyId로 제주 의안 정조회 ─────────────────────────
def fetch_by_rid(rid):
    items=[]; seen=set()
    for pg in range(SCAN_PAGES):
        # rasmblyId 파라미터로 직접 필터. searchKeyword는 비워 전체(해당 의회) 최신순.
        code,msg,total,rows = call({"startCount":pg*LIST_COUNT,"rasmblyId":rid,
                                    "searchType":"ALL","searchKeyword":""})
        print(f"  [rid p{pg}] code={code} total={total} rows={len(rows)}")
        if code!="SUCCESS": 
            print(f"  ⚠ rid 조회 오류: {msg}"); break
        if pg==0 and rows:
            print("  ★ 첫 행:", json.dumps(rows[0], ensure_ascii=False)[:400])
        if not rows: break
        added=0
        for r in rows:
            nm=(r.get("RASMBLY_NM") or "").strip()
            # rasmblyId가 무시될 수 있으니 이름으로 한번 더 확인
            if COUNCIL not in nm: continue
            d=norm(r)
            if not d["_docid"] or d["_docid"] in seen: continue
            seen.add(d["_docid"]); items.append(d); added+=1
        if added==0 and pg>0: break     # 제주가 더 안 나오면 종료
        if len(rows)<LIST_COUNT: break
        time.sleep(0.3)
    return items

# ── 3단계(폴백): 전국스캔하며 제주만 필터 ───────────────────────
def fetch_by_scan():
    items=[]; seen=set()
    for pg in range(SCAN_PAGES):
        code,msg,total,rows = call({"startCount":pg*LIST_COUNT,
                                    "searchType":"ALL","searchKeyword":COUNCIL})
        if code!="SUCCESS":
            print(f"  [scan p{pg}] 오류 {msg}"); break
        if not rows: break
        added=0
        for r in rows:
            nm=(r.get("RASMBLY_NM") or "").strip()
            if COUNCIL not in nm: continue
            d=norm(r)
            if not d["_docid"] or d["_docid"] in seen: continue
            seen.add(d["_docid"]); items.append(d); added+=1
        print(f"  [scan p{pg}] rows={len(rows)} 제주누적={len(items)}")
        if len(rows)<LIST_COUNT: break
        time.sleep(0.3)
    return items

def main():
    if not KEY:
        print("CLIK_KEY 미설정 — 지방의정포털 인증키를 Secrets에 등록"); return

    print("[1] 제주 RASMBLY_ID 자동탐색")
    rid = discover_rid()

    items=[]
    if rid:
        print(f"[2] rasmblyId={rid}로 제주 의안 조회")
        items = fetch_by_rid(rid)

    if not items:
        print("[3] 폴백: 전국스캔 필터")
        items = fetch_by_scan()

    if not items:
        print("제주 의안 0건 — API 응답 확인 필요"); return

    # _docid 내부필드 제거
    for x in items: x.pop("_docid", None)
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
    print(f"✅ wrote {len(items)}건 · 상태:{by_status} · 종류:{by_kind}")

if __name__=="__main__": main()
