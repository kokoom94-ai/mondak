# -*- coding: utf-8 -*-
"""
제주관광 여론 LLM 판정 v2 — Claude가 문맥으로 최종 분류한다.

왜 LLM인가
  규칙 엔진은 단어 매칭이라 문맥을 못 본다. 실측된 실패들:
    · 인사 기사 본문의 "과거 바가지요금 논란 때 대응했다" → 비용·상거래 부정
    · "'불친절 섬'은 옛말" (울릉도 기사)              → 응대·서비스 부정
    · "[제주아닌] 동남아여행지 추천"                   → 제주 비용 불만
    · "제주 숙박시설 화재안전조사" (행정 점검)          → 숙박 부정
    · "성수기 바가지 요금은 피하고 싶고" (회피 성공)     → 부정
  전부 인용·과거·반전·배제 판정이라 규칙으로는 원리적으로 못 잡는다.

비용 설계 — 「예산 0원」 표기를 지키기 위해
  ① 배치 API      : 토큰 단가 50% (24시간 내 처리. 주간·30일 지수라 지연은 무해)
  ② 프롬프트 캐싱 : 고정 시스템 프롬프트 재사용
  ③ 캐시 파일     : 한 번 판정한 글은 두 번 부르지 않는다
  ④ 본문 절삭     : 판정에 필요한 만큼만 보낸다
  ⑤ 규칙 1차 필터 : 명백한 무관 글은 LLM에 보내지 않는다

동작 (GitHub Actions 하루 2회 실행에 맞춘 2단계 구조)
  실행 N   : 대기 중인 배치가 있으면 결과를 회수 → 새 배치 제출
  실행 N+1 : 그 배치를 회수 → 다시 제출 …
  제출 직후 LLM_WAIT_SEC 동안은 같은 실행에서 기다려 본다(대개 1시간 내 완료).
  못 받으면 다음 실행에서 회수하고, 그동안 화면은 규칙 판정으로 버틴다(폴백).

실행
  ANTHROPIC_API_KEY=... python scripts/llm_classify.py
"""
import os, sys, json, time, urllib.request, urllib.error

HERE  = os.path.dirname(os.path.abspath(__file__))
# 판정 대상 — 이슈체크(issue)와 관광AX(ax)를 같은 엔진으로 처리한다.
#   python scripts/llm_classify.py       → 이슈체크
#   python scripts/llm_classify.py ax    → 관광AX
TARGET = (sys.argv[1] if len(sys.argv) > 1 else "issue").strip().lower()
if TARGET not in ("issue", "ax"): TARGET = "issue"

SRC   = os.path.join(HERE, "..", "data", f"{TARGET}.json")
CACHE = os.path.join(HERE, "..", "data", f"{TARGET}_llm_cache.json")
STATE = os.path.join(HERE, "..", "data", f"{TARGET}_llm_batch.json")

API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL    = os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")
BATCH    = int(os.environ.get("LLM_BATCH", "20"))       # 한 요청에 담을 글 수
MAX_NEW  = int(os.environ.get("LLM_MAX_NEW", "2000"))   # 1회 실행 판정 상한(비용 안전장치)
WAIT_SEC = int(os.environ.get("LLM_WAIT_SEC", "900"))   # 제출 후 대기 상한(초)
SYNC     = os.environ.get("LLM_SYNC", "") == "1"        # 배치 대신 즉시 호출
BODY_CUT = 140                                          # 본문 절삭 길이

API = "https://api.anthropic.com/v1"
HDR = {"content-type": "application/json",
       "x-api-key": API_KEY,
       "anthropic-version": "2023-06-01"}

FIELDS = ["응대·서비스","비용·상거래","환경·청결","이동·교통","숙박",
          "먹거리","볼거리·체험","치안·안전","정책·행정"]

