# -*- coding: utf-8 -*-
"""제주도청 고시/공고 probe 3단계 — 마지막 확인.

2단계에서 알아낸 것
  · 상세  : SAPGosiBizProcess.do?command=searchDetail&flag=gosiGL&svp=Y&sido=&sno=&gosiGbn= 로 폼 전송
  · 목록  : 같은 .do 에 command=searchList, 폼값 currPageNo 로 페이지 넘김
  · 전송 인코딩은 EUC-KR (document.charset="euc-kr")
  · 폼에 TOKEN_SAB(세션 토큰)·기간(conIfmStdt_Date/conIfmEnddt_Date)이 함께 간다
  · 한 페이지 10건

3단계에서 확인할 것
  ① 목록 페이지에서 토큰·쿠키를 받아 POST 하면 2·3페이지가 실제로 넘어가는가
  ② 기간을 넓히면(예: 2026-01-01~) 더 많은 건이 나오는가
  ③ 상세 POST 가 본문을 주는가 — 내용·첨부·신청기간을 뽑을 수 있는가
  ④ 이용자에게 줄 원문 '직링크'가 성립하는가 (주소만으로 열리는가)

아무 파일도 만들지 않고 화면에만 출력한다.
"""
import re, ssl, urllib.request, urllib.parse, http.cookiejar

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA  = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
BASE = "https://www.jeju.go.kr"
LIST = BASE + "/news/news/law/jeju.htm"
DO   = BASE + "/citynet/jsp/sap/SAPGosiBizProcess.do"

JAR = http.cookiejar.CookieJar()
OP  = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR),
                                  urllib.request.HTTPSHandler(context=CTX))

def call(url, data=None, ref=LIST, enc="euc-kr"):
    h = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml",
         "Accept-Language": "ko-KR,ko;q=0.9", "Referer": ref}
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data, encoding=enc, errors="replace").encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=h)
    with OP.open(req, timeout=30) as r:
        raw = r.read(); ct = r.headers.get("Content-Type", "")
    e = "euc-kr" if "euc-kr" in ct.lower() else "utf-8"
    t = raw.decode(e, "replace")
    if e == "utf-8" and t.count("\ufffd") > 30:
        t = raw.decode("euc-kr", "replace"); e = "euc-kr(재해석)"
    return len(raw), e, t

def titles(t):
    return [re.sub(r"\s+", " ", x).strip()
            for x in re.findall(r'd_tb_left">\s*([^<]{6,90}?)\s*</td>', t)][:6:2]

def head(s): print("\n" + "=" * 70 + "\n" + s)

# 목록 페이지에서 폼 값 수집
n, e, html = call(LIST, ref=BASE + "/")
form = {}
for m in re.finditer(r"<input[^>]*name=['\"]?([\w]+)['\"]?[^>]*value=['\"]?([^'\">]*)", html):
    form[m.group(1)] = m.group(2)
print("목록 응답", n, e, "· 쿠키", [c.name for c in JAR])
print("폼 값:", {k: v[:24] for k, v in form.items()})
base_titles = titles(html)
print("1페이지 제목:", base_titles)

# ── ① 페이지 넘김 ─────────────────────────────────────────
head("① currPageNo 로 페이지가 넘어가는가")
url_list = DO + "?command=searchList&flag=gosiGL&svp=Y&sido="
for p in ("1", "2", "3"):
    d = dict(form); d["currPageNo"] = p; d["flag"] = "gosiGL"
    try:
        n, e, t = call(url_list, d)
        ts = titles(t)
        print(f"  {p}페이지 · {n:7d}바이트 · {e} · {'다름 ★' if ts and ts != base_titles else '같음/빈값'}")
        for x in ts[:2]: print("      ", x[:60])
    except Exception as ex:
        print(f"  {p}페이지 실패: {ex!r}")

# ── ② 기간 넓히기 ────────────────────────────────────────
head("② 기간을 넓히면 더 나오는가 (2026-01-01 ~ 오늘)")
d = dict(form); d["currPageNo"] = "1"
d["conIfmStdt_Date"] = "20260101"; d["conIfmEnddt_Date"] = "20261231"
try:
    n, e, t = call(url_list, d)
    rows = re.findall(r"viewData\('(\d+)','(\w)'\)", t)
    print("  응답", n, e, "· 행", len(rows), "· 총건수 표기:",
          re.findall(r"(?:총|전체)\s*[:：]?\s*([\d,]+)\s*건", t)[:3])
    for x in titles(t)[:3]: print("      ", x[:60])
except Exception as ex:
    print("  실패:", repr(ex))

# ── ③ 상세 본문 ─────────────────────────────────────────
head("③ 상세 POST 가 본문을 주는가 (sno=67621)")
sno, gb = "67621", "A"
url_det = (DO + "?command=searchDetail&flag=gosiGL&svp=Y&sido=&sno=" + sno + "&gosiGbn=" + gb)
d = dict(form); d["sno"] = sno; d["gosiGbn"] = gb; d["flag"] = "gosiGL"
try:
    n, e, t = call(url_det, d)
    print("  응답", n, e, "· 히트펌프 포함:", "히트펌프" in t)
    txt = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", t)
    txt = re.sub(r"<[^>]+>", " ", txt); txt = re.sub(r"\s+", " ", txt).strip()
    print("  본문 앞부분:", txt[:700])
    print("  첨부파일 링크:", re.findall(r'href="([^"]*(?:download|file|atch)[^"]*)"', t, re.I)[:5])
except Exception as ex:
    print("  실패:", repr(ex))

# ── ④ 직링크 성립 여부 ──────────────────────────────────
head("④ 주소만으로 상세가 열리는가 (새 접속 = 쿠키 없음)")
for name, url in (("GET 상세 .do", url_det),
                  ("GET 목록 htm", LIST)):
    try:
        h = {"User-Agent": UA, "Referer": ""}
        req = urllib.request.Request(url, headers=h)
        with urllib.request.build_opener(urllib.request.HTTPSHandler(context=CTX)).open(req, timeout=25) as r:
            raw = r.read()
        t2 = raw.decode("utf-8", "replace")
        if t2.count("\ufffd") > 30: t2 = raw.decode("euc-kr", "replace")
        print(f"  {name:12s} {len(raw):7d}바이트 · 히트펌프 {'히트펌프' in t2}")
    except Exception as ex:
        print(f"  {name:12s} 실패: {ex!r}")

print("\n" + "=" * 70)
print("이 출력을 보내주시면 수집기를 씁니다.")
