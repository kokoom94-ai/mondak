# -*- coding: utf-8 -*-
"""제주도청 고시/공고 수집기 — data/jeju_notice.json

왜 필요한가
  히트펌프 보급사업처럼 도청이 직접 내는 사업은 정부24 API에 없어서
  챗봇이 "모른다"고 답했다. 도청 고시/공고 목록에는 올라와 있다.

확인된 사실 (실제 응답으로 확인, 2026-08-31)
  · 목록  https://www.jeju.go.kr/news/news/law/jeju.htm — 값 없이도 서버가 10건을 그려 준다
  · 인코딩 UTF-8, 표 구조. 열 = 공고번호 / 제목 / 부서 / 날짜 / 조회수
  · 각 행에 onclick="viewData('67621','A')" — 앞이 글번호(sno), 뒤가 구분(gosiGbn)
  · 상세는 브라우저가 폼으로 넘어간다:
      /citynet/jsp/sap/SAPGosiBizProcess.do?command=searchDetail&flag=gosiGL&svp=Y&sido=&sno=..&gosiGbn=..
  · 그 주소로 서버 밖에서 바로 POST 하면 오류 페이지를 준다 (세션 검사)

그래서 이렇게 만든다
  · 1페이지는 확실히 되므로 그것을 뼈대로 삼는다.
  · 페이지 넘김은 실행할 때 여러 방식을 실제로 시험해 보고, 되는 것이 있으면 그것으로 더 긁는다.
    되는 게 없으면 1페이지만 가져오고 조용히 넘어간다 — 하루 두 번 돌며 쌓이므로
    시간이 지나면 목록이 채워진다. (issue 수집기와 같은 누적 방식)
  · 이전 결과와 합쳐 글번호로 중복을 없애고 최근 600건을 남긴다.
  · 어떤 방식이 통했는지 로그와 meta 에 남긴다. 사이트가 바뀌면 여기만 보면 된다.

환경변수 없음. 실패해도 이전 파일을 지우지 않는다.
"""
import json, os, re, socket, ssl, sys, time, urllib.parse, urllib.request, http.cookiejar
from datetime import datetime, timedelta, timezone

KST  = timezone(timedelta(hours=9))
NOW  = datetime.now(KST)
BASE = "https://www.jeju.go.kr"
LIST = BASE + "/news/news/law/jeju.htm"
DETAIL = (BASE + "/citynet/jsp/sap/SAPGosiBizProcess.do"
          "?command=searchDetail&flag=gosiGL&svp=Y&sido=&sno={sno}&gosiGbn={gb}")
OUT  = os.path.join("data", "jeju_notice.json")
KEEP = 600                      # 보관 건수
MAXP = int(os.environ.get("NOTICE_PAGES", "12"))   # 페이지 넘김이 되면 여기까지
UA   = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

# 공공기관 서버는 IPv6 주소가 등록돼 있어도 응답하지 않는 경우가 많다.
# 러너는 IPv6 를 먼저 시도하다 그대로 시간을 다 쓰고 타임아웃이 난다. IPv4 로 고정한다.
_getaddrinfo = socket.getaddrinfo
def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return _getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_only

class HttpsRedirect(urllib.request.HTTPRedirectHandler):
    """도청이 가끔 http:// 로 되돌린다. 러너에서 http 는 연결이 막혀 타임아웃이 나므로
    되돌아온 주소가 http 면 https 로 바꿔 따라간다. (실제로 probe 가 여기서 죽었다)"""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if newurl.startswith("http://"):
            newurl = "https://" + newurl[len("http://"):]
        return super().redirect_request(req, fp, code, msg, headers, newurl)

JAR = http.cookiejar.CookieJar()
OP  = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR),
                                  urllib.request.HTTPSHandler(context=CTX),
                                  HttpsRedirect())

def call(url, data=None, enc="utf-8", tries=4, timeout=45):
    """목록 페이지를 받아 온다. 실패하면 잠깐 쉬고 다시."""
    h = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml",
         "Accept-Language": "ko-KR,ko;q=0.9", "Referer": LIST}
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data, encoding=enc, errors="replace").encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    last = None
    for t in range(tries):
        try:
            with OP.open(urllib.request.Request(url, data=body, headers=h), timeout=timeout) as r:
                raw = r.read(); ct = r.headers.get("Content-Type", "")
            e = "euc-kr" if "euc-kr" in ct.lower() else "utf-8"
            txt = raw.decode(e, "replace")
            if txt.count("\ufffd") > 30:
                txt = raw.decode("euc-kr", "replace")
            return txt
        except Exception as ex:
            last = ex; time.sleep(2 + t * 4)
    print("   ! 요청 실패:", url[:80], "→", repr(last))
    return ""

