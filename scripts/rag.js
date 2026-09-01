/* ══════════════════════════════════════════════════════════════
   몬딱 RAG 엔진 (브라우저) — rag.js
   데이터 로드·문서화·후보 추출을 브라우저에서 수행한다.
   서버(Worker)는 LLM 호출만 담당하므로, 데이터가 늘어도
   서버 코드를 다시 배포할 필요가 없다.
   ※ chat.js(Netlify 함수)의 동일 로직을 그대로 이식한 것.
   ══════════════════════════════════════════════════════════════ */
(function (global) {
"use strict";

const SUPPORT = [{"title": "제주 생활 속 히트펌프 보급사업 (2026)", "text": "[제주 생활 속 히트펌프 보급사업 2026] 가스·기름 보일러를 전기로 움직이는 공기열 히트펌프로 바꾸는 가구에 설치비를 지원하는 제주도 사업입니다. 난방비 부담과 온실가스를 함께 줄이는 것이 목적입니다. 2026년 상반기에는 1,042가구를 지원했고, 하반기에는 신청 절차를 간소화해 1,418가구를 모집했습니다(신청 8월 31일 마감, 승인 가구는 9월 11일까지 서류 제출). 지원 규모는 설치비의 일정 비율이며 연도·차수·제품에 따라 달라집니다. 신청 가구가 제조사 배정 물량보다 많으면 평가를 거쳐 고득점순으로 대상을 정합니다. 신청은 제주도 누리집 공고에서 제조사를 선택해 접수하고, 현장 확인과 서류 심사를 거쳐 확정됩니다. 차수별 모집 시기·지원 금액·잔여 물량은 해마다 달라지므로 반드시 제주도 누리집(jeju.go.kr)의 최신 공고를 확인하시고, 문의는 제주120(064-120)으로 하시기 바랍니다.", "url": "https://www.jeju.go.kr", "contact": "제주120 064-120"}, {"title": "제주 전기차 구매보조금 (2026)", "text": "[제주 전기차 구매보조금 2026] 제주도는 전국 광역자치단체 중 가장 높은 수준의 전기차 구매보조금을 지원합니다. 2026년 승용차 기본보조금은 최대 980만원(국고보조금 최대 580만원 + 제주도 지자체보조금 400만원)입니다. 화물차는 소형·경형 500만원, 초소형 400만원 수준이며 차종·가격에 따라 달라집니다. 제주도는 행정시 구분 없이 단일 광역 단위로 보조금이 적용되며, 기본보조금 외에 양방향 충전(V2G)·충전기 설치 등 다른 시·도에 없는 추가보조금도 지원합니다. 2026년 하반기에는 8월 6일부터 승용차 1,200대·화물차 400대 등을 추가 접수했습니다. 가장 정확한 최신 정보(잔여물량·신청방법·자격)는 제주120(064-120)으로 문의하거나 무공해차 통합누리집(www.ev.or.kr)과 제주도 홈페이지 공고에서 확인하시기 바랍니다.", "url": "https://www.ev.or.kr", "contact": "제주120 064-120"}, {"title": "저소득층 희귀난치성 및 중증질환자 교통비 지원", "text": "[저소득층 희귀난치성 및 중증질환자 교통비 지원] 대상: 모든 도민. 마감: 상시신청. 내용: 저소득층 희귀난치성질환 및 중증질환자에게 항공비 및 선박비 지원 지원내용: ○ 도외 병원 진료를 위한 항공료 또는 선박료 실비(KTX, 열차비 등 현지교통비 제외) ○ 연 12회(예산범위 내, 도외 병원 진료 후 3", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000214", "contact": ""}, {"title": "빅데이터 기반 1인 가구 안부 살피미", "text": "[빅데이터 기반 1인 가구 안부 살피미] 대상: 모든 도민. 마감: 상시신청. 내용: 수급자 등에 속하는 1인가구를 대상으로 안부살피미 서비스 지원 지원내용: ○ 서비스내용 - 전력, 통신 사용 여부를 분석하여 이상 감지 발생 시 읍면동에서 안부확인 서비스 - 한국전력공사 ○ 지원대상 :", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000216", "contact": ""}, {"title": "어르신 이·미용료 및 목욕료 지원", "text": "[어르신 이·미용료 및 목욕료 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 기초생활수급권자(생계급여 또는 의료급여) 노인에게 이·미용료 및 목욕료 지원 지원내용: ○ 1인 월 11,000원 지원 - 이․미용료 : 1인당 5,000원/월, (년 60,000원) - 목 욕 료 : 1인당 6,", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000217", "contact": ""}, {"title": "노인고용촉진장려금 지원", "text": "[노인고용촉진장려금 지원] 대상: 이동약자·어르신. 마감: ○분기별 5일까지(4월, 7월, 10월, 12월). 내용: 65세 이상 노인을 고용한 업체에 분기별 고용촉진장려금 지원 지원내용: ○ 도내에 주소지를 둔 65세 이상 노인 1인 고용 시 월 20만원 지원 - 업체당 최대 5인 지원 - 분기별 지급(4월, 7월, 10월", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000220", "contact": ""}, {"title": "참전유공자 TV수신료 지원", "text": "[참전유공자 TV수신료 지원] 대상: 모든 도민. 마감: 신청 불필요. 내용: 6.25 및 월남참전유공자에게 TV수신료 지원 지원내용: ○ 지원대상: 6.25 및 월남참전유공자 * 순수 참전용사만 해당 ○ 지원금액: 1세대 당 월 2,500원(지원시 일괄지급 연 30,000원)", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000221", "contact": ""}, {"title": "기타과수 생산시설 현대화 지원", "text": "[기타과수 생산시설 현대화 지원] 대상: 농어업인. 마감: 접수기관 별 상이. 내용: 기타과수 재배 농업인에게 비상발전기 외 10개사업 지원 지원내용: ○ 농업경영체에 등록한 기타과수(감귤류를 제외한 과수) 재배 농업인에게 생산기반시설(*비상발전기 외 10개사업) 설치 비용 지원 * 지", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000222", "contact": ""}, {"title": "고품질 만감류 장려금 지원", "text": "[고품질 만감류 장려금 지원] 대상: 농어업인. 마감: 접수기관 별 상이. 내용: 고품질 만감류 출하농가에 장려금 지원 지원내용: ○ 품질 기준 이상의 만감류(한라봉, 천혜향, 레드향, 황금향, 카라향)를 출하하는 농가에게 인센티브 제공", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000223", "contact": ""}, {"title": "어르신 틀니·보청기 지원", "text": "[어르신 틀니·보청기 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 어르신에게 틀니 및 보청기 지원 지원내용: ○틀니 - 완전틀니(악당) 시술 비용: 의사 처방에 따라 상악, 하악 또는 양악 - 시술비용 건강보험 급여 적용 후 본인부담금의 50% 지원", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000225", "contact": ""}, {"title": "정신질환자 취업자립촉진비 지원", "text": "[정신질환자 취업자립촉진비 지원] 대상: 모든 도민. 마감: 상시신청. 내용: 취업을 3개월 이상 유지한 정신질환자에게 취업자립촉진비 지원 지원내용: ○ 정신장애인 등급을 받은 자 및 조현병, 분열 및 망상장애, 기분(정동)장애를 가진 정신질환자 중 3개월 이상 취업을 유지한자 - 월 2", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000226", "contact": ""}, {"title": "중증장애인 교통비 지원", "text": "[중증장애인 교통비 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 중증장애인 1인 월 25,000원 교통비 분기별 지원 지원내용: ○ 1인 월 25,000원 지원 - 분기별 본인 통장 입금(3·6·9·12월)", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000227", "contact": ""}, {"title": "경작지 암반제거 지원", "text": "[경작지 암반제거 지원] 대상: 모든 도민. 마감: 매년 1월 중. 내용: 밭작물 재배농지의 암반제거 비용 지원 지원내용: ○ 농업경영체에 등록한 밭작물 재배농지(과수원 제외)에 암반 존재할 경우 암반제거 비용 지원 ○ 200㎥ 이하 암반 제거 및 지반 정리에", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000229", "contact": ""}, {"title": "조손가정 학습 지원", "text": "[조손가정 학습 지원] 대상: 육아·양육. 마감: 보조사업으로 공모를 통해 신청(통상적 공모시기 : 2월). 내용: 경제적으로 어려운 조손 가정에 아동 교육 프로그램 지원 지원내용: ○ 조손 가정 아동 교육 : 학습, 미술교육, NIE프로그램", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000230", "contact": ""}, {"title": "(중장년) 중소기업 장기재직 재형저축 지원", "text": "[(중장년) 중소기업 장기재직 재형저축 지원] 대상: 소상공인·창업. 마감: 제주도청 홈페이지에 참여기업 및 근로자 모집 공고. 내용: 중소기업 근로자( 40세 ~ 64세)를 대상으로 장기재직 시 재형저축 지원 지원내용: ○ (중장년) 중소기업 장기재직 재형저축 사업 : 중소기업 근로자( 40세 ~ 64세) 10만원, 기업 12만원, 도 12만원을 5년간 적립해", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000231", "contact": ""}, {"title": "수출용 화훼종구(묘) 구입지원", "text": "[수출용 화훼종구(묘) 구입지원] 대상: 농어업인. 마감: 매년 1월 초부터 약 2주간. 내용: 수출 화훼농가에 수출용 화훼 종구(묘) 구입비 일부 지원 지원내용: ○ 농업경영체로 등록하였고 서귀포시 원예전문생산단지 소속 수출 참여 농가 및 생산자 단체 소속 수출 참여 농업인에게 수출용 화훼 종구(묘) 구입", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000233", "contact": ""}, {"title": "고령운전자 운전면허 자진반납 지원", "text": "[고령운전자 운전면허 자진반납 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 운전면허를 자진반납한 어르신(65세이상 제주도민)에게 교통비 지원 지원내용: ○ 제주특별자치도에 주민등록 된 65세 이상 어르신 중 2019.6.12. 이후 운전면허 자진반납한 사람 대상으로 교통비 지원(1회에 한함)", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000234", "contact": ""}, {"title": "공공자전거 스테이션 운영", "text": "[공공자전거 스테이션 운영] 대상: 모든 도민. 마감: 상시신청. 내용: 자전거 이용자 누구나 이용 가능 지원내용: ○ 공공자전거 대여 서비스 제공 - 운영시간 : 07시 ~ 24시 ○ 공공자전거 스테이션 위치 - 탐라도서관 주차장 - 국기로", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000235", "contact": ""}, {"title": "아동복지시설 보호아동지원금", "text": "[아동복지시설 보호아동지원금] 대상: 육아·양육. 마감: 상시신청. 내용: 아동복지시설 9개소에 보호아동지원금 지급 지원내용: ○ 아동복지시설 보호아동 지원금 - 대상 : 아동복지시설 9개소 - 주요내용 : 시설에 보호중인 입소 아동 대상 보호아동지원금 교부", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000238", "contact": ""}, {"title": "균음성 폐결핵 의심자 정밀검사(CT검사)비용 지원", "text": "[균음성 폐결핵 의심자 정밀검사(CT검사)비용 지원] 대상: 모든 도민. 마감: 상시신청. 내용: 결핵 유소견자에게 의료기관 CT검사 비용 지원 지원내용: ○ 균음성 폐결핵 의심자 정밀검사(CT검사)비용 지원 : 관내 노인·노숙인 등 결핵검진사업 대상자 중 X-Ray 상 균음성 폐결핵 의심자의", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000239", "contact": ""}, {"title": "정신건강 검진비 지원", "text": "[정신건강 검진비 지원] 대상: 모든 도민. 마감: 상시신청. 내용: 정신건강검진이 필요한 시민에게 1인당 최대 57,900원까지 정신건강 상담 및 검진비 지원 지원내용: ○ 정신건강검진 및 상담 - 대상: 정신건강검진이 필요한 서귀포시민 누구나 - 지원기준: 정신건강의학과 초진환자(1년 이내 정신의학과 진", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000240", "contact": ""}, {"title": "흑우 소득 직불금 지원", "text": "[흑우 소득 직불금 지원] 대상: 농어업인. 마감: 2025.12.19~2026.01.09. 내용: 흑우암소 사육농가에 직불금 지원 지원내용: ○ 시업기간 : 2026.1 ~ 12 ○ 사업내용 : 12개월령 이상 흑우암소 사육농가에 직불금 지원 ○ 협조기관 : 지역축협(제주축", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000242", "contact": ""}, {"title": "낙농산업 육성 지원", "text": "[낙농산업 육성 지원] 대상: 농어업인. 마감: 2025.12.19~2026.01.09. 내용: 젖소사육농가 및 유가공업체 등에 사료비, 성감별정액 지원, 유가공시설 및 장비 지원 등 지원내용: ○ 사업기간 : 2026. 1~12월 ○ 사업내용 : 유제품 생산시설, 목장형 유가공시설 및 장비 지원 ○ 지원비율 : 보조율 60", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000243", "contact": ""}, {"title": "양식산업 육성 및 관리", "text": "[양식산업 육성 및 관리] 대상: 모든 도민. 마감: 제주시 공고 참조. 내용: 양식어가 등에 운영비, 시설 등 육성 및 관리 지원 지원내용: ○ 운영비 지원 : 해조류 종자 구입지원, 양식품종 다양화 종자 구입 지원 등", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000244", "contact": ""}, {"title": "기초생활수급자 등 검정고시학습비 지원", "text": "[기초생활수급자 등 검정고시학습비 지원] 대상: 모든 도민. 마감: 상시신청. 내용: 기초생활수급자 등에게 검정고시학습비 지원 지원내용: ○ 검정고시 학원비 연 45만원(3개월분) , 교재비 연 7만원, 사회진출금* 1회 20만원 * 검정고시 합격자에 한하며(학원비 미", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000245", "contact": ""}, {"title": "기초생활수급자 등 중·고교신입생교복비 지원", "text": "[기초생활수급자 등 중·고교신입생교복비 지원] 대상: 모든 도민. 마감: 상시신청. 내용: 저소득층 자녀 중 도외 중·고교 신입생에게 교복비 지원 지원내용: ○ 도외 중,고교 신입생 교복비 1인 35만원(연 1회) ※ 신입생 자녀가 자퇴·재입학·전학 시 추가 지원 불가", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000246", "contact": ""}, {"title": "저소득주민 특별생계비 지원", "text": "[저소득주민 특별생계비 지원] 대상: 모든 도민. 마감: 상시신청. 내용: 비수급 저소득주민에게 특별생계비 지원 지원내용: ○ 생계비 지원(최대 12개월) - 1인가구 :256,420원, 2인가구 :419,930원, 3인가구 : 535,900원, 4인가구", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000247", "contact": ""}, {"title": "중증장애인 의료비 지원", "text": "[중증장애인 의료비 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 중증장애인에게 외래, 입원 등 의료비 지원 지원내용: ○ 외래시 : 본인부담 의료비 중 타 법령에 의해 지급되는 비용을 제외한 금액 전액 지원 ○ 입원시 : 본인부담 의료비 중 타 법령에 의해", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000248", "contact": ""}, {"title": "중증장애인 상해보험 가입 지원", "text": "[중증장애인 상해보험 가입 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 제주시 거주 중증장애인을 위한 상해보험 가입 지원 지원내용: ○ 본인 상해로 인한 사망시 : 1,000만원 ○ 본인 상해로 인한 후유장해 발생시 : 30만원 ~ 1,000만원 ○ 골절발생위로금(", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000249", "contact": ""}, {"title": "중증장애인 추가수당 지원", "text": "[중증장애인 추가수당 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 수급자 및 차상위장애인 중 ('19.7.1.이전) 1급 장애인에게 추가수당 지원 지원내용: 1인 월 30,000원 중증장애인 추가수당 지원(2019.7.1이전 1급 장애인)", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000250", "contact": ""}, {"title": "저소득 중증장애인 유료방송 이용요금 지원", "text": "[저소득 중증장애인 유료방송 이용요금 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 저소득 중증장애인에게 유료방송 이용요금 지원 지원내용: ○ 협약방송사(㈜KCTV제주방송)의 디지털방송 기본요금 및 STB(Set Top Box) 사용료에 대하여 월 7,700원 지원", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000251", "contact": ""}, {"title": "장애인 자동차운전면허 취득교육비 지원", "text": "[장애인 자동차운전면허 취득교육비 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 운전면허를 취득한 장애인에게 운전면허 취득교육비 지원 지원내용: ○ 운전면허 제 1,2종 보통 : 1인당 50만원 이내 ○ 운전면허 대형 : 1인당 65만원 이내 *장애인 1인당 1회에 한하여 지원", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000252", "contact": ""}, {"title": "가정위탁보호아동 양육보조금 지원", "text": "[가정위탁보호아동 양육보조금 지원] 대상: 육아·양육. 마감: 상시신청. 내용: 가정위탁보호아동을 대상으로 양육보조금 지원 지원내용: ○ 가정위탁아동 양육보조금 지원 - 지원내용 : 가정위탁아동 양육에 따른 양육보조금 지원 - 지원대상 : 가정위탁아동 - 지원기준", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000253", "contact": ""}, {"title": "가정위탁아동 양육지원", "text": "[가정위탁아동 양육지원] 대상: 육아·양육. 마감: 상시신청. 내용: 가정위탁보호아동을 위해 학습비, 문화활동비, 월동대책비 등 지원 지원내용: ○ 가정위탁아동 세대 월동대책비 지원 - 지원내용 : 동절기를 대비하기 위한 월동대책비 지원 - 지원대상 : 가정위탁세대 - 지원기준", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000254", "contact": ""}, {"title": "결식아동 급식 지원", "text": "[결식아동 급식 지원] 대상: 육아·양육. 마감: 상시신청. 내용: 저소득 가정의 아동을 대상으로 급식 지원 지원내용: ○ 저소득 가정의 아동을 대상으로 결식예방 및 영양개선을 위한 급식 지원", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000255", "contact": ""}, {"title": "장수수당 지원", "text": "[장수수당 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 80세 이상 노인에게 장수수당 지원 지원내용: ○ 1인 월 25,000원 장수수당 지원 ○ 지급시기 및 지급방법 - 지급시기: 매월 20일 - 지급방법 : 대상자 명의 금융 계좌", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000256", "contact": ""}, {"title": "국가유공자 상수도사용료 감면", "text": "[국가유공자 상수도사용료 감면] 대상: 모든 도민. 마감: 상시신청. 내용: 국가유공자 및 대표유족 등에 대한 상수도 사용료 감면 지원내용: ○ 감면대상자 - 국가유공자, 국가유공자 유족, 참전유공자(6.25참전유공자, 월남참전자, 고엽제후유의증환자) ○ 지원액 - 월", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000257", "contact": ""}, {"title": "자활사업 참여자 자격증 취득 지원", "text": "[자활사업 참여자 자격증 취득 지원] 대상: 모든 도민. 마감: 상시신청(예산소진시 지원 마감). 내용: 자활사업참여자를 대상으로 국가 자격증 취득을 위한 실기학원비 지원(80만원 이내) 지원내용: ○ 자활사업(자활근로사업, 자활기업)에 참여하는 기초수급자 및 차상위계층 중 자격증 필기시험에 합격한 자에대하여 자격증취득을 위한 실기 학원비", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000258", "contact": ""}, {"title": "제주특별자치도 학자금 대출이자 지원", "text": "[제주특별자치도 학자금 대출이자 지원] 대상: 모든 도민. 마감: 상반기: 1~4월, 하반기: 7~9월. 내용: 대학(원)생 및 졸업생 학자금 대출이자 지원 지원내용: <2026년 제주특별자치도 하반기 학자금 대출이자 지원사업> - 2010년 이후부터 한국장학재단을 통해 대출받은 학자금 대출에 따라 발생한", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000259", "contact": ""}, {"title": "저소득층 간병 인부임 지원", "text": "[저소득층 간병 인부임 지원] 대상: 모든 도민. 마감: 상시신청이나 예산 조기소진시 지원 불가. 내용: 기초생활보장수급자 등 보호자가 없는 저소득층이 병원 입원 시 간병비 지원 지원내용: ○ 지원기준 : 간병인부임 지원 - 8시간 기준 : 30,000원(주간, 야간 공통) - 12시간 기준 : 45,000원 - 1인", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000260", "contact": ""}, {"title": "희귀난치성 중증질환자 교통비 지원", "text": "[희귀난치성 중증질환자 교통비 지원] 대상: 모든 도민. 마감: 상시신청. 내용: 희귀중증질환자으로 등록된 의료급여수급에게 도외 교통 항공료 또는 선박비 지원 지원내용: ○ 지원대상 : 희귀난치성질환자 및 중증질환으로 등록된 의료급여수급자 및 차상위본인부담경감대상자 ○ 지원내용 : 도외 교통 항공료 또는", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000261", "contact": ""}, {"title": "저소득층 위기가정 지원", "text": "[저소득층 위기가정 지원] 대상: 모든 도민. 마감: 상시신청이나 예산 조기 소진시 지원불가. 내용: 위기상황 발생가구에 생계비, 의료비, 장제비 등 지원 지원내용: ○ 위기상황이 발생한 기준 중위소득 100% 이하가구에 생계비, 의료비, 장제비 등 지원 - 생계비 : 당해년도 긴급복지지원 기준에 정한 가", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000262", "contact": ""}, {"title": "해피아이 육아지원금 지원", "text": "[해피아이 육아지원금 지원] 대상: 육아·양육. 마감: 상시신청. 내용: 첫째아 또는 둘째아를 출산,양육하는 부모에게 육아지원금 지급 지원내용: ○ 첫째아 육아지원금 : 5년간 500만원(0세 50만원, 1~2세120만원,3세 110만원, 4세100만원) ○ 둘째아 이상 육아지원", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000263", "contact": ""}, {"title": "취약계층 1인 가구 건강음료 지원사업", "text": "[취약계층 1인 가구 건강음료 지원사업] 대상: 모든 도민. 마감: 상시신청. 내용: 고독사 위험군 1인가구를 대상으로 건강음료 배달 및 안부 확인 지원내용: ○ 서비스내용 : 건강음료 전문판매원 활용, 건강음료 배달 시 안부확인을 병행하여 1인 가구의 건강한 삶 지원 ○ 지원대상 : 고독사 등에", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000264", "contact": ""}, {"title": "아이돌봄서비스 본인부담금 지원", "text": "[아이돌봄서비스 본인부담금 지원] 대상: 모든 도민. 마감: 아이돌봄서비스 지원시 연계지원. 내용: 아이돌봄서비스 이용가정에 본인부담금의 일부 지원 지원내용: ○ 만 3개월~만 12세 이하 아동대상 아이돌봄서비스 이용가정 본인부담금의 20~40% 도비로 지원 ○ 지원률 : 양육공백 여부 및 기준중", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000266", "contact": ""}, {"title": "통합복지기금(청소년육성계정) 장학금 지원", "text": "[통합복지기금(청소년육성계정) 장학금 지원] 대상: 청년·신혼. 마감: 매년 3월(공고일에 따라 달라질 수 있음). 내용: 기초생활수급자 등 어려운 고등학생 및 대학생, 학교밖청소년에게 장학금 지원 지원내용: ○ 고교생 - 수업료 학교운영지원비(무상교육 제외, 1인 2백 5십만원 이내) ○ 대학생 - 등록장학금(1인 2백 5십만원 이내) ○ 기", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000267", "contact": ""}, {"title": "노인사회활동 및 생활안정 지원", "text": "[노인사회활동 및 생활안정 지원] 대상: 이동약자·어르신. 마감: 노인건강진단 실시 계획 수립 후 읍면동 방문 신청. 내용: 의료급여수급권자 중 희망자에게 노인건강진단 지원 지원내용: ○ 의료급여수급권자 중 희망자에게 노인건강진단 지원 ※1인당 150,000원 범위 내에서 검진 항목이 변경될 수 있음", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000268", "contact": ""}, {"title": "주거비 지원(신혼부부 전세이자 지원, 둘째자녀 주거임차비, 사회초년생 연월세 이자 지원)", "text": "[주거비 지원(신혼부부 전세이자 지원, 둘째자녀 주거임차비, 사회초년생 연월세 이자 지원)] 대상: 청년·신혼. 마감: 연월세 지원: 상시/전세지원:도청홈페이지 공고 접수기간 참고/주거임차비: 상시. 내용: 무주택 가구 등에 주거임차비, 전세자금 대출이자 등 지원 지원내용: ○ 무주택 자녀출산 가구 주거 임차비 지원 - '21. 1. 1일이후 둘째자녀 이상 출산(입양) 무주택 가구 주거임차비 지원(연 280만원", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000269", "contact": ""}, {"title": "제주특별자치도 여성농업인 행복이용권 지원", "text": "[제주특별자치도 여성농업인 행복이용권 지원] 대상: 농어업인. 마감: 2026.03.09~2026.03.31. 내용: 도내 20세 이상 ~ 80세 미만 여성농업인을 대상으로 행복이용권 지원(20만원/인) 지원내용: ○ 지원대상: 농업경영정보를 등록한 20세 이상 ~ 80세 미만 여성농업인 ○ 지원내용: 1인당 행복이용권(NH채움카드 바우처) 20만원 지원", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000270", "contact": ""}, {"title": "제주특별자치도 출산 농가도우미 지원", "text": "[제주특별자치도 출산 농가도우미 지원] 대상: 육아·양육, 농어업인. 마감: 상시신청. 내용: 도내 출산(예정) 여성농업인을 대상으로 출산 전후 영농도우미 이용 금액 정액 지원 지원내용: ○ 지원대상: 농업경영정보를 등록한 도내 출산(예정)* 여성농업인 * 임신 4개월(85일) 이후 발생한 유산·조산·사산의 경우 출산으로", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000271", "contact": ""}, {"title": "고품질 감귤 생산지원(원지정비 생산자재 지원 및 향토재래귤 지원)", "text": "[고품질 감귤 생산지원(원지정비 생산자재 지원 및 향토재래귤 지원)] 대상: 농어업인. 마감: 접수기관 별 상이. 내용: 향토재래귤 재배농가 등에 약제구입비, 생산자재비 등 지원 지원내용: ○ 향토재래귤 관리 농가에 약제구입비 지원 ○ 감귤원 원지정비 농가에 생산자재비 지원", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000272", "contact": ""}, {"title": "난임부부 시술비 지원", "text": "[난임부부 시술비 지원] 대상: 모든 도민. 마감: 상시신청. 내용: 난임부부에게 시술비 지원 지원내용: ○ 일부 및 전액 본인부담금, 비급여(배아동결비, 유산방지제, 착상보조제) 등 ○ 시술비 25회(신선배아, 동결배아,, 인공수정)", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000273", "contact": ""}, {"title": "임산부 건강관리 서비스", "text": "[임산부 건강관리 서비스] 대상: 육아·양육. 마감: 상시신청. 내용: - 취약 출산가정 방문 및 전화상담 건강관리 서비스 제공 - 임산부 프로그램 운영 등 지원내용: ○ 취약 출산가정 임산부 방문 교육 및 상담 실시", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000274", "contact": ""}, {"title": "고혈압·당뇨병 환자 진료비 및 약제비 지원", "text": "[고혈압·당뇨병 환자 진료비 및 약제비 지원] 대상: 모든 도민. 마감: 상시신청. 내용: 만 65세 이상 고혈압·당뇨병 질환자 월1회 진료비·약제비 지원 지원내용: ○ 주민등록상 관내 거주 만 30세 이상(당해년도 12월 31일 기준) 고혈압 당뇨병 환자 - 만 30세 이상~64세 : 의료기관에 등록비", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000275", "contact": ""}, {"title": "감자 종서 구입비 지원", "text": "[감자 종서 구입비 지원] 대상: 농어업인. 마감: 매년 1~2월. 내용: 농업인에게 가을 재배용 감자 종서 구입비 일부 지원 지원내용: ○ 농업경영체로 등록한 농업인(농업경영체에 등록된 감자 재배지 기준)에게 가을 재배용 감자 종서 구입비 일부(60%) 지원", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000278", "contact": ""}, {"title": "제주청년 희망사다리 재형저축", "text": "[제주청년 희망사다리 재형저축] 대상: 청년·신혼, 소상공인·창업. 마감: 재형저축 사업 공고시. 내용: 중소기업 근로자( 15세 ~ 39세) 대상 재형저축 사업 지원내용: ○ 제주 청년 희망사다리 재형저축 사업 : 중소기업 근로자( 15세 ~ 39세) 10만원, 기업 15만원, 도 25만원을 5년간 적립해서 만", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000279", "contact": ""}, {"title": "홀로 사는 노인 에너지드림 지원", "text": "[홀로 사는 노인 에너지드림 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: ○ 노인맞춤돌봄서비스 대상자 중 차상위계층, 기초연금수급 홀로 사는 노인에게 냉난방비 지원 지원내용: ○ 냉난방비 1인당 연 100,000원 지원 - 에너지드림 바우처카드 지급 원칙 - 전기요금 예외 지급 가능 ※ 냉난방 방식이", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000280", "contact": ""}, {"title": "입양축하금 지원", "text": "[입양축하금 지원] 대상: 모든 도민. 마감: 상시신청. 내용: 입양가정에 입양 축하금 지원 지원내용: ○ 지원대상 : 입양신고일 당시 제주도에 1년 이상 주민등록을 두고 실제 거주하면서 보호대상아동을 입양한 가정 ○ 지원금액 - 일반입양", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000281", "contact": ""}, {"title": "제주특별자치도 보훈예우수당", "text": "[제주특별자치도 보훈예우수당] 대상: 모든 도민. 마감: 상시신청. 내용: 국가유공자(유족) 등을 위해 보훈예우수당, 사망위로금, 현충수당, 호국수당 지원 지원내용: ○ 보훈예우수당: 제주특별자치도에 주소를 둔 국가유공자(유족)에게 매월 수당 지급 ○ 사망위로금: 보훈예우수당 지급을 받던 유족이 사망시", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000282", "contact": ""}, {"title": "산모·신생아 건강관리 서비스 본인부담금 지원", "text": "[산모·신생아 건강관리 서비스 본인부담금 지원] 대상: 육아·양육. 마감: 상시신청. 내용: 출산가정에 산모신생아 건강관리 서비스 본인부담금 지원 지원내용: 산모신생아 건강관리 서비스 정부지원금 외 본인부담금 일부 지원 ○ 본인부담금의 50%지원: 최대 40만원", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000283", "contact": ""}, {"title": "여성장애인 가사도우미 지원", "text": "[여성장애인 가사도우미 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 여성장애인(저소득층 우선)을 위한 가사도우미 지원 지원내용: 여성장애인 가구에 주2회~5회(1회 평균 2~5시간) 가사도우미 지원으로 임신․출산․양육, 외출, 가사지원 제공", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000284", "contact": ""}, {"title": "한우 산업 육성 지원", "text": "[한우 산업 육성 지원] 대상: 농어업인. 마감: 2025.12.19~2026.01.09. 내용: 한우농가 등에 축사, 퇴비사, 조사료 등 시설 장비 지원 지원내용: ○ 사업기간 : 2026.1.~12. ○ 사업내용 : 축사, 퇴비사, 조사료 장비(본체 포함) 등 한(흑)우 송아지 생산 사육에 필요한 시", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000286", "contact": ""}, {"title": "저소득층 국민건강보험료 지원", "text": "[저소득층 국민건강보험료 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 저소득 노인, 장애인 세대당 건강보험료(장기요양보험료 포함) 전액 지원 지원내용: ○ 지원대상: 제주특별자치도에 주소를 둔 건강보험공단 가입자 중 「의료급여법」제3조에 따른 수급권자가 아닌 자로서 건강보험료 부과금액이「건강보험", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000287", "contact": ""}, {"title": "의사상자 지원제도", "text": "[의사상자 지원제도] 대상: 모든 도민. 마감: 상시신청. 내용: 의사상자를 위한 보상금 지급 지원내용: ○ 의사상자 지원제도 - 직무외의 행위로 위해에 처한 다른 사람의 생명, 신체 또는 재산을 구하다가 사망하거나 부상을 입은 사람을 의사자 또는", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000290", "contact": ""}, {"title": "농업인 안전재해보험 지원", "text": "[농업인 안전재해보험 지원] 대상: 농어업인. 마감: 상시신청. 내용: 농업인에게 안전재해보험료 지원 지원내용: ○ 농업인 안전재해보험 가입비 지원 - 지원대상 : 공제가입일 현재 제주시 또는 서귀포시에 주소를 두고, 영농활동에 종사하는 만 15세 이상", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000291", "contact": ""}, {"title": "장애인 활동지원 추가지원", "text": "[장애인 활동지원 추가지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 시간이 부족한 장애인활동지원 대상자에게 활동지원급여 추가 지원 지원내용: 장애인활동지원 기본 시간 소멸 이후 추가지원 요건 충족 장애인에게 월 30시간 ~ 90시간 지원 <추가지원 요건> 1. 정기적 사회활동", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000292", "contact": ""}, {"title": "해녀 육성·보호 및 장비 지원", "text": "[해녀 육성·보호 및 장비 지원] 대상: 모든 도민. 마감: 접수기관 별 상이. 내용: 해녀 대상 장비, 어촌계 가입비, 안전공제 가입비 지원 지원내용: ○ 장비지원 : 제주시 관내 해녀에게 해녀복 및 테왁 보호망 지원 ○ 해녀육성 : 신규해녀 어촌계 가입비 지원 ○ 해녀보호 : 해녀", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000293", "contact": ""}, {"title": "노인 건강진단 지원", "text": "[노인 건강진단 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 65세 이상 의료급여수급권자 중 희망자에게 노인건강진단 지원 지원내용: 65세 이상 의료급여수급권자를 대상으로 노인건강진단 실시", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000294", "contact": ""}, {"title": "보리생산 농가 수매가 보전 지원", "text": "[보리생산 농가 수매가 보전 지원] 대상: 농어업인. 마감: 지역농협의 보리 수매 계약재배 신청기간 내. 내용: 보리 계약재배 농가 수매가 차액 보전 지원 지원내용: ○ 보리생산농가 수매가 차액 보전 지원", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000295", "contact": ""}, {"title": "기초생활수급 무주택 독거노인 주거비 지원", "text": "[기초생활수급 무주택 독거노인 주거비 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: ○ 무주택 독거노인 가구에 주거비 차등 지원( 연 1회) 지원내용: ○ 무주택 독거노인 가구에 주거비 지원(연 1회 지원) - 임대료에 따라 가구당 400,000원~700,000원 차등지원 - 가형: 임대", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000296", "contact": ""}, {"title": "입양아동 축하금 지원", "text": "[입양아동 축하금 지원] 대상: 육아·양육. 마감: 상시신청. 내용: 아동을 입양한 가정에 축하금 지원 2,000천원 지원내용: ○ 지원대상 : 입양신고일 당시 제주도에 1년 이상 주민등록을 두고 실제 거주하면서 보호대상아동을 입양한 가정 ○ 지원금액 - 일반입양", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000297", "contact": ""}, {"title": "임산물 생산 및 유통지원", "text": "[임산물 생산 및 유통지원] 대상: 모든 도민. 마감: 매년 초(공고 시). 내용: 임업인 등에게 톱밥배지, 표고자목 운송비 지원 지원내용: ○ 톱밥배지, 표고자목 운송비 지원", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000298", "contact": ""}, {"title": "홀로사는노인지원센터 운영지원", "text": "[홀로사는노인지원센터 운영지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 홀로사는 노인을 대상으로 인식개선사업 및 실태조사 등 실시 지원내용: ○ 만 65세 이상의 홀로 사는 노인에 대한 인식개선 사업 및 주거개선 사업, 실태조사 등", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000299", "contact": ""}, {"title": "청각장애인 인공달팽이관 수술 지원", "text": "[청각장애인 인공달팽이관 수술 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 청각장애인에게 인공달팽이관 수술 및 재활·매핑 치료비 지원 지원내용: ○ 수술비 지원 : 수술에 소요되는 비용으로 1인당 700만원 이내 ○ 재활·매핑 치료비 : 수술 다음 연도부터 2년간 1인당 300만원", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000300", "contact": ""}, {"title": "고엽제후유(의)증환자 도외병원 수진교통비", "text": "[고엽제후유(의)증환자 도외병원 수진교통비] 대상: 모든 도민. 마감: 상시신청. 내용: 고엽제후유(의)증환자에게 연1회 등급판정을 위한 신체검사시 도외병원에 대한 수진교통비 지원 지원내용: ○ 지원대상: 2026년 1월 ~ 12월 중 도외검진을 받은 고엽제 후유(의)증 환자 * 연 1회 등급판정을 위한 신체검사에 한해 지원,", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000301", "contact": ""}, {"title": "감염병 환자 진료를 위한 항공비 지원", "text": "[감염병 환자 진료를 위한 항공비 지원] 대상: 모든 도민. 마감: 상시신청. 내용: HIV 감염인에게 도외 의료기관 진료시 발생한 항공비 지원 지원내용: ○ 감염병(HIV환자 등) 진료를 위한 항공비 등 지원 : HIV 감염인 도외 의료기관 진료시 발생한 항공비 지원 - 항공료는 월 1회 11", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000302", "contact": ""}, {"title": "제주 지역사랑상품권 탐나는전 안내", "text": "[제주 지역사랑상품권 탐나는전 안내] 대상: 모든 도민. 마감: 상시신청. 내용: 소비자에게 할인 및 소득공제 혜택, 가맹점에 수수료 절감 혜택 등 제공 지원내용: ○ 소비자 - 탐나는전 카드 및 모바일 결제 시 결제액의 일정비율 포인트 적립(캐시백) (적립) 연 매출액 10억원 이하 가맹점 결제", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000303", "contact": ""}, {"title": "저소득 한부모가족 자립 지원", "text": "[저소득 한부모가족 자립 지원] 대상: 육아·양육. 마감: 상시신청. 내용: 저소득 한부모가족에게 중·고교 자녀학습비, 세대주 직업훈련비, 월동준비금 등 자립 지원 지원내용: ○ 한부모가족 세대주 직업훈련비 지원 : 1인/월 30만원(최대 6개월 지원) ○ 한부모가족 중지 가구(자녀 연령도래) 자립정착금 지원", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000305", "contact": ""}, {"title": "가정위탁종료 및 시설퇴소아동 자립정착금 지원", "text": "[가정위탁종료 및 시설퇴소아동 자립정착금 지원] 대상: 육아·양육. 마감: 상시신청. 내용: 가정위탁 및 시설퇴소 아동에게 자립지원금 지급 지원내용: ○ 자립준비청년(보호종료아동) 자립정착금 지원 - 지급대상 : 만 18세 이후 아동복지시설 및 가정위탁 보호가 종료된 자립준비청년(보호종료", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000307", "contact": ""}, {"title": "청각·언어장애인 영상전화 사용료 지원", "text": "[청각·언어장애인 영상전화 사용료 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 청각 및 언어장애인에게 영상전화 사용료 지원 지원내용: ○ 1인 월 33,300원 지원 - 인터넷 사용료 30,000원, 기본요금 3,300원 - 매 분기마다 지급(3·6·9·12)", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000308", "contact": ""}, {"title": "구강보건서비스", "text": "[구강보건서비스] 대상: 모든 도민. 마감: 상시신청. 내용: 서귀포시 주민에게 불소양치용액 무료 제공 지원내용: ○ 서귀포시 지역주민에게 불소양치용액을 무료로 제공", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000309", "contact": ""}, {"title": "백내장 수술비 지원", "text": "[백내장 수술비 지원] 대상: 이동약자·어르신. 마감: 상시신청. 내용: 만 65세 이상 노인에게 백내장 수술비(본인부담금) 지원 - 1안구 12만원 이내 지원내용: ○ 지원내용 : 백내장 수술비 1인당 년 1회 ○ 지원기준 : 1인당 1안구 본인부담금 최대 120,000원 지원 ○ 시술의료기관 :", "url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/650000000310", "contact": ""}];
const CONTACTS = {"meta": {"note": "제주 주요 기관 대표번호 — 챗봇 폴백용. 검색으로 지속 보강 예정"}, "default": {"name": "제주120 만덕콜센터", "tel": "064-120", "detail": "유료, 07~22시, 야간·공휴일은 당직실(064-710-2222) 전환, 연중무휴", "desc": "제주도 통합 민원·안내"}, "orgs": [{"keywords": ["관광", "여행", "맛집", "축제", "크루즈", "올레"], "name": "제주관광공사", "tel": "064-740-6000", "detail": "평일 09~18시", "desc": "관광 정보·마케팅"}, {"keywords": ["창업", "스타트업", "벤처", "기업"], "name": "제주창조경제혁신센터", "tel": "064-759-9200", "detail": "평일 09~18시", "desc": "창업·스타트업 지원"}]};


const DATA_BASE = "https://kokoom94-ai.github.io/mondak/data/";
const CACHE = { at: 0, corpus: null, key: null };          // 모듈 캐시 (웜 인스턴스 재사용)
const CACHE_TTL = 60 * 60 * 1000;               // 60분 (대역폭 절감)

async function loadJson(name) {
  try {
    const r = await fetch(DATA_BASE + name, { headers: { Accept: "application/json" } });
    if (!r.ok) { console.warn("데이터 로드 실패:", name, r.status); return null; }
    return await r.json();
  } catch (e) { console.warn("데이터 로드 예외:", name, e.message); return null; }
}

function clip(s, n) { s = (s || "").toString().replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n) : s; }

// 조례·법령 링크 (몬딱 lawUrl 규칙과 동일)
function lawUrl(l) {
  if (l.url) return l.url;
  const local = /(조례|규칙|훈령|예규)/.test(l.ty || "");
  const kind = local ? "자치법규" : "법령";
  return "https://www.law.go.kr/" + kind + "/" + encodeURIComponent((l.t || "").replace(/ /g, ""));
}

// 각 데이터 → 통일 포맷 {title, text, url, contact, kind}
function normPolicy(x) {
  const parts = [
    "[지원사업] " + (x.t || ""),
    x.s || "",
    x.who && x.who.length ? "대상: " + x.who.join(",") : "",
    x.due ? "마감: " + x.due : "",
    x.amt ? "지원: " + x.amt : "",
    x.where ? "주관: " + x.where : "",
  ].filter(Boolean);
  return { title: x.t || "", text: clip(parts.join(" / "), 300), url: x.url || "", contact: "", kind: "지원사업" };
}
function normLaw(l) {
  const parts = [
    "[" + (l.ty || "법령") + "] " + (l.t || ""),
    l.f ? "(" + l.f + " 분야)" : "",
    l.d ? "제정·개정 " + l.d : "",
  ].filter(Boolean);
  return { title: l.t || "", text: clip(parts.join(" "), 200), url: l.url || lawUrl(l), contact: "", kind: "법령·조례" };
}
function normVisit(v) {
  const parts = [
    "[관광:" + (v.catLabel || "") + "] " + (v.title || ""),
    v.region ? "(" + v.region + ")" : "",
    v.intro || "",
    v.tags ? "태그: " + clip(v.tags, 80) : "",
    v.addr || "",
  ].filter(Boolean);
  const url = v.id ? "https://www.visitjeju.net/kr/detail/view?contentsid=" + v.id : "";
  return { title: v.title || "", text: clip(parts.join(" "), 280), url, contact: v.phone || "", kind: "관광" };
}

// 통합 코퍼스 구축 (캐시)
// 공공기관 (orgs.json) → 코퍼스
function normOrg(o) {
  const parts = [
    "[기관] " + (o.name || ""),
    o.type ? "(" + o.type + ")" : "",
    o.biz ? "주요사업: " + o.biz : "",
    o.notice_kind ? "공고: " + o.notice_kind : "",
    o.phone ? "전화: " + o.phone + (o.verified ? "" : " ※출처별 상이·미검증, 제주120(064-120) 경유 권장") : "",
    o.jurisdiction === "제주 관할(도외 소재)" ? "※ 제주에 청사 없음, " + (o.region || "") + " 소재 기관이 제주 관할" : "",
    o.region ? "소재: " + o.region : "",
    o.alias && o.alias.length ? "별칭: " + o.alias.join(",") : "",
  ].filter(Boolean);
  return {
    title: o.name || "",
    text: clip(parts.join(" / "), 300),
    url: o.site || "",
    contact: o.phone || "",
    kind: o.layer === "L8" ? "민원전화" : "공공기관",
  };
}

// FAQ (faq.json) → 코퍼스
function normFaq(f) {
  return {
    title: f.q || "",
    text: clip("[정책FAQ·" + (f.cat || "") + "] " + (f.a || "") +
      (f.tags && f.tags.length ? " / 키워드: " + f.tags.join(",") : "") +
      " ※관리자 정리 참고자료로 금액·요건은 변동 가능, 제주120(064-120) 확인 권장", 340),
    url: "",
    contact: "",
    kind: "정책FAQ",
  };
}

// 관광 데이터가 필요한 질문인지 판정
//  1) 일반 관광 키워드  2) 관광지 고유명사(비짓제주 제목 매칭)
const NAMECACHE = { at: 0, names: null };
async function needTourism(question) {
  if (TOURISM_RE.test(question)) return true;
  // 관광지 이름이 질문에 들어있는지 — 제목만 가볍게 확인
  try {
    if (!NAMECACHE.names || Date.now() - NAMECACHE.at > CACHE_TTL) {
      const vj = await loadJson("visitjeju.json");
      NAMECACHE.names = (vj && vj.items ? vj.items : []).map(x => (x.title || "").trim()).filter(t => t.length >= 2);
      NAMECACHE.at = Date.now();
      NAMECACHE.raw = vj;   // 이미 받았으므로 재사용
    }
    const q = question.replace(/\s+/g, "");
    // 접미 지역어를 뗀 핵심명도 함께 비교 ("9.81파크 제주" → "9.81파크")
    const strip = (t) => t.replace(/\s+/g, "").replace(/(제주|제주도|서귀포|본점|점)$/, "");
    for (const n of NAMECACHE.names) {
      const nn = n.replace(/\s+/g, "");
      if (nn.length >= 3 && q.includes(nn)) return true;
      const core = strip(nn);
      if (core.length >= 3 && q.includes(core)) return true;
      // 질문이 등록명보다 짧은 경우 (예: "카멜리아" → "카멜리아힐")
      if (nn.length >= 4 && nn.includes(q) && q.length >= 4) return true;
    }
  } catch (e) { console.warn("관광 판정 예외:", e.message); }
  return false;
}

// 축제·행사(festival.json) → 코퍼스
// 화면(제주행사모음)에는 있는데 챗봇 코퍼스에는 빠져 있어 "9월 축제"를 몰랐다.
function normFest(f, today){
  const st = f.start || "", en = f.end || "";
  let state = f.status || "";
  if (!state) state = (en && en < today) ? "종료" : (st && st > today ? "예정" : "진행중");
  const period = (st && en) ? (st + " ~ " + en) : (st || en || "기간미상");
  const parts = [
    "[축제·행사] " + state,
    "기간: " + period,
    f.region ? "지역: " + f.region : "",
    f.addr || "",
    f.intro || "",
  ].filter(Boolean);
  return {
    title: f.title || "",
    text: clip(parts.join(" / "), 300),
    url: f.link || "https://www.visitjeju.net/kr/festival",
    contact: "",
    kind: "축제",
  };
}

// 관광 통계(tourism_static.json / tourism.json) → 코퍼스
function normTour(title, text, tag){
  // 관광 통계는 수치 나열이라 340자로는 최근 값이 잘린다 → 넉넉히
  return { title: title, text: clip("[관광통계·"+tag+"] "+text, 900),
           url: "https://data.ijto.or.kr", contact: "", kind: "관광통계" };
}
function tourDocs(st, dy){
  const out=[];
  try{
    // 연도별 추이
    const ys=(st&&st.yearly&&st.yearly.items)||[];
    const full=ys.filter(x=>!x.partial);
    if(full.length){
      const pk=full.reduce((a,b)=>b.foreign>a.foreign?b:a);
      const dpk=full.reduce((a,b)=>b.domestic>a.domestic?b:a);
      const lt=full[full.length-1];
      out.push(normTour("제주 연도별 입도 관광객 수 추이 내국인 외국인",
        full.map(x=>x.year+"년 전체 "+x.total.toLocaleString()+"명(내국인 "+x.domestic.toLocaleString()+
        ", 외국인 "+x.foreign.toLocaleString()+")").join(" / "), "연도별"));
      out.push(normTour("제주 입도객 최고·최저 기록",
        "외국인 최고 "+pk.year+"년 "+pk.foreign.toLocaleString()+"명, 내국인 최고 "+dpk.year+"년 "+
        dpk.domestic.toLocaleString()+"명. 최근 "+lt.year+"년 외국인은 정점의 "+
        Math.round(lt.foreign/pk.foreign*100)+"% 수준.", "기록"));
    }
    // 국가별
    const na=(st&&st.nations)||{};
    if(na.items&&na.items.length) out.push(normTour("국가별 외국인 관광객 입도객 수 비중 중국 일본 대만 ("+na.month+")",
      na.items.map(x=>x.name+" "+x.value.toLocaleString()+"명("+x.share+"%)").join(", "), "국가별"));
    // 거주지
    const og=(st&&st.origin)||{};
    if(og.sido&&og.sido.length){
      out.push(normTour("국내 관광객 거주지 어디서 오나 시도별 서울 경기 ("+og.month+")",
        "총 "+Number(og.total).toLocaleString()+"명 · "+
        og.sido.map(x=>x.name+" "+Number(x.value).toLocaleString()+"명("+x.share+"%)").join(", "), "거주지"));
      if(og.sgg_top&&og.sgg_top.length) out.push(normTour("제주 방문객 많은 시군구 도시 순위 ("+og.month+")",
        og.sgg_top.map((x,i)=>(i+1)+"위 "+x.name+" "+Number(x.value).toLocaleString()+"명").join(", "), "거주지"));
    }
    // 국가별 소비
    const sp=(st&&st.spend_nation)||{};
    if(sp.items&&sp.items.length){
      out.push(normTour("국가별 외국인 소비 금액 카드 지출 ("+sp.year+"년)",
        sp.items.map(x=>x.name+" "+Math.round(x.value/1e8).toLocaleString()+"억원("+x.share+"%)").join(", "), "소비"));
      const g=(sp.rank_gap||[]).filter(x=>x.gap>=2);
      if(g.length) out.push(normTour("입도객 대비 소비가 많은 국가",
        g.map(x=>x.name+" 입도객 "+x.visit_rank+"위 → 소비 "+x.spend_rank+"위").join(", ")+
        ". 기준 시점이 달라 순위로만 비교한 값입니다.", "양보다질"));
    }
    // 읍면동
    const em=(dy&&dy.emd)||null;
    if(em&&em.items){
      out.push(normTour("읍면동 지역별 방문객 유동인구 순위 전체 ("+em.month+")",
        em.items.map(x=>x.rank+"위 "+x.name+" "+x.native.toLocaleString()+"명"+
          (typeof x.native_yoy==="number"?"(전년 "+(x.native_yoy>0?"+":"")+x.native_yoy+"%)":"")).join(", "), "읍면동"));
      // 읍면동별 개별 문서 — "애월읍 방문객 몇 명" 같은 질문 대응
      em.items.forEach(x=>{
        const p=(v)=>typeof v==="number"?((v>0?"+":"")+v+"%"):"-";
        out.push(normTour(x.name+" 방문객 관광객 수 ("+em.month+")",
          x.name+" 방문객 "+em.count+"곳 중 "+x.rank+"위. 내국인 "+Number(x.native).toLocaleString()+
          "명(전년 "+p(x.native_yoy)+", 전월 "+p(x.native_mom)+"), 외국인 "+Number(x.foreign).toLocaleString()+
          "명(전년 "+p(x.foreign_yoy)+"). 외국인 비중 "+x.foreign_ratio+"%"+
          (x.flags&&x.flags.length?" ["+x.flags.join("·")+"]":"")+
          ". 통신사 기준 추정치입니다.", "읍면동"));
      });
      if(em.dist&&em.dist.native&&em.dist.foreign){
        const D=em.dist;
        out.push(normTour("읍면동 방문객 증감 분포 평균 편차 ("+em.month+")",
          "43개 읍면동 전년 동월 대비 — 내국인 평균 "+D.native.mean+"%(범위 "+D.native.min+"~"+D.native.max+
          "%, 표준편차 "+D.native.sd+"), 외국인 평균 "+D.foreign.mean+"%(범위 "+D.foreign.min+"~"+D.foreign.max+
          "%, 표준편차 "+D.foreign.sd+"). 외국인은 지역별 편차가 작고 내국인은 큽니다.", "분포"));
      }
      if(em.alerts&&em.alerts.length) out.push(normTour("평균에서 크게 벗어난 읍면동 이례 지역",
        em.alerts.slice(0,12).map(a=>a.name+" 내국인 "+a.native_yoy+"%"+
          (a.z_native!=null?"("+a.z_native+"σ)":"")+" 외국인 "+a.foreign_yoy+"%"+
          (a.z_foreign!=null?"("+a.z_foreign+"σ)":"")+" ["+a.tags.join("·")+"]").join(" / ")+
        ". σ는 43곳 평균에서 벗어난 정도이며 1.5 이상이면 이례적입니다.", "이례지역"));
      if(em.intl_spots&&em.intl_spots.length) out.push(normTour("외국인 비중 높은 읍면동",
        em.intl_spots.map(x=>x.name+" "+x.ratio+"%").join(", ")+" (평균 "+em.avg_foreign_ratio+"%)", "외국인비중"));
    }
    // 카드매출
    const cd=(dy&&dy.card)||null;
    if(cd&&cd.trend) out.push(normTour("제주 카드매출 관광객 대 도민 ("+cd.period+")",
      "최신 "+cd.latest+" 기준 관광객 소비 비중 "+cd.trend.share_last+"%, 도민 "+
      (100-cd.trend.share_last).toFixed(1)+"%. 1년 전 대비 "+(cd.trend.share_delta>0?"+":"")+
      cd.trend.share_delta+"%p. 카드 정산 주기로 최신월이 지연됩니다.", "소비주체"));
    // 항공·여객선
    const air=(dy&&dy.air)||null;
    if(air&&air.items&&air.items.length){
      const it=air.items;
      const pick=(k)=>it.filter(x=>typeof x[k]==="number"&&x[k]>0);
      const line=(lb,k)=>{
        const v=pick(k); if(v.length<2) return "";
        const lo=v.reduce((a,b)=>b[k]<a[k]?b:a), pk=v.reduce((a,b)=>b[k]>a[k]?b:a), lt=v[v.length-1];
        return lb+" 최근 "+lt.date+" "+Number(lt[k]).toLocaleString()+
               ", 최저 "+lo.date+" "+Number(lo[k]).toLocaleString()+
               "(대비 "+(lt[k]/lo[k]).toFixed(1)+"배), 최고 "+pk.date+" "+Number(pk[k]).toLocaleString()+
               "(대비 "+Math.round(lt[k]/pk[k]*100)+"%)";
      };
      const parts=[line("국내선","domestic"),line("국제선","intl"),line("전체","total")].filter(Boolean);
      if(parts.length) out.push(normTour("제주 항공 운항 편수 국내선 국제선 회복 ("+air.period+")",
        parts.join(" / ")+". 단위는 편(운항 횟수)이며 금액이 아닙니다. 이 통계 기간 안에서의 최저·최고 대비 값입니다.", "항공"));
    }
    // 여객선
    const shp=(dy&&dy.ship)||null;
    if(shp&&shp.items&&shp.items.length){
      const v=shp.items.filter(x=>typeof x.value==="number"&&x.value>0);
      if(v.length>1){
        const lo=v.reduce((a,b)=>b.value<a.value?b:a), lt=v[v.length-1];
        out.push(normTour("제주 여객선 이용객 ("+shp.period+")",
          "최근 "+lt.date+" "+Number(lt.value).toLocaleString()+"명"+
          (typeof lt.yoy==="number"?"(전년 대비 "+lt.yoy+"%)":"")+
          ", 가장 적었던 "+lo.date+" "+Number(lo.value).toLocaleString()+"명 대비 "+
          (lt.value/lo.value).toFixed(1)+"배. 단위는 명(이용 인원)입니다.", "여객선"));
      }
    }
    // 업종별
    const ind=(dy&&dy.industry)||null;
    if(ind&&ind.items&&ind.items.length) out.push(normTour("업종별 카드 소비 금액 ("+ind.month+")",
      ind.items.slice(0,12).map(x=>x.name+" "+Math.round((x.value||0)/1e8).toLocaleString()+"억원"+
        (typeof x.share==="number"?"("+x.share+"%)":"")).join(", ")+". 카드 결제 금액 기준입니다.", "업종별"));
    // 일별 입도객 — "8월 24일 관광객 몇 명" 같은 질문 대응
    const dl=(dy&&dy.daily)||null;
    if(dl&&dl.items&&dl.items.length){
      const fmt=(d)=>String(d).slice(0,4)+"년 "+Number(String(d).slice(4,6))+"월 "+Number(String(d).slice(6,8))+"일";
      // 최신 날짜를 앞에 둔다 — 문서 길이 제한에 뒷부분이 잘려 최근 수치가 사라지는 것을 막기 위함
      const dsc=dl.items.slice().reverse();
      const line=(x)=>fmt(x.date)+" 내국인 "+Number(x.kor||0).toLocaleString()+"명, 외국인 "+
        Number(x.forgn||0).toLocaleString()+"명, 합계 "+Number(x.total||0).toLocaleString()+"명";
      out.push(normTour("일별 제주 입도 관광객 수 ("+dl.period+")",
        dsc.map(line).join(" / ")+". 제주관광 빅데이터 플랫폼 집계입니다.", "일별입도"));
      // 제공 기간 안내 — 범위 밖 날짜를 물었을 때 "없다"가 아니라 "어디까지 있다"를 답하도록
      {
        const f=dl.items[0], l=dl.items[dl.items.length-1];
        out.push(normTour("일별 입도객 자료 제공 기간 최신 날짜",
          "일별 입도 관광객 자료는 "+fmt(f.date)+"부터 "+fmt(l.date)+"까지만 있습니다. "+
          "가장 최근 집계는 "+fmt(l.date)+"이며 합계 "+Number(l.total||0).toLocaleString()+"명입니다. "+
          "그 이후 날짜(오늘·어제 포함)는 아직 집계되지 않아 제공할 수 없습니다. "+
          "집계는 며칠 뒤에 반영되므로, 최신 수치는 제주관광 빅데이터 플랫폼(data.ijto.or.kr)에서 확인해 주세요.",
          "제공기간"));
      }
      // 날짜별 개별 문서 — 특정 날짜 질문에 정확히 대응
      dl.items.forEach(x=>out.push(normTour(fmt(x.date)+" 제주 입도 관광객 수",
        fmt(x.date)+" 제주 입도객은 내국인 "+Number(x.kor||0).toLocaleString()+"명, 외국인 "+
        Number(x.forgn||0).toLocaleString()+"명, 합계 "+Number(x.total||0).toLocaleString()+"명입니다."+
        (typeof x.total_yoy==="number"?" 작년 같은 날 대비 "+(x.total_yoy>0?"+":"")+x.total_yoy+"%.":""),
        "일별입도")));
    }
    // 월별 계절
    const mo=(dy&&dy.monthly)||null;
    if(mo&&mo.items&&mo.items.length) out.push(normTour("월별 입도객 성수기 비수기 ("+mo.period+")",
      mo.items.map(x=>x.date+" 전체 "+Number(x.total).toLocaleString()+"명(내국인 "+
        Number(x.domestic||0).toLocaleString()+", 외국인 "+Number(x.foreign||0).toLocaleString()+")").join(", ")+
      (mo.peak?" 최성수기 "+mo.peak.month+", 최비수기 "+mo.low.month+", 격차 "+mo.gap_ratio+"배.":""), "월별"));
    // 시간대
    const hr=(dy&&dy.hourly)||null;
    if(hr&&hr.items){
      out.push(normTour("시간대별 카드 소비 금액 24시간 전체 ("+hr.month+")",
        hr.items.filter(x=>typeof x.hour==="number").map(x=>
          x.hour+"시 관광객 "+Math.round((x.tourist||0)/1e8).toLocaleString()+"억원("+
          Math.round(x.tourist_share||0)+"%), 도민 "+Math.round((x.local||0)/1e8).toLocaleString()+"억원"
        ).join(" / ")+". 카드 결제 금액 기준입니다.", "시간대"));
    }
    if(hr&&hr.items) out.push(normTour("시간대별 소비 패턴 몇 시 피크 ("+hr.month+")",
      "관광객 매출 정점 "+hr.peak_tourist+"시, 도민 정점 "+hr.peak_local+
      "시. 새벽 시간대는 관광객·도민 모두 소비 금액이 가장 적어 비중만으로 판단하면 오해가 생길 수 있습니다. 관광객 비중 최고 "+
      (hr.share_high?hr.share_high.hour+"시("+hr.share_high.share+"%)":"-")+", 최저 "+
      (hr.share_low?hr.share_low.hour+"시("+hr.share_low.share+"%)":"-")+".", "시간대"));
  }catch(e){ console.warn("관광 코퍼스 오류:", e.message); }
  return out;
}


// ── 화면에 있는 나머지 데이터도 전부 코퍼스에 넣는다.
//    (화면에 표시되는데 챗봇이 모르는 상황을 없애기 위함)
function normDoc(title, text, url, kind){
  return { title: title, text: clip(text, 340), url: url || "", contact: "", kind: kind };
}
function extraDocs(asm, cnc, edu, nws, plg, sch, sts){
  const out=[];
  try{
    // 국회의원
    const ms=(asm&&asm.members)||[];
    const bn=(m)=>Array.isArray(m.bills)?m.bills.length:(Number(m.bills)||0);
    if(ms.length) out.push(normDoc("제주 국회의원 명단 지역구 정당 상임위",
      ms.map(m=>`${m.name}(${m.dist}·${m.party}·${m.cmit||""}, 발의 ${bn(m)}건)`).join(", "),
      "https://www.assembly.go.kr", "국회의원"));
    ms.forEach(m=>{
      out.push(normDoc(`국회의원 ${m.name} ${m.dist} 프로필`,
        `${m.name} 의원. 지역구 ${m.dist}, 정당 ${m.party}, 상임위 ${m.cmit||"-"}, 당선 ${m.since||"-"}, 발의 법안 ${bn(m)}건.`,
        "https://www.assembly.go.kr", "국회의원"));
      const bs=Array.isArray(m.bills)?m.bills:[];
      if(bs.length) out.push(normDoc(`${m.name} 의원 발의 법안 목록`,
        bs.slice(0,25).map(b=>`${b.t}(${b.d||""}, ${b.result||b.stage||"-"}, ${b.cmit||""})`).join(" / "),
        "https://www.assembly.go.kr", "국회의원"));
      bs.slice(0,15).forEach(b=>out.push(normDoc(`법안 ${b.t}`,
        `${m.name} 의원 발의. 발의일 ${b.d||"-"}, 처리상태 ${b.result||b.stage||"-"}, 소관 ${b.cmit||"-"}.`,
        b.url||"https://www.assembly.go.kr", "국회의원")));
    });
    // 도의회 의안
    const ci=(cnc&&cnc.items)||[];
    if(ci.length){
      out.push(normDoc("제주도의회 의안 발의 현황",
        `최근 의안 ${ci.length}건. ` + ci.slice(0,25).map(x=>`${x.t}(${x.proposer||"-"}, ${x.status||"-"}, ${x.date||""})`).join(" / "),
        "https://www.council.jeju.kr", "도의회"));
      ci.slice(0,60).forEach(x=>out.push(normDoc(`도의회 의안 ${x.t}`,
        `${x.kind||"의안"} · 발의 ${x.proposer||"-"} · 상태 ${x.status||"-"} · ${x.date||""}`+(x.numpr?` · 공동발의 ${x.numpr}인`:""),
        x.url||"https://www.council.jeju.kr", "도의회")));
    }
    // 교육
    if(edu){
      const sp=edu.superintendent||{};
      if(sp.name) out.push(normDoc("제주 교육감 프로필 학력 경력",
        `${sp.name}${sp.hanja?"("+sp.hanja+")":""} 교육감. ${sp.note||""} `+
        (sp.edu?`학력: ${[].concat(sp.edu).join(", ")}. `:"")+
        (sp.career?`주요 경력: ${[].concat(sp.career).slice(0,6).join(", ")}.`:""),
        "https://www.jje.go.kr", "교육"));
      const pl=edu.pledges||[];
      if(pl.length) out.push(normDoc("제주 교육감 주요 공약",
        pl.map(p=>`${p.no}. ${p.title} — ${p.desc||""}`).join(" / ")+(edu.pledge_note?` (${edu.pledge_note})`:""),
        "https://www.jje.go.kr", "교육"));
      const bg=edu.budget||{};
      if(bg.total) out.push(normDoc("제주 교육청 예산 규모 구성",
        `${bg.year||""}년 총 ${bg.total}. `+
        ((bg.items||[]).map(x=>`${x.name} ${x.amount}(${x.share}%)`).join(", "))+
        (bg.rank?` 전국 ${bg.rank}.`:""),
        "https://eduinfo.go.kr", "교육"));
      const un=edu.universities||[];
      if(un.length) out.push(normDoc("제주 대학교 목록",
        un.map(u=>`${u.name}(${u.type}, ${u.region||""})`).join(", "), "", "교육"));
    }
    // 학교 — 201곳 전부 개별 문서화(전화·주소·홈페이지·설립구분까지)
    const si=(sch&&sch.items)||[];
    if(si.length){
      const SCH_LINK="https://www.schoolinfo.go.kr/ei/ss/Pneiss_b01_s0.do?SHL_IDF_CD=";
      const by={}, byRegion={};
      si.forEach(x=>{
        (by[x.level]=by[x.level]||[]).push(x.name);
        const rg=x.region||"기타"; (byRegion[rg]=byRegion[rg]||[]).push(x.name);
      });
      out.push(normDoc("제주 학교 수 초등학교 중학교 고등학교 현황",
        Object.entries(by).map(([k,v])=>`${k} ${v.length}곳`).join(", ")+` (총 ${si.length}곳)`,
        "https://www.schoolinfo.go.kr", "학교"));
      Object.entries(by).forEach(([lv,names])=>out.push(normDoc(`제주 ${lv} 목록 전체`,
        names.join(", "), "https://www.schoolinfo.go.kr", "학교")));
      Object.entries(byRegion).forEach(([rg,names])=>out.push(normDoc(`${rg} 학교 목록`,
        `${rg} 소재 학교 ${names.length}곳: `+names.join(", "), "https://www.schoolinfo.go.kr", "학교")));
      // 설립구분별
      const byF={};
      si.forEach(x=>{ const f=x.fond||"기타"; (byF[f]=byF[f]||[]).push(x.name); });
      Object.entries(byF).forEach(([f,names])=>out.push(normDoc(`제주 ${f} 학교 목록`,
        `${f} ${names.length}곳: `+names.join(", "), "https://www.schoolinfo.go.kr", "학교")));
      // 학교별 상세
      si.forEach(x=>{
        const parts=[];
        if(x.level) parts.push(x.level);
        if(x.fond)  parts.push(x.fond);
        if(x.region)parts.push(x.region);
        if(x.branch)parts.push("분교장");
        const info=[
          x.tel  ? `전화 ${x.tel}` : "",
          x.addr ? `주소 ${x.addr}` : "",
          x.site ? `홈페이지 ${x.site}` : "",
        ].filter(Boolean).join(" · ");
        out.push(normDoc(`${x.name} 전화번호 주소 홈페이지`,
          `${x.name}(${parts.join("·")}). ${info}`+
          (x.code?" 학교알리미에서 급식·학생수·공시정보를 볼 수 있습니다.":""),
          x.code ? SCH_LINK+x.code
                 : "https://www.schoolinfo.go.kr/ng/go/pnnggo_a01_l0.do?SEARCH_KEYWORD="+encodeURIComponent(x.name),
          "학교"));
      });
    }
    // 공약
    if(Array.isArray(plg)&&plg.length){
      const g={};
      plg.forEach(p=>{ (g[p.g]=g[p.g]||[]).push(`${p.no}.${p.t}`); });
      out.push(normDoc("제주 민선9기 100대 공약 분야별",
        Object.entries(g).map(([k,v])=>`[${k}] ${v.length}개`).join(", "), "", "공약"));
      Object.entries(g).forEach(([k,v])=>out.push(normDoc(`제주 공약 ${k} 분야`,
        v.join(" / "), "", "공약")));
    }
    // 뉴스 (최근만)
    const ni=(nws&&nws.items)||[];
    if(ni.length) out.push(normDoc("제주 최근 뉴스 헤드라인",
      ni.slice(0,30).map(x=>`${x.t}(${x.src||""}, ${x.d||""})`).join(" / "),
      "", "뉴스"));
    // 통계 셀
    if(sts&&sts.cells){
      const cs=sts.cells;
      const arr=Array.isArray(cs)?cs:Object.entries(cs).map(([k,v])=>({k:k,v:v}));
      if(arr.length) out.push(normDoc("제주 주요 통계 지표",
        arr.slice(0,40).map(x=>{
          const k=x.k||x.name||x.label||x.title||"", v=x.v||x.value||x.val||"";
          return typeof v==="object" ? `${k} ${JSON.stringify(v)}` : `${k} ${v}`;
        }).join(", "), "https://www.jeju.go.kr/stats", "통계"));
    }
  }catch(e){ console.warn("추가 코퍼스 오류:", e.message); }
  return out;
}

// 뉴스에서 '신청·모집' 소식만 따로 뽑아 지원사업으로 다시 싣는다.
// 도청 고시/공고를 직접 긁는 길이 막혀(러너 IP 차단) 있어, 이미 들어오는 뉴스에서
// 신청·모집 건을 건져 올린다. 언론이 다루는 지원사업은 대부분 여기로 잡힌다.
const APPLY_RE = /모집|공모|접수|신청|지원사업|보조금|보급사업|지원금|바우처|융자|이자\s?지원|선정/;
function normApplyNews(x){
  const t = x.t || x.title || "";
  return { title: t,
    text: clip("[신청·모집 소식] " + (x.d||"") + " " + (x.src||"") + " 보도. "
      + "접수 기간과 지원 규모는 원문 기사와 제주도 누리집(jeju.go.kr) 고시/공고를 확인하세요. "
      + "문의는 제주120(064-120).", 300),
    url: x.link || "https://www.jeju.go.kr/news/news/law/jeju.htm",
    contact: "제주120 064-120", kind: "지원공고" };
}

// 제주도청 고시/공고(jeju_notice.json) → 코퍼스
// 도청이 직접 내는 사업(히트펌프 보급사업 등)은 정부24 API에 없어 여기로만 들어온다.
function normNotice(x){
  const parts=[
    "[도청 공고] "+(x.sec||""),
    x.no ? "공고번호 "+x.no : "",
    x.dept ? "담당 "+x.dept : "",
    x.d ? "게시 "+x.d : "",
    x.apply ? "신청·모집 공고입니다. 접수 기간과 지원 규모는 원문 공고에서 확인하세요." : "",
    "도청 고시/공고 목록에서 공고번호 " + (x.no||"") + " 로 찾을 수 있습니다.",
    "문의는 제주120(064-120).",
  ].filter(Boolean);
  return { title: x.t||"", text: clip(parts.join(" / "), 300),
           url: x.link || x.list || "https://www.jeju.go.kr/news/news/law/jeju.htm",
           contact: "제주120 064-120", kind: "도청공고" };
}

// 화면에는 있는데 챗봇이 모르던 나머지 데이터
//  관광AX인사이트 / 인구현황 / 정부정책 브리핑 / 도의회 보도 / 입찰공고 / 이슈체크 여론지수 / 축제 시드
function moreDocs(ax, pop, pb, cn, bid, idx, fseed){
  const out=[];
  const n=(v)=>Number(v||0).toLocaleString();
  try{
    // 관광AX인사이트 — 기관별 AI 전환 동향
    const ai=(ax&&ax.items)||[];
    if(ai.length){
      out.push(normDoc("관광 AX 인사이트 기관별 AI 전환 동향 요약",
        `수집 ${ai.length}건(${(ax.meta&&ax.meta.since)||""} 이후). 최근: `+
        ai.slice(0,20).map(x=>`${x.title}(${x.source||""}, ${x.date||""})`).join(" / "),
        "https://www.korea.kr", "AX"));
      ai.slice(0,120).forEach(x=>out.push(normDoc(`[AX] ${x.title}`,
        `${x.description||""} 출처 ${x.source||""} ${x.date||""}`+(x.org?` · 기관 ${x.org}`:"")+(x.topic?` · 주제 ${x.topic}`:""),
        x.link||"", "AX")));
    }
    // 인구 현황 — 도 전체 + 읍면동 43곳
    if(pop&&pop.total){
      const t=pop.total;
      out.push(normDoc("제주 인구 현황 총인구 세대수 등록외국인",
        `${t.month||""} 기준 총인구 ${n(t.total)}명(주민등록 ${n(t.local)}명, 등록외국인 ${n(t.foreign)}명), `+
        `세대 ${n(t.house)}세대. 제주시 ${n(t.jeju_si)}명, 서귀포시 ${n(t.seogwipo)}명.`,
        "https://www.jeju.go.kr/stats/index.htm", "인구"));
      const em=pop.emd||[];
      if(em.length){
        out.push(normDoc("제주 읍면동 인구 순위 43곳",
          em.slice().sort((a,b)=>(b.total||0)-(a.total||0)).map(x=>`${x.name} ${n(x.total)}명`).join(", "),
          "https://www.jeju.go.kr/stats/index.htm", "인구"));
        em.forEach(x=>out.push(normDoc(`${x.name} 인구`,
          `${x.name} 총인구 ${n(x.total)}명(내국인 ${n(x.local)}명, 외국인 ${n(x.foreign)}명, 남 ${n(x.male)}·여 ${n(x.female)}).`,
          "https://www.jeju.go.kr/stats/index.htm", "인구")));
      }
    }
    // 정부정책 브리핑
    const pi=(pb&&pb.items)||[];
    if(pi.length){
      out.push(normDoc("정부정책 브리핑 최근 정책뉴스",
        pi.slice(0,25).map(x=>`${x.title}(${x.date||""})`).join(" / "),
        "https://www.korea.kr", "정책브리핑"));
      pi.slice(0,80).forEach(x=>out.push(normDoc(`[정책브리핑] ${x.title}`,
        `대한민국 정책브리핑 ${x.date||""}`, x.link||"https://www.korea.kr", "정책브리핑")));
    }
    // 도의회 관련 보도
    const ci=(cn&&cn.items)||[];
    if(ci.length){
      out.push(normDoc("제주도의회 관련 최근 보도",
        `${(cn.meta&&cn.meta.from)||""} 이후 ${ci.length}건. `+
        ci.slice(0,25).map(x=>`${x.t}(${x.d||""})`).join(" / "),
        "https://www.council.jeju.kr", "도의회"));
      ci.slice(0,120).forEach(x=>out.push(normDoc(`[도의회 보도] ${x.t}`,
        `${x.desc||""} ${x.src||""} ${x.d||""}`+((x.who&&x.who.length)?` · 관련 의원 ${x.who.join(", ")}`:""),
        x.link||"", "도의회")));
    }
    // 입찰·용역 공고 (나라장터)
    const bi=(bid&&bid.items)||[];
    if(bi.length){
      out.push(normDoc("제주 입찰 용역 공고 나라장터",
        `접수 중 ${bi.length}건. `+bi.slice(0,20).map(x=>`${x.title}(${x.org||""}, ~${x.close||""})`).join(" / "),
        "https://www.g2b.go.kr", "공고"));
      bi.forEach(x=>out.push(normDoc(`[공고] ${x.title}`,
        `${x.kind||""} · 발주 ${x.org||""} · 공고 ${x.posted||""} · 마감 ${x.close||""}`+
        (x.price?` · 추정가격 ${n(x.price)}원`:"")+(x.method?` · ${x.method}`:""),
        x.link||"https://www.g2b.go.kr", "공고")));
    }
    // 이슈체크 여론지수 — 요약만 (원문 목록은 화면에서 본다)
    if(idx&&idx.current){
      const c=idx.current, m=idx.meta||{}, p=(m.period||{});
      out.push(normDoc("제주 관광 여론지수 이슈체크 최근 현황",
        `${p.from||""}~${p.to||""} 수집 ${n(c.total)}건 중 부정 ${c.neg}%·중립 ${c.neu}%·긍정 ${c.pos}%. `+
        ((idx.rank||[]).slice(0,6).map(r=>`${r.name} ${r.n}건(부정 ${r.neg_n})`).join(", "))+
        ` 자체 수집·분류한 참고자료입니다.`,
        "https://kokoom94-ai.github.io/mondak/#gwan-issue", "여론"));
      const v=idx.voice||{};
      if(v.mix&&v.mix.length) out.push(normDoc("제주 관광 불만 구성비 분야별",
        `모인 불만 ${n(v.neg_n)}건 기준 — `+v.mix.map(x=>`${x.name} ${x.share}%(${x.n}건)`).join(", "),
        "https://kokoom94-ai.github.io/mondak/#gwan-issue", "여론"));
      const rk=(idx.risk&&idx.risk.clusters)||[];
      if(rk.length) out.push(normDoc("제주 관광 이슈 사건 묶음 확산도",
        rk.map(x=>`${x.label} ${x.n}건·매체 ${x.media}곳(${x.spread})`).join(", "),
        "https://kokoom94-ai.github.io/mondak/#gwan-issue", "여론"));
    }
    // 축제 시드 (비짓제주 미등록분 보완)
    const fs2=(fseed&&fseed.items)||[];
    if(fs2.length) out.push(normDoc("2026 제주 행사 통합일정 목록",
      fs2.map(x=>`${x.title}(${x.start||"기간미상"}${x.end?"~"+x.end:""}${x.kind?", "+x.kind:""})`).join(" / "),
      "https://www.visitjeju.net/kr/festival", "축제"));
  }catch(e){ console.warn("추가 코퍼스2 오류:", e.message); }
  return out;
}

async function buildCorpus(needTour) {
  const key = needTour ? "tour" : "base";
  if (CACHE.corpus && CACHE.key === key && Date.now() - CACHE.at < CACHE_TTL) return CACHE.corpus;

  const corpus = [];
  // 1) 지원사업: 내장 SUPPORT (검증된 핵심) + policies.json (최신 크롤링)
  for (const d of SUPPORT) corpus.push({ title: d.title, text: d.text, url: d.url || "", contact: d.contact || "", kind: "지원사업" });
  const pol = await loadJson("policies.json");
  if (pol && pol.items) { const seen = new Set(corpus.map(c => c.title)); for (const x of pol.items) { if (x && x.t && !seen.has(x.t)) { seen.add(x.t); corpus.push(normPolicy(x)); } } }

  // 2) 조례·법령
  const laws = await loadJson("laws.json");
  if (laws && laws.items) for (const l of laws.items) if (l && l.t) corpus.push(normLaw(l));

  // 3) 관광 (비짓제주) — 2.1MB로 크므로 관광 질문일 때만 로드
  //    buildCorpus(needTour) 인자로 제어

  // 4) 공공기관·민원전화 (orgs.json)
  const orgs = await loadJson("orgs.json");
  if (orgs && orgs.items) for (const o of orgs.items) if (o && o.name) corpus.push(normOrg(o));

  // 5) 관광 통계 (tourism_static.json + tourism.json)
  const [tstat, tdyn] = await Promise.all([
    loadJson("tourism_static.json"), loadJson("tourism.json")
  ]);
  if (tstat || tdyn) for (const d of tourDocs(tstat, tdyn)) corpus.push(d);

  // 5-2) 화면에 있는 나머지 데이터 전부
  const [asm, cnc, edu, nws, plg, sch, sts] = await Promise.all([
    loadJson("assembly.json"), loadJson("council.json"), loadJson("edu.json"),
    loadJson("news.json"), loadJson("pledges.json"), loadJson("schools.json"),
    loadJson("stats.json")
  ]);
  for (const d of extraDocs(asm, cnc, edu, nws, plg, sch, sts)) corpus.push(d);

  // 5-3) 축제·행사 (festival.json) — 172건으로 가벼워 항상 싣는다
  const fest = await loadJson("festival.json");
  if (fest && fest.items) {
    const today = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
    for (const f of fest.items) if (f && f.title) corpus.push(normFest(f, today));
  }

  // 5-4) 화면에 있는 나머지 데이터 (AX·인구·정책브리핑·도의회보도·공고·여론지수·축제시드)
  const [axd, popd, pbd, cnd, bidd, idxd, fsd] = await Promise.all([
    loadJson("ax.json"), loadJson("population.json"), loadJson("policybrief.json"),
    loadJson("councilnews.json"), loadJson("bids.json"), loadJson("issue_index.json"),
    loadJson("festival_seed.json")
  ]);
  for (const d of moreDocs(axd, popd, pbd, cnd, bidd, idxd, fsd)) corpus.push(d);

  // 5-5) 제주도청 고시/공고 (jeju_notice.json)
  const nt = await loadJson("jeju_notice.json");
  if (nt && nt.items) for (const x of nt.items) if (x && x.t) corpus.push(normNotice(x));

  // 5-6) 뉴스 중 신청·모집 건을 지원사업으로 한 번 더
  try{
    const nw = await loadJson("news.json");
    if (nw && nw.items) for (const x of nw.items)
      if (x && (x.t||"") && APPLY_RE.test(x.t)) corpus.push(normApplyNews(x));
  }catch(e){}

  // 6) 정책 FAQ 100선 (faq.json)
  const faq = await loadJson("faq.json");
  if (faq && faq.items) for (const f of faq.items) if (f && f.q) corpus.push(normFaq(f));

  // 관광 데이터는 관광 질문일 때만 (2.1MB 절감)
  if (needTour) {
    const vj = (NAMECACHE.raw && Date.now() - NAMECACHE.at < CACHE_TTL)
      ? NAMECACHE.raw : await loadJson("visitjeju.json");
    if (vj && vj.items) for (const v of vj.items) if (v && v.title) corpus.push(normVisit(v));
  }

  CACHE.corpus = corpus; CACHE.at = Date.now(); CACHE.key = key;
  console.log("코퍼스 구축:", corpus.length, "건 (지원+조례+관광+축제+기관+FAQ+관광통계+의회+교육+학교+공약+뉴스+AX+인구+정책브리핑+공고+여론+도청공고+지원공고)");
  return corpus;
}

// 질문 키워드로 후보 사전필터 (전체 ~5000 → 상위 N)
const QSTOP = new Set(["제주", "특별자치도", "도민", "어디", "무엇", "뭐", "알려줘", "있나요", "인가요", "관련", "정보", "해줘", "하는", "되는", "관해", "대해", "대한", "추천", "가볼", "갈만한", "싶어", "좋은", "해주", "무슨", "있어", "있는", "해서", "에서", "으로",
  "지원","신청","안내","운영","추진","사업","제도","관련","내용","방법","무엇","뭐","있어","어디","언제","어떻게","알려","궁금","해줘","주세요",
  "지원사업","지원금","보조사업","지원제도","지원정책"]);
const TOURISM_RE = /맛집|관광지|카페|오름|해변|해수욕장|여행|가볼|먹을|볼거리|명소|드라이브|숙소|흑돼지|해산물|올레|박물관|미술관|체험|근처|주변|여행지|놀거리|먹거리|디저트|브런치|축제|행사|페스티벌|공연|전시/;
const POLICY_RE = /조례|법령|법률|규정|규칙|근거|지원|보조금|신청|자격|대상|예산|정책|사업|지원금|혜택|보조/;
const ORG_RE = /전화|연락처|번호|문의|민원|신고|상담|어디로|어디에|담당|기관|공사|공단|재단|진흥원|연구원|센터|본부|청사|누리집|홈페이지|사무소|관할/;

function tokenize(s) { return (s.match(/[가-힣A-Za-z0-9]{2,}/g) || []).filter(t => !QSTOP.has(t)); }

// 도민이 쓰는 말과 문서에 적힌 말이 다르다.
// "농사 지원"을 물으면 자료에는 '농업·농가·영농·감귤'이라고만 적혀 있어 한 건도 안 잡혔다.
// 낱말 하나를 고치는 대신, 생활어 → 문서어를 통째로 넓힌다.
const SYN = {
  "농사": ["농업", "농가", "영농", "농산물"], "농민": ["농업인", "농가"], "밭": ["경작", "농지"],
  "귤": ["감귤", "만감류"], "고기": ["축산", "한우", "양돈"], "소": ["한우", "축산"], "돼지": ["양돈", "축산"],
  "고기잡이": ["어업", "수산"], "어부": ["어업인", "어가"], "바다일": ["어업", "수산"],
  "어업": ["수산", "양식", "어가", "해녀"], "낚시": ["수산", "어업"], "해녀": ["해녀", "어업"],
  "집": ["주택", "주거", "임대"], "전세": ["주택", "임차", "전세자금"], "월세": ["임차", "주거"],
  "아이": ["아동", "보육", "영유아", "자녀"], "애기": ["영유아", "보육"], "육아": ["보육", "아동", "돌봄"],
  "어르신": ["노인", "경로"], "노인": ["어르신", "경로"], "장애": ["장애인"],
  "병원": ["의료", "진료", "보건"], "아플": ["의료", "건강"], "약값": ["의료비", "약제비"],
  "쓰레기": ["폐기물", "재활용", "자원순환"], "물값": ["상수도", "수도요금"],
  "차": ["자동차", "차량"], "전기차": ["전기자동차"], "버스": ["대중교통", "교통"],
  "취업": ["일자리", "고용", "취업지원"], "일자리": ["고용", "취업"], "장사": ["소상공인", "상권", "자영업"],
  "가게": ["소상공인", "점포", "상권"], "회사": ["기업", "사업체"], "창업": ["창업", "스타트업"],
  "학교": ["교육", "학생"], "학원": ["사교육", "교육"], "등록금": ["장학", "학자금"],
  "군대": ["병역", "병무"], "결혼": ["신혼", "혼인"], "출산": ["출산", "임신", "산모"],
  "청년": ["청년", "대학생"], "이사": ["전입", "주거"], "세금": ["지방세", "세정"],
  "태양광": ["신재생", "재생에너지"], "난방": ["에너지", "히트펌프", "난방비"],
  "관광객": ["입도객", "방문객"], "여행객": ["관광객", "입도객"],
};
function expand(qs, question) {
  const out = qs.slice();
  for (const k in SYN) if (question.indexOf(k) >= 0)
    for (const v of SYN[k]) if (out.indexOf(v) < 0) out.push(v);
  return out;
}

function prefilter(question, corpus, N) {
  const qs = expand(tokenize(question), question);
  const qStr = question.toLowerCase();
  // 질문 의도 → 가중할 데이터 종류
  const boostTour = TOURISM_RE.test(question);
  const boostPol = POLICY_RE.test(question);
  const boostOrg = ORG_RE.test(question);
  if (!qs.length) return corpus.slice(0, N);

  const scored = [];
  for (const doc of corpus) {
    const titleLc = doc.title.toLowerCase();
    const hay = (doc.title + " " + doc.text).toLowerCase();
    let sc = 0;
    // 정방향: 질문 토큰이 제목/본문에
    for (const t of qs) {
      const tl = t.toLowerCase();
      // 긴 낱말일수록 신뢰도가 높다. 2자짜리 흔한 낱말이 순위를 흔들지 않게 낮게 준다.
      // 두 글자여도 '감귤·어업·축산·인구'처럼 뜻이 분명한 낱말이 많다.
      // 흔한 행정어는 이미 QSTOP 에서 걸러지므로, 제목에 있으면 충분히 세어 준다.
      if (titleLc.includes(tl)) sc += (t.length >= 4 ? 6 : t.length >= 3 ? 4 : 3.5);
      else if (hay.includes(tl)) sc += (t.length >= 4 ? 3 : t.length >= 3 ? 2 : 1);
    }
    // 역방향: 제목의 의미있는 단어가 질문에 (복합어 대응)
    for (const w of titleLc.split(/[\s·,]+/)) {
      // '지원·신청·안내' 같은 흔한 행정어는 역방향 매칭에서도 세지 않는다.
      // (이것 때문에 '농사 지원'이 '장애인 교통비 지원' 문서를 1등으로 만들었다)
      if (w.length >= 2 && !QSTOP.has(w) && qStr.includes(w)) sc += 1;
    }
    // 기관명이 질문에 통째로 포함 → 강한 가중 (전화·문의처 질문 정확도)
    if ((doc.kind === "공공기관" || doc.kind === "민원전화") &&
        doc.title.length >= 3 && qStr.includes(titleLc)) sc += 12;
    // 별칭(약칭) 매칭 — "제주개발공사", "도청" 등
    if (doc.kind === "공공기관") {
      const am = doc.text.match(/별칭: ([^/]+)/);
      if (am) for (const al of am[1].split(",")) {
        const a2 = al.trim().toLowerCase();
        if (a2.length >= 2 && qStr.includes(a2)) { sc += 10; break; }
      }
    }
    // 의도 가중 (매치가 있을 때만 → 무관한 데이터 유입 방지)
    if (sc > 0) {
      if (boostTour && doc.kind === "관광") sc += 4;
      if (doc.kind === "축제" && /축제|행사|페스티벌|이벤트|공연|전시|열리|개최|일정|볼거리/.test(question)) sc += 6;
      if (doc.kind === "AX"       && /ax|인공지능|ai|디지털|전환|스마트/i.test(question)) sc += 6;
      if (doc.kind === "인구"     && /인구|세대|주민등록|외국인|읍면동|몇 ?명/.test(question)) sc += 6;
      if (doc.kind === "정책브리핑" && /정부|국정|정책|브리핑|부처/.test(question)) sc += 4;
      if (doc.kind === "공고"     && /공고|입찰|용역|발주|나라장터|수의|계약/.test(question)) sc += 6;
      if (doc.kind === "여론"     && /여론|이슈|평판|불만|부정|긍정|민심|이슈체크/.test(question)) sc += 6;
      if (doc.kind === "도청공고" && /공고|고시|모집|접수|신청|지원|보조금|사업|보급|공모/.test(question)) sc += 7;
      if (doc.kind === "지원공고" && /공고|모집|접수|신청|지원|보조금|사업|보급|공모|혜택/.test(question)) sc += 6;
      if (boostPol && (doc.kind === "법령·조례" || doc.kind === "지원사업")) sc += 3;
      // 생활어로 물었을 때 해당 분야 지원사업이 위로 오게
      if (doc.kind === "지원사업" && /농사|농업|농가|귀농|감귤|축산|어업|수산|해녀/.test(question)) sc += 4;
      if (boostOrg && (doc.kind === "공공기관" || doc.kind === "민원전화")) sc += 4;
      if (doc.kind === "정책FAQ") sc += 3;
      if (doc.kind === "국회의원" && /국회의원|의원|지역구|상임위|발의/.test(question)) sc += 6;
      if (doc.kind === "도의회"   && /도의회|의안|조례안|발의|의원/.test(question)) sc += 6;
      if (doc.kind === "교육"     && /교육|교육감|학교|공약|예산|대학/.test(question)) sc += 6;
      if (doc.kind === "학교"     && /학교|초등|중학|고등|학생|분교|공립|사립|급식/.test(question)) sc += 6;
      if (doc.kind === "공약"     && /공약|민선|약속|추진/.test(question)) sc += 6;
      if (doc.kind === "뉴스"     && /뉴스|기사|소식|보도|최근/.test(question)) sc += 5;
      if (doc.kind === "통계"     && /통계|인구|지표|현황|수치/.test(question)) sc += 5;
      // 관광 통계 — 수치·추세 질문 대응
      if (doc.kind === "관광통계" &&
          /관광객|입도|방문객|외국인|내국인|소비|매출|카드|읍면동|추이|몇\s*명|비중|순위|중국|일본|대만|싱가|통계|데이터/.test(question)) sc += 6;
      // 날짜를 지정한 질문이면 '제공 기간' 문서를 항상 후보에 올린다.
      // (자료 범위 밖 날짜일 때 "없다"가 아니라 "어디까지 있다"를 답하게 하기 위함)
      // 날짜를 콕 집어 물었을 때만 올린다. 전에는 '최근'만 들어가도 20점을 받아
      // "도의회 최근 의안" 같은 질문을 관광통계 안내문이 가로챘다.
      if (doc.title.indexOf("자료 제공 기간") >= 0 &&
          /\d{1,2}\s*월\s*\d{1,2}\s*일|오늘|어제|그제/.test(question) &&
          /관광객|입도|방문객|통계|자료/.test(question)) sc += 20;
      // 국번없는 번호는 짧아서 토큰 매칭이 약함 → 민원/신고/상담 질문에 보정
      if (doc.kind === "민원전화" && /민원|신고|상담|콜센터|국번/.test(question)) sc += 2;
    }
    if (sc > 0) scored.push({ doc, sc });
  }
  scored.sort((a, b) => b.sc - a.sc);
  // 최고점이 너무 낮으면 '관련 자료 없음'으로 본다.
  // 억지로 끼워 맞춘 문서를 근거로 답하면 엉뚱한 답이 나온다.
  if (!scored.length || scored[0].sc < 3.5) return [];
  return scored.slice(0, N).map(x => x.doc);
}

// ── 외부 공개 API ──
global.MondakRAG = {
  /* 질문에 대한 후보 문서 N건을 돌려준다. */
  async candidates(question, N) {
    const corpus = await buildCorpus(await needTourism(question));
    return prefilter(question, corpus, N || 20);
  },
  /* 코퍼스 전체 (디버그용) */
  async corpus(question) {
    return buildCorpus(await needTourism(question || ""));
  },
  /* 캐시 비우기 (데이터 갱신 직후 강제 반영) */
  clearCache() { CACHE.corpus = null; CACHE.at = 0; NAMECACHE.names = null; NAMECACHE.at = 0; },
  version: "rag-1.0"
};

})(typeof window !== "undefined" ? window : globalThis);
