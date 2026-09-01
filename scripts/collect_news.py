#!/usr/bin/env python3
"""몬딱 새소식 수집기 v3 — 제주 관련성 필터 + 매체수 집계 수정판.
v2 버그 수정: (1)동일제목을 군집 前 삭제해 매체수가 못 늘던 문제 (2)무관 기사 유입 (3)한국어 제목 군집 정밀도"""
import json, re, ssl, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET
from pathlib import Path

KST=timezone(timedelta(hours=9)); NOW=datetime.now(KST)
OUT=Path(__file__).resolve().parent.parent/"data"/"news.json"

LOCAL_FEEDS=[("헤드라인제주","https://www.headlinejeju.co.kr/rss/allArticle.xml"),
 ("뉴스제주","https://www.newsjeju.net/rss/allArticle.xml"),
 ("제주의소리","https://www.jejusori.net/rss/allArticle.xml"),
 ("뉴스N제주","https://newsnjeju.com/rss/allArticle.xml"),
 ("제주일보","https://www.jejunews.com/rss/allArticle.xml")]
GOOGLE_QUERIES=["제주도 when:14d","제주도청 OR 제주도의회 when:14d","제주 관광 when:14d",
 "제주 (AI OR 스타트업) when:14d","제주 (복지 OR 돌봄) when:14d",
 "제주 (감귤 OR 농업 OR 어업) when:14d","제주 (환경 OR 에너지) when:14d","제주 (사고 OR 폭우 OR 안전) when:14d"]

# ── 분류부 v2 (2026-08-31) ─────────────────────────────────────────
# 이전 판은 낱말 안의 낱말이 걸려 오분류가 났다.
#   "중기부 장관"→기부, "천상의"→상의, "제주가"→주가
# 그리고 행정 낱말이 교육·관광·복지 기사를 가로챘다.
# v2는 (1) 짧은 낱말에 앞뒤 조건을 달고 (2) 분야가 뚜렷한 것을 먼저 보고
#        (3) 도·시의 대응·발표는 맨 마지막에 가져간다.
SEC_EDU  = "교육/청년"
SEC_AGRI = "1차산업"
SEC_CULT = "문화/관광/스포츠"
SEC_WELF = "복지/사회서비스"
SEC_SAFE = "안전/민원행정"
SEC_ENV  = "환경/에너지"
SEC_TECH = "신산업/AX"
SEC_BIZ  = "창업/경제"
SEC_GOV  = "정치/행정"
SEC_ETC  = "사건사고/기타"

# ── 짧아서 오작동하는 낱말: 앞뒤를 함께 본다 ──────────────────────
GUARD = {
    # '중기부'의 기부 / '기부금·기부채납'은 진짜 기부
    # '중기부'의 부(部) 앞 글자가 '기'라서 '기부'가 걸린다 → 바로 앞 한 글자를 본다
    "기부": r"(?<!중)기부",
    # '천상의·합의·협의'의 상의 / 진짜는 상공회의소
    "상의": r"상공회의소|제주상의\b",
    # '제주가·전주가'의 주가 / 진짜는 증시
    "주가": r"주가\s*(상승|하락|급등|급락|폭락|반등|약세|강세)|코스피|코스닥|증시",
    # '통상적으로'의 통상 / 진짜는 무역
    "통상": r"통상(?!적)",
    # '고용노동부'는 행정, '고용 창출·고용률'은 경제
    "고용": r"고용(률|창출|지표|한파|불안|안정)|일자리",
    # '비어가든·장어가게'의 어가 / 진짜는 어업 가구
    "어가": r"(?<![가-힣])어가|어가(소득|인구|수|당)",
    # '당근마켓'의 당근 / 진짜는 작물
    "당근": r"당근(?!마켓)",
}
def g(name):
    return GUARD[name]

# ── 분야별 낱말 (뚜렷한 것부터) ─────────────────────────────────
# 1) 수사·범죄 — 어떤 낱말이 섞여도 사건사고
P_CRIME = (r"국과수|부검|시신|숨진 채|사망 사고|살해|피살|변사|"
           r"영장|구속영장|체포영장|검찰 송치|압수수색|입건|피의자|"
           r"구속 기소|불구속|징역|집행유예|벌금형|법정 구속|성범죄|사기 혐의")

