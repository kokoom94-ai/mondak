# -*- coding: utf-8 -*-
"""제주도청 고시/공고 구조 확인 probe 2단계.

1단계에서 알아낸 것
  · 목록 https://www.jeju.go.kr/news/news/law/jeju.htm · UTF-8 · <table> 행 구조
    열 = 공고번호 / 제목 / 부서 / 날짜 / 조회수
  · 상세는 링크가 아니라 onclick="viewData('67621','A')"
  · 뒤에 붙은 처리 주소 /citynet/jsp/sap/SAPGosiBizProcess.do
  · ?page=2 는 1페이지와 같은 내용 → 페이지 넘김 방식이 따로 있다

2단계에서 확인할 것
  ① viewData 가 실제로 어디로 보내는가 (상세 직링크를 만들 수 있는가)
  ② 페이지 넘김은 어떤 이름의 값으로 하는가
  ③ 고시(gosi.htm) 목록은 어디서 자료를 받아오는가

아무 파일도 만들지 않고 화면에만 출력한다.
"""
import re, ssl, urllib.request, urllib.parse

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA  = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
BASE = "https://www.jeju.go.kr"
LIST = BASE + "/news/news/law/jeju.htm"

def get(url, data=None, ref=BASE + "/"):
    h = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/json",
         "Accept-Language": "ko-KR,ko;q=0.9", "Referer": ref}
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data, encoding="utf-8").encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
        return r.status, r.read().decode("utf-8", "replace")

def head(s): print("\n" + "=" * 70 + "\n" + s)

# ── ① 목록 페이지의 스크립트·폼 ───────────────────────────────
head("① 목록 페이지 내부 — viewData / 폼 / 페이지 넘김")
st, html = get(LIST)
print("상태", st, "길이", len(html))

for fn in ("viewData", "goPage", "fn_page", "doSearch", "gotoPage", "fnList"):
    m = re.search(r"function\s+" + fn + r"\s*\([^)]*\)\s*\{[\s\S]{0,700}?\n\s*\}", html)
    if m:
        print("\n[function " + fn + "]")
        print(re.sub(r"\n\s*", "\n  ", m.group(0))[:700])

print("\n[form]")
for m in re.finditer(r"<form[^>]*>", html):
    print("  ", m.group(0)[:200])
print("[hidden input]")
for m in re.finditer(r'<input[^>]*type=["\']?hidden["\']?[^>]*>', html, re.I):
    print("  ", re.sub(r"\s+", " ", m.group(0))[:160])
print("[페이지 넘김 부분]")
for m in re.finditer(r'<a[^>]*(?:href|onclick)="[^"]*(?:page|Page|pg)[^"]*"[^>]*>[\s\S]{0,40}?</a>', html):
    print("  ", re.sub(r"\s+", " ", m.group(0))[:200])
print("[전체 행 수]", len(re.findall(r'onclick="viewData\(', html)))
print("[viewData 인자 예시]", re.findall(r"viewData\('([^']+)','([^']+)'\)", html)[:6])

# ── ② 상세 주소 후보 시험 ────────────────────────────────────
head("② 상세 주소 후보 — 어느 것이 본문을 주는가 (seq=67621)")
for name, url, data in [
    ("GET .do?q_seq",  BASE + "/citynet/jsp/sap/SAPGosiBizProcess.do?act=view&seq=67621&gb=A", None),
    ("GET .do?gosiGbn", BASE + "/citynet/jsp/sap/SAPGosiBizProcess.do?gosiGbn=A&gosiSeq=67621", None),
    ("POST .do",       BASE + "/citynet/jsp/sap/SAPGosiBizProcess.do", {"act": "view", "seq": "67621", "gb": "A"}),
    ("목록 htm?seq",    LIST + "?act=view&seq=67621&gb=A", None),
]:
    try:
        s, t = get(url, data, ref=LIST)
        hit = "히트펌프" in t
        print(f"  {name:16s} 상태 {s} · 길이 {len(t):7d} · 히트펌프 {hit}")
        if hit:
            i = t.index("히트펌프")
            print("      본문 주변:", re.sub(r"\s+", " ", t[max(0, i-200):i+300])[:480])
    except Exception as e:
        print(f"  {name:16s} 실패: {e!r}")

# ── ③ 페이지 넘김 값 시험 ────────────────────────────────────
head("③ 페이지 넘김 — 2페이지가 1페이지와 다른가")
first_titles = re.findall(r'd_tb_left">\s*([^<]{6,80}?)\s*</td>', html)[:3]
print("  1페이지 첫 제목:", first_titles)
for key in ("pageIndex", "currentPage", "cpage", "pageNo", "startPage", "p_page", "nowPage"):
    try:
        s, t = get(LIST + "?" + key + "=2", ref=LIST)
        ts = re.findall(r'd_tb_left">\s*([^<]{6,80}?)\s*</td>', t)[:3]
        print(f"  {key:12s} → {'다름 ★' if ts and ts != first_titles else '같음'} {ts[:2]}")
    except Exception as e:
        print(f"  {key:12s} 실패: {e!r}")

# ── ④ 고시 목록의 자료 출처 ─────────────────────────────────
head("④ 고시 목록(gosi.htm)이 부르는 자료 주소")
try:
    s, g = get(BASE + "/news/news/law/gosi.htm")
    for m in re.finditer(r'(?:axios|fetch|\$\.(?:get|post|ajax))\s*\(\s*["\']([^"\']+)["\']', g):
        print("   ", m.group(1)[:160])
    for m in re.finditer(r'url\s*:\s*["\']([^"\']+)["\']', g):
        print("   url:", m.group(1)[:160])
    for m in re.finditer(r'["\'](/[\w/\.\-]*(?:gosi|Gosi|GOSI)[\w/\.\-]*)["\']', g):
        print("   후보:", m.group(1)[:160])
except Exception as e:
    print("  실패:", repr(e))

print("\n" + "=" * 70)
print("이 출력을 그대로 보내주시면 수집기를 씁니다.")
