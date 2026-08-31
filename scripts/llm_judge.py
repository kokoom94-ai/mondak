# -*- coding: utf-8 -*-
"""이슈체크 LLM 판정기 v9 — Hasa AI Hub(open.hasa.re.kr)로 관련성·감성·분야를 판정하고,
판정 결과를 코드가 다시 점검한다.

v8까지의 문제: 판정 기준(프롬프트)만 고쳐 왔고, 새는 글은 사람이 발견해야만 드러났다.
v9에서 바뀐 것
  ① LLM이 「평가·문제 삼는 대상(who)」과 「확신(conf)」을 반드시 적는다.
  ② 판정 뒤 코드가 점검한다 (audit).
       A 대상 불일치 — who가 다른 지역·기관인데 rel=true            → 제외
       B 알림글      — who가 '없음'이거나 근거가 홍보·개최·모집 등        → 제외
       C 제주 부재   — 제목·본문 어디에도 제주가 없음                     → 제외
       D 저확신      — conf=낮음                                          → 제외
       E 감성 불일치 — sent와 why의 방향이 어긋남                         → 재판정
       G 분야 없음   — rel=true인데 분야가 비어 있음                      → 재판정
     재판정 뒤에도 어긋나면 중립으로 두고 표시를 남긴다.
  ③ 점검 결과와 판정 실패 원문을 data/issue_audit.json 에 남긴다.
     화면 확인 없이도 무엇이 왜 빠졌는지 파일로 볼 수 있다.
  ④ 판정 실패 묶음은 1건이 될 때까지 반으로 쪼개 다시 묻는다.

환경변수: HUB_API_KEY (Cloudflare Worker와 같은 키). 키가 없으면 판정은 건너뛰고 점검만 한다.
사용:  python scripts/llm_judge.py            판정 + 점검
       python scripts/llm_judge.py --audit    점검만 (API 호출 없음)
"""
import json, os, re, ssl, sys, time, urllib.request, collections
from datetime import datetime, timedelta, timezone

HUB   = "https://open.hasa.re.kr/v1/templates/llm-chat/run"
MODEL = os.environ.get("HUB_MODEL", "exaone-4.0-32b")
KEY   = os.environ.get("HUB_API_KEY", "").strip()

SRC   = os.path.join("data", "issue.json")
AUD   = os.path.join("data", "issue_audit.json")
BATCH = int(os.environ.get("LLM_BATCH", "8"))
LIMIT = int(os.environ.get("LLM_LIMIT", "99999"))
DAYS  = int(os.environ.get("LLM_DAYS", "60"))
VER   = "llm-v9"                                   # 판정 기준이 바뀌면 올린다
AUDIT_ONLY = "--audit" in sys.argv

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

CATS = ["치안·안전", "비용·상거래", "숙박", "이동·교통", "먹거리",
        "볼거리·체험", "정책·행정", "응대·서비스", "환경·청결"]

