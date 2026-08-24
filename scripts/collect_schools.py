# -*- coding: utf-8 -*-
"""
제주 초·중·고 학교정보 수집기 (학교알리미 OpenAPI)
출처: 학교알리미 (공공누리 제1유형 출처표시)

- http / https 를 모두 시도하고, 실패 시 재시도합니다.
- 타임아웃을 짧게 잡아 전체 실행이 오래 걸리지 않게 합니다.
"""
import os, sys, json, time, ssl, urllib.request, urllib.parse, urllib.error

KEY = os.environ.get("SCHOOLINFO_API_KEY", "").strip()
if not KEY:
    print("SCHOOLINFO_API_KEY 환경변수가 없습니다."); sys.exit(1)
print(f"인증키 확인: {KEY[:4]}...{KEY[-4:]} (길이 {len(KEY)})")

HOSTS = [
    "http://www.schoolinfo.go.kr/openApi.do",
    "https://www.schoolinfo.go.kr/openApi.do",
    "http://schoolinfo.go.kr/openApi.do",
]
SIDO = "50"
SGG  = ["50110", "50130"]
KND  = {"02":"초등","03":"중등","04":"고등","05":"특수","06":"그외","07":"각종"}

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "schools.json")

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def try_fetch(params, timeout=12):
    """여러 호스트/프로토콜을 순차 시도"""
    last = None
    for base in HOSTS:
        url = base + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; mondak-collector/1.0)",
            "Accept": "application/json, text/plain, */*",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                txt = r.read().decode("utf-8", "replace")
                return json.loads(txt), base
        except Exception as e:
            last = f"{base.split('//')[0]}// → {e}"
            continue
    raise RuntimeError(last)

def collect():
    got, okbase = {}, None
    for knd in ["02","03","04","05","06","07"]:
        for sgg in SGG:
            p = {"apiKey": KEY, "apiType": "0", "sidoCode": SIDO,
                 "sggCode": sgg, "schulKndCode": knd}
            d = None
            for attempt in (1, 2):
                try:
                    d, okbase = try_fetch(p)
                    break
                except Exception as e:
                    if attempt == 2:
                        print(f"  ! {KND[knd]}/{sgg} 실패: {e}")
                    else:
                        time.sleep(1.5)
            if not d: continue
            if d.get("resultCode") != "success":
                print(f"  ! {KND[knd]}/{sgg} 응답오류: {d.get('resultMsg')}"); continue
            rows = d.get("list") or []
            for r in rows:
                nm = (r.get("SCHUL_NM") or "").strip()
                if not nm or r.get("ABSCH_YN") == "Y": continue
                site = (r.get("HMPG_ADRES") or "").strip()
                got[nm] = {
                    "code": r.get("SHL_IDF_CD",""),
                    "schul_code": r.get("SCHUL_CODE",""),
                    "site": site if (not site or site.startswith("http")) else "http://"+site,
                    "tel": (r.get("USER_TELNO") or "").strip(),
                    "addr": (r.get("SCHUL_RDNMA") or "").strip(),
                    "fond": (r.get("FOND_SC_CODE") or "").strip(),
                    "region": (r.get("ADRCD_NM") or "").replace("제주특별자치도 ","").strip(),
                    "hs_kind": (r.get("HS_KND_SC_NM") or "").strip(),
                    "lat": r.get("LTTUD"), "lng": r.get("LGTUD"),
                }
            print(f"  {KND[knd]}/{sgg}: {len(rows)}건")
            time.sleep(0.4)
    if okbase: print(f"\n접속 성공 URL: {okbase}")
    return got

def main():
    db = json.load(open(DATA, encoding="utf-8"))
    items = db["items"]
    print(f"대상 {len(items)}교 · 수집 시작")
    got = collect()
    print(f"API 수집: {len(got)}교")

    if not got:
        print("\n수집 결과가 없어 기존 파일을 유지합니다.")
        print("→ GitHub 서버에서 학교알리미 접속이 차단된 것으로 보입니다.")
        print("→ 로컬 PC에서 실행하거나, 브라우저로 API를 호출해 결과를 저장해 주세요.")
        sys.exit(0)

    hit = new = 0
    known = {x["name"] for x in items}
    LV = {"초":"초등학교","중":"중학교","고":"고등학교","특":"특수·기타"}
    for it in items:
        g = got.get(it["name"])
        if not g: continue
        for k in ("code","schul_code","site","tel","addr","fond","region","hs_kind","lat","lng"):
            if g.get(k) not in (None,""): it[k] = g[k]
        hit += 1
    for nm, g in got.items():
        if nm in known: continue
        lv = "초" if "초등학교" in nm else "중" if "중학교" in nm else "고" if "고등학교" in nm else "특"
        new += 1
        items.append({"id":"sch_new_%03d"%new, "name":nm, "level":LV[lv], "lv":lv,
                      "branch":"분교장" in nm, **g})

    miss = [x["name"] for x in items if not x.get("code")]
    db["meta"]["updated"] = time.strftime("%Y-%m-%d")
    db["meta"]["count"] = len(items)
    json.dump(db, open(DATA,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n갱신 {hit}교 · 신규 {new}교 · 코드 미확보 {len(miss)}교")

if __name__ == "__main__":
    main()
