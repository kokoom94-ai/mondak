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

# 제주 43개 읍면동 — destHdongNm 파라미터에 하나씩 넣어 조회한다.
# (인구빅데이터는 목록을 한 번에 주지 않고 읍면동을 지정해 묻는 방식이다)
HDONG = [
 # 제주시 읍면
 "한림읍","애월읍","구좌읍","조천읍","한경면","추자면","우도면",
 # 제주시 동
 "일도1동","일도2동","이도1동","이도2동","삼도1동","삼도2동","용담1동","용담2동",
 "건입동","화북동","삼양동","봉개동","아라동","오라동","연동","노형동",
 "외도동","이호동","도두동",
 # 서귀포시 읍면
 "대정읍","남원읍","성산읍","안덕면","표선면",
 # 서귀포시 동
 "송산동","정방동","중앙동","천지동","효돈동","영천동","동홍동","서홍동",
 "대륜동","대천동","중문동","예래동",
]

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
SUMMARY = [None]
txt_cache = []
GENDER = "https://www.jeju.go.kr/population/chart/getJuminHDongGender"

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


def call_hdong(month, name, show=False):
    """읍면동 하나의 인구를 조회한다."""
    q = [("month", month), ("gender[]", "M"), ("gender[]", "F"),
         ("destHdongNm", name), ("inflowCd", ""), ("hdong", "true")]
    url = GENDER + "?" + urllib.parse.urlencode(q)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with OPENER.open(req, timeout=25) as r:
            txt = r.read().decode("utf-8", "replace")
    except Exception as e:
        print("   ! " + name + ": " + str(e))
        return None
    if show:
        print("")
        print("── " + name + " 응답 원문 (" + str(len(txt)) + "자) ──")
        print(txt[:900].replace("\n", " "))
        print("──────────")
    try:
        return json.loads(txt)
    except Exception:
        return None