SYSTEM = """당신은 제주 관광 여론을 분류합니다. 아래 세 질문을 순서대로 던져 판정하고,
JSON 배열로만 답하세요. 예시는 이해를 돕는 참고일 뿐, 판단은 항상 질문으로 하세요.

═══ 질문 1. 이 글은 누구에 대한 글인가? (who · rel) ═══
**"이 글이 다루는 대상, 평가하거나 문제 삼는 상대가 누구인가"**를 먼저 물으세요.
그 대상을 who 에 12자 이내로 적으세요. (예: "제주 식당", "제주도 행정", "부안군의회", "김제시장", "없음")
그 대상이 제주(제주도·제주 관광업계·제주를 찾은 여행자)가 아니면 rel=false 입니다.
제주에서 일어난 일이라도, 따지는 상대가 제주가 아니면 제주 여론이 아닙니다.

false 인 경우
 · **대상이 다른 지역의 사람·기관인 글**
   타 지역 의회·지자체·정치인·기업·경찰의 처신을 다루는 기사는, 제주가 그 무대·계기였더라도
   그 지역의 문제입니다. 제주는 장소로만 등장합니다.
   (다른 지역 의원들의 제주 연수·출장, 다른 지역 인사의 제주 관련 의혹,
    제주 사건을 계기로 다른 지역 경찰이 점검한다는 기사)
 · 제주가 비유·예시·나열의 하나로만 스쳐 나옴
   (다른 곳 사건과 제주를 함께 묶은 기사, 여행업계·증권가 전반 동향에 제주가 사례로 나온 것,
    지점 나열에 제주점이 포함된 것, 다른 곳 여행기에 제주가 비유로 나온 것, 연예인 방송 논란)
 · 제주에서 일어났어도 여행·관광과 무관 (지역 상권 광고, 주민 생활 서비스)

판별이 헷갈리면 이렇게 물으세요.
"이 기사를 읽고 고개를 숙여야 할 쪽이 제주인가, 다른 곳인가."
다른 곳이면 false 이고, who 에는 그 '다른 곳'을 적으세요.

═══ 질문 2. 알리는 글인가, 평가하는 글인가? ═══
**알리는 글이면 rel=false, who="없음" 입니다.** 여론이 아니라 발표·홍보이기 때문입니다.
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

개인 글은 **문장 전체가 향하는 방향**으로 봅니다. 부정 낱말이 있어도 결론이 호의적이면
긍정입니다. ("비싸다고 들었는데 가보니 괜찮았다" → 걱정이 해소됐으므로 긍정)
일정·준비물만 정리한 정보성 글은 중립입니다.

═══ 분야 (cats) — 최대 2개 ═══
치안·안전 / 비용·상거래 / 숙박 / 이동·교통 / 먹거리 / 볼거리·체험 / 정책·행정 / 응대·서비스 / 환경·청결
**행정이 대응하는 글은 반드시 「정책·행정」을 포함하세요.**
소재가 교통·숙박·환경이어도 큰 틀에서 행정 사안이므로 두 분야를 함께 답합니다.
(질문 3에서 '대응'으로 판정된 글은 거의 언제나 여기 해당합니다)
여행자가 겪은 일이 중심이면 그 소재 분야 하나만 고릅니다.
rel=true 이면 cats 는 비워 두지 마세요.

═══ 확신 (conf) ═══
"높음" 또는 "낮음". 다음 중 하나라도 자신이 없으면 "낮음"입니다.
 · 대상이 제주인지 다른 곳인지   · 알림글인지 평가글인지   · 감성의 방향
낮음으로 표시된 글은 목록에서 빠지므로, 근거가 분명할 때만 높음으로 답하세요.

═══ 출력 ═══
설명 없이 JSON 배열만. why 는 12자 이내로 '판정 근거'를 적습니다.
[{"i":0,"rel":true,"who":"제주 치안","sent":"부정","cats":["치안·안전"],"why":"실종사건 불안","conf":"높음"},
 {"i":1,"rel":true,"who":"제주도 행정","sent":"중립","cats":["정책·행정","이동·교통"],"why":"대책 추진","conf":"높음"},
 {"i":2,"rel":false,"who":"부안군의회","sent":"중립","cats":[],"why":"타지역 연수 논란","conf":"높음"},
 {"i":3,"rel":false,"who":"없음","sent":"중립","cats":[],"why":"업체 광고","conf":"높음"}]
"""

