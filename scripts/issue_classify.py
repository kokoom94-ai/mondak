# -*- coding: utf-8 -*-
"""
제주관광 여론 판정 엔진 v8 — 3단 게이트
  1단계 관련성: 제주 관광과 관련 있나 (아니면 폐기)
  2단계 유형  : 뉴스/후기/광고/연예/행정 (광고·연예는 지수 제외)
  3단계 감성  : 긍정/부정/중립
※ 원인 추정·위험도 판단은 하지 않는다. 계산 결과만 낸다.
"""
import re
from issue_geo import (ADMIN, EMD, SPOT, EMD_BASE, AMBIG_EMD, TOURISM, TOUR_PLACE,
                 DAILY_PLACE, ENTERTAIN, AD, OTHER_REGIONS, geo_hit, geo_reason)

ENGINE_VERSION = "v9-20260826"

# ── 부정어 (가중치 3=강, 2=중, 1=약)
NEG = {
 "바가지":3,"폭리":3,"덤터기":3,"사기":3,"갑질":3,"불친절":3,"횡포":3,
 "최악":3,"다신 안":3,"두 번 다시":3,"환불 거부":3,"돈 아깝":3,"돈아깝":3,
 "비싸":2,"비쌌":2,"과하게":2,"터무니":2,"불쾌":2,"실망":2,"별로":2,"짜증":2,
 "불결":2,"더럽":2,"지저분":2,"위생 불량":2,"낡았":2,"노후":2,
 "기대 이하":2,"기대이하":2,"후회":2,"불편":1,"아쉽":1,"애매":1,"글쎄":1,
}
# ── 긍정어
POS = {
 "최고":3,"강추":3,"인생":2,"만족":2,"친절":2,"깨끗":2,"추천":2,"또 가고":3,
 "재방문":2,"좋았":2,"훌륭":2,"맛있":1,"예쁘":1,"멋지":1,"편했":1,"가성비":2,
}
# 사건 심각도 — 사건어는 그 자체로 부정 신호
INCIDENT_WEIGHT = {
 "사망":4,"숨져":4,"숨진":4,"실종":4,"익사":4,"성폭행":4,"살해":4,
 "추락":3,"화재":3,"붕괴":3,"조난":3,"고립":3,"폭행":3,"성추행":3,"마약":3,"흉기":3,"강도":3,
 "부상":2,"다쳐":2,"다친":2,"침수":2,"절도":2,"도난":2,"음주운전":3,"만취":2,"무면허":2,
 "검거":2,"붙잡":2,"입건":2,"구속":2,"고발":2,"수사":1,"적발":2,"단속":1,
}

# ── 사건·사고어 (뉴스 판정용)
INCIDENT = ["사망","숨져","숨진","실종","추락","익사","화재","붕괴","침수","조난","고립",
"부상","다쳐","다친","폭행","성추행","성폭행","마약","흉기","강도","절도","도난",
"음주운전","만취","무면허","검거","붙잡","입건","구속","수사","적발","단속","고발"]
# ── 행정 조치어
GOV_ACT = ["대책","개선","점검","단속","근절","정비","개편","시행","강화","캠페인","예방",
"방지","특별점검","합동점검","도입","마련","추진","조례","방침","계획","협약","지정","공모"]

# ══════════ 분류 축 ══════════
# 겹침을 없애기 위해 두 축으로 나눈다.
#   ① 분야(FIELD)  — 무엇에 관한 글인가 (관광객 여정 기준, 서로 배타적)
#   ② 성격(NATURE) — 어떤 종류의 글인가 (사건사고 / 불만·후기 / 정보·소식)
# 예) "렌터카 추돌 사고" → 분야: 이동·교통, 성격: 사건사고
#     "렌터카 비쌌다"    → 분야: 이동·교통, 성격: 불만·후기
# 이렇게 하면 '안전·사건사고'가 모든 걸 삼키는 문제가 사라진다.