def flat_nums(o, prefix=""):
    """중첩 구조를 펴서 숫자 필드만 모은다."""
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flat_nums(v, prefix + "." + k if prefix else k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            out.update(flat_nums(v, prefix + "[" + str(i) + "]"))
    else:
        n = to_int(o)
        if n is not None: out[prefix] = n
    return out


# 연월(202606)·연도(2026) 같은 값이 인구로 잘못 잡히던 문제를 막는다.
# 실측: 43곳 전부 total=202606 으로 찍혔다 — month 필드를 인구로 오인한 것이다.
def _is_ym(v):
    if not isinstance(v, int): return False
    s = str(v)
    if len(s) == 6 and s[:2] == "20" and "01" <= s[4:6] <= "12": return True   # 202606
    if len(s) == 4 and 1900 <= v <= 2100: return True                          # 2026
    return False

BAD_KEY = ("ym", "month", "mm", "year", "yyyy", "date", "dt", "prev", "curr",
           "code", "cd", "id", "seq", "idx", "rank", "no")


def pick_pop(payload):
    """한 읍면동 응답에서 총인구·세대수·외국인을 뽑는다.

    실제 응답 구조(확인 완료):
      { "prevYm":..., "currYm":...,
        "M":{"total":13094,"totalFo":2815,"totalLocal":10279,...},   남성
        "F":{"total":10734,...},                                     여성
        "TOTAL":{"total":23828,"totalFo":3829,"totalLocal":19999,...} 합계 }
    TOTAL을 그대로 쓴다. 없을 때만 아래의 자동 탐색으로 넘어간다.
    """
    if isinstance(payload, dict):
        t = payload.get("TOTAL") or payload.get("total") if isinstance(payload.get("TOTAL"), dict) else payload.get("TOTAL")
        if isinstance(t, dict):
            tot = to_int(t.get("total"))
            if tot:
                m = payload.get("M") if isinstance(payload.get("M"), dict) else {}
                f = payload.get("F") if isinstance(payload.get("F"), dict) else {}
                return {"total": tot,
                        "house": to_int(t.get("totalHouse")) or 0,
                        "foreign": to_int(t.get("totalFo")) or 0,
                        "local": to_int(t.get("totalLocal")) or 0,
                        "male": to_int(m.get("total")) or 0,
                        "female": to_int(f.get("total")) or 0}
    if not isinstance(payload, (dict, list)): return None
    raw = flat_nums(payload)
    # 연월·코드 계열 필드와 연월처럼 생긴 값은 후보에서 뺀다
    nums = {k: v for k, v in raw.items()
            if not any(w in k.lower() for w in BAD_KEY) and not _is_ym(v)}
    if not nums: return None

    def by(*words):
        best = None
        for k, v in nums.items():
            kl = k.lower()
            if any(w in kl for w in words):
                if best is None or v > best: best = v
        return best

    # 'femaleCnt' 안에 'male'이 들어 있어 남성 값으로 잘못 잡히던 문제 — 여성을 먼저 가른다
    def by_ex(words, exclude=()):
        best = None
        for k, v in nums.items():
            kl = k.lower()
            if any(w in kl for w in exclude): continue
            if any(w in kl for w in words):
                if best is None or v > best: best = v
        return best
    female = by_ex(("female", "woman", "여성", "_f"))
    male   = by_ex(("male", "man", "남성", "_m"), exclude=("female", "woman", "여성"))
    forgn  = by("foreign", "forgn", "외국", "totalfo", "fo")
    house  = by("house", "hous", "hh", "gagu", "세대")
    local  = by("local", "jumin", "주민")
    total  = by("total") or by("sum", "pop", "cnt")

    # 남/여가 있으면 그 합이 가장 믿을 만하다
    if male and female: total = male + female
    # 그래도 없으면 주민등록 + 외국인
    if not total and local: total = local + (forgn or 0)
    # 최후 수단 — 남은 값 중 최댓값 (외국인·세대수보다 커야 인구다)
    if not total:
        cand = [v for v in nums.values() if v > max(forgn or 0, house or 0)]
        total = max(cand) if cand else None
    if not total: return None
    return {"total": total, "house": house or 0, "foreign": forgn or 0,
            "male": male or 0, "female": female or 0}


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


def summary_of(p):
    """읍면동 목록이 아니라 도 전체 요약만 올 때 — 그것도 쓴다."""
    if not isinstance(p, dict): return None
    t = to_int(p.get("total"))
    if not t: return None
    return {"total": t,
            "house": to_int(p.get("totalHouse")) or 0,
            "foreign": to_int(p.get("totalFo")) or 0,
            "local": to_int(p.get("totalLocal")) or 0,
            "mom": to_int(p.get("totalMom")) or 0,
            "month": str(p.get("currYm") or "")}


def main():
    warmup()
    # 1) 집계가 끝난 최신 월 찾기 (요약 조회로 빠르게 판별)
    months = [(NOW - timedelta(days=30 * i)).strftime("%Y%m") for i in range(0, 8)]
    used = ""
    for mm in months:
        sm = summary_of(call(mm))
        if sm and sm["total"]:
            used = mm
            print("■ 기준월 " + mm + " · 도 전체 " + format(sm["total"], ",") + "명")
            SUMMARY[0] = sm
            break
        time.sleep(0.3)
    if not used:
        print("집계된 월을 찾지 못했습니다 — 기존 파일 보존"); return

    # 2) 읍면동 43곳을 하나씩 조회
    print("■ 읍면동 조회 — " + str(len(HDONG)) + "곳")
    data, fail = [], []
    for i, name in enumerate(HDONG, 1):
        p = call_hdong(used, name, show=(i <= 2))
        v = pick_pop(p)
        if not v:
            fail.append(name)
        else:
            data.append({"name": name, "region": region_of(name), **v})
        if i % 10 == 0:
            print("   " + str(i) + "/" + str(len(HDONG)) + " · 확보 " + str(len(data)))
        time.sleep(0.25)
    if fail:
        print("   ! 값을 못 얻은 곳 " + str(len(fail)) + ": " + ", ".join(fail[:8]))

    if not data:
        print("읍면동 인구를 얻지 못했습니다 — 기존 파일 보존"); return

    # 온전성 검사 — 값이 다 같거나 도 전체와 크게 어긋나면 저장하지 않는다
    vals = [x["total"] for x in data]
    ref = (SUMMARY[0] or {}).get("total") or 0
    ssum = sum(vals)
    if len(set(vals)) <= 2:
        print("!! 읍면동 인구가 거의 모두 같은 값입니다 (" + str(vals[0]) + ") — 잘못 읽은 것으로 보고 저장하지 않습니다")
        return
    if ref and not (0.7 * ref <= ssum <= 1.3 * ref):
        print("!! 합계 " + format(ssum, ",") + "명이 도 전체 " + format(ref, ",") + "명과 크게 다릅니다 — 저장하지 않습니다")
        print("   위의 응답 원문을 확인해 주세요.")
        return

    # 3) 지역 단위로 합산
    by_region = {}
    for x in data:
        r = x["region"]
        if not r: continue
        b = by_region.setdefault(r, {"total": 0, "house": 0, "foreign": 0, "local": 0, "emd": 0})
        b["total"] += x["total"]; b["house"] += x["house"]
        b["foreign"] += x["foreign"]; b["local"] += x.get("local", 0); b["emd"] += 1

    total_all = sum(v["total"] for v in by_region.values())
    os.makedirs("data", exist_ok=True)
    json.dump({"meta": {"updated": NOW.strftime("%Y-%m-%d %H:%M"), "month": used,
                        "source": "제주특별자치도 인구빅데이터 (주민등록인구 및 등록외국인)",
                        "total": total_all, "emd_count": len(data)},
               "regions": by_region, "total": SUMMARY[0], "emd": data},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("")
    print("기준월 " + used + " · 읍면동 " + str(len(data)) + "곳 · 합계 " + format(total_all, ",") + "명")
    for k, v in sorted(by_region.items(), key=lambda x: -x[1]["total"]):
        print("  " + k.ljust(7) + " " + format(v["total"], ">9,") + "명 (" + str(v["emd"]) + "개)")
    print("→ " + OUT)


if __name__ == "__main__":
    main()
