# -*- coding: utf-8 -*-
"""비짓제주 축제 목록 페이지 안에 심긴 데이터를 찾는다.

앞선 진단에서 /_nuxt/ 경로가 확인됐다 — Nuxt로 만든 화면이다.
Nuxt는 서버가 만든 데이터를 페이지 안 <script id="__NUXT_DATA__">에 통째로 심는다.
그러므로 축제 목록과 기간이 이미 HTML 안에 있을 수 있다. 그걸 확인한다.

저장하지 않는다. 로그만 남긴다.
"""
import json, re, ssl, urllib.request

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA  = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
PAGE = ("https://www.visitjeju.net/kr/festival/list?"
        "menuId=DOM_000001718007000000&cate1cd=cate0000001360")


def get(url, timeout=25):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html,application/json;q=0.9",
        "Accept-Language": "ko,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def main():
    try:
        html = get(PAGE)
    except Exception as e:
        print(f"페이지를 못 받았습니다: {e}")
        return
    print(f"페이지 {len(html)}자")

    # ── 1. Nuxt가 심어둔 데이터 덩어리 ──
    print("\n" + "=" * 60)
    print("1. 페이지에 심긴 데이터(__NUXT_DATA__)")
    print("=" * 60)
    m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        m = re.search(r'window\.__NUXT__\s*=\s*(.*?)</script>', html, re.S)
    if m:
        blob = m.group(1)
        print(f"  발견 · {len(blob)}자")
        # 날짜꼴 문자열이 몇 개나 들어 있나
        ymd = re.findall(r'"(20\d{2}[-.]?\d{2}[-.]?\d{2})"', blob)
        print(f"  날짜꼴 값 {len(ymd)}개 · 표본: {sorted(set(ymd))[:14]}")
        # 축제 제목으로 위치를 잡아 주변을 본다
        for kw in ("축제", "페스티벌", "박람회"):
            i = blob.find(kw)
            if i > 0:
                print(f"\n  '{kw}' 주변 (앞뒤 700자):")
                print("  " + blob[max(0, i-700):i+700].replace("\n", " "))
                break
    else:
        print("  없음")

    # ── 2. 목록 항목이 HTML로 그려져 있는지 ──
    print("\n" + "=" * 60)
    print("2. 목록 항목이 HTML에 그려져 있는가")
    print("=" * 60)
    for pat, label in [
        (r'<li[^>]*class="[^"]*(?:item|card|festival)[^"]*"[^>]*>(.{0,600}?)</li>', "li 항목"),
        (r'class="[^"]*tit[^"]*"[^>]*>([^<]{4,60})<', "제목류"),
        (r'(\d{4}[.\-]\d{2}[.\-]\d{2}\s*[~\-]\s*\d{4}[.\-]\d{2}[.\-]\d{2})', "기간 표기"),
        (r'(\d{2}\.\d{2}\s*~\s*\d{2}\.\d{2})', "짧은 기간 표기"),
    ]:
        found = re.findall(pat, html, re.S)
        print(f"  · {label}: {len(found)}건")
        for x in found[:6]:
            print(f"      {re.sub(r'\\s+', ' ', str(x))[:110]}")

    # ── 3. Nuxt 데이터 파일 ──
    print("\n" + "=" * 60)
    print("3. Nuxt 데이터 경로")
    print("=" * 60)
    for u in sorted(set(re.findall(r'["\'](/_nuxt/[^"\']+)["\']', html)))[:10]:
        print(f"  {u}")
    payload = re.findall(r'["\']([^"\']*_payload[^"\']*)["\']', html)
    print(f"  payload 경로: {sorted(set(payload))[:5] or '없음'}")

    # ── 4. API 후보 직접 두드리기 ──
    print("\n" + "=" * 60)
    print("4. 목록 API 후보")
    print("=" * 60)
    cands = [
        "https://api.visitjeju.net/vsjApi/festival/list?locale=kr&year=2026&month=09&state=all",
        "https://www.visitjeju.net/api/festival/list?year=2026&month=09&state=all",
        "https://www.visitjeju.net/kr/festival/list.json?year=2026&month=09&state=all",
    ]
    for u in cands:
        try:
            t = get(u, 15)
            ok = "축제" in t or '"items"' in t or '"list"' in t
            print(f"  · {u.split('//')[1][:58]} → {len(t)}자 {'★내용있음' if ok else ''}")
            if ok: print("      " + t[:500].replace("\n", " "))
        except Exception as e:
            print(f"  · {u.split('//')[1][:58]} → {e}")


def safe(label, fn):
    import traceback
    try:
        fn()
    except Exception:
        print(f"\n!! {label} 중 오류 — 계속 진행합니다")
        traceback.print_exc()


if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception:
        print("!! 전체 오류")
        traceback.print_exc()
    print("\n끝. 위 결과를 그대로 붙여 주세요.")
