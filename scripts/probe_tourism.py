# -*- coding: utf-8 -*-
"""
제주관광 빅데이터 플랫폼 API 접근 테스트 (probe)
- 세션 쿠키 없이 POST 호출이 되는지 확인만 합니다. 데이터는 저장하지 않습니다.
- 결과는 로그로만 출력합니다.
"""
import json, ssl, urllib.request, urllib.error

URL = "https://data.ijto.or.kr/api/dataPick/chart/renderChart.do"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def call(payload, label):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Referer": "https://data.ijto.or.kr/",
        "Origin": "https://data.ijto.or.kr",
    })
    print(f"\n=== {label} ===")
    print("payload:", json.dumps(payload, ensure_ascii=False))
    try:
        with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
            raw = r.read().decode("utf-8", "replace")
            print("HTTP:", r.status, "| 길이:", len(raw))
            head = raw[:600]
            print("응답 앞부분:")
            print(head)
            # 로그인 페이지로 튕겼는지 판별
            low = raw.lower()
            if "<html" in low and ("login" in low or "로그인" in raw):
                print(">>> 판정: 로그인 페이지 반환 (세션 필요)")
                return None
            try:
                d = json.loads(raw)
                print(">>> 판정: JSON 정상 수신 ✅")
                if isinstance(d, dict):
                    print("    최상위 키:", list(d.keys())[:15])
                return d
            except Exception:
                print(">>> 판정: JSON 아님 (HTML 등)")
                return None
    except urllib.error.HTTPError as e:
        print("HTTPError:", e.code, e.reason)
        try: print(e.read().decode("utf-8","replace")[:400])
        except Exception: pass
    except Exception as e:
        print("오류:", e)
    return None

if __name__ == "__main__":
    print("제주관광 빅데이터 플랫폼 API 접근 테스트")
    print("URL:", URL)
    # 브라우저에서 관찰된 실제 payload
    d = call({"regSn":"17","chartIndex":0,"searchDataBgnDt":"","searchDataEndDt":""}, "regSn=17")
    if d:
        # 다른 데이터셋도 되는지
        call({"regSn":"1","chartIndex":0,"searchDataBgnDt":"","searchDataEndDt":""}, "regSn=1")
        call({"regSn":"20","chartIndex":0,"searchDataBgnDt":"","searchDataEndDt":""}, "regSn=20")
    print("\n테스트 종료")