FIELD = [
 ("이동·교통",   ["렌터카","렌트카","항공","비행기","공항","결항","지연","여객선","배편","버스","택시",
                "주차","도로","교통","자차","시외","공영주차","드라이브","길","정체","우회","견인","과속","음주운전","무면허"]),
 ("숙박",        ["호텔","펜션","리조트","게스트하우스","게하","민박","콘도","숙소","숙박","체크인","체크아웃",
                "객실","1박","예약금","노쇼","독채","한달살기"]),
 ("먹거리",      ["맛집","식당","음식","메뉴","횟집","고깃집","흑돼지","해산물","전복","갈치","한식","카페",
                "디저트","브런치","맛있","맛없","반찬","회","국수","김밥","커피","베이커리","술집","포차"]),
 ("볼거리·체험", ["관광지","오름","올레","해수욕장","해변","폭포","동굴","박물관","미술관","전망대","수목원",
                "테마파크","유원지","축제","공연","전시","체험","승마","잠수함","유람선","포토존","산책",
                "한라산","성산일출봉","우도","비양도","마라도","섭지코지","산방산","비자림","사려니","코스"]),
 ("비용·상거래", ["바가지","폭리","덤터기","요금","가격","물가","비싸","비쌌","대여료","입장료","숙박비",
                "환불","취소수수료","결제","계산","영수증","팁","추가금","할증","면세점","기념품","시장","쇼핑"]),
 ("응대·서비스", ["불친절","친절","갑질","응대","무례","태도","서비스","직원","사장님","안내","응답","고객",
                "예약 거부","입장 거부","차별"]),
 ("치안·안전",   ["실종","사망","숨져","숨진","익사","추락","조난","고립","화재","붕괴","침수","부상","다쳐",
                "폭행","성추행","성폭행","마약","흉기","강도","절도","도난","살해","검거","붙잡","입건","구속",
                "수사","적발","단속","고발","범죄","안전사고","위험","신고","경찰","해경","소방","구조"]),
 ("환경·청결",   ["쓰레기","청결","위생","더럽","지저분","불결","악취","오염","분리수거","벌레","곰팡이",
                "해양쓰레기","미세먼지","방역","소독"]),
 ("정책·행정",   ["조례","정책","행정","예산","도의회","도청","당국","공모","협약","지정","선정","추진",
                "제도","계획","고시","공고","시행","개편","입도세","환경보전분담금","관광청"]),
]

NATURE = [
 ("사건사고", ["실종","사망","숨져","숨진","익사","추락","조난","고립","화재","붕괴","침수","부상","다쳐",
             "폭행","성추행","성폭행","마약","흉기","강도","절도","도난","살해","검거","붙잡","입건","구속",
             "수사","적발","단속","고발","사고","구조","신고 접수"]),
 ("정보·소식", ["조례","정책","예산","도의회","공모","협약","지정","선정","추진","시행","개편","발표","계획",
             "고시","공고","모집","개최","운영","오픈","취항","증편","신설","확대"]),
]
# 위 둘에 안 걸리면 "불만·후기"

# 화면·지수에서 쓰는 분야 목록 (순서 = 표시 순서)
CATEGORY = FIELD

# ── 부정문·해소 표현 (부정어를 무력화)
NEG_CANCEL = [
 # 과거·전언 인용: "바가지니 하면서 방송에 나온 적이 있는데", "~다 뭐다 해서"
 r"[가-힣]{1,6}니\s?하(면서|며|는)",
 r"[가-힣]{1,6}이?다\s?뭐다\s?해서",
 r"(라는|다는)\s?(말|얘기|이야기|소리|기사|방송)",
 r"나온\s?적이?\s?있",
 r"(예전|과거|한때|당시|작년|재작년)에?[가-힣\s]{0,10}(논란|불거|있었)",
 r"논란이\s?(불거졌을\s?때|있었을\s?때)",
 r"바가지\s*요금?[가-힣\s]{0,8}(없|걱정|근절|방지|제거|차단|잡|퇴출|사라)",
 r"바가지[가-힣\s]{0,10}(없|않|아니|걱정.{0,4}(없|안)|근절|방지)",
 r"(사고|불편|문제|논란)[가-힣\s]{0,6}(없이|없었|없고|없다|않았)",
 r"걱정했는데[가-힣\s]{0,10}(괜찮|좋|만족)",
 r"안\s?[가-힣]{0,2}면\s?후회", r"놓치면\s?후회",
 r"(비싸|불친절|더럽)[가-힣\s]{0,4}(지\s?않|않았|않고)",
]
# ── 실물 바가지 (동음이의)
BAGAJI_LITERAL = r"한\s?바가지|바가지로\s?(떨어|받|퍼|끼얹)|물\s?바가지|바가지\s?물|박\s?바가지|바가지\s?머리"
# ── 동음이의 일반
HOMONYM = [(r"의\s?고장", "의 지역"), (r"폭탄\s?(계란|계란찜|주먹밥|세일)", "\\1"),
           (r"대박\s?(세일|할인)", "할인"), (r"(맛|말|예향)의\s?고장", "지역")]

def _norm(t):
    t = (t or "").lower()
    for pat, rep in HOMONYM:
        t = re.sub(pat, rep, t)
    for pat in NEG_CANCEL:
        t = re.sub(pat, " [해소] ", t)
    return t

# ══════════ 1단계 — 관련성 ══════════
def gate_relevance(title, body=""):
    """제주 관광 관련성. (통과여부, 사유)"""
    full = f"{title} {body}"
    if not geo_hit(full):
        return False, "제주 지역 신호 없음"
    # 전국 나열형
    if sum(1 for r in OTHER_REGIONS if r in title) >= 2:
        return False, "전국 나열형"
    t = full.lower()
    has_tour = any(w in t for w in TOURISM)
    has_inc  = any(w in t for w in INCIDENT)
    if has_tour:
        return True, "관광 맥락"
    if has_inc:
        # 사건인데 관광 맥락이 없으면 → 장소로 판단
        if any(w in t for w in TOUR_PLACE):
            return True, "관광 시설 사건"
        if any(w in t for w in DAILY_PLACE):
            return False, "일상 공간 사건"
        return None, "장소 불명 사건"      # None = 보류(반복 보도면 승격)
    if any(w in t for w in GOV_ACT):
        return True, "행정·정책"
    return False, "관광 맥락 없음"

