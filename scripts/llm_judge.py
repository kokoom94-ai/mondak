# -*- coding: utf-8 -*-
"""이슈체크 LLM 판정기 — Hasa AI Hub(open.hasa.re.kr)로 관련성·감성·분야를 판정한다.

규칙(정규식)으로는 원리적으로 못 잡는 것들이 있었다.
  · "비싸다고 들었지만 실제론 아니었다"  → 반전을 못 읽어 부정으로
  · 카자흐스탄 여행기의 "제주도에서 차 빌리듯" → 비유를 못 읽어 제주 이슈로
  · 김제시장 향응 의혹, 부안 의원 관광성 연수 → 제주 여행자의 일이 아닌데 채택
  · "애월 펜션 가성비 최고"              → 근거 없이 부정
LLM은 문장의 방향과 주체를 읽으므로 이 유형을 걸러낸다.

환경변수: HUB_API_KEY  (Cloudflare Worker에 쓰는 것과 같은 키)

판정 결과는 항목의 llm 필드에 남기고, 이미 판정한 것은 다시 부르지 않는다.
"""
import json, os, re, ssl, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

HUB   = "https://open.hasa.re.kr/v1/templates/llm-chat/run"
MODEL = os.environ.get("HUB_MODEL", "exaone-4.0-32b")
KEY   = os.environ.get("HUB_API_KEY", "").strip()

SRC   = os.path.join("data", "issue.json")
BATCH = int(os.environ.get("LLM_BATCH", "8"))      # 한 번에 판정할 건수
LIMIT = int(os.environ.get("LLM_LIMIT", "400"))    # 실행당 상한
DAYS  = int(os.environ.get("LLM_DAYS", "21"))      # 최근 며칠분만 판정
VER   = "llm-v1"                                   # 판정 기준이 바뀌면 올린다

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

CATS = ["치안·안전", "비용·상거래", "숙박", "이동·교통", "먹거리",
        "볼거리·체험", "정책·행정", "응대·서비스", "환경·청결"]

SYSTEM = """당신은 제주 관광 여론을 분류하는 전문가입니다. 주어진 글 여러 건을 판정해 JSON 배열로만 답하세요.

【1단계 — 대상 여부(rel)】
다음을 모두 만족할 때만 true입니다.
· 제주도에서 일어난 일이거나 제주 여행·관광과 직접 관련될 것
· 여행자·방문객·도민이 겪었거나 겪을 일일 것
· 제주 관광에 영향을 주는 사건·정책일 것

false로 판정할 대표 사례:
· 다른 지역의 사건인데 '제주'가 비유·예시·부수적으로만 언급된 글
  (예: 카자흐스탄 여행기에 "제주도에서 차 빌리듯", 김제시장 향응 의혹에 '제주여행' 언급)
· 타 지역 정치인·공무원의 연수·출장에 대한 지적
· 제주점·부산점처럼 지점 나열에 제주가 들어간 광고·홍보 글
· 제주와 무관한 일반 상품·서비스 홍보

【2단계 — 감성(sent)】 긍정 / 부정 / 중립
글쓴이가 제주(또는 그 대상)에 대해 어떤 태도인지 **문장 전체의 방향**으로 판단하세요.
· "비싸다고 들었는데 막상 가보니 괜찮았다" → 긍정 (걱정이 해소된 것)
· "여기는 원래 비싸지만 저렴하게 가는 방법이 있다" → 긍정 또는 중립 (해법 제시)
· "가성비 최고였다", "만족했다" → 긍정
· 부정 낱말이 있어도 결론이 호의적이면 긍정입니다.
· 사실 전달 위주의 보도·안내·홍보는 중립입니다.
· 불만·실망·피해·불안·경고가 결론이면 부정입니다.

【3단계 — 분야(cat)】 다음 중 하나만 고르세요.
치안·안전 / 비용·상거래 / 숙박 / 이동·교통 / 먹거리 / 볼거리·체험 / 정책·행정 / 응대·서비스 / 환경·청결
· 사건사고·범죄·실종·안전 문제 → 치안·안전
· 물가·요금·바가지 → 비용·상거래
· 숙소에서 겪은 일 → 숙박
· 항공·버스·택시·렌터카 → 이동·교통
· 식당·음식 → 먹거리
· 관광지·체험·축제 → 볼거리·체험
· 제주도 관광정책·행정 → 정책·행정
· 종사자 응대·친절 → 응대·서비스
· 쓰레기·오버투어리즘·난개발 → 환경·청결

【출력 형식】
설명 없이 JSON 배열만 출력하세요.
[{"i":0,"rel":true,"sent":"부정","cat":"치안·안전","why":"실종사건으로 여행 취소 언급"},
 {"i":1,"rel":false,"sent":"중립","cat":"","why":"타 지역 사건, 제주는 비유로만 언급"}]
why는 12자 이내로 짧게 쓰세요."""