# ── 점검 규칙에 쓰는 낱말 ────────────────────────────────────────────
JEJU = re.compile(r"제주|서귀포|탐라|도내|도정|도의회|JTO|관광공사|한라|우도|성산|애월|중문|한림|조천|구좌|대정|안덕|남원|표선|한경|추자|마라|가파")
# 다른 지역·기관 — who에 이것이 있고 제주 낱말이 없으면 '대상 불일치'
NONJEJU = re.compile(r"서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|"
                     r"김제|부안|군산|익산|정읍|완주|고창|순창|임실|무주|진안|장수|"
                     r"목포|여수|순천|나주|광양|담양|곡성|구례|고흥|보성|화순|장흥|강진|해남|영암|무안|함평|영광|장성|완도|진도|신안|"
                     r"경주|포항|안동|구미|영주|영천|상주|문경|경산|울릉|울진|영덕|청도|칠곡|성주|고령|봉화|예천|의성|군위|청송|영양|"
                     r"창원|진주|통영|사천|김해|밀양|거제|양산|의령|함안|창녕|고성|남해|하동|산청|함양|거창|합천|"
                     r"춘천|원주|강릉|동해|태백|속초|삼척|홍천|횡성|영월|평창|정선|철원|화천|양구|인제|고성군|양양|"
                     r"청주|충주|제천|보은|옥천|영동|증평|진천|괴산|음성|단양|"
                     r"천안|공주|보령|아산|서산|논산|계룡|당진|금산|부여|서천|청양|홍성|예산|태안|"
                     r"수원|성남|고양|용인|화성|평택|안산|안양|시흥|파주|김포|의정부|광명|하남|양주|남양주|오산|이천|구리|안성|포천|의왕|양평|여주|동두천|과천|가평|연천|"
                     r"타지역|타 지역|다른 지역|타지자체|타 지자체")
ANN_WHO  = re.compile(r"광고|홍보|협찬|제휴|보도자료|개최|모집|공고|출시|개관|개장|체결|협약|위촉|시상|수상|임명|취임|발표|안내|소개|출범|론칭|런칭")
# why 에 대한 알림 판정은 좁게 본다 — 블로그의 '명소 소개'·'주차장 안내'는 방문기·정보성 글이지 홍보가 아니다
ANN_WHY  = re.compile(r"광고|홍보|협찬|제휴|보도자료|개최|모집|공고|출시|개관|개장|체결|협약|위촉|시상|임명|취임|출범|론칭|런칭")
POS_WHY = re.compile(r"호평|만족|추천|성과|개선|회복|긍정|칭찬|좋았|즐거|힐링|가성비")
NEG_WHY = re.compile(r"불만|불안|비판|논란|피해|실망|우려|의혹|위험|사망|실종|불편|취소|감소|사고|바가지|불친절|부족|혼잡|오염|훼손")
NOWHO   = re.compile(r"^(없음|해당 ?없음|없다|-|—|N/?A)$", re.I)

FAIL_SAMPLES = []          # (건수, 응답 앞부분) — 왜 파싱이 실패했는지 남긴다

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
        if not isinstance(raw, list): raw = [o.get("cat")]
        cats = []
        for c in raw:
            c = str(c or "").strip()
            if c in CATS and c not in cats: cats.append(c)
        cats = cats[:2]
        conf = str(o.get("conf") or "").strip()
        out[i] = {
            "rel":  bool(o.get("rel")),
            "who":  str(o.get("who") or "")[:20].strip(),
            "sent": sent if sent in ("긍정", "부정", "중립") else "중립",
            "cat":  cats[0] if cats else "",
            "cats": cats,
            "why":  str(o.get("why") or "")[:30],
            "conf": "낮음" if conf.startswith("낮") else ("높음" if conf else ""),
            "v":    VER,
        }
    return out

def make_prompt(items, notes=None):
    lines = []
    for i, x in enumerate(items):
        t = (x.get("title") or "").strip()[:90]
        d = (x.get("description") or "").strip()[:220]
        ch = {"blog": "블로그", "cafe": "카페", "news": "뉴스"}.get(x.get("channel"), x.get("channel") or "")
        s = "[" + str(i) + "] (" + ch + ") 제목: " + t + "\n     본문: " + d
        if notes and notes.get(i): s += "\n     ※ " + notes[i]
        lines.append(s)
    return "다음 " + str(len(items)) + "건을 판정하세요.\n\n" + "\n\n".join(lines)

