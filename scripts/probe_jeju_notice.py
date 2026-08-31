# -*- coding: utf-8 -*-
"""제주도청 고시/공고 구조 확인용 probe — 수집기가 아니라 '무엇이 오는지 보는' 스크립트.

왜 필요한가
  제주도청(jeju.go.kr)은 여기(개발 샌드박스)에서 접근이 막혀 있어 응답을 볼 수 없다.
  구조를 모르는 채로 파서를 쓰면 반드시 다시 만들게 되므로, GitHub Actions 러너에서
  실제 응답을 먼저 찍어 본다. 이 출력만 보내주면 수집기를 정확히 쓸 수 있다.

아무 파일도 만들지 않고, 화면에만 출력한다. (읽기 전용)
"""
import re, ssl, sys, urllib.request, urllib.parse

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA  = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# 확인할 후보 주소 — 어느 것이 목록을 주는지 본다
CANDS = [
    ("공고 목록",      "https://www.jeju.go.kr/news/news/law/jeju.htm"),
    ("고시 목록",      "https://www.jeju.go.kr/news/news/law.htm"),
    ("고시공고 통합",  "https://www.jeju.go.kr/news/news/law/gosi.htm"),
    ("공고 2페이지",   "https://www.jeju.go.kr/news/news/law/jeju.htm?page=2"),
    ("검색(히트펌프)", "https://www.jeju.go.kr/news/news/law/jeju.htm?q=히트펌프"),
]

def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9", "Referer": "https://www.jeju.go.kr/"})
    with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
        raw = r.read()
        return r.status, dict(r.headers), raw

def show(name, url):
    print("=" * 70)
    print("[" + name + "] " + url)
    try:
        st, hd, raw = get(url)
    except Exception as e:
        print("  실패:", repr(e)); return
    print("  상태:", st, "· 길이:", len(raw), "· Content-Type:", hd.get("Content-Type"))
    enc = "utf-8"
    m = re.search(r"charset=([\w-]+)", hd.get("Content-Type", ""), re.I)
    if m: enc = m.group(1)
    html = raw.decode(enc, "replace")
    if "euc-kr" not in enc.lower() and "charset=euc-kr" in html[:2000].lower():
        html = raw.decode("euc-kr", "replace"); enc = "euc-kr"
    print("  인코딩:", enc)

    # 목록으로 보이는 링크 — 상세 주소 형태를 알아야 직링크를 만들 수 있다
    links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{4,80}?)\s*</a>', html)
    cand = [(h, t.strip()) for h, t in links
            if re.search(r"(seq|idx|no|articleNo|nttId|bbsId)=", h) or "act=view" in h]
    print("  상세로 보이는 링크:", len(cand))
    for h, t in cand[:8]:
        print("     ", t[:46], "→", h[:100])

    # 목록 행 구조 — 표인지 목록인지
    print("  <table>", html.count("<table"), "· <tbody>", html.count("<tbody"),
          "· <tr>", html.count("<tr"), "· <li>", html.count("<li"))
    m = re.search(r"<tbody[\s\S]{0,1200}?</tr>", html)
    if m: print("  첫 행 원문:\n     ", re.sub(r"\s+", " ", m.group(0))[:600])

    # 날짜·부서처럼 보이는 것
    for label, pat in (("날짜", r"20\d\d[-.]\d\d[-.]\d\d"), ("공고번호", r"제\s?20\d\d\s?-\s?\d+\s?호")):
        f = re.findall(pat, html)[:5]
        print("  " + label + " 예시:", f)

    # 목록이 스크립트로 그려지는 경우 — 호출 주소를 찾는다
    ajax = set(re.findall(r'["\'](/[\w/\.\-]+\.(?:do|json|jsp|htm))\?[^"\']*["\']', html))
    if ajax: print("  스크립트가 부르는 주소:", list(ajax)[:8])

    if "히트펌프" in html:
        i = html.index("히트펌프")
        print("  ※ '히트펌프' 발견 —", re.sub(r"\s+", " ", html[max(0, i-160):i+160]))

for name, url in CANDS:
    show(name, url)
print("=" * 70)
print("여기까지의 출력을 그대로 보내주시면 파서를 씁니다.")