SYSTEM = """당신은 제주 관광 여론 분석가입니다. 수집된 글을 한 건씩 판정합니다.

## 판정 목적
제주 여행·관광 과정에서 생긴 불만·불편·신고와, 제주 관광에 타격을 줄 수 있는 사건을 가려냅니다.
최종 목적은 "어느 분야를 정책으로 보완해야 하는가"를 읽어내는 것입니다.

## 반드시 제외(keep=false)
- 인사·임명·지명·낙점·표창 기사. 본문에 과거 관광 이슈가 언급돼도 그 기사의 주제는 인사입니다.
  예: "민선 9기 첫 서귀포시장에 김희찬 전 관광국장 지명" — 본문에 바가지요금이 나와도 제외.
- 주어가 제주가 아닌 글. 제주를 비교 대상으로만 언급한 타지역 기사.
  예: "'불친절 섬'은 옛말…울릉도 바다에 빠진 관광객들" — 울릉도 기사이므로 제외.
- 글쓴이가 제주가 아니라고 밝힌 글. 예: "[제주아닌] 동남아여행지 추천해주세요"
- 광고·홍보·체험단·협찬 글, 연예 가십, 부동산·법률·대출 영업글.
- 관광과 무관한 사건. 제주에서 일어났을 뿐인 가정폭력·조직범죄 등.
  단 관광객이 당사자이거나 관광지·숙박시설에서 일어난 사건은 포함합니다.

## 감성(sentiment)
- "부정" : 글쓴이가 실제로 겪었거나 보도된 문제·불만·피해·사건.
- "긍정" : 만족·추천.
- "중립" : 정보 전달, 판단 유보.

부정이 아닌 것 — 특히 주의하십시오.
- 과거 논란의 회고: "당시 바가지요금 논란이 불거졌을 때 대응했다"
- 부정을 뒤집는 표현: "'불친절 섬'은 옛말", "걱정했는데 괜찮았다"
- 문제를 피하는 데 성공한 후기: "성수기 바가지 요금은 피하고 싶어서 비수기에 갔다"
- 행정의 점검·대책 발표: "제주 숙박시설 불시 화재안전조사" — 대응 소식이므로 track="info", 중립.
- 인용된 남의 말이 글쓴이의 주장이 아닌 경우

## 분야(category)
응대·서비스 / 비용·상거래 / 환경·청결 / 이동·교통 / 숙박 / 먹거리 / 볼거리·체험 / 치안·안전 / 정책·행정
그 글이 무엇에 관한 것인지로 정합니다. 제목이 사건이면 치안·안전입니다.
애매하면 null. 억지로 채우지 마십시오.

## 트랙(track)
- "voice" : 겪은 사람이 직접 쓴 글(블로그·카페·스레드·유튜브). 정책 근거가 됩니다.
- "risk"  : 사건·사고 보도. 관광 이미지 타격 감시용입니다.
- "info"  : 행정·홍보 소식. 지수에서 제외됩니다.

## 사건 식별자(event_key)
같은 사건을 다룬 글에는 같은 짧은 한글 문자열을 부여하십시오.
예: "한림 실종사건", "평화로 렌터카 화재". 서로 다른 사건은 반드시 다르게 씁니다.
사건 보도가 아니면 null. 같은 사건이 여러 매체에 실려도 하나로 세기 위한 값입니다.

## 출력
JSON 배열만 출력합니다. 설명·머리말·코드펜스를 붙이지 마십시오.
{"id":1,"keep":true,"track":"voice","category":"이동·교통","sentiment":"부정","event_key":null,"why":"렌터카 인수 지연 후기"}
why는 20자 이내 한글 한 줄입니다."""

AX_ORG_TAGS = ["부처","공사","지자체","지역관광","우리","유관","민간","해외"]
AX_TOPICS = ["AI 여행플래너·추천","챗봇·컨시어지","수요예측·관광 빅데이터","스마트관광도시",
             "다국어·번역·통역","접근성·관광약자","마케팅 자동화","관광 데이터 플랫폼",
             "AI 인프라·거버넌스","콘텐츠 제작 AI"]

