# -*- coding: utf-8 -*-
"""제주 읍면동 인구 — 제주특별자치도 인구빅데이터에서 받아 data/population.json으로.

경로: www.jeju.go.kr/population/chart/getJuminHDongRegion  (인구현황 화면이 쓰는 것)
키는 필요 없다. hdong=true 로 읍면동 단위를 받는다.

응답 필드 이름을 확신할 수 없으므로 스스로 찾아낸다.
  · 지역명처럼 보이는 문자열 필드 → 읍면동명
  · 숫자 필드 중 가장 큰 값 → 총인구, 그다음 → 세대수·외국인
필드가 어긋나도 로그에 무엇을 봤는지 남기므로 다음 실행에서 바로 고칠 수 있다.
"""
import json, os, re, ssl, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://www.jeju.go.kr/population/chart/getJuminHDongRegion"
PAGE = "https://www.jeju.go.kr/livingpopulation/jeju/state.htm"
OUT  = os.path.join("data", "population.json")

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
PROBE = "--probe" in sys.argv

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA  = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

import http.cookiejar
JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR),
                                     urllib.request.HTTPSHandler(context=CTX))
HEADERS = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
           "Accept-Language": "ko-KR,ko;q=0.9", "Referer": PAGE,
           "X-Requested-With": "XMLHttpRequest"}

# 읍면동 → 비짓제주 축제 지역 (화면의 지역 구분과 같은 체계)
REGION_OF = [
    ("애월", "애월"), ("한림", "한림"), ("한경", "한경"), ("조천", "조천"),
    ("구좌", "구좌"), ("우도", "우도"), ("추자", "추자도"),
    ("성산", "성산"), ("대정", "대정"), ("안덕", "안덕"), ("남원", "남원"), ("표선", "표선"),
    ("중문", "중문"), ("예래", "중문"),
]
SEOGWI_DONG = ("송산", "정방", "중앙", "천지", "효돈", "영천", "동홍", "서홍", "대륜", "대천")


def region_of(name):
    n = str(name or "")
    for key, reg in REGION_OF:
        if key in n: return reg
    if any(d in n for d in SEOGWI_DONG): return "서귀포시내"
    if n.endswith("동") or "동" in n: return "제주시내"   # 남은 동지역은 제주시
    return ""


def warmup():
    try:
        req = urllib.request.Request(PAGE, headers={
            "User-Agent": UA, "Accept": "text/html", "Accept-Language": "ko-KR,ko;q=0.9"})
        with OPENER.open(req, timeout=25) as r:
            r.read(2048)
        print("■ 세션 준비 — 쿠키 " + str(len(list(JAR))) + "개")
    except Exception as e:
        print("■ 세션 준비 실패(계속): " + str(e))


RAW_SHOWN = [False]

def call(month, show=False):
    q = [("month", month), ("gender[]", "M"), ("gender[]", "F"),
         ("destHdongNm", ""), ("inflowCd", ""), ("hdong", "true")]
    url = BASE + "?" + urllib.parse.urlencode(q)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with OPENER.open(req, timeout=25) as r:
            txt = r.read().decode("utf-8", "replace")
    except Exception as e:
        print("   ! " + month + ": " + str(e))
        return None
    if (show or PROBE) and not RAW_SHOWN[0]:
        RAW_SHOWN[0] = True
        print("")
        print("── 응답 원문 앞 1200자 (" + month + ", " + str(len(txt)) + "자) ──")
        print(txt[:1200].replace("\n", " "))
        print("──────────")
    try:
        return json.loads(txt)
    except Exception as e:
        print("   ! " + month + ": JSON 아님 (" + str(e) + ")")
        return {"__raw__": txt}


def rows_of(payload):
    """응답에서 목록을 찾아낸다. 감싸는 이름이 무엇이든 가장 큰 dict 배열을 쓴다."""
    if payload is None: return []
    if isinstance(payload, list): return payload
    best = []
    def walk(o):
        nonlocal best
        if isinstance(o, list):
            if o and isinstance(o[0], dict) and len(o) > len(best): best = o
            for v in o[:5]: walk(v)
        elif isinstance(o, dict):
            for v in o.values(): walk(v)
    walk(payload)
    return best


