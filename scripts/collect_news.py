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

RULES=[
 ("정치/행정",r"도정|시정|도지사|시장|도의회|의회|의원|조례|예산안|인사청문|청문회|간담회|시민사회|시위|집회|외교|국민의힘|더불어민주당|민주당|당협|선거|공천|위성곤|오영훈|이상봉|4·3|4\.3|위령제|추념|행정체제|도청|공무원|위촉|감사원|국정감사|행정사무감사|정기인사|인사 발표|인사 단행|이사관|국장|서기관|승진|발탁|사장 후보|공사 사장|예결위|녹색당|시민단체|서명운동|칼럼|사설|기자상|여성가족|성평등|청렴|교부금|교총|국비|현판식|파트너십|협약|MOU|기부|고향사랑|이장|공청회|주민자치|주유소|공영주차장|공공요금|보조금|지원사업|시범사업|공모사업|수당|바우처 사업|조례 개정|규제 완화|민원 처리"),
 ("복지/사회서비스",r"복지|돌봄|어르신|노인|장애|취약계층|아동|보육|의료급여|건강보험|국민연금|바우처|사회보장|지역사회보장|요양|한부모|기초생활|자립|나눔|한끼|경로|장수|저소득|치매|헌혈|사례관리|고령자|반려동물|예방접종|심폐소생술|자선|기부금|복지위생|적십자|의용소방대|자원봉사|봉사단|미용 봉사|이·미용|건강한 노후|안전한 노후"),
 ("1차산업",r"감귤|만감류|한라봉|천혜향|바나나|망고|농가|농업|어업|어민|축산|한우|흑우|월동무|당근|메밀|딸기|가뭄|조업|수산|양식|품종|노지|비닐하우스|유리온실|재배|과수|출하|어가|밭작물|농산물|귀농|귀촌|농지|직불금|양돈|마사회|구제역|백신|풋귤|유제품|농단협|경관보전|국립공원|마을만들기|제주마|밭담"),
 ("신산업/AX",r"AI|인공지능|AX|디지털|데이터센터|빅데이터|UAM|드론|우주|위성|발사체|ICT|클라우드|바이오|바이오헬스|반도체|로봇|모빌리티|과기원|스타링크|신소재|R&D|연구개발|첨단|블록체인|메타버스"),
 ("환경/에너지",r"환경|에너지|탄소|재활용|일회용|다회용|정원도시|그린수소|풍력|태양광|재생에너지|신재생|생태|기후위기|친환경|탄소중립|용천수|유수율|난방전기화|히트펌프|자연자원|해양도립공원"),
 ("교육/청년",r"학교|학생|교육청|교육감|늘봄|고교학점제|장학|대학교|청소년|입시|교사|학부모|유치원|대학병원|제주대|학폭|공교육|도서관|연구센터|수료식|중등교육"),
 ("문화/관광/스포츠",r"관광|여행|렌터카|렌트카|크루즈|올레길|축제|페스티벌|공연|전시|문화|미술|박물관|콘서트|영화|호텔|리조트|방문객|워케이션|면세|MICE|스포츠|체육|선수|경기|리그|마라톤|대회|감독|구단|제주SK|아시안게임|올림픽|월드컵|비엔날레|음악제|리사이틀|신화|문인협회|신인문학상|국가유산|관아|만장굴|비자림|테라피|그림책|개인전|명상|항공좌석|항공편|항공사|항공이동권|e스포츠|피아니스트|바이올린|화가|래퍼|가볼 만한|여정|힐링|설문대할망|열쇠|해녀|잠녀|무형유산|유네스코"),
 ("창업/경제",r"스타트업|창업|수출|기업|경제|투자|고용|일자리|소상공인|상권|매출|벤처|자영업|은행|주가|증시|액면분할|상의|상공회의소|가맹|이자카야|소비|인구|4만명|돌파|펫패스|무신사|테크노파크|FTA|통상|판로|박람회"),
 ("안전/민원행정",r"태풍|호우|폭우|폭염|지진|화재|침수|재난|안전|특보|경보|구조|해경|119|민방위|단속|민원|점검|교통사고|붕괴|누수|정전|날씨|소나기|무더위|열대야|온열질환|식중독|을지연습|소방|횡단보도|신호등|실종|수색|물에 빠져|숨져|심정지|입적|난투극|흉기|최저기온|기온|더위"),
 ("사건사고/기타",r"사건|사고|체포|구속|기소|검찰|경찰|법원|판결|재판|연예|방송|드라마|아이돌|배우|가수|출연|절도|폭행|음주운전|마약|나혼자산다|나혼산|차예련|이찬원|톡파원|예능|시청률|벌금|의혹|고발|은폐|허위"),
]
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
def classify(t):
    # ── 선처리 ─────────────────────────────────────────────
    # 아래 RULES는 위에서부터 먼저 걸리는 구조라 순서 의존이 크다.
    # 그래서 "어떤 분야어가 섞여도 이건 이 분야"인 것들을 먼저 확정한다.
    # 실사용 오분류 지적(2026-08-27)을 반영해 순서를 다시 짰다.

    # 1) 강력 사건사고 — 수사·부검·시신 등은 어떤 분야어가 섞여도 사건사고
    if re.search(r"국과수|부검|시신|숨진 채|사망 사고|살해|피살|실종자|변사|"
                 r"영장|구속영장|체포영장|검찰 송치|압수수색|입건|피의자", t):
        return "사건사고/기타"

    # 2) 인사청문·선출직 후보 — 도정 인사 절차는 정치/행정
    #    (지적: 부지사 후보 인사청문이 기타로 갔다)
    if re.search(r"인사청문|청문회|청문 보고서|경과보고서|"
                 r"(도지사|부지사|시장|교육감|청장|사장|원장|의장)\s?(후보자?|내정자?|지명|임명)|[가-힣]{2,4}\s?후보자[,·\s]", t):
        return "정치/행정"

    # 3) 국가·지방 정책 의제 — 특별법·공동성명·건의 등
    #    (지적: 행정수도특별법 공동성명이 기타로 갔다)
    if re.search(r"특별법|법률안 제정|입법 예고|공동성명|공동건의|대정부 건의|"
                 r"국회 통과|시행령|정부안|국정과제|균형발전|행정수도", t):
        return "정치/행정"

    # 4) 복지·사회서비스 — 대상이 사람인 지원은 행정 행위여도 복지
    #    (지적: 다문화가족 교육활동비, 위기가구 지원체계가 기타·교육으로 갔다)
    if re.search(r"봉사|나눔|후원|기부|성금|위문|돌봄|요양원|경로당|무료 급식|"
                 r"어르신|노인|장애인|취약계층|저소득|한부모|결식|"
                 r"다문화|위기가구|복지 사각|사회보장|보육료|아동수당|자립 지원|"
                 r"긴급복지|생계급여|의료급여|기초생활|"
                 r"기탁|기증|보건소|건강검진|헬스케어|예방접종|금연|정신건강|자살예방|"
                 r"출생아|출산율|저출생|난임|산후|다자녀|"
                 r"무연고|장사시설|봉안|공설묘지|화장장", t):
        return "복지/사회서비스"

    # 5) 해녀 = 문화유산
    if re.search(r"해녀|잠녀", t): return "문화/관광/스포츠"

    # 6) 학교·교육 — 학교 시설·교육과정도 교육
    #    (지적: 표선고 기숙사 개관이 다른 분야로 갔다)
    # 학교 이름은 '○○초·중·고' 뒤에 쉼표·가운뎃점이 오거나 '학교/교'로 끝날 때만 인정한다.
    # ('저수고 바나나', '안전사고 주의보'의 '고'가 학교로 잡히던 문제)
    if re.search(r"[가-힣]{2,}(초|중|고)등학교|[가-힣]{2,}(초|중|고)교[ ,·]|"
                 r"[가-힣]{2,}(초|중|고)[,·]|"
                 r"학생|교사|교직원|동아리|오케스트라|학예|진로|방과후|급식실|"
                 r"기숙사|교육과정|IB |국제바칼로레아|교육청|교육감|학교급식|"
                 r"입학|졸업|수업|교장|학부모|"
                 r"청년[가-힣]{0,4}(사업|지원|정책|일자리|주택|수당)|청년드림|"
                 r"대학생|취업 지원|진로 체험|장학금", t):
        return "교육/청년"

    # 7) 1차산업 — 품종 개발·재배·수매는 농수축산
    #    (지적: 저수고 바나나 개발이 교육/청년으로 갔다)
    if re.search(r"감귤|만감류|한라봉|천혜향|바나나|망고|키위|블루베리|"
                 r"품종 개발|신품종|재배|육묘|하우스 재배|수매|출하|작황|병해충|"
                 r"농가|어가|양식장|축산농가|영농|파종|수확|"
                 r"병해충|매미충|과실파리|방제|농협|수협|축협|영농조합|"
                 r"농촌|어촌|귀농|귀어", t):
        return "1차산업"

    # 8) 재난·기상 특보 — 안전
    #    (지적: 태풍 풍랑 주의보가 다른 분야로 갔다)
    if re.search(r"태풍|호우|폭우|폭설|풍랑|너울|강풍|한파|폭염|지진|해일|"
                 r"주의보|경보 발령|특보|대피|침수|산사태|안전사고 주의", t):
        return "안전/민원행정"

    # 8-2) 단속·생활안전 — 불법 주정차·번호판 영치·식품 위생
    if re.search(r"번호판[^,]{0,10}영치|영치|불법 주정차|과태료|계도|단속 강화|"
                 r"식약처|식품안전|위생 점검|부적합 판정|회수 조치|"
                 r"음주단속|과속|어린이보호구역", t):
        return "안전/민원행정"

    # 9) 화재·소방 (봉사가 아닌 실제 화재)
    if re.search(r"소방|화재|폭발|산불", t): return "안전/민원행정"

    # 10) 관광·체육 행사 — 대회·공연·모집
    #     (지적: 전국노래자랑 참가자 모집이 행정으로 갔다)
    if re.search(r"전국체전|전국노래자랑|가요제|음악회|영화제|비엔날레|"
                 r"관광객|입도객|렌터카|렌트카|숙박업|관광지|관광정책|관광진흥|"
                 r"올레길|둘레길|캠핑장|해수욕장 개장", t):
        return "문화/관광/스포츠"

    # 10-2) 항공·해운 노선 — 관광 접근성 소식
    if re.search(r"노선|취항|증편|감편|운항|직항|결항|여객선|크루즈 기항|"
                 r"항공권|좌석난|항공좌석", t):
        return "문화/관광/스포츠"

    # 11) 산업·경제 지원기관 — 제품 개발·수출·통상
    #     (지적: 제주TP 가공식품 출시, FTA 설명회가 다른 분야로 갔다)
    if re.search(r"테크노파크|제주TP|FTA|통상|수출 상담|판로 개척|박람회 참가|"
                 r"가공식품|상품화|시제품|기술이전|경영 컨설팅|소상공인 지원|"
                 r"창업보육|투자유치|기업 지원", t):
        return "창업/경제"

    # 12) 출판·전시·창작 — 문화
    #     (지적: 생태작가 출간 소식이 기타로 갔다)
    if re.search(r"출간|펴내|출판|저서|시집|소설집|산문집|화보집|"
                 r"개인전|초대전|작품전|공모전 수상|문학상|등단|"
                 r"서예|서예전|가곡|국악|합창|무용|연극|뮤지컬|사진전|조각전|"
                 r"책방|독서|도서관 프로그램|북토크|"
                 r"휴양림|생태관광|둘레길|트레킹|"
                 r"파크골프|게이트볼|생활체육|동호회|러닝|마라톤|자전거 대회|"
                 r"展|전시회|기획전|뮤지션|밴드|패션위크|컬렉션|"
                 r"예술인|창작 지원|문화예술|아트|갤러리|공예|한복", t):
        return "문화/관광/스포츠"

    # 11-2) 환경·에너지 — 폐기물·자원순환·에너지 설비
    if re.search(r"현수막|폐기물|자원순환|분리배출|재활용|매립장|소각장|"
                 r"BESS|에너지저장장치|전기차 충전|충전 인프라|"
                 r"오폐수|하수처리|악취|미세먼지|생물다양성|습지|보전지역", t):
        return "환경/에너지"

    # 12-2) 신산업·AX — '제주도, AI 도입' 처럼 행정어와 붙어도 기술 분야로 본다
    if re.search(r"인공지능|\bAI\b|AX|디지털 전환|빅데이터|데이터센터|"
                 r"UAM|드론|위성|발사체|블록체인|메타버스|로봇|자율주행|"
                 r"클라우드|반도체|바이오헬스", t):
        return "신산업/AX"

    # 12-3) 읍면동 행정 — 주민센터 프로그램·업무회의·이·통장
    if re.search(r"[가-힣]{1,4}\d?(동|읍|면)(주민센터|사무소)|[가-힣]{2,4}\d?(동|읍|면)[,·]\s|"
                 r"주간업무회의|업무보고회|이·통장|통장 회의|주민자치위원|"
                 r"대기발령|직위해제|전보 인사|정기 인사|승진 임용|"
                 r"병무청|보훈|국가유공자 포상|정부포상", t):
        return "정치/행정"

    # 12-4) 광역 정책 의제 — 초광역권·특별자치·정부 계획
    if re.search(r"초광역|특별자치|메가시티|지방시대|균형발전|국가균형|"
                 r"공동대응|공동건의|시·도지사 협의|중앙정부 건의|3특|원팀", t):
        return "정치/행정"

    # 12-4b) 행정 감찰·의혹 조사 — 수사가 아닌 행정 내부 조치
    if re.search(r"감찰|감사 착수|자체 감사|인허가 의혹|정관계|유착 의혹|"
                 r"고도제한|도시계획|용도지역|지구단위|제2공항|공항 건설", t):
        return "정치/행정"

    # 12-4c) 국회·정치권 발언 — 의원·장관·당 관계자 코멘트
    if re.search(r"국회의원|장관|의원[,·]|여당|야당|당대표|최고위|국정감사|"
                 r"상임위|교육위|행안위|국토위|정치권|기자회견|논평|성명서", t):
        return "정치/행정"

    # 12-5) 교통 기반시설 — 트램·도로·버스 정책 (교통 분야가 없어 행정으로 둔다)
    if re.search(r"트램|경전철|도시철도|버스 노선 개편|준공영제|교통체계|"
                 r"도로 개설|우회도로|주차난|주차장 조성", t):
        return "정치/행정"

    # 13) 도·시 정책 발표 — 위 분야에 걸리지 않은 나머지 행정 행위
    #     (앞으로 옮긴 이유: 이 규칙이 복지·교육·관광 기사를 통째로 가로채고 있었다)
    if re.search(r"(제주도|제주시|서귀포시|도교육청|행정시)[,·]?\s*(.{0,12})?"
                 r"(모집|공모|접수|시행|추진|도입|확대|개선|지정|선정|운영|실시|마련|발표)", t):
        return "정치/행정"

    for s,p in RULES:
        if re.search(p,t): return s
    return "사건사고/기타"

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