def judge_chunk(chunk, notes=None):
    """묶음을 판정한다. 실패하면 1건이 될 때까지 반으로 쪼개 다시 묻는다."""
    txt = call_hub(make_prompt(chunk, notes))
    res = parse_answer(txt, len(chunk))
    if res: return res
    if len(chunk) == 1:
        if len(FAIL_SAMPLES) < 20:
            FAIL_SAMPLES.append({"title": chunk[0].get("title", "")[:60],
                                 "resp": (txt or "(빈 응답)")[:300]})
        return {}
    half = len(chunk) // 2
    out = {}
    for off, part in ((0, chunk[:half]), (half, chunk[half:])):
        sub = {}
        if notes: sub = {k - off: v for k, v in notes.items() if off <= k < off + len(part)}
        r2 = judge_chunk(part, sub or None)
        for k, v in r2.items(): out[k + off] = v
        time.sleep(0.4)
    return out

# ── 판정 뒤 점검 ─────────────────────────────────────────────────────
def flags_of(x):
    """rel=true 로 채택된 항목에서 수상한 점을 찾는다. (규칙, 설명, 조치) 목록.
    조치는 LLM이 스스로 적은 값(who·conf)에서 나온 것만 '제외'하고,
    코드가 낱말로 짐작한 것(why 의 알림성, 감성 불일치, 분야 없음)은 '재판정'으로 돌린다."""
    j = x.get("llm") or {}
    if not j.get("rel"): return []
    who, why, sent = j.get("who") or "", j.get("why") or "", j.get("sent") or ""
    text = (x.get("title") or "") + " " + (x.get("description") or "")
    f = []
    if who:
        if NOWHO.match(who) or ANN_WHO.search(who):
            f.append(("B", "대상 없음/홍보: " + who, "drop"))
        elif NONJEJU.search(who) and not JEJU.search(who):
            f.append(("A", "대상이 제주 아님: " + who, "drop"))
    if ANN_WHY.search(why) and not NEG_WHY.search(why):
        f.append(("B", "알림성 근거: " + why, "recheck"))
    if not JEJU.search(text):
        f.append(("C", "제목·본문에 제주 없음", "drop"))
    if j.get("conf") == "낮음":
        f.append(("D", "저확신", "drop"))
    if sent == "긍정" and NEG_WHY.search(why) and not POS_WHY.search(why):
        f.append(("E", "긍정인데 근거가 부정: " + why, "recheck"))
    if sent == "부정" and POS_WHY.search(why) and not NEG_WHY.search(why):
        f.append(("E", "부정인데 근거가 긍정: " + why, "recheck"))
    if not j.get("cats"):
        f.append(("G", "분야 없음", "recheck"))
    return f

RULE_NAME = {"A": "대상 불일치", "B": "알림글", "C": "제주 부재", "D": "저확신",
             "E": "감성 불일치", "G": "분야 없음"}

