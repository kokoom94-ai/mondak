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
BATCH = int(os.environ.get("LLM_BATCH", "12"))     # 한 번에 판정할 건수
LIMIT = int(os.environ.get("LLM_LIMIT", "99999"))  # 실행당 상한 (기본: 제한 없음)
DAYS  = int(os.environ.get("LLM_DAYS", "60"))      # 보관 기간 전체를 판정한다
VER   = "llm-v7"                                   # 판정 기준이 바뀌면 올린다

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

CATS = ["치안·안전", "비용·상거래", "숙박", "이동·교통", "먹거리",
        "볼거리·체험", "정책·행정", "응대·서비스", "환경·청결"]

SYSTEM = """당신은 제주 관광 여론을 분류합니다. 아래 세 질문을 순서대로 던져 판정하고,
JSON 배열로만 답하세요. 예시는 이해를 돕는 참고일 뿐, 판단은 항상 질문으로 하세요.

═══ 질문 1. 이 글의 중심이 제주 관광인가? (rel) ═══
"이 글을 한 줄로 요약하면 무엇에 대한 글인가"를 스스로 물으세요.
그 한 줄에 제주 관광·여행이 들어가지 않으면 rel=false 입니다.

false 인 경우
 · 제주가 비유·예시·나열의 하나로만 스쳐 나옴
   (다른 지역 사건 기사에 제주가 함께 묶인 것, 여행업계·증권가 전반 동향에 제주가 사례로 나온 것,
    지점 나열에 제주점이 포함된 것, 다른 곳 여행기에 제주가 비유로 나온 것)
 · 사건의 주체와 무대가 제주 밖 (다른 지역 정치·행정·기업 사안)
 · 제주에서 일어났어도 여행·관광과 무관 (지역 상권 광고, 주민 생활 서비스)

═══ 질문 2. 알리는 글인가, 평가하는 글인가? ═══
**알리는 글이면 rel=false 입니다.** 여론이 아니라 발표·홍보이기 때문입니다.
 · 업체·상품을 소개하고 이용을 권하는 글 (협찬·제휴 후기, 예약 유도 포함)
 · 기관·기업이 낸 보도자료를 옮긴 기사
 · 행사 개최 안내, 모집 공고, 협약 체결, 개관·출시, 시상·위촉 소식
 · 특정 업체를 소개하는 기사형 광고

**평가하는 글이면 rel=true 입니다.**
 · 겪은 일에 대한 소감·불만·후기
 · 실태를 취재하거나 문제를 짚은 보도
 · 지표의 변화를 다룬 보도, 정책에 대한 비판·논쟁
 · 사건·사고 보도

═══ 질문 3. 이 사안은 어느 단계인가? (sent) ═══
하나의 사안은 「문제 → 대응 → 해결」을 거칩니다. 글이 어느 단계를 다루는지 보세요.

 · 부정 = 문제
   아직 풀리지 않은 문제가 글의 핵심일 때.
   불편·불만·피해·부족·감소·비판이 결론인 경우.

 · 중립 = 대응
   그 문제에 무엇을 하겠다는 단계. 결과는 아직 없습니다.
   대책·계획·추진·검토·협의체·전담팀·회의·용역·예산 편성.
   **"~하겠다·추진한다·마련한다·검토한다"는 성과가 아니므로 긍정이 아닙니다.**
   문제를 언급하며 시작해도 글의 핵심이 대응이면 중립입니다.
   사실만 전달하거나 우려를 가라앉히는 보도("영향 제한적", "정상 운영")도 중립입니다.

 · 긍정 = 해결·성과
   실제로 나아졌음이 결과로 확인될 때.
   늘었다·줄었다·개선됐다·만족도 상승·호평.

개인 글은 **문장 전체가 향하는 방향**으로 봅니다.
 부정 낱말이 있어도 결론이 호의적이면 긍정입니다.
 ("비싸다고 들었는데 가보니 괜찮았다" → 걱정이 해소됐으므로 긍정)
 일정·준비물만 정리한 정보성 글은 중립입니다.

═══ 분야 (cats) — 최대 2개 ═══
치안·안전 / 비용·상거래 / 숙박 / 이동·교통 / 먹거리 / 볼거리·체험 / 정책·행정 / 응대·서비스 / 환경·청결

**행정이 대응하는 글은 반드시 「정책·행정」을 포함하세요.**
소재가 교통·숙박·환경이어도 큰 틀에서 행정 사안이므로 두 분야를 함께 답합니다.
(질문 3에서 '대응'으로 판정된 글은 거의 언제나 여기 해당합니다)

여행자가 겪은 일이 중심이면 그 소재 분야 하나만 고릅니다.

═══ 출력 ═══
설명 없이 JSON 배열만.
[{"i":0,"rel":true,"sent":"부정","cats":["치안·안전"],"why":"실종사건 불안"},
 {"i":1,"rel":true,"sent":"중립","cats":["정책·행정","이동·교통"],"why":"대책 추진"},
 {"i":2,"rel":false,"sent":"중립","cats":[],"why":"업체 광고"}]
why는 12자 이내."""


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
        raw  = o.get("cats")
        if not isinstance(raw, list):
            raw = [o.get("cat")]                     # 옛 형식도 받아 준다
        cats = []
        for c in raw:
            c = str(c or "").strip()
            if c in CATS and c not in cats: cats.append(c)
        cats = cats[:2]
        out[i] = {
            "rel":  bool(o.get("rel")),
            "sent": sent if sent in ("긍정", "부정", "중립") else "중립",
            "cat":  cats[0] if cats else "",          # 대표 분야
            "cats": cats,                             # 전체 분야
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

    pool = [x for x in items
            if (x.get("date") or "") >= cut
            and (x.get("llm") or {}).get("v") != VER]

    # 화면에 보이는 것부터 판정한다.
    # 분야별 부정 여론에 뜨는 건 '부정' 판정분이므로 그것이 1순위,
    # 그다음 긍정(홍보글이 섞여 비율을 흔든다), 마지막이 중립이다.
    def prio(x):
        s = x.get("sentiment")
        p = 0 if s == "부정" else (1 if s == "긍정" else 2)
        return (p, -(len(x.get("date") or "")), str(x.get("date") or ""))
    pool.sort(key=lambda x: (0 if x.get("sentiment") == "부정" else
                             1 if x.get("sentiment") == "긍정" else 2,
                             str(x.get("date") or "")), reverse=False)
    # 같은 우선순위 안에서는 최신 글부터
    pool.sort(key=lambda x: (0 if x.get("sentiment") == "부정" else
                             1 if x.get("sentiment") == "긍정" else 2,
                             "" if not x.get("date") else
                             "".join(chr(255 - ord(c)) for c in str(x["date"]))))
    todo = pool[:LIMIT]

    import collections as _c
    print("■ LLM 판정 — 남은 " + str(len(pool)) + "건 중 " + str(len(todo)) + "건 처리"
          + " (최근 " + str(DAYS) + "일)")
    print("   우선순위: " + str(dict(_c.Counter(x.get("sentiment") for x in todo))))
    if not todo:
        print("   판정할 항목이 없습니다"); return

    BUDGET = int(os.environ.get("LLM_BUDGET_SEC", "18000"))   # 5시간
    t0 = time.time()
    done = fail = 0
    for s in range(0, len(todo), BATCH):
        if time.time() - t0 > BUDGET:
            print("   시간 예산 도달 — 나머지는 다음 실행에서 이어갑니다")
            break
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
        if (s // BATCH) % 10 == 0:
            el = int(time.time() - t0)
            print("   " + str(min(s + BATCH, len(todo))) + "/" + str(len(todo))
                  + " · 성공 " + str(done) + " · 실패 " + str(fail)
                  + " · " + str(el // 60) + "분 경과")
        time.sleep(0.4)

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
        x["categories"] = j.get("cats") or ([j["cat"]] if j["cat"] else [])

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