SYSTEM_AX = """당신은 관광 분야 인공지능 전환(AX) 동향 분석가입니다.
수집된 보도자료를 한 건씩 판정합니다.

## 목적
"어느 기관이 관광 AX의 어떤 주제를 추진하고 있는가"를 정리해,
제주관광공사가 벤치마킹할 지점을 찾는 것입니다.

## 반드시 제외(keep=false)
- 관광과 무관한 AI 기사. 제조·의료·국방·교육 등 다른 분야의 AI 도입.
- AI·디지털 전환과 무관한 관광 기사. 단순 행사·인사·실적 발표.
- 개인 블로그·광고·홍보성 글, 언론 칼럼·사설.
- 같은 내용을 여러 매체가 받아쓴 중복 보도 중 두 번째 이후(event_key로 묶습니다).

## 기관(org)
기사의 주체가 되는 기관명을 정확히 씁니다. 예: "문화체육관광부", "한국관광공사",
"제주관광공사", "서울관광재단", "제주특별자치도".
korea.kr(정책브리핑)에 실린 기사는 도메인이 아니라 본문에 나온 부처를 따릅니다.
확인되지 않으면 null. 추측하지 마십시오.

## 기관 유형(org_tag)
부처 / 공사 / 지자체 / 지역관광 / 우리(제주관광공사) / 유관 / 민간 / 해외

## 주제(topic) — 하나만 고릅니다
AI 여행플래너·추천 / 챗봇·컨시어지 / 수요예측·관광 빅데이터 / 스마트관광도시 /
다국어·번역·통역 / 접근성·관광약자 / 마케팅 자동화 / 관광 데이터 플랫폼 /
AI 인프라·거버넌스 / 콘텐츠 제작 AI
어디에도 맞지 않으면 null. 억지로 채우지 마십시오.

## 단계(stage)
"발표" (계획·구상 발표) / "추진" (사업 착수·시범) / "운영" (실제 서비스 중) / "성과" (결과·실적)

## 마일스톤(milestone)
관광 AX의 이정표가 될 만한 건이면 true. 최초 도입, 대규모 사업, 제도·지침 신설 등.
일상적 소식이면 false. 남발하지 마십시오.

## 사건 식별자(event_key)
같은 발표를 여러 매체가 다룬 경우 같은 짧은 한글 문자열을 부여합니다.
예: "문체부 AI 여행플래너 시범". 아니면 null.

## 요약(summary)
보도자료에서 확인되는 내용만 40자 이내로 요약합니다.
확인되지 않는 것은 쓰지 않습니다. 추측·평가·전망을 넣지 마십시오.

## 출력
JSON 배열만 출력합니다. 설명·머리말·코드펜스를 붙이지 마십시오.
{"id":1,"keep":true,"org":"한국관광공사","org_tag":"공사","topic":"챗봇·컨시어지","stage":"운영","milestone":false,"event_key":null,"summary":"외국인 대상 생성형 AI 관광안내 챗봇 개시"}"""


