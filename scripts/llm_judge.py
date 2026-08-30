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
VER   = "llm-v5"                                   # 판정 기준이 바뀌면 올린다

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

CATS = ["치안·안전", "비용·상거래", "숙박", "이동·교통", "먹거리",
        "볼거리·체험", "정책·행정", "응대·서비스", "환경·청결"]

SYSTEM = """당신은 제주 관광 여론을 분류하는 전문가입니다. 주어진 글 여러 건을 판정해 JSON 배열로만 답하세요.

【1단계 — 대상 여부(rel)】
"제주 여행·관광에 대한 여론"으로 볼 수 있을 때만 true입니다.

false로 판정해야 하는 것 (중요):
· **업체 홍보·광고성 글** — 렌터카·숙소·식당·투어·세차 등 상품이나 업체를 소개·추천하는 글.
  제목에 업체명·"추천"·"할인"·"이용 후기"가 있고 내용이 이용 안내·가격 소개면 광고입니다.
  협찬·제휴 후기, 예약 링크 유도 글도 광고입니다.
· **홍보성 언론보도** — 기사 형태여도 알리는 것이 목적인 글은 여론이 아닙니다.
  기관·기업이 낸 보도자료를 그대로 옮긴 기사,
  행사·축제·프로그램 개최 안내, 참가자·수상자 모집 공고,
  협약·업무협약(MOU) 체결, 개관·개장·출시 소식,
  시설 확충·예산 투입·사업 추진 계획 발표,
  기관장 인사말·수상 소식·표창·홍보대사 위촉,
  특정 업체·상품을 소개하는 기사(기사형 광고)
  → 이런 기사는 제주 관광에 대한 사람들의 평가가 아니므로 제외합니다.
· **도민 생활 서비스 광고** — 세차, 이사, 인테리어, 학원 등 여행과 무관한 지역 상권 홍보
· **다른 지역 일인데 제주가 비유·예시·부수적으로만 언급된 글**
  (예: 카자흐스탄 여행기의 "제주도에서 차 빌리듯", 김제시장 향응 의혹의 '제주여행' 언급)
· **타 지역 정치인·공무원의 연수·출장에 대한 지적**
· 제주점·부산점처럼 지점 나열에 제주가 들어간 광고
· 여행 정보를 담고 있어도 결국 특정 업체로 유도하는 글

true인 것:
· 여행자가 제주에서 실제로 겪은 일에 대한 소감·불만·후기(업체 홍보가 아닌 것)
· 제주 관광에 영향을 주는 사건·사고 보도 (실종·범죄·안전사고 등)
· 제주 관광의 실태를 취재하거나 문제를 지적한 보도
· 관광객 수·만족도 같은 지표의 변화를 다룬 보도
· 제주 관광정책에 대한 비판·평가·논쟁

판단 기준 한 줄: **"이 글은 알리려는 글인가, 평가하는 글인가."**
알리려는 글이면 false, 평가·경험·문제제기면 true입니다.

【2단계 — 감성(sent)】 긍정 / 부정 / 중립

**뉴스(보도)의 경우 — 「문제 → 대응 → 해결」 3단으로 봅니다**

하나의 사안은 대개 세 단계를 거칩니다. 기사가 **어느 단계를 다루는지**로 판정하세요.

· **부정 = 문제**
  제주 관광·여행에 문제가 있다고 드러내는 보도.
  "항공좌석 부족으로 관광객 불편", "바가지 요금 여전", "관광객 감소",
  "쓰레기 몸살", "불친절 민원 급증", "안전사고 잇따라"
  → 아직 해결되지 않은 문제가 기사의 핵심일 때

· **중립 = 대응**
  그 문제에 대해 무엇을 하겠다는 보도. 아직 결과는 나오지 않았습니다.
  "전담팀 출범", "TF 가동", "대책 추진", "협의회 개최", "용역 착수",
  "제도 개선 검토", "예산 편성", "긴급회의", "매뉴얼 마련"
  → 대응·계획·추진 단계는 성과가 아니므로 **긍정이 아니라 중립**입니다.
  (문제를 언급하며 시작해도, 기사의 핵심이 대응이면 중립입니다)

· **긍정 = 해결·성과**
  실제로 나아졌음이 확인된 보도.
  "항공좌석 늘었다", "항공료 내렸다", "관광객 증가", "만족도 상승",
  "대기시간 단축", "민원 줄었다", "재방문 의향 상승"
  → 결과가 수치나 사실로 확인될 때만 긍정입니다.

**주의**
· 제주 관광과 무관한 성과 보도는 긍정이 아니라 1단계에서 제외하세요.
  (예: 특정 항공사의 정시율 1위, 기업 실적 — 제주 노선이 스쳐 언급될 뿐이면 홍보성 기사입니다)
· "~하겠다·추진한다·마련한다·검토한다"는 거의 항상 중립입니다.
· "~늘었다·줄었다·개선됐다·나아졌다"처럼 결과가 있어야 긍정입니다.

**블로그·카페(개인 글)의 경우**
· 글쓴이가 제주에 대해 어떤 태도인지 **문장 전체의 방향**으로 판단하세요.
· "비싸다고 들었는데 막상 가보니 괜찮았다" → 긍정 (걱정이 해소된 것)
· "여기는 원래 비싸지만 저렴하게 가는 방법이 있다" → 긍정 또는 중립 (해법 제시)
· "가성비 최고였다", "만족했다" → 긍정
· 부정 낱말이 있어도 결론이 호의적이면 긍정입니다.
· 불만·실망·피해·불안·경고가 결론이면 부정입니다.
· 일정·경로·준비물만 정리한 정보성 글은 중립입니다.

【3단계 — 분야(cat)】 최대 두 개까지 고를 수 있습니다.

**행정이 대응하는 기사는 반드시 「정책·행정」을 포함하세요.**
제주도청·행정시가 대책을 세우거나 협의체·TF를 꾸리거나 제도를 고치는 기사는
소재가 교통·숙박·환경이어도 큰 틀에서 행정 사안입니다.
  "심야 교통대책 추진"        → 정책·행정, 이동·교통  (둘 다)
  "항공 접근성 협의체 추진"    → 정책·행정, 이동·교통  (둘 다)
  "숙박 요금 관리 강화 방안"   → 정책·행정, 숙박      (둘 다)
이런 기사는 감성도 **중립**입니다(대응 단계이므로).

반대로 여행자가 겪은 일이 중심이면 그 소재 분야 하나만 고르세요.
  "밤에 택시가 없어 한 시간 기다렸다"  → 이동·교통 (부정)
  "렌터카 직원이 친절했다"            → 이동·교통 (긍정)

고를 수 있는 분야:
치안·안전 / 비용·상거래 / 숙박 / 이동·교통 / 먹거리 / 볼거리·체험 / 정책·행정 / 응대·서비스 / 환경·청결
· 사건사고·범죄·실종·안전 → 치안·안전
· 물가·요금·바가지 → 비용·상거래
· 숙소에서 겪은 일 → 숙박
· 항공·버스·택시·렌터카 → 이동·교통
· 식당·음식 → 먹거리
· 관광지·체험·축제 → 볼거리·체험
· 제주도 관광정책·행정 → 정책·행정
  ※ 행정이 대응·대책·정책을 내놓는 기사는 소재가 교통·숙박이어도 **정책·행정**입니다.
     "심야 교통대책 추진", "항공좌석 전담팀 출범", "숙박 요금 관리 강화" → 정책·행정
     반대로 여행자가 실제로 겪은 불편·경험이 중심이면 그 소재의 분야입니다.
     "밤에 택시가 없어 한 시간 기다렸다" → 이동·교통
· 종사자 응대·친절 → 응대·서비스
· 쓰레기·오버투어리즘·난개발 → 환경·청결

【출력 형식】
설명 없이 JSON 배열만 출력하세요.
[{"i":0,"rel":true,"sent":"부정","cats":["치안·안전"],"why":"실종사건 불안"},
 {"i":1,"rel":true,"sent":"중립","cats":["정책·행정","이동·교통"],"why":"교통대책 추진"},
 {"i":2,"rel":false,"sent":"중립","cats":[],"why":"렌터카 업체 광고"}]
cats는 최대 2개이며, 행정 대응 기사는 첫 번째에 "정책·행정"을 두세요.
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
