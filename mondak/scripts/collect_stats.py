#!/usr/bin/env python3
"""인구·관광 통계 자동 갱신(가능 항목만). 실패 시 기존값 유지."""
import json,re,ssl,urllib.request
from pathlib import Path
OUT=Path(__file__).resolve().parent.parent/"data"/"stats.json"
st=json.loads(OUT.read_text()) if OUT.exists() else {"cells":{}}
C=st.setdefault("cells",{})
def fetch(u):
    ctx=ssl.create_default_context();ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
    return urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=25,context=ctx).read().decode("utf-8","ignore")
try:  # 주민등록 인구 (월 단위)
    h=fetch("https://superkts.com/population/data/Jeju-do")
    m=re.search(r"(\d{4})년\s*(\d{1,2})월 기준.*?([\d,]+)명입니다",h,re.S)
    if m:C["pv2"]={"l":f"주민등록 ('{m.group(1)[2:]}.{int(m.group(2))})","v":m.group(3)+"명"};print("pop:",m.group(3))
except Exception as e:print("pop skip",e)
try:  # 관광 누적·크루즈 (관광빅데이터플랫폼 위젯)
    h=fetch("https://www.visitjeju.net/tourdata/")
    m=re.search(r"누적 입도 관광객 수[^0-9]{0,40}([\d,]+)\s*명",h)
    if m:C["tv1"]={"l":"누적 관광객 (기준월까지)","v":m.group(1)+"명"};print("tour:",m.group(1))
    m=re.search(r"누적 크루즈 입도객 수[^0-9]{0,40}([\d,]+)\s*명",h)
    if m:C["tv3"]={"l":"크루즈 누적 (연간)","v":m.group(1)+"명"};print("cruise:",m.group(1))
    md=re.search(r"(\d{4}-\d{2}-\d{2})[^0-9]{0,20}제주방문 관광객 일일통계",h)
    m=re.search(r"외국인 일일 입도객 수[^0-9]{0,40}([\d,]+)\s*명",h)
    if m:
        lb="외국인 일일 입도"+(f" ('{md.group(1)[2:4]}.{int(md.group(1)[5:7])}.{int(md.group(1)[8:10])})" if md else " (전일)")
        C["tv2"]={"l":lb,"v":m.group(1)+"명"};print("daily:",m.group(1))
except Exception as e:print("tour skip",e)
OUT.write_text(json.dumps(st,ensure_ascii=False,indent=1));print("stats saved")