# 1-2) 체육이 주제인 글 — '교실·프로그램' 같은 낱말 때문에 교육으로 새지 않게 먼저 본다
P_SPORT = (r"체육회|생활체육|체육대회|체전|스포츠클럽|선수단|국가대표|"
           r"축구단|야구단|배구단|농구단|리그전|우승|준우승|메달")

# 2) 교육/청년 — 학교·대학·학생·교육청, 그리고 청년정책
P_EDU = (r"[가-힣]{2,}(초|중|고)등학교|[가-힣]{2,}(초|중|고)교[ ,·]|[가-힣]{2,}(초|중|고)[,·]|"
         r"학생|교사|교직원|교장|교감|학부모|학교|학급|교실|"
         r"교육청|교육감|교육지원청|교육과정|공교육|사교육|방과후|늘봄|돌봄교실|"
         r"입학|졸업|수업|수능|입시|학업|학폭|진로|진학|장학|장학금|"
         r"유치원|어린이집 교사|보육교사|"
         r"대학교|대학생|대학원|총장|캠퍼스|산학협력|학과|전공|"
         r"[가-힣]{2,}(국립대|과학대|여대|전문대|사이버대)|제주대|한라대|국제대|"
         r"런케이션|워크캠프|교환학생|유학생|어학연수|"
         r"청년[가-힣]{0,4}(사업|지원|정책|일자리|주택|수당|센터|창업|공간)|청년드림|청년정책|"
         r"청소년|동아리|오케스트라|학예|기숙사|IB |국제바칼로레아|학교급식|"
         r"평생교육|직업교육|특성화고|마이스터고|교육위원회|교육활동|도서관|독서|"
         r"검정고시|교직|교원|퇴임|임용|교육지원|교육 프로그램|체험학습|산림교육|"
         r"[가-힣]{2,}교육|어린이집|유아")

# 3) 1차산업
P_AGRI = (r"감귤|만감류|한라봉|천혜향|레드향|황금향|풋귤|바나나|망고|키위|블루베리|"
          r"품종 개발|신품종|재배|육묘|하우스 재배|수매|출하|작황|병해충|방제|"
          r"농가|" + g("어가") + r"|양식장|축산농가|영농|파종|수확|월동무|" + g("당근") + r"|메밀|브로콜리|"
          r"농협|수협|축협|영농조합|농어촌|농촌|어촌|귀농|귀어|농지|직불금|"
          r"조업|어선|해녀 조업|양돈|한우|흑우|말산업|마사회|구제역|럼피스킨")

# 3-2) 첨단기술이 주제인 글 — 1차산업 낱말이 스쳐도 이쪽이 먼저다
#      ("제주 최대 수출품, 감귤 아닌 반도체" 가 '감귤' 때문에 1차산업으로 갔다)
P_TECH_STRONG = (r"반도체|첨단단지|첨단산업|첨단산단|데이터센터|우주산업|우주기업|위성 발사|발사체|"
                 r"UAM|자율주행|블록체인|메타버스|양자|슈퍼컴퓨터|국가AI|AI 승부수")

# 4) 문화/관광/스포츠 — 축제·행사·전시·관광·체육
#    '박람회·페스타·프로모션'을 여기로 되돌린다(전에는 창업/경제가 가져갔다)
P_CULT = (r"관광|여행|입도객|렌터카|렌트카|크루즈|올레길|둘레길|워케이션|면세|MICE|"
          r"축제|페스티벌|페스타|박람회|엑스포|잔치|한마당|경연|가요제|영화제|비엔날레|"
          r"공연|전시|展|기획전|개인전|초대전|작품전|사진전|콘서트|리사이틀|음악제|"
          r"박물관|미술관|갤러리|도서관 프로그램|북토크|문학상|등단|출간|펴내|출판|저서|"
          r"문화|예술|공예|한복|국악|합창|무용|연극|뮤지컬|밴드|뮤지션|래퍼|피아니스트|"
          r"스포츠|체육|선수|구단|리그|감독|경기장|마라톤|대회|전국체전|아시안게임|올림픽|"
          r"파크골프|게이트볼|생활체육|동호회|러닝|라이딩|자전거|미니벨로|골프장|"
          r"해수욕장 개장|캠핑장|휴양림|생태관광|트레킹|한라산 탐방|"
          r"해녀|잠녀|무형유산|국가유산|유네스코|설문대할망|만장굴|비자림|"
          r"호텔|리조트|숙박업|게스트하우스|프로모션|이벤트 개최|관람객|방문객|"
          r"제주SK|제주유나이티드|K리그|프로축구|프로배구|프로농구|승점|골 넣|무승부|"
          r"노선|취항|증편|감편|운항|직항|결항|여객선|항공권|탑승객|기항|"
          r"단체전|정기전|기념식|기념행사|[가-힣]{2,}의 날|학술대회|학회|연수회|강연|특강|"
          r"북토크|프로그램 진행|체험 프로그램|대행진|호국|숭고한|반려견|반려동물|"
          r"특별전|개막|오페라|성악|서예가|작가|시인|화백|공연장|"
          r"관광객|관광지|관광정책|관광진흥|전국노래자랑|가요제")