def _req(url, data=None, method=None, timeout=120):
    r = urllib.request.Request(url, data=(json.dumps(data).encode() if data else None),
                               headers=HDR, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return f.read().decode()


def build_params(chunk):
    """한 요청의 payload. 시스템 프롬프트는 캐싱 대상으로 표시한다.
       모델별 최소 캐시 토큰에 못 미치면 캐싱은 자동으로 무시된다."""
    payload = [{"id": i, "채널": x["ch"], "제목": x["t"], "본문": x["b"][:BODY_CUT]}
               for i, x in enumerate(chunk)]
    return {"model": MODEL, "max_tokens": 4000, "temperature": 0,
            "system": [{"type": "text", "text": (SYSTEM_AX if TARGET == "ax" else SYSTEM),
                        "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user",
                          "content": "다음 글을 판정하십시오.\n" +
                                     json.dumps(payload, ensure_ascii=False)}]}


def parse_text(txt):
    txt = (txt or "").strip()
    if txt.startswith("```"):
        p = txt.split("```")
        txt = p[1] if len(p) > 1 else txt
        if txt.startswith("json"): txt = txt[4:]
    return json.loads(txt.strip())


def valid(r):
    if not isinstance(r, dict): return False
    if TARGET == "ax":
        if r.get("org_tag") not in AX_ORG_TAGS + [None]: return False
        if r.get("topic") not in AX_TOPICS + [None]: return False
        if r.get("stage") not in ("발표","추진","운영","성과",None): return False
        return True
    return (r.get("sentiment") in ("부정", "긍정", "중립")
            and r.get("track") in ("voice", "risk", "info")
            and r.get("category") in FIELDS + [None])


def store(cache, key, r):
    if TARGET == "ax":
        cache[key] = {"keep": bool(r.get("keep", True)),
                      "org": r.get("org"), "org_tag": r.get("org_tag"),
                      "topic": r.get("topic"), "stage": r.get("stage"),
                      "milestone": bool(r.get("milestone")),
                      "event_key": r.get("event_key"),
                      "summary": (r.get("summary") or "")[:80]}
        return
    cache[key] = {"keep": bool(r.get("keep", True)), "track": r["track"],
                  "category": r["category"], "sentiment": r["sentiment"],
                  "event_key": r.get("event_key"), "why": (r.get("why") or "")[:40]}


# ─────────────────────────── 배치 ───────────────────────────
def batch_submit(chunks):
    reqs = [{"custom_id": cid, "params": build_params(items)} for cid, _keys, items in chunks]
    d = json.loads(_req(f"{API}/messages/batches", {"requests": reqs}))
    return d["id"]


def batch_status(bid):
    return json.loads(_req(f"{API}/messages/batches/{bid}"))


def batch_results(url):
    """결과는 JSONL. 한 줄이 한 요청."""
    out = {}
    for line in _req(url, timeout=300).splitlines():
        line = line.strip()
        if not line: continue
        try: rec = json.loads(line)
        except Exception: continue
        res = rec.get("result") or {}
        if res.get("type") != "succeeded": continue
        msg = res.get("message") or {}
        txt = "".join(c.get("text", "") for c in msg.get("content", []) if c.get("type") == "text")
        out[rec.get("custom_id")] = txt
    return out


def harvest(bid, keymap, cache):
    """배치 결과를 회수해 캐시에 넣는다. 아직 처리 중이면 False."""
    st = batch_status(bid)
    if st.get("processing_status") != "ended":
        print(f"  배치 {bid} 진행 중 {st.get('request_counts')}")
        return False
    got = batch_results(st["results_url"])
    n = 0
    for cid, txt in got.items():
        keys = keymap.get(cid) or []
        try: arr = parse_text(txt)
        except Exception:
            print(f"  {cid} 파싱 실패 — 규칙 판정 유지"); continue
        by = {r.get("id"): r for r in arr if isinstance(r, dict)}
        for i, k in enumerate(keys):
            r = by.get(i)
            if valid(r): store(cache, k, r); n += 1
    print(f"  회수 완료 · {n}건 반영 (요청 {st.get('request_counts')})")
    return True


# ─────────────────────────── 즉시 호출(폴백) ───────────────────────────
def sync_run(chunks, cache):
    n = 0
    for i, (_cid, keys, items) in enumerate(chunks, 1):
        try:
            d = json.loads(_req(f"{API}/messages", build_params(items)))
            txt = "".join(c.get("text", "") for c in d.get("content", []) if c.get("type") == "text")
            arr = parse_text(txt)
        except Exception as e:
            print(f"  묶음 {i} 실패 ({e}) — 규칙 판정 유지"); time.sleep(3); continue
        by = {r.get("id"): r for r in arr if isinstance(r, dict)}
        for j, k in enumerate(keys):
            r = by.get(j)
            if valid(r): store(cache, k, r); n += 1
        print(f"  {i}/{len(chunks)} · 누적 {n}건")
        time.sleep(0.4)
    return n


# ─────────────────────────── 본체 ───────────────────────────
def apply_cache(d, cache):
    key = lambda x: (x.get("link") or x.get("title") or "").strip()
    out, dropped = [], 0
    for x in d["items"]:
        c = cache.get(key(x))
        if not c:
            x["judge"] = "rule"; out.append(x); continue
        if not c["keep"]:
            dropped += 1; continue
        if TARGET == "ax":
            x.update({k: c.get(k) for k in
                      ("org","org_tag","topic","stage","milestone","event_key","summary")})
            x["judge"] = "llm"
        else:
            x.update({"track": c["track"], "category": c["category"],
                      "sentiment": c["sentiment"], "event_key": c.get("event_key"),
                      "why": c.get("why"), "judge": "llm"})
        out.append(x)
    d["items"] = out
    d["meta"]["llm"] = {"model": MODEL, "mode": "sync" if SYNC else "batch",
                        "judged": sum(1 for x in out if x.get("judge") == "llm"),
                        "rule_fallback": sum(1 for x in out if x.get("judge") == "rule"),
                        "dropped_by_llm": dropped}
    return d


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    if not API_KEY:
        print("ANTHROPIC_API_KEY 없음 — 규칙 판정을 그대로 둡니다.")
        return

    cache = {}
    if os.path.exists(CACHE):
        try: cache = json.load(open(CACHE, encoding="utf-8"))
        except Exception: cache = {}
    state = {}
    if os.path.exists(STATE):
        try: state = json.load(open(STATE, encoding="utf-8"))
        except Exception: state = {}

    # ── 1단계 : 지난 실행이 남긴 배치를 회수
    if state.get("id"):
        print(f"■ 대기 중인 배치 회수 · {state['id']}")
        try:
            if harvest(state["id"], state.get("map") or {}, cache):
                state = {}
        except Exception as e:
            print(f"  회수 실패 ({e}) — 다음 실행에서 재시도")

    # ── 2단계 : 신규 판정 대상
    key = lambda x: (x.get("link") or x.get("title") or "").strip()
    inflight = set()
    for ks in (state.get("map") or {}).values(): inflight.update(ks)
    todo = [x for x in d["items"]
            if key(x) and key(x) not in cache and key(x) not in inflight]
    print(f"■ [{TARGET}] 전체 {len(d['items'])}건 · 캐시 {len(cache)}건 · 신규 대상 {len(todo)}건")
    if len(todo) > MAX_NEW:
        print(f"  상한 {MAX_NEW}건까지만(최신순). 나머지는 다음 실행에서.")
        todo = sorted(todo, key=lambda x: x.get("date") or "", reverse=True)[:MAX_NEW]

    chunks = []
    for i in range(0, len(todo), BATCH):
        part = todo[i:i+BATCH]
        chunks.append((f"c{i//BATCH:04d}",
                       [key(x) for x in part],
                       [{"ch": x.get("channel",""), "t": x.get("title",""),
                         "b": x.get("description","") or ""} for x in part]))

    if chunks and not state.get("id"):
        if SYNC:
            print(f"■ 즉시 호출 {len(chunks)}묶음")
            sync_run(chunks, cache)
        else:
            print(f"■ 배치 제출 {len(chunks)}묶음 · {len(todo)}건 (단가 50%)")
            try:
                bid = batch_submit(chunks)
                keymap = {cid: keys for cid, keys, _ in chunks}
                state = {"id": bid, "map": keymap, "submitted": time.time()}
                print(f"  배치 {bid} 제출됨")
                waited = 0
                while waited < WAIT_SEC:
                    time.sleep(30); waited += 30
                    try:
                        if harvest(bid, keymap, cache):
                            state = {}; break
                    except Exception as e:
                        print(f"  회수 오류 ({e})"); break
                if state.get("id"):
                    print(f"  {WAIT_SEC}초 내 미완료 — 다음 실행에서 회수합니다.")
            except Exception as e:
                print(f"  배치 제출 실패 ({e}) — 규칙 판정 유지")
    elif state.get("id"):
        print("  이전 배치가 아직 처리 중이라 이번 실행은 제출을 건너뜁니다.")

    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    if state.get("id"):
        json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
    elif os.path.exists(STATE):
        os.remove(STATE)

    d = apply_cache(d, cache)
    json.dump(d, open(SRC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    from collections import Counter
    m = d["meta"]["llm"]
    print(f"\nLLM 판정 {m['judged']}건 · 규칙 폴백 {m['rule_fallback']}건 · LLM이 제외 {m['dropped_by_llm']}건")
    if TARGET == "ax":
        print("  기관:", dict(Counter(x.get("org") for x in d["items"]).most_common(6)))
        print("  주제:", dict(Counter(x.get("topic") for x in d["items"]).most_common(6)))
        print("  마일스톤:", sum(1 for x in d["items"] if x.get("milestone")), "건")
    else:
        print("  감성:", dict(Counter(x["sentiment"] for x in d["items"])))
        print("  트랙:", dict(Counter(x.get("track") for x in d["items"])))
    print("저장:", os.path.relpath(SRC))


if __name__ == "__main__":
    main()
