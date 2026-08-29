# -*- coding: utf-8 -*-
"""긍·부정 키워드 자동 추출 — data/keywords.json

수집된 글에서 자주 나온 표현을 뽑고, LLM이 감성을 판정한다.
사전을 사람이 손으로 채우지 않아도 데이터가 바뀌면 키워드도 따라 바뀐다.

주의: 사람 이름·지명 같은 고유명사는 LLM이 걸러 낸다.
      (실종사건 피해자 이름이 워드맵에 뜨는 일이 없어야 한다)

환경변수: HUB_API_KEY
"""
import json, os, re, ssl, time, urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

SRC   = os.path.join("data", "issue.json")
OUT   = os.path.join("data", "keywords.json")
HUB   = "https://open.hasa.re.kr/v1/templates/llm-chat/run"
MODEL = os.environ.get("HUB_MODEL", "exaone-4.0-32b")
KEY   = os.environ.get("HUB_API_KEY", "").strip()

KST  = timezone(timedelta(hours=9))
NOW  = datetime.now(KST)
DAYS = int(os.environ.get("KW_DAYS", "30"))
TOPN = int(os.environ.get("KW_TOPN", "160"))   # LLM에 물어볼 후보 수
MINN = int(os.environ.get("KW_MINN", "3"))     # 최소 등장 횟수

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

# 뜻이 없거나 흔해서 의미가 없는 말
STOP = set("""제주 제주도 서귀포 제주시 여행 관광 관광객 있다 없다 하다 되다 이다 그리고 하지만
위해 통해 대한 관련 지난 이번 오늘 내일 우리 사람 경우 정도 때문 생각 이런 저런 그런 가장
매우 정말 진짜 너무 조금 많이 다시 계속 바로 아주 함께 모두 여기 거기 저기 이제 지금 어제
그냥 좀더 그거 이거 저거 하는 하고 해서 에서 으로 에게 까지 부터 이라고 라고 했다 한다
합니다 입니다 대해 통해서 위한 있는 없는 같은 다른 여러 각종 관계자 기자 사진 제공 무단
전재 배포 금지 뉴스 기사 보도 오전 오후 시간 지역 도내 전국 국내 해외""".split())

WORD = re.compile(r"[가-힣]{2,6}")


def fetch_json(url, body, tries=3):
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    for t in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=90, context=CTX) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            print("   ! 호출 실패(" + str(t + 1) + "): " + str(e))
            time.sleep(2 + t * 3)
    return None


SYSTEM = """당신은 한국어 감성 표현을 가려내는 전문가입니다.
낱말 목록을 받아 각각이 '감성을 담은 표현'인지 판정해 JSON 배열로만 답하세요.

【채택할 것 — 감성 표현】
· 평가·느낌을 담은 형용사·동사·명사
  좋다 만족 친절 깨끗 가성비 편하다 아름답다 즐겁다 감동 여유 기대
  실망 불편 비싸다 불친절 불안 위험 부족 혼잡 논란 취소 지연 오염
· 변화·상태를 나타내며 좋고 나쁨이 분명한 말
  증가 감소 개선 악화 회복 급감 상승 하락

【버릴 것 — 감성이 없는 말】
· 사람 이름, 지명, 기관명, 상호 (예: 장미란, 애월, 제주공항, 신화월드)
· 사물·주제어 (예: 맛집, 숙소, 호텔, 렌터카, 실종, 경찰, 예산, 조례)
· 행위·절차어 (예: 발표, 개최, 신청, 접수) — 다만 중립 표현으로는 채택 가능
· 숫자·단위·날짜, 뜻이 모호한 조각

【감성 구분】
pos = 좋게 보는 표현 / neg = 나쁘게 보는 표현 / neu = 사실 전달·행정 절차
감성이 아예 없으면 keep을 false로 하세요.

【표기】
label에는 사전형(기본형)을 쓰세요. '맛있는·맛있었'는 '맛있다'로.

【출력】
설명 없이 JSON 배열만.
[{"i":0,"keep":true,"pol":"pos","label":"맛있다"},
 {"i":1,"keep":false,"pol":"","label":""}]"""