# ── 행 파싱 ────────────────────────────────────────────────────
# <tr ... onclick="viewData('67621','A')" >
#   <td class="d_tb_center">2026-2903</td>
#   <td class="d_tb_left">「2026년 … 모집 공고(수정)</td>
#   <td class="d_tb_left"> 기후에너지국 분산에너지과 </td>
#   <td class="d_tb_center">2026-08-31</td>
#   <td class="d_tb_center">14</td> </tr>
ROW = re.compile(
    r"viewData\('(?P<sno>\d+)','(?P<gb>\w)'\)"
    r"[\s\S]{0,120}?d_tb_center\">\s*(?P<no>[^<]*?)\s*</td>"
    r"[\s\S]{0,80}?d_tb_left\">\s*(?P<title>[^<]*?)\s*</td>"
    r"[\s\S]{0,80}?d_tb_left\">\s*(?P<dept>[^<]*?)\s*</td>"
    r"[\s\S]{0,80}?d_tb_center\">\s*(?P<date>\d{4}-\d{2}-\d{2})\s*</td>")

def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()

def parse(html):
    out = []
    for m in ROW.finditer(html):
        d = m.groupdict()
        title = clean(d["title"])
        if not title: continue
        out.append({
            "sno":   d["sno"],
            "gb":    d["gb"],
            "no":    clean(d["no"]),
            "t":     title,
            "dept":  clean(d["dept"]),
            "d":     d["date"],
            "link":  DETAIL.format(sno=d["sno"], gb=d["gb"]),
            "list":  LIST,
        })
    return out

# ── 분야 — 부서 이름으로 가른다 (제목보다 흔들리지 않는다) ──────
DEPT_SEC = [
    (r"기후|에너지|환경|자원순환|상하수도", "환경/에너지"),
    (r"관광|문화|체육|예술|유산",           "문화/관광/스포츠"),
    (r"복지|보건|여성|가족|아동|노인|장애",  "복지/보건"),
    (r"농축산|해양|수산|감귤|축산",         "1차산업"),
    (r"교통|건설|도시|주택|건축|안전|재난|소방", "안전·도시"),
    (r"경제|일자리|기업|소상공인|투자|통상", "경제/일자리"),
    (r"미래|디지털|정보|과학|우주",         "신산업/디지털"),
    (r"교육|청년",                          "교육/청년"),
]
def section(dept, title):
    for pat, sec in DEPT_SEC:
        if re.search(pat, dept or ""): return sec
    if re.search(r"모집|공모|지원|보조금", title or ""): return "지원·모집"
    return "행정 일반"

def is_apply(t):
    """신청·모집형 공고인지 — 챗봇이 '신청하는 사업'을 먼저 보게 한다"""
    return bool(re.search(r"모집|공모|접수|신청|선정|지원사업|보급사업", t or ""))

# ── 페이지 넘김: 실행할 때 실제로 시험해 본다 ──────────────────
def hidden_fields(html):
    f = {}
    for m in re.finditer(r"<input[^>]*name=['\"]?([\w]+)['\"]?[^>]*value=['\"]?([^'\">]*)", html):
        f[m.group(1)] = m.group(2)
    return f

def find_pager(html, first):
    """2페이지를 가져오는 방법을 찾는다. 찾으면 (설명, 함수) 를 돌려준다."""
    ids = [x["sno"] for x in first]
    form = hidden_fields(html)
    trials = [
        ("GET currPageNo",       lambda p: call(LIST + "?currPageNo=%d" % p)),
        ("GET page",             lambda p: call(LIST + "?page=%d" % p)),
        ("POST currPageNo",      lambda p: call(LIST, dict(form, currPageNo=str(p)))),
        ("POST currPageNo euckr", lambda p: call(LIST, dict(form, currPageNo=str(p)), "euc-kr")),
    ]
    for name, fn in trials:
        try:
            rs = parse(fn(2))
        except Exception:
            continue
        if rs and [x["sno"] for x in rs] != ids:
            print("   페이지 넘김 방식:", name)
            return name, fn
        time.sleep(0.6)
    print("   페이지 넘김 방식을 찾지 못했습니다 — 1페이지만 가져옵니다(누적으로 채웁니다)")
    return "", None

def opens(url, item):
    """쿠키 없는 새 접속으로 열어 본다. 그 공고의 제목이 실제로 보이면 열리는 것."""
    key = re.sub(r"[^가-힣0-9]", "", item.get("t", ""))[:10]
    if not key: return False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CTX), HttpsRedirect())
        with opener.open(req, timeout=30) as r:
            raw = r.read()
        t = raw.decode("utf-8", "replace")
        if t.count("\ufffd") > 30: t = raw.decode("euc-kr", "replace")
        if "문제가 있습니다" in t: return False
        return key in re.sub(r"[^가-힣0-9]", "", t)
    except Exception:
        return False

def q(v, enc):
    return urllib.parse.quote(str(v), encoding=enc, errors="replace")

# 이용자가 클릭했을 때 실제로 열리는 주소를 찾는다.
# 위에서부터 시험해 첫 번째로 통하는 방식을 모든 공고에 쓴다.
LINK_WAYS = [
    ("상세 직링크",
     lambda x: DETAIL.format(sno=x["sno"], gb=x.get("gb", "A"))),
    ("공고번호로 목록 열기",
     lambda x: LIST + "?conAnnounceNo=" + q(x.get("no", ""), "utf-8")),
    ("공고번호로 목록 열기(euc-kr)",
     lambda x: LIST + "?conAnnounceNo=" + q(x.get("no", ""), "euc-kr")),
    ("제목으로 목록 열기",
     lambda x: LIST + "?conTitle=" + q(re.sub(r"[「」\[\]()（）]", "", x.get("t", ""))[:18], "utf-8")),
    ("제목으로 목록 열기(euc-kr)",
     lambda x: LIST + "?conTitle=" + q(re.sub(r"[「」\[\]()（）]", "", x.get("t", ""))[:18], "euc-kr")),
    ("글번호로 목록 열기",
     lambda x: LIST + "?sno=" + x["sno"] + "&gosiGbn=" + x.get("gb", "A")),
]

