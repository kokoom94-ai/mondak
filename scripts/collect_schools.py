# -*- coding: utf-8 -*-
"""
제주 초·중·고 학교정보 수집기 (학교알리미 OpenAPI)
출처: 학교알리미 (공공누리 제1유형 출처표시)
"""
import os, sys, json, time, urllib.request, urllib.parse

KEY = os.environ.get("SCHOOLINFO_API_KEY", "").strip()
if not KEY:
    print("SCHOOLINFO_API_KEY 환경변수가 없습니다."); sys.exit(1)

BASE = "https://www.schoolinfo.go.kr/openApi.do"
SIDO = "50"
SGG  = ["50110", "50130"]
KND  = {"02": "초등학교", "03": "중학교", "04": "고등학교",
        "05": "특수·기타", "06": "특수·기타", "07": "특수·기타"}

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "schools.json")

def fetch(params, timeout=25):
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "mondak-collector/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def collect():
    got = {}
    for knd in ["02", "03", "04", "05", "06", "07"]:
        for sgg in SGG:
            p = {"apiKey": KEY, "apiType": "0", "sidoCode": SIDO,
                 "sggCode": sgg, "schulKndCode": knd}
            try:
                d = fetch(p)
            except Exception as e:
                print(f"  ! {knd}/{sgg} 오류: {e}"); continue
            if d.get("resultCode") != "success":
                print(f"  ! {knd}/{sgg} 실패: {d.get('resultMsg')}"); continue
            rows = d.get("list") or []
            for r in rows:
                nm = (r.get("SCHUL_NM") or "").strip()
                if not nm or r.get("ABSCH_YN") == "Y":
                    continue
                site = (r.get("HMPG_ADRES") or "").strip()
                got[nm] = {
                    "code": r.get("SHL_IDF_CD", ""),
                    "schul_code": r.get("SCHUL_CODE", ""),
                    "site": site if (not site or site.startswith("http")) else "http://" + site,
                    "tel": (r.get("USER_TELNO") or "").strip(),
                    "addr": (r.get("SCHUL_RDNMA") or "").strip(),
                    "fond": (r.get("FOND_SC_CODE") or "").strip(),
                    "region": (r.get("ADRCD_NM") or "").replace("제주특별자치도 ", "").strip(),
                    "hs_kind": (r.get("HS_KND_SC_NM") or "").strip(),
                    "lat": r.get("LTTUD"), "lng": r.get("LGTUD"),
                }
            print(f"  {KND.get(knd, knd)}/{sgg}: {len(rows)}건")
            time.sleep(0.4)
    return got

def main():
    db = json.load(open(DATA, encoding="utf-8"))
    items = db["items"]
    print(f"대상 {len(items)}교 · 수집 시작")
    got = collect()
    print(f"\nAPI 수집: {len(got)}교")

    hit = new = 0
    known = {x["name"] for x in items}
    for it in items:
        g = got.get(it["name"])
        if not g: continue
        for k in ("code", "schul_code", "site", "tel", "addr", "fond", "region", "hs_kind", "lat", "lng"):
            if g.get(k) not in (None, ""):
                it[k] = g[k]
        hit += 1
    for nm, g in got.items():
        if nm in known: continue
        lv = "특"
        if "초등학교" in nm: lv = "초"
        elif "중학교" in nm: lv = "중"
        elif "고등학교" in nm: lv = "고"
        LV = {"초": "초등학교", "중": "중학교", "고": "고등학교", "특": "특수·기타"}
        new += 1
        items.append({"id": "sch_new_%03d" % new, "name": nm,
                      "level": LV[lv], "lv": lv,
                      "branch": "분교장" in nm, **g})

    miss = [x["name"] for x in items if not x.get("code")]
    db["meta"]["updated"] = time.strftime("%Y-%m-%d")
    db["meta"]["count"] = len(items)
    json.dump(db, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n갱신 {hit}교 · 신규 {new}교 · 코드 미확보 {len(miss)}교")
    if miss:
        print("  미확보 예:", ", ".join(miss[:10]))

if __name__ == "__main__":
    main()