# 4-2) 주거 정책 — 주택·전세·임대는 행정(주거복지 부서 소관이지만 발표 형식이 행정)
P_HOUSE = (r"주택전세자금|전세자금|주거급여|임대주택|공공주택|주택 공급|주거 지원|"
           r"주택 정책|분양|재개발|재건축|주거환경|빈집 정비")

# 4-3) 대회·행사 이름에 분야 낱말이 섞인 경우 — 행사가 먼저다
#      ("전국(장애인)체전 성공기원 …" 이 '장애' 때문에 복지로 갔다)
P_EVENT = (r"체전|전국체육대회|장애인체육|생활체육대회|성공\s?기원|성황리|개막식|폐막식|"
           r"워터밤|비어가든|불꽃축제|야시장|플리마켓|버스킹|퍼레이드")

# 5) 복지/사회서비스·보건
P_WELF = (r"복지|돌봄|요양|경로당|무료 급식|무료급식|"
          r"어르신|노인|장애인|취약계층|저소득|한부모|결식|다문화|위기가구|"
          r"복지 사각|사회보장|보육료|아동수당|자립 지원|긴급복지|생계급여|의료급여|기초생활|"
          r"봉사|나눔|후원|성금|위문|" + g("기부") + r"|기탁|기증|"
          r"보건소|보건의료|건강검진|예방접종|금연|정신건강|자살예방|"
          r"모유|수유|산모|산후|임산부|난임|출산|출생아|출산율|저출생|다자녀|영유아|"
          r"의료원|병원|응급실|진료|간호|감염병|백신 접종|"
          r"무연고|장사시설|봉안|공설묘지|화장장|적십자|헌혈|사례관리")

# 6) 안전/민원행정 — 재난·치안·단속·생활안전
P_SAFE = (r"태풍|호우|폭우|폭설|풍랑|너울|강풍|한파|폭염|지진|해일|산사태|침수|"
          r"주의보|경보 발령|특보|대피|기상|무더위|열대야|온열질환|최저기온|"
          r"소방|화재|폭발|산불|구조 활동|해경|119|민방위|안전대책|안전 점검|안전관리|"
          r"CCTV|방범|순찰|치안|범죄 예방|실종 예방|수색|"
          r"번호판[^,]{0,10}영치|영치|불법 주정차|과태료|계도|단속|음주단속|과속|"
          r"어린이보호구역|횡단보도|신호등|교통사고|식중독|식품안전|위생 점검|부적합 판정|회수 조치|"
          r"민원 처리|불편 신고|누수|정전|붕괴|"
          r"실종|수색|구조|안전 이상|더위|날씨|천둥|안개|호우 예보|비 예보|"
          r"숨져|숨진|사망|익사|추락|고립|표류|응급 이송|정체전선|장맛비|소나기|기온|"
          r"경찰|파출소|지구대|부실 대응|초기 대응")

# 7) 환경/에너지
P_ENV = (r"환경|에너지|탄소|탄소중립|재생에너지|신재생|그린수소|수소차|수소충전|"
         r"풍력|태양광|전기차|하이브리드|충전 인프라|충전요금|충전소|BESS|에너지저장|"
         r"재활용|일회용|다회용|폐기물|자원순환|분리배출|매립장|소각장|"
         r"오폐수|하수처리|악취|미세먼지|용천수|유수율|난방전기화|히트펌프|"
         r"생태계 보전|생태 복원|생태공원|생물다양성|습지|보전지역|곶자왈 보전|자연자원|정원도시|기후위기|친환경|"
         r"플로깅|정화 활동|정화활동|해변정화|줍깅|숲|산림|버섯|상어|해양생물|"
         r"곤충|시민과학|모니터링|서식지|멸종위기|외래종")

