# -*- coding: utf-8 -*-
"""비짓제주 축제 전용 엔드포인트의 파라미터를 맞춘다.

앞선 진단 결과:
  · searchList 응답에 기간 필드 없음
  · 상세 조회 주소는 모두 404
  · 목록 페이지 HTML에도 기간 없음 (브라우저가 따로 받아 채운다)
  · 다만 api.visitjeju.net/vsjApi/festival/list 가 420자짜리 '다른' 응답을 돌려줌
    → 전용 경로는 있고 파라미터만 어긋난 것으로 보인다. 그 응답을 읽고 맞춘다.

저장하지 않는다. 로그만 남긴다.
"""
import json, os, ssl, urllib.parse, urllib.request

KEY = os.environ.get("VISITJEJU_KEY", "").strip()
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA  = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
API = "https://api.visitjeju.net/vsjApi"


def get(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko", "Referer": "https://www.visitjeju.net/kr/festival/list"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def show(label, url):
    try:
        t = get(url)
    except Exception as e:
        print("  · " + label + " → " + str(e))
        return None
    short = t[:600].replace("\n", " ")
    print("  · " + label + " → " + str(len(t)) + "자")
    print("      " + short)
    return t


def main():
    print("=" * 62)
    print("1. festival/list 응답 원문 (파라미터 힌트를 읽는다)")
    print("=" * 62)
    show("파라미터 없음", API + "/festival/list")
    show("키만", API + "/festival/list?apiKey=" + urllib.parse.quote(KEY))
    show("키+locale", API + "/festival/list?apiKey=" + urllib.parse.quote(KEY) + "&locale=kr")
    show("키+locale+page", API + "/festival/list?apiKey=" + urllib.parse.quote(KEY)
         + "&locale=kr&page=1")
    show("연월 지정", API + "/festival/list?apiKey=" + urllib.parse.quote(KEY)
         + "&locale=kr&page=1&year=2026&month=09&state=all")

    print("")
    print("=" * 62)
    print("2. 다른 이름 후보")
    print("=" * 62)
    for path in ["contents/festivalList", "festival/searchList", "contents/searchFestival",
                 "festival/list.json", "contents/festival"]:
        show(path, API + "/" + path + "?apiKey=" + urllib.parse.quote(KEY) + "&locale=kr&page=1")

    print("")
    print("=" * 62)
    print("3. searchList에 기간 파라미터를 붙이면 기간이 돌아오는가")
    print("=" * 62)
    base = (API + "/contents/searchList?apiKey=" + urllib.parse.quote(KEY)
            + "&locale=kr&category=c5&page=1")
    for extra, label in [("", "그대로"),
                         ("&state=ing", "state=ing"),
                         ("&year=2026&month=09", "연월"),
                         ("&startDate=20260901&endDate=20260930", "기간지정")]:
        t = show(label, base + extra)
        if t:
            try:
                j = json.loads(t)
                n = len(j.get("items") or [])
                tot = j.get("totalCount")
                first = (j.get("items") or [{}])[0]
                print("      건수 " + str(n) + " / 전체 " + str(tot)
                      + " · 첫 항목 키: " + str(sorted(first.keys())))
            except Exception:
                pass


if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception:
        traceback.print_exc()
    print("")
    print("끝.")