def resolve_link(samples):
    """표본 몇 건으로 시험해, 모두 열리는 방식을 고른다."""
    for name, fn in LINK_WAYS:
        try:
            if all(opens(fn(x), x) for x in samples):
                print("   원문 링크 방식:", name)
                return name, fn
        except Exception:
            pass
        time.sleep(0.5)
    print("   ! 바로 열리는 주소를 찾지 못했습니다 — 목록 주소로 둡니다")
    return "", None

def main():
    os.makedirs("data", exist_ok=True)
    print("■ 제주도청 고시/공고 수집")
    html = ""
    for entry in (LIST, LIST + "?currPageNo=1",
                  LIST.replace("https://www.", "https://"),
                  BASE + "/news/news/law.htm"):
        html = call(entry)
        if html and "d_tb_left" in html:
            if entry != LIST: print("   진입 주소:", entry)
            break
        html = ""
    if not html:
        print("목록을 받지 못했습니다. 이전 파일을 그대로 둡니다.")
        print("   (도청 서버 응답 없음 — 다음 실행에서 다시 시도합니다)")
        return
    first = parse(html)
    print("   1페이지", len(first), "건")
    if not first:
        # 화면 구조가 바뀐 경우 — 덮어쓰지 않고 알린다
        print("   ! 행을 하나도 읽지 못했습니다. 목록 구조가 바뀌었을 수 있습니다.")
        print("     응답 일부:", re.sub(r"\s+", " ", html[:400]))
        return

    items = list(first)
    name, pager = find_pager(html, first)
    if pager:
        seen = {x["sno"] for x in items}
        for p in range(2, MAXP + 1):
            rs = parse(pager(p))
            new = [x for x in rs if x["sno"] not in seen]
            if not new:
                print("   %d페이지에서 새 글 없음 — 중단" % p); break
            for x in new: seen.add(x["sno"])
            items += new
            print("   %d페이지 +%d (누적 %d)" % (p, len(new), len(items)))
            time.sleep(0.8)

    # ── 직링크가 실제로 열리는지 확인한다 ────────────────────────
    # 상세는 사이트 안에서 폼으로 넘어가는 구조라, 주소만으로 열리지 않을 수 있다.
    # 열리지 않으면 이용자에게 깨진 링크를 주지 않고 목록 주소로 돌린다(공고번호로 찾게).
    try:
        way, linkfn = resolve_link(first[:2])
    except Exception as ex:                     # 링크 확인이 실패해도 수집은 계속한다
        print("   ! 링크 확인 중 오류:", repr(ex)); way, linkfn = "", None

    # 이전 결과와 합치기 (누적)
    prev = []
    if os.path.exists(OUT):
        try: prev = json.load(open(OUT, encoding="utf-8")).get("items", [])
        except Exception: prev = []
    merged, seen = [], set()
    for x in items + prev:
        if x["sno"] in seen: continue
        seen.add(x["sno"])
        x["sec"] = section(x.get("dept"), x.get("t"))
        x["apply"] = is_apply(x.get("t"))
        x["detail"] = DETAIL.format(sno=x["sno"], gb=x.get("gb", "A"))
        try:
            x["link"] = linkfn(x) if linkfn else LIST
        except Exception:
            x["link"] = LIST
        x["list"] = LIST
        merged.append(x)
    merged.sort(key=lambda x: (x.get("d") or "", x.get("sno") or ""), reverse=True)
    merged = merged[:KEEP]

    data = {"meta": {
        "updated": NOW.strftime("%Y-%m-%d %H:%M"),
        "source": "제주특별자치도 고시/공고 (jeju.go.kr)",
        "list_url": LIST,
        "pager": name or "1페이지만",
        "link_way": way or "목록 주소(바로 열리는 주소를 찾지 못함)",
        "count": len(merged),
        "new_this_run": len([x for x in items if x["sno"] not in {p["sno"] for p in prev}]),
        "note": "상세는 도청 사이트에서 열립니다. 신청 기간·금액은 원문 공고를 확인하세요.",
    }, "items": merged}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    from collections import Counter
    print("")
    print("이번 실행 새 글", data["meta"]["new_this_run"], "· 보관", len(merged), "건")
    print("분야:", dict(Counter(x["sec"] for x in merged)))
    print("신청·모집형:", sum(1 for x in merged if x["apply"]), "건")
    print("최근 5건:")
    for x in merged[:5]:
        print("   ", x["d"], x["no"], "|", x["dept"], "|", x["t"][:46])
    print("→", OUT)

if __name__ == "__main__":
    main()