# 8) 신산업/AX — '우주박물관' 같은 관광시설은 위(4)에서 이미 걸러진다
P_TECH = (r"인공지능|\bAI\b|AX|디지털 전환|빅데이터|데이터센터|클라우드|"
          r"UAM|드론|위성 발사|발사체|우주산업|우주센터|블록체인|메타버스|로봇|자율주행|"
          r"반도체|바이오헬스|신소재|R&D|연구개발|기술 실증|규제자유특구|첨단산업|첨단산단|첨단기술|"
          r"첨단|우주기업|위성|광통신|국제자유도시|JDC")

# 9) 창업/경제 — 좁게: 창업·기업·투자·상권·수출·고용
P_BIZ = (r"창업|스타트업|벤처|엑셀러레이터|액셀러레이터|투자유치|투자 유치|시드 투자|"
         r"소상공인|자영업|상권|골목상권|전통시장 상인|매출|폐업|휴업|"
         r"기업 유치|기업 지원|중소기업|대기업|법인 설립|"
         r"수출|" + g("통상") + r"|판로|무역|관세|FTA|바이어|"
         r"경기 침체|경기 회복|물가|소비 심리|내수|경제 성장|경제 지표|"
         + g("주가") + r"|" + g("상의") + r"|" + g("고용") + r"|"
         r"은행|금융 지원|대출|이자 보전|테크노파크|제주TP|창업보육|시제품|기술이전|"
         r"소비심리|소비자심리|실물경기|산업생산|판매 부진|경기 지표|"
         r"판촉|해외 진출|현지 법인|신용보증|보증재단|우수기업|물류|항만 물류|뱃길|해운 항로")

# 10) 정치/행정 — 인사·의회·정치권·정책 대응/발표
P_GOV_STRONG = (r"인사청문|청문회|경과보고서|"
                r"(도지사|부지사|시장|교육감|청장|사장|원장|의장|장관|차관)\s?(후보자?|내정자?|지명|임명|사퇴|취임)|"
                r"국회의원|의원[,·]|의원은|의원이|여당|야당|당대표|최고위|국정감사|행정사무감사|"
                r"국민의힘|더불어민주당|조국혁신당|진보당|무소속|공천|선거|출마|정치권|"
                r"상임위|예결위|본회의|도의회|시의회|조례안|예산안|추경|"
                r"특별법|법률안|입법 예고|공동성명|공동건의|대정부 건의|국회 통과|시행령|국정과제|"
                r"초광역|특별자치|메가시티|지방시대|균형발전|행정수도|행정체제|"
                r"감찰|자체 감사|감사원|정관계|유착 의혹|"
                r"제2공항|공항 건설|고도제한|도시계획|용도지역|지구단위|개발사업|유원지|관광단지 조성|재시동|정상화|"
                r"트램|경전철|버스 노선 개편|준공영제|교통체계|도로 개설|우회도로|"
                r"주간업무회의|업무보고회|이·통장|주민자치위원|대기발령|직위해제|전보 인사|정기 인사|승진 임용|"
                r"공무원|위촉|현판식|협약|MOU|자매결연|기자회견|논평|성명서|"
                r"4·3|4\.3|위령제|추념|보훈|국가유공자|병무청|"
                r"민주당|양성평등|성평등|주민자치회|교부금|국비 지원|국비 확보|예산 확보|대정부|"
                r"도정질문|도정 질문|교육행정 질문|교육행정질문|정책토론회|현장 행정|정치인|"
                r"포럼|세미나|심포지엄|공청회|간담회|협의체|추진단|위원회 개최|"
                r"국비|건의|기자수첩|칼럼|사설|민심|도지사|시장[,·]|정부 요청|국가와 함께")

# 11) 도·시의 대응·발표 — 분야가 드러나지 않은 나머지 행정 행위
# 주어(도·시)와 동사 사이의 거리를 재지 않는다. 전에는 14자를 넘으면 놓쳤다
#  (실측: "제주도, 민선9기 100일 '97개 과제' 추진과정 공개" 가 기타로 갔다)
P_GOV_SUBJ = r"(제주도|제주특별자치도|제주시|서귀포시|도교육청|행정시|도정|시정)"
P_GOV_VERB = (r"(모집|공모|접수|시행|추진|도입|확대|개선|지정|선정|운영|실시|마련|발표|공개|"
              r"점검|대응|대책|계획|용역|착수|개최|협의|검토|지급|지원|나선|밝혀|추진과정)")