def audit(items, can_call):
    """채택된 항목을 점검해 제외·재판정·표시한다. 점검 결과 요약을 돌려준다."""
    cnt = collections.Counter(); samples = collections.defaultdict(list)
    recheck = []
    def record(x, fl):
        j = x["llm"]
        for c, d, a in fl:
            cnt[c] += 1
            if len(samples[c]) < 40:
                samples[c].append({"rule": RULE_NAME[c], "note": d, "action": "제외" if a == "drop" else "재판정",
                                   "title": (x.get("title") or "")[:80], "link": x.get("link", ""),
                                   "channel": x.get("channel"), "who": j.get("who"), "why": j.get("why"),
                                   "sent": j.get("sent"), "conf": j.get("conf")})
    for x in items:
        j = x.get("llm")
        if not j or j.get("v") != VER or not j.get("rel"): continue
        fl = flags_of(x)
        j["flags"] = [c for c, _, _ in fl]
        if not fl: continue
        record(x, fl)
        drops = [d for c, d, a in fl if a == "drop"]
        if drops:
            j["rel"] = False; j["audit_drop"] = drops[0]; cnt["dropped"] += 1
        elif not j.get("rechecked"):              # 두 번째 의견은 한 번만 받는다
            recheck.append(x)

    # 재판정 — 코드가 짐작으로 표시한 것만, 표시한 이유를 적어 다시 묻는다
    if recheck and can_call:
        print("■ 재판정 " + str(len(recheck)) + "건")
        for s in range(0, len(recheck), 4):
            chunk = recheck[s:s + 4]
            notes = {}
            for i, x in enumerate(chunk):
                j = x["llm"]
                notes[i] = ("앞선 판정 rel=true, sent=" + j.get("sent", "") + ", 근거='" + j.get("why", "")
                            + "', cats=" + json.dumps(j.get("cats") or [], ensure_ascii=False)
                            + " — 점검에서 '" + "; ".join(d for c, d, a in flags_of(x)) + "'가 지적됐습니다."
                            + " 질문 1~3을 다시 던져 판정하세요.")
            res = judge_chunk(chunk, notes)
            for i, x in enumerate(chunk):
                if i in res:
                    new = res[i]; new["rechecked"] = True; new["flags_before"] = x["llm"].get("flags", [])
                    x["llm"] = new; cnt["rechecked"] += 1
            time.sleep(0.4)
    # 재판정 뒤 다시 본다. 여전히 어긋나면 안전한 쪽으로 둔다.
    # (재판정을 못 한 경우 — 키 없음·--audit·예산 소진 — 에는 제외하지 않고 표시만 남긴다)
    for x in recheck:
        j = x["llm"]
        if not j.get("rel"):                      # 재판정이 관련 없다고 봤다
            cnt["dropped"] += 1; continue
        fl = flags_of(x); j["flags"] = [c for c, _, _ in fl]
        if not fl: continue
        drops = [d for c, d, a in fl if a == "drop"]
        if drops:                                 # 재판정에서 who·conf 로 스스로 걸러졌다
            j["rel"] = False; j["audit_drop"] = drops[0]; cnt["dropped"] += 1; continue
        codes = [c for c, _, _ in fl]
        if "B" in codes and j.get("rechecked"):   # 두 번 물어도 알림성 근거 → 제외
            j["rel"] = False; j["audit_drop"] = [d for c, d, a in fl if c == "B"][0]; cnt["dropped"] += 1; continue
        if "E" in codes: j["sent"] = "중립"
        if "G" in codes and not j.get("cats"):
            j["cats"] = ["정책·행정"] if x.get("channel") == "news" else ["볼거리·체험"]
            j["cat"] = j["cats"][0]
        j["unresolved"] = codes; cnt["unresolved"] += 1
    return cnt, samples

def apply(data, items):
    """LLM 판정을 실제 분류에 반영하고, 관련 없는 항목을 목록에서 뺀다."""
    changed = 0
    for x in items:
        j = x.get("llm")
        if not j or j.get("v") != VER: continue
        if not x.get("llm_prev"):
            x["llm_prev"] = {"sentiment": x.get("sentiment"), "category": x.get("category")}
        if not j["rel"]:
            x["keep"] = False
            x["drop_why"] = "점검: " + j["audit_drop"] if j.get("audit_drop") else "LLM: " + (j.get("why") or "관련 없음")
            continue
        x["keep"] = True
        if x.get("sentiment") != j["sent"]:
            x["sentiment"] = j["sent"]; changed += 1
        if j.get("cat") and x.get("category") != j["cat"]:
            x["category"] = j["cat"]
        x["categories"] = j.get("cats") or ([j["cat"]] if j.get("cat") else [])
    before = len(items)
    items = [x for x in items if x.get("keep") is not False]
    data["items"] = items
    return items, changed, before - len(items)