def to_int(v):
    if isinstance(v, (int, float)): return int(v)
    if isinstance(v, str):
        t = v.replace(",", "").strip()
        if re.fullmatch(r"-?\d+", t): return int(t)
    return None


def parse(rows):
    """지역명과 숫자들을 뽑는다."""
    out = []
    for r in rows:
        if not isinstance(r, dict): continue
        name = ""
        for k, v in r.items():
            if isinstance(v, str) and re.search(r"(동|읍|면)$", v.strip()):
                name = v.strip(); break
        if not name:
            for k, v in r.items():
                if isinstance(v, str) and 2 <= len(v) <= 12 and not v.replace(",", "").isdigit():
                    name = v.strip(); break
        if not name: continue
        nums = {}
        for k, v in r.items():
            n = to_int(v)
            if n is not None and n >= 0: nums[k] = n
        if not nums: continue
        # 총인구 = 가장 큰 값. 세대수·외국인은 이름으로 잡고, 없으면 비워 둔다.
        total_k = max(nums, key=nums.get)
        def by(*words):
            for k in nums:
                kl = k.lower()
                if any(w in kl for w in words): return nums[k]
            return None
        out.append({"name": name, "region": region_of(name),
                    "total": nums[total_k],
                    "house": by("house", "hous", "세대", "gagu", "hh"),
                    "foreign": by("foreign", "forgn", "외국"),
                    "male": by("male", "man", "_m"), "female": by("female", "woman", "_f")})
    return out


def main():
    warmup()
    # 최신 월부터 거슬러 찾는다 (플랫폼이 한두 달 늦게 올린다)
    months = [(NOW - timedelta(days=30 * i)).strftime("%Y%m") for i in range(0, 8)]
    data, used = [], ""
    for i, mm in enumerate(months):
        p = call(mm, show=(i == 0))
        if isinstance(p, dict) and i == 0:
            print("   응답 최상위 키: " + str(list(p.keys())[:12]))
            for k, v in list(p.items())[:12]:
                kind = type(v).__name__
                size = (len(v) if isinstance(v, (list, dict, str)) else "")
                print("      " + str(k) + " : " + kind + " " + str(size))
        rows = rows_of(p)
        got = parse(rows)
        print("   " + mm + ": 목록 " + str(len(rows)) + "건 · 해석 " + str(len(got)) + "건")
        if PROBE and rows:
            print("")
            print("[probe] 첫 행 원문")
            print(json.dumps(rows[0], ensure_ascii=False, indent=1)[:1200])
            return
        if len(got) >= 20:
            data, used = got, mm; break
        time.sleep(0.5)

    if not data:
        print("인구 데이터를 얻지 못했습니다 — 기존 파일 보존"); return

    by_region = {}
    for x in data:
        r = x["region"]
        if not r: continue
        b = by_region.setdefault(r, {"total": 0, "house": 0, "foreign": 0, "emd": 0})
        b["total"] += x["total"] or 0
        b["house"] += x["house"] or 0
        b["foreign"] += x["foreign"] or 0
        b["emd"] += 1

    total_all = sum(v["total"] for v in by_region.values())
    os.makedirs("data", exist_ok=True)
    json.dump({"meta": {"updated": NOW.strftime("%Y-%m-%d %H:%M"), "month": used,
                        "source": "제주특별자치도 인구빅데이터 (주민등록인구 및 등록외국인)",
                        "total": total_all, "emd_count": len(data)},
               "regions": by_region, "emd": data},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("")
    print("기준월 " + used + " · 읍면동 " + str(len(data)) + "곳 · 총 " + format(total_all, ",") + "명")
    print("지역: " + str({k: v["total"] for k, v in sorted(by_region.items(), key=lambda x: -x[1]["total"])}))
    print("→ " + OUT)


if __name__ == "__main__":
    main()
