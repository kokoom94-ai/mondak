#!/usr/bin/env python3
"""제주특별자치도의회 의안정보 수집 — 국회도서관 지방의정포털(CLIK) Open API.

제주 코드 확정: RASMBLY_ID == "064001"
  · bill.do는 RASMBLY_NM(이름) 필드를 주지 않고 RASMBLY_ID(코드)만 준다.
  · searchKeyword는 제목검색으로만 동작 → '제주특별자치도'로 제목검색 후
    응답행의 RASMBLY_ID=="064001"인 것만 채택.

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
JEJU_RID = "064001"              # ★ 제주특별자치도의회 코드 (확정)
LIST_COUNT = 100
MAX_PAGES = 20                   # 제목검색 '제주특별자치도' 결과를 훑을 최대 페이지
KEEP = 150                       # 저장할 최근 의안 수
# 제목검색 키워드(넓게 잡고 RID로 정밀필터). 제주 의안은 대부분 제목에 '제주' 포함.
SEARCH_KEYWORD = "제주특별자치도"

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
    if isinstance(j,list): j = j[0] if j else {}   # bill.do는 [ {...} ] 배열로 감쌈
    return j

def dt(v):
    v=str(v or "")
    if len(v)>=8 and v[:8].isdigit() and v[:8]!="19700101":
        return f"{v[:4]}-{v[4:6]}-{v[6:8]}"
    return ""

def rows_of(j):
    return [ (it.get("ROW") or it) for it in (j.get("LIST") or []) ]

def call(params):
    q={"key":KEY,"type":"json","displayType":"list","listCount":LIST_COUNT}
    q.update(params)
    url=BASE+"?"+urllib.parse.urlencode(q)
    try: j=parse(get(url))
    except Exception as e:
        return "REQFAIL", str(e), "?", []
    if not j: return "PARSEFAIL","","?",[]
    return j.get("RESULT_CODE"), j.get("RESULT_MESSAGE"), j.get("TOTAL_COUNT","?"), rows_of(j)

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

def main():
    if not KEY:
        print("CLIK_KEY 미설정 — 지방의정포털 인증키를 Secrets에 등록"); return

    items=[]; seen=set(); scanned=0
    for pg in range(MAX_PAGES):
        # 제목검색(BI_SJ)으로 '제주특별자치도'를 넓게 잡고, RASMBLY_ID로 제주만 정밀필터
        code,msg,total,rows = call({"startCount":pg*LIST_COUNT,
                                    "searchType":"BI_SJ","searchKeyword":SEARCH_KEYWORD})
        if code!="SUCCESS":
            print(f"  [p{pg}] 오류 code={code} msg={msg}")
            if pg==0: 
                # 제목검색 실패 시 ALL로 한 번 더 시도
                code,msg,total,rows = call({"startCount":0,"searchType":"ALL","searchKeyword":SEARCH_KEYWORD})
                print(f"  [p0/ALL재시도] code={code} total={total} rows={len(rows)}")
                if code!="SUCCESS": break
            else:
                break
        if pg==0:
            print(f"  [p0] total={total} rows={len(rows)}")
            if rows: print("  ★ 첫 행:", json.dumps(rows[0], ensure_ascii=False)[:300])
        if not rows: break
        scanned += len(rows)
        added=0
        for r in rows:
            rid=(r.get("RASMBLY_ID") or "").strip()
            if rid != JEJU_RID:          # ★ 제주(064001)만
                continue
            d=norm(r)
            if not d["_docid"] or d["_docid"] in seen: continue
            seen.add(d["_docid"]); items.append(d); added+=1
        print(f"  [p{pg}] rows={len(rows)} 제주채택+{added} 누적={len(items)}")
        if len(rows)<LIST_COUNT: break   # 마지막 페이지
        time.sleep(0.3)

    if not items:
        print(f"제주 의안 0건 (훑은 행={scanned}) — RASMBLY_ID={JEJU_RID} 확인 필요"); return

    for x in items: x.pop("_docid", None)
    items.sort(key=lambda x: x["date"], reverse=True)
    items = items[:KEEP]

    by_status={}; by_kind={}
    for x in items:
        if x["status"]: by_status[x["status"]]=by_status.get(x["status"],0)+1
        if x["kind"]: by_kind[x["kind"]]=by_kind.get(x["kind"],0)+1

    out={"meta":{"collected_at":NOW.strftime("%Y-%m-%d %H:%M KST"),
        "council":COUNCIL,"rasmbly_id":JEJU_RID,"count":len(items),
        "by_status":by_status,"by_kind":by_kind,
        "source":"국회도서관 CLIK 공공데이터"},
        "items":items}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding="utf-8")
    print(f"✅ wrote {len(items)}건 · 상태:{by_status} · 종류:{by_kind}")

if __name__=="__main__": main()