# ══════════ 2단계 — 유형 ══════════
# 방송·유튜브가 '소개 매체'로 쓰인 경우는 연예가 아님
MEDIA_MENTION = [r"방송에\s?나온", r"방송\s?출연\s?맛집", r"tv에\s?나온", r"티비에\s?나온",
                 r"유튜브에\s?나온", r"백종원", r"맛집으로\s?소개", r"소개된\s?맛집"]
# 인물 인사·임명 기사 (관광 이슈 아님)
PERSONNEL = ["임용","임명","취임","승진","인사","전보","내정","위촉","선임","해임","사임 처리"]

def gate_type(title, body="", channel=""):
    t = f"{title} {body}".lower()
    ttl = title.lower()
    if any(w in ttl for w in PERSONNEL): return "인사"
    if any(re.search(p, t) for p in MEDIA_MENTION):
        pass                                  # 매체 언급일 뿐 → 연예 아님
    elif any(w in t for w in ENTERTAIN): return "연예"
    if any(w in t for w in AD):        return "광고"
    if any(w in t for w in INCIDENT):  return "사건"
    if any(w in t for w in GOV_ACT) and any(w in t for w in ["조례","정책","행정","예산","도의회","당국"]):
        return "행정"
    if channel in ("news",):           return "뉴스"
    return "후기"

# ══════════ 3단계 — 감성 ══════════
def bagaji_fare(t):
    if "바가지" not in t: return False
    if not re.sub(BAGAJI_LITERAL, "", t).count("바가지"): return False
    return any(w in t for w in ["요금","가격","값","비싸","상술","물가","씌","썼","당했","숙박비","대여료"])

def gate_sentiment(title, body="", typ=""):
    t = _norm(f"{title} {body}")
    neg = pos = 0
    reasons = []
    for w, wt in NEG.items():
        if w in t: neg += wt; reasons.append(w)
    if bagaji_fare(t): neg += 3; reasons.append("바가지(요금)")
    # 사건 유형이면 사건어 자체가 부정 신호 (제목에 있을 때만 — 본문 스침 방지)
    if typ == "사건":
        tt = _norm(title)
        for w, wt in INCIDENT_WEIGHT.items():
            if w in tt: neg += wt; reasons.append(w)
    for w, wt in POS.items():
        if w in t: pos += wt
    if neg >= 3 and neg > pos:      return "부정", neg, pos, list(dict.fromkeys(reasons))[:6]
    if neg >= 1 and neg > pos:      return "부정약", neg, pos, list(dict.fromkeys(reasons))[:6]
    if pos >= 3 and pos > neg:      return "긍정", neg, pos, []
    return "중립", neg, pos, []

def categorize(title, body=""):
    """분야 판정 — 제목을 우선하고, 없으면 본문에서 찾는다.
       여러 분야가 걸리면 제목에서 먼저 나온 쪽을 택한다."""
    ttl = (title or "").lower()
    bdy = (body or "").lower()
    # 1) 제목에서 가장 앞에 등장하는 분야
    best, pos = None, 10**9
    for name, ws in FIELD:
        for w in ws:
            k = ttl.find(w)
            if k >= 0 and k < pos: best, pos = name, k
    if best: return best
    # 2) 제목에 없으면 본문
    for name, ws in FIELD:
        if any(w in bdy for w in ws): return name
    return None

def nature(title, body=""):
    """성격 판정 — 사건사고 / 정보·소식 / 불만·후기"""
    t = f"{title} {body}".lower()
    for name, ws in NATURE:
        if any(w in t for w in ws): return name
    return "불만·후기"

# ══════════ 통합 ══════════
def judge(item):
    """item: {title, description, channel} → 판정 결과"""
    title = item.get("title") or ""
    body  = item.get("description") or ""
    ch    = item.get("channel") or ""
    rel, rel_why = gate_relevance(title, body)
    if rel is False:
        return {"keep": False, "stage": "관련성", "why": rel_why}
    typ = gate_type(title, body, ch)
    if typ in ("광고", "연예", "인사"):
        return {"keep": False, "stage": "유형", "why": typ}
    cat = categorize(title, body)
    sent, neg, pos, why = gate_sentiment(title, body, typ)
    # 카테고리가 없어도 후기·뉴스의 감성은 전체 지수에 반영한다.
    # 다만 카테고리별 순위에서는 빠진다(기타 카테고리를 만들지 않음).
    if cat is None and sent == "중립":
        return {"keep": False, "stage": "카테고리", "why": "분류 불가·중립"}
    nat = nature(title, body)
    return {"keep": True, "pending": rel is None, "type": typ, "category": cat, "nature": nat,
            "sentiment": "부정" if sent.startswith("부정") else sent,
            "strength": "강" if sent == "부정" else ("약" if sent == "부정약" else ""),
            "neg": neg, "pos": pos, "reasons": why,
            "rel_why": rel_why, "geo": geo_reason(f"{title} {body}")}
