# -*- coding: utf-8 -*-
"""비짓제주에서 '축제 기간'을 얻는 경로를 찾는 진단 스크립트.

searchList 응답에는 기간 필드가 없다(실측 확인). 그런데 비짓제주 축제 목록 화면은
year·month·state(진행중/예정/종료)로 거르므로, 어딘가는 기간을 알고 있다.
후보 두 가지를 한 번에 확인한다.

  A. 공개 API의 상세 조회 — contentsid로 개별 조회하면 기간이 오는가
  B. 축제 목록 화면이 부르는 내부 주소 — 화면이 쓰는 그 경로에 기간이 오는가

저장하지 않는다. 로그만 남긴다.
"""
import json, os, re, ssl, urllib.parse, urllib.request

KEY = os.environ.get("VISITJEJU_KEY", "").strip()
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA  = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")


def get(url, headers=None, timeout=20):
    h = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "ko,en;q=0.8"}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def head(txt, n=1200):
    return txt[:n].replace("\n", " ")[:n]


# ══════════ A. 상세 조회 ══════════
def probe_detail():
    print("\n" + "=" * 62)
    print("A. 공개 API 상세 조회 — 기간이 오는가")
    print("=" * 62)
    # 목록에서 축제 하나를 집어 그 contentsid로 시험한다
    try:
        d = json.loads(get("https://api.visitjeju.net/vsjApi/contents/searchList?"
                           + urllib.parse.urlencode({"apiKey": KEY, "locale": "kr",
                                                     "category": "c5", "page": 1})))
        items = d.get("items") or []
    except Exception as e:
        print(f"  목록 조회 실패: {e}"); return
    if not items:
        print("  목록이 비었습니다"); return

    sample = items[0]
    cid = sample.get("contentsid")
    print(f"  시험 대상: {sample.get('title')} ({cid})")

    forms = [
        ("경로형",   f"https://api.visitjeju.net/vsjApi/contents/contentsid/{cid}?apiKey={KEY}&locale=kr"),
        ("파라미터형", f"https://api.visitjeju.net/vsjApi/contents/contentsid?apiKey={KEY}&locale=kr&contentsid={cid}"),
        ("detail",   f"https://api.visitjeju.net/vsjApi/contents/detail?apiKey={KEY}&locale=kr&contentsid={cid}"),
        ("searchList+cid", f"https://api.visitjeju.net/vsjApi/contents/searchList?apiKey={KEY}&locale=kr&cid={cid}"),
    ]
    for name, u in forms:
        try:
            txt = get(u)
        except Exception as e:
            print(f"  · {name}: 실패 {e}"); continue
        print(f"  · {name}: 응답 {len(txt)}자")
        try:
            j = json.loads(txt)
        except Exception:
            print(f"      (JSON 아님) {head(txt, 200)}"); continue
        flat = json.dumps(j, ensure_ascii=False)
        # 기간처럼 보이는 키가 있는지
        keys = re.findall(r'"([A-Za-z가-힣_]*(?:[Dd]ate|ymd|YMD|기간|일자|start|end|Start|End)[A-Za-z_]*)"', flat)
        print(f"      날짜 관련 키: {sorted(set(keys)) or '없음'}")
        if keys:
            print("      ── 응답 전문 ──")
            print(json.dumps(j, ensure_ascii=False, indent=1)[:2500])
            return


# ══════════ B. 축제 목록 화면의 내부 주소 ══════════
def probe_page():
    print("\n" + "=" * 62)
    print("B. 축제 목록 화면 — 화면이 부르는 주소에 기간이 있는가")
    print("=" * 62)
    page = ("https://www.visitjeju.net/kr/festival/list?"
            "menuId=DOM_000001718007000000&cate1cd=cate0000001360")
    try:
        html = get(page)
    except Exception as e:
        print(f"  페이지 조회 실패: {e}"); return
    print(f"  페이지 {len(html)}자")

    # 1) 페이지에 박힌 JSON 후보
    for pat, label in [(r'festival[A-Za-z]*\s*[:=]\s*(\[.{80,}?\])', "인라인 festival 배열"),
                       (r'var\s+list\s*=\s*(\[.{80,}?\])', "var list")]:
        m = re.search(pat, html, re.S)
        if m:
            print(f"  · {label} 발견: {head(m.group(1), 400)}")

    # 2) 화면이 부르는 주소 후보 — ajax/json/list 가 들어간 경로를 긁는다
    urls = set(re.findall(r'["\'](/[A-Za-z0-9_\-/\.]*(?:ajax|json|list|Api|api)[A-Za-z0-9_\-/\.]*)["\']', html))
    print(f"  · 내부 경로 후보 {len(urls)}개")
    for u in sorted(urls)[:25]:
        print(f"      {u}")

    # 3) 상태·기간 낱말이 HTML 안에 있는지 (서버가 일부라도 그려주는지)
    for w in ["진행중", "예정", "종료", "기간", "startDate", "sDate", "fstvl"]:
        c = html.count(w)
        if c: print(f"  · '{w}' {c}회 등장")

    # 4) 스크립트 파일 목록 — 그 안에 주소가 있을 수 있다
    js = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', html)
    print(f"  · 스크립트 {len(js)}개")
    for u in js[:12]:
        print(f"      {u}")
    # 화면 전용 스크립트를 하나 열어 주소를 찾아본다
    for u in js:
        if not any(w in u.lower() for w in ("festival", "list", "common", "app")): continue
        full = u if u.startswith("http") else ("https://www.visitjeju.net" + u if u.startswith("/")
                                               else "https://www.visitjeju.net/" + u)
        try:
            code = get(full)
        except Exception:
            continue
        hits = set(re.findall(r'["\'](/[A-Za-z0-9_\-/\.]*(?:festival|search|list)[A-Za-z0-9_\-/\.]*)["\']', code))
        if hits:
            print(f"  · {u} 안의 경로: {sorted(hits)[:12]}")


if __name__ == "__main__":
    if not KEY:
        print("VISITJEJU_KEY 미설정")
    probe_detail()
    probe_page()
    print("\n끝. 위 결과를 그대로 붙여 주세요.")