def call_hub(prompt, tries=3):
    body = json.dumps({"inputs": {"message": prompt, "system": SYSTEM,
                                  "use_web": "off", "model": MODEL}}).encode()
    req = urllib.request.Request(HUB, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    for t in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=90, context=CTX) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            return (d.get("answer") or d.get("output") or d.get("result")
                    or d.get("text") or d.get("response") or "").strip()
        except Exception as e:
            print("   ! 호출 실패(" + str(t + 1) + "/" + str(tries) + "): " + str(e))
            time.sleep(2 + t * 3)
    return ""


def parse_answer(txt, n):
    """답변에서 JSON 배열을 꺼낸다. 코드블록·설명이 섞여도 견딘다."""
    if not txt: return None
    m = re.search(r"\[[\s\S]*\]", txt)
    if not m: return None
    try:
        arr = json.loads(m.group(0))
    except Exception:
        # 흔한 흠: 끝에 쉼표, 홑따옴표
        s = m.group(0).replace("'", '"')
        s = re.sub(r",\s*([\]}])", r"\1", s)
        try: arr = json.loads(s)
        except Exception: return None
    if not isinstance(arr, list): return None
    out = {}
    for o in arr:
        if not isinstance(o, dict): continue
        try: i = int(o.get("i"))
        except Exception: continue
        if not (0 <= i < n): continue
        sent = str(o.get("sent") or "").strip()
        cat  = str(o.get("cat") or "").strip()
        out[i] = {
            "rel":  bool(o.get("rel")),
            "sent": sent if sent in ("긍정", "부정", "중립") else "중립",
            "cat":  cat if cat in CATS else "",
            "why":  str(o.get("why") or "")[:30],
            "v":    VER,
        }
    return out


def make_prompt(items):
    lines = []
    for i, x in enumerate(items):
        t = (x.get("title") or "").strip()[:90]
        d = (x.get("description") or "").strip()[:220]
        ch = {"blog": "블로그", "cafe": "카페", "news": "뉴스"}.get(x.get("channel"), x.get("channel") or "")
        lines.append("[" + str(i) + "] (" + ch + ") 제목: " + t + "\n     본문: " + d)
    return "다음 " + str(len(items)) + "건을 판정하세요.\n\n" + "\n\n".join(lines)


def main():
    if not KEY:
        print("HUB_API_KEY 미설정 — 판정을 건너뜁니다"); return
    if not os.path.exists(SRC):
        print(SRC + " 없음"); return

    data = json.load(open(SRC, encoding="utf-8"))
    items = data.get("items") or []
    cut = (NOW - timedelta(days=DAYS)).strftime("%Y-%m-%d")

    todo = [x for x in items
            if (x.get("date") or "") >= cut
            and (x.get("llm") or {}).get("v") != VER]
    todo = todo[:LIMIT]

    print("■ LLM 판정 — 대상 " + str(len(todo)) + "건 (최근 " + str(DAYS) + "일 · 상한 " + str(LIMIT) + ")")
    if not todo:
        print("   판정할 항목이 없습니다"); return

    done = fail = 0
    for s in range(0, len(todo), BATCH):
        chunk = todo[s:s + BATCH]
        res = parse_answer(call_hub(make_prompt(chunk)), len(chunk))
        if not res:
            fail += len(chunk)
        else:
            for i, x in enumerate(chunk):
                if i in res:
                    x["llm"] = res[i]; done += 1
                else:
                    fail += 1
        if (s // BATCH) % 5 == 0:
            print("   " + str(min(s + BATCH, len(todo))) + "/" + str(len(todo)) + " · 성공 " + str(done))
        time.sleep(0.6)

    # 판정 결과를 실제 분류에 반영한다 (규칙 판정은 llm_prev 에 남겨 둔다)
    changed = dropped = 0
    for x in items:
        j = x.get("llm")
        if not j or j.get("v") != VER: continue
        if not x.get("llm_prev"):
            x["llm_prev"] = {"sentiment": x.get("sentiment"), "category": x.get("category")}
        if not j["rel"]:
            x["keep"] = False; x["drop_why"] = "LLM: " + (j.get("why") or "관련 없음")
            dropped += 1; continue
        x["keep"] = True
        if x.get("sentiment") != j["sent"]:
            x["sentiment"] = j["sent"]; changed += 1
        if j["cat"] and x.get("category") != j["cat"]:
            x["category"] = j["cat"]

    # 관련 없다고 판정된 항목은 목록에서 뺀다
    before = len(items)
    items = [x for x in items if x.get("keep") is not False]
    data["items"] = items
    meta = data.setdefault("meta", {})
    meta["llm"] = {"version": VER, "model": MODEL,
                   "judged": done, "failed": fail,
                   "dropped": before - len(items),
                   "updated": NOW.strftime("%Y-%m-%d %H:%M")}

    json.dump(data, open(SRC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    import collections
    print("")
    print("판정 성공 " + str(done) + " · 실패 " + str(fail))
    print("감성 바뀜 " + str(changed) + "건 · 관련 없어 제외 " + str(before - len(items)) + "건")
    print("남은 " + str(len(items)) + "건 감성: " +
          str(dict(collections.Counter(x.get("sentiment") for x in items))))
    print("→ " + SRC)


if __name__ == "__main__":
    main()