def ask(words):
    lines = [str(i) + ". " + w for i, w in enumerate(words)]
    msg = "다음 낱말을 판정하세요.\n\n" + "\n".join(lines)
    body = json.dumps({"inputs": {"message": msg, "system": SYSTEM,
                                  "use_web": "off", "model": MODEL}}).encode()
    d = fetch_json(HUB, body)
    if not d: return {}
    txt = (d.get("answer") or d.get("output") or d.get("result")
           or d.get("text") or d.get("response") or "").strip()
    m = re.search(r"\[[\s\S]*\]", txt)
    if not m: return {}
    try:
        arr = json.loads(m.group(0))
    except Exception:
        t = re.sub(r",\s*([\]}])", r"\1", m.group(0).replace("'", '"'))
        try: arr = json.loads(t)
        except Exception: return {}
    out = {}
    for o in arr:
        if not isinstance(o, dict): continue
        try: i = int(o.get("i"))
        except Exception: continue
        if not (0 <= i < len(words)): continue
        pol = str(o.get("pol") or "").strip()
        out[i] = {"keep": bool(o.get("keep")) and pol in ("pos", "neg", "neu"),
                  "pol": pol if pol in ("pos", "neg", "neu") else "",
                  "label": (str(o.get("label") or "").strip() or words[i])[:12]}
    return out


def main():
    if not os.path.exists(SRC):
        print(SRC + " 없음"); return
    items = json.load(open(SRC, encoding="utf-8")).get("items", [])
    cut = (NOW - timedelta(days=DAYS)).strftime("%Y-%m-%d")
    recent = [x for x in items if (x.get("date") or "") >= cut] or items
    print("■ 키워드 후보 추출 — 최근 " + str(DAYS) + "일 " + str(len(recent)) + "건")

    # 감성별로 따로 센다.
    # 전체 빈도로만 뽑으면 글이 많은 쪽(대개 긍정)이 후보를 독차지해
    # 부정 표현이 아예 후보에 못 들어간다.
    buckets = {"긍정": Counter(), "부정": Counter(), "중립": Counter()}
    total = Counter()
    for x in recent:
        t = (x.get("title") or "") + " " + (x.get("description") or "")
        ws = set(WORD.findall(t))
        b = buckets.get(x.get("sentiment") or "중립")
        for w in ws:
            if w in STOP: continue
            total[w] += 1
            if b is not None: b[w] += 1

    per = max(40, TOPN // 3)
    picked = []
    for name, c in buckets.items():
        got = [w for w, n in c.most_common() if n >= MINN][:per]
        picked += got
        print("   " + name + " 후보 " + str(len(got)) + "개")
    seen, cand = set(), []
    for w in picked:
        if w in seen: continue
        seen.add(w); cand.append((w, total[w]))
    cand.sort(key=lambda x: -x[1])
    print("   후보 합계 " + str(len(cand)) + "개 (최소 " + str(MINN) + "회 이상)")
    if not cand:
        print("   후보가 없습니다"); return

    if not KEY:
        print("HUB_API_KEY 미설정 — 판정을 건너뜁니다"); return

    # 기존 판정을 재사용해 호출을 줄인다
    prev = {}
    if os.path.exists(OUT):
        try:
            for k in json.load(open(OUT, encoding="utf-8")).get("all", []):
                prev[k["w"]] = k
        except Exception:
            prev = {}

    todo = [w for w, _ in cand if w not in prev]
    print("   새로 판정할 낱말 " + str(len(todo)) + "개 (재사용 "
          + str(len(cand) - len(todo)) + "개)")

    judged = dict(prev)
    B = 40
    for s in range(0, len(todo), B):
        chunk = todo[s:s + B]
        res = ask(chunk)
        for i, w in enumerate(chunk):
            r = res.get(i)
            judged[w] = {"w": w, "keep": bool(r and r["keep"]),
                         "pol": (r or {}).get("pol", ""),
                         "label": (r or {}).get("label", w)}
        print("   " + str(min(s + B, len(todo))) + "/" + str(len(todo)))
        time.sleep(0.5)

    # 사전형이 같으면 합친다 (맛있는·맛있었 → 맛있다)
    merged = {}
    for w, n in cand:
        j = judged.get(w)
        if not j or not j["keep"]: continue
        lab = j["label"] or w
        m = merged.setdefault(lab, {"label": lab, "pol": j["pol"], "n": 0, "words": []})
        m["n"] += n
        m["words"].append(w)

    words = sorted(merged.values(), key=lambda x: -x["n"])
    by = Counter(x["pol"] for x in words)

    os.makedirs("data", exist_ok=True)
    json.dump({"meta": {"updated": NOW.strftime("%Y-%m-%d %H:%M"),
                        "days": DAYS, "based_on": len(recent),
                        "count": len(words), "by": dict(by)},
               "words": words[:120],
               "all": list(judged.values())[:1200]},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("")
    print("채택 " + str(len(words)) + "개 · " + str(dict(by)))
    for k in ("pos", "neg", "neu"):
        top = [x["label"] + "(" + str(x["n"]) + ")" for x in words if x["pol"] == k][:10]
        print("  " + k + ": " + ", ".join(top))
    print("→ " + OUT)


if __name__ == "__main__":
    main()