ORDER = [
    (P_CRIME, SEC_ETC),
    (P_SPORT, SEC_CULT),
    (P_EDU,   SEC_EDU),
    (P_TECH_STRONG, SEC_TECH),
    (P_AGRI,  SEC_AGRI),
    (P_CULT,  SEC_CULT),
    (P_EVENT, SEC_CULT),
    (P_HOUSE, SEC_GOV),
    (P_WELF,  SEC_WELF),
    (P_SAFE,  SEC_SAFE),
    (P_ENV,   SEC_ENV),
    (P_TECH,  SEC_TECH),
    (P_BIZ,   SEC_BIZ),
    (P_GOV_STRONG, SEC_GOV),
]
ORDER = [(re.compile(p), s) for p, s in ORDER]
RE_GOV_SUBJ = re.compile(P_GOV_SUBJ)
RE_GOV_VERB = re.compile(P_GOV_VERB)

def classify(t):
    """제목 하나를 10분야 중 하나로 배정한다.
    규칙은 위에서부터 순서대로 본다 — 분야가 뚜렷한 것이 먼저,
    도·시의 대응·발표는 마지막. 어디에도 안 걸리면 사건사고/기타."""
    for pat, sec in ORDER:
        if pat.search(t):
            return sec
    # 마지막: 도·시가 주어이고 대응·발표 동사가 있으면 행정
    if RE_GOV_SUBJ.search(t) and RE_GOV_VERB.search(t):
        return SEC_GOV
    return SEC_ETC

# 제주 관련성: 이 중 하나는 제목에 있어야 함 (제주 정치인·주요인물 포함)
JEJU=r"제주|서귀포|한라|탐라|올레|우도|추자|마라도|성산|중문|애월|조천|한림|대정|구좌|표선|남원|안덕|곶자왈|해녀|감귤|도의회|도정|도지사|제주시|JDC|제주관광|도내|도민|위성곤|오영훈|이상봉|문성유|김광수|4·3|4\.3|위령제|섯알오름|다랑쉬"
# 타지역 기사: 타지역 지명 있고 제주 실질 키워드 없으면 무조건 제외 (PDF: 타지역 기사 무조건 제외)
OTHER_REGION=r"울산|부산|대구|인천|광주|대전|세종|수원|성남|용인|고양|창원|청주|천안|전주|포항|김해|경기|강원|충청|충북|충남|전라|전북|전남|경상|경북|경남|영덕|울릉|통영|여수|목포|속초|강릉"
# 강한 제주 신호: 타지역 단어가 함께 있을 때는 이게 있어야만 제주 기사로 인정 (해녀·감귤 등 약한 신호로는 타지역 못 이김)
JEJU_STRONG=r"제주|서귀포|한라|탐라|애월|조천|한림|대정|구좌|표선|남원|안덕|성산|중문|우도|추자|마라도|곶자왈|도의회|도정|도지사|JDC|위성곤|오영훈|이상봉|4·3|4\.3|섯알오름"
# 사명 속 '제주'는 관련성 증거로 안 침 — 진짜 제주 키워드가 따로 있어야 통과
BRAND=r"제주항공|제주은행|제주유나이티드|제주드림타워"
# 제주와 무관한 노선·행사 (제주 항공사가 주어라도 제주 소식이 아님)
NONJEJU_ROUTE=r"(인천|김포|김해|청주|대구|무안|양양)\s*[~\-–—]\s*[가-힣A-Za-z]+|" \
              r"[가-힣]+\s*[~\-–—]\s*(도쿄|오사카|후쿠오카|삿포로|히로시마|나고야|타이베이|홍콩|방콕|다낭|세부|하노이|상하이|베이징|괌|사이판)"
def jeju_ok(t):
    clean=re.sub(BRAND,"",t)
    # 제주를 오가지 않는 노선 기사는 제외 (제주항공·대한항공 등 회사명만 걸리는 경우)
    if re.search(NONJEJU_ROUTE,t) and not re.search(r"제주\s*[~\-–—]|[~\-–—]\s*제주|제주공항|제주 노선|제주행|제주발",t):
        return False
    if re.search(OTHER_REGION,t):
        return bool(re.search(JEJU_STRONG,clean))  # 타지역 있으면 강한 제주신호 필수
    return bool(re.search(JEJU, clean))