def main():
    if not os.path.exists(SRC):
        print(SRC + " 없음"); return
    data = json.load(open(SRC, encoding="utf-8"))
    items = data.get("items") or []
    can_call = bool(KEY) and not AUDIT_ONLY
    done = fail = 0
    BUDGET = int(os.environ.get("LLM_BUDGET_SEC", "18000"))
    t0 = time.time()

    if can_call:
        cut = (NOW - timedelta(days=DAYS)).strftime("%Y-%m-%d")
        pool = [x for x in items
                if (x.get("date") or "") >= cut
                and (x.get("llm") or {}).get("v") != VER]
        # 화면에 보이는 것부터: 부정 → 긍정 → 중립, 같은 우선순위 안에서는 최신 글부터
        pool.sort(key=lambda x: (0 if x.get("sentiment") == "부정" else
                                 1 if x.get("sentiment") == "긍정" else 2,
                                 "" if not x.get("date") else
                                 "".join(chr(255 - ord(c)) for c in str(x["date"]))))
        todo = pool[:LIMIT]
        print("■ LLM 판정 — 남은 " + str(len(pool)) + "건 중 " + str(len(todo)) + "건 처리 (최근 " + str(DAYS) + "일)")
        print("   우선순위: " + str(dict(collections.Counter(x.get("sentiment") for x in todo))))
        for s in range(0, len(todo), BATCH):
            if time.time() - t0 > BUDGET:
                print("   시간 예산 도달 — 나머지는 다음 실행에서 이어갑니다"); break
            chunk = todo[s:s + BATCH]
            res = judge_chunk(chunk)
            for i, x in enumerate(chunk):
                if i in res: x["llm"] = res[i]; done += 1
                else: fail += 1
            if (s // BATCH) % 10 == 0:
                print("   " + str(min(s + BATCH, len(todo))) + "/" + str(len(todo))
                      + " · 성공 " + str(done) + " · 실패 " + str(fail)
                      + " · " + str(int(time.time() - t0) // 60) + "분 경과")
            time.sleep(0.4)
    else:
        print("■ " + ("점검만 실행 (--audit)" if AUDIT_ONLY else "HUB_API_KEY 미설정 — 판정을 건너뛰고 점검만 합니다"))

    # ── 점검 (재판정은 예산이 남았을 때만)
    cnt, samples = audit(items, can_call and time.time() - t0 < BUDGET)
    items, changed, dropped = apply(data, items)

    meta = data.setdefault("meta", {})
    meta["llm"] = {"version": VER, "model": MODEL, "judged": done, "failed": fail,
                   "dropped": dropped, "audit_dropped": cnt.get("dropped", 0),
                   "updated": NOW.strftime("%Y-%m-%d %H:%M")}
    json.dump(data, open(SRC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    judged_all = [x for x in items if (x.get("llm") or {}).get("v") == VER]
    audit_out = {
        "meta": {"version": VER, "updated": NOW.strftime("%Y-%m-%d %H:%M"), "mode": "audit" if not can_call else "judge",
                 "judged_this_run": done, "failed_this_run": fail,
                 "judged_total": len(judged_all), "items_total": len(items),
                 "conf": dict(collections.Counter((x["llm"].get("conf") or "미기재") for x in judged_all)),
                 "sent": dict(collections.Counter(x["llm"].get("sent") for x in judged_all))},
        "rules": {c: {"name": RULE_NAME[c], "n": cnt.get(c, 0)} for c in RULE_NAME},
        "dropped": cnt.get("dropped", 0), "rechecked": cnt.get("rechecked", 0), "unresolved": cnt.get("unresolved", 0),
        "samples": {RULE_NAME[c]: samples[c] for c in samples},
        "fail_samples": FAIL_SAMPLES,
        "note": "samples 는 규칙별 최대 40건. 제외된 글은 issue.json 에서 빠지고 여기 기록만 남습니다.",
    }
    json.dump(audit_out, open(AUD, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("")
    print("판정 성공 " + str(done) + " · 실패 " + str(fail))
    print("점검: " + " · ".join(RULE_NAME[c] + " " + str(cnt.get(c, 0)) for c in RULE_NAME)
          + " → 제외 " + str(cnt.get("dropped", 0)) + " · 재판정 " + str(cnt.get("rechecked", 0))
          + " · 미해결 " + str(cnt.get("unresolved", 0)))
    print("감성 바뀜 " + str(changed) + "건 · 목록에서 제외 " + str(dropped) + "건")
    print("남은 " + str(len(items)) + "건 감성: " + str(dict(collections.Counter(x.get("sentiment") for x in items))))
    print("→ " + SRC + " · " + AUD)

if __name__ == "__main__":
    main()