# 수집 단계 하드 제외: 완전 무관한 전국 스포츠·부고류 (분류 대상 아닌 것만)
EXCLUDE=r"프로야구|KBO리그|\[부고\]|\[동정\]|로또"
def fetch(url,timeout=20):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (mondak)"})
    with urllib.request.urlopen(req,timeout=timeout,context=ssl.create_default_context()) as r:
        return r.read()

def norm(t):
    """군집용 정규화: 매체명 꼬리·괄호·따옴표·기호 제거"""
    t=re.sub(r"\s*-\s*[^-]{2,20}$","",t)          # " - 매체명" 꼬리
    t=re.sub(r"[\[\(][^\]\)]{1,12}[\]\)]","",t)   # [단독][속보](종합)
    t=re.sub(r"[\"'“”‘’…·,.:;!?~—\-\s]","",t)
    return t

def bigrams(t):
    n=norm(t); return {n[i:i+2] for i in range(len(n)-1)} if len(n)>1 else {n}

def parse_rss(xml_bytes, force_src=None):
    items=[]
    for it in ET.fromstring(xml_bytes).iter("item"):
        title=(it.findtext("title") or "").strip()
        link=(it.findtext("link") or "").strip()
        pub=it.findtext("pubDate")
        src_el=it.find("source"); src=(src_el.text or "").strip() if src_el is not None else ""
        if force_src: src=force_src
        elif src and title.endswith(" - "+src): title=title[:-(len(src)+3)].strip()
        elif " - " in title and not src: title,_,src=title.rpartition(" - ")
        d=None
        if pub:
            try: d=parsedate_to_datetime(pub).astimezone(KST).strftime("%Y-%m-%d")
            except Exception: pass
        if not title or re.search(EXCLUDE,title): continue
        items.append({"t":title,"link":link,"src":src,"d":d})
    return items


import os
NAVER_ID=os.environ.get("NAVER_ID","").strip(); NAVER_SECRET=os.environ.get("NAVER_SECRET","").strip()  # NAVER API HUB(ncloud)
DOMAP={"headlinejeju.co.kr":"헤드라인제주","newsjeju.net":"뉴스제주","jejusori.net":"제주의소리",
 "newsnjeju.com":"뉴스N제주","jejunews.com":"제주일보","jejudomin.co.kr":"제주도민일보","jejuilbo.net":"제주新보",
 "yna.co.kr":"연합뉴스","news1.kr":"뉴스1","newsis.com":"뉴시스","joongang.co.kr":"중앙일보","chosun.com":"조선일보",
 "donga.com":"동아일보","hani.co.kr":"한겨레","khan.co.kr":"경향신문","kbs.co.kr":"KBS","imnews.imbc.com":"MBC",
 "sbs.co.kr":"SBS","jtbc.co.kr":"JTBC","ytn.co.kr":"YTN","mk.co.kr":"매일경제","hankyung.com":"한국경제",
 "jibs.co.kr":"JIBS","kctvjeju.com":"KCTV제주방송","ihalla.com":"한라일보"}
def naver_news():
    if not (NAVER_ID and NAVER_SECRET): print("naver(API HUB): 키 미설정, 건너뜀"); return []
    out=[]
    for q in ("제주","제주도청 OR 제주도의회","제주 관광","제주 감귤 OR 농업","제주 축제"):
        try:
            u="https://naverapihub.apigw.ntruss.com/search/v1/news?display=100&sort=date&query="+urllib.parse.quote(q)
            req=urllib.request.Request(u,headers={"x-ncp-apigw-api-key-id":NAVER_ID,"x-ncp-apigw-api-key":NAVER_SECRET})
            with urllib.request.urlopen(req,timeout=20,context=ssl.create_default_context()) as r:
                j=json.loads(r.read().decode("utf-8"))
            for it in j.get("items",[]):
                t=re.sub(r"<[^>]+>","",it.get("title","")).replace("&quot;",'"').replace("&amp;","&").replace("&lt;","<").replace("&gt;",">").strip()
                link=(it.get("originallink") or it.get("link") or "").strip()
                if not t or not link or re.search(EXCLUDE,t) or not jeju_ok(t): continue
                d=None
                try: d=parsedate_to_datetime(it["pubDate"]).astimezone(KST).strftime("%Y-%m-%d")
                except Exception: pass
                dom=re.sub(r"^www\.","",urllib.parse.urlparse(link).netloc)
                src=DOMAP.get(dom) or DOMAP.get(".".join(dom.split(".")[-2:])) or dom
                out.append({"t":t,"link":link,"src":src,"d":d,"direct":True})
        except Exception as e: print("skip naver",q,repr(e))
    print("naver:",len(out),"건")
    return out

def main():
    all_items=[]; seen_links=set()
    # 누적: 직전 결과를 합산해 14일 창 안에서 매체수·기사수가 줄지 않게 함
    try:
        for pv in json.loads(OUT.read_text()).get("items",[]):
            lk=pv.get("link","")
            if not lk or lk in seen_links: continue
            seen_links.add(lk)
            all_items.append({"t":pv["t"],"link":lk,"src":pv.get("src",""),"d":pv.get("d"),
                              "direct":True,"outlets_prev":pv.get("outlets",[])})
        print("이전 누적",len(all_items),"건 병합")
    except Exception: pass
    for name,url in LOCAL_FEEDS:
        try:
            for it in parse_rss(fetch(url), force_src=name):
                # 지역지: 제주 키워드 있거나 8분야로 분류되면 유지(제목에 '제주' 없어도 도내 기사)
                # 지역지는 제목에 '제주'가 없어도 도내 기사이므로 유지한다.
                # 단, 명백히 타지역 사안이면 제외한다.
                if not jeju_ok(it["t"]) and re.search(OTHER_REGION, it["t"]): continue
                if it["link"] in seen_links: continue
                seen_links.add(it["link"]); it["direct"]=True; all_items.append(it)
        except Exception as e: print("skip local",name,e)
    for it in naver_news():                              # 네이버: 원문 직링크·매체 폭
        if it["link"] in seen_links: continue
        seen_links.add(it["link"]); all_items.append(it)
    for q in GOOGLE_QUERIES:
        try:
            u="https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=ko&gl=KR&ceid=KR:ko"
            for it in parse_rss(fetch(u)):
                if not jeju_ok(it["t"]): continue   # 구글발: 사명 제외하고 제주 키워드 필수
                if it["link"] in seen_links: continue
                seen_links.add(it["link"]); it["direct"]=False; all_items.append(it)
        except Exception as e: print("skip google",q,e)
    cutoff=(NOW-timedelta(days=14)).strftime("%Y-%m-%d")
    all_items=[i for i in all_items if not i["d"] or i["d"]>=cutoff]
    today=NOW.strftime("%Y-%m-%d")
    for i in all_items:
        if not i["d"]: i["d"]=today
    print("수집",len(all_items),"건")
    clusters=[]
    for it in all_items:
        bg=bigrams(it["t"]); nk=norm(it["t"])[:30]; placed=False
        for cl in clusters:
            if nk and nk==cl["nk"]:                       # 동일 제목 → 즉시 병합(매체수 집계 핵심)
                cl["items"].append(it); placed=True; break
            j=len(bg&cl["bg"])/(len(bg|cl["bg"]) or 1)    # 대표 제목과만 비교(군집 비대 방지)
            if j>=0.30: cl["items"].append(it); placed=True; break
        if not placed: clusters.append({"bg":bg,"nk":nk,"items":[it]})
    out=[]
    for cl in clusters:
        direct=[i for i in cl["items"] if i.get("direct")]
        rep=dict(max(direct or cl["items"], key=lambda x:len(x["t"])))
        outlets=[]
        for i in cl["items"]:
            s=(i.get("src") or "").strip()
            if s and s not in outlets: outlets.append(s)
            for s2 in i.get("outlets_prev",[]):
                if s2 and s2 not in outlets: outlets.append(s2)
        rep["outlets"]=outlets[:8]; rep["n"]=max(len(outlets),1)
        rep["sec"]=classify(rep["t"]); rep.pop("direct",None)
        out.append(rep)
    out.sort(key=lambda x:(x["d"] or "0000",x["n"]), reverse=True)  # 최신→매체수 순
    out=out[:400]
    if not out: print("no items; keeping previous"); return
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({"meta":{"collected_at":NOW.strftime("%Y-%m-%d %H:%M KST"),
        "window_days":14,"cadence":"3h","source":"지역 언론 RSS 5곳(직링크)+Google News — 사안별 보도 매체수 집계","count":len(out)},
        "items":out},ensure_ascii=False,indent=1),encoding="utf-8")
    top=out[0]; print("wrote",len(out),"items · top:",top["n"],"개사 —",top["t"][:40])

if __name__=="__main__": main()
