#!/usr/bin/env python3
"""인구·관광 통계 자동 갱신(가능 항목만). 실패 시 기존값 유지.
관광 3종: data.ijto.or.kr(제주관광 빅데이터 플랫폼) index.do HTML 파싱."""
import json,re,ssl,urllib.request
from pathlib import Path
OUT=Path(__file__).resolve().parent.parent/"data"/"stats.json"
st=json.loads(OUT.read_text()) if OUT.exists() else {"cells":{}}
C=st.setdefault("cells",{})

def fetch(u):
    ctx=ssl.create_default_context();ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
    req=urllib.request.Request(u,headers={
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language":"ko-KR,ko;q=0.9",
        "Referer":"https://data.ijto.or.kr/"})
    return urllib.request.urlopen(req,timeout=25,context=ctx).read().decode("utf-8","ignore")

# ── 주민등록 인구 (월 단위) ──
try:
    h=fetch("https://superkts.com/population/data/Jeju-do")
    m=re.search(r"(\d{4})년\s*(\d{1,2})월 기준.*?([\d,]+)명입니다",h,re.S)
    if m:C["pv2"]={"l":f"주민등록 ('{m.group(1)[2:]}.{int(m.group(2))})","v":m.group(3)+"명"};print("pop:",m.group(3))
except Exception as e:print("pop skip",e)

# ── 관광 3종 (제주관광 빅데이터 플랫폼) ──
def fmt_date(raw):
    """'2026-08-18 (화)' → '26.8.18' / '2026년 8월 19일(3주차)' → '26.8 3주차'"""
    m=re.search(r"(\d{4})-(\d{2})-(\d{2})",raw)
    if m:return f"{m.group(1)[2:]}.{int(m.group(2))}.{int(m.group(3))}"
    m=re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*\((\d+주차)\)",raw)
    if m:return f"{m.group(1)[2:]}.{int(m.group(2))} {m.group(4)}"
    m=re.search(r"(\d{4})-(\d{2})",raw)
    if m:return f"{m.group(1)[2:]}.{int(m.group(2))}"
    return raw.strip()

def grab(html,label_kw):
    for m in re.finditer(r'card-item[^>]*>(.*?)(?=<div class="flex-item|</li>|$)',html,re.S):
        block=m.group(1)
        if not re.search(r'class="label">[^<]*'+label_kw+r'[^<]*</span>',block):continue
        date=re.search(r'class="date">([^<]+)</span>',block)
        val=re.search(r'class="value">\s*([\d,]+)명\s*</span>',block)
        if val:return (date.group(1).strip() if date else ''),val.group(1)
    return None,None

try:
    h=fetch("https://data.ijto.or.kr/bigdata/index.do")
    # tv1 내국인 일일 입도
    d,v=grab(h,"내국인 일일 입도")
    if v:C["tv1"]={"l":f"내국인 일일 입도 ('{fmt_date(d)})","v":v+"명"};print("dom_daily:",v,d)
    # tv2 외국인 일일 입도
    d,v=grab(h,"외국인 일일 입도")
    if v:C["tv2"]={"l":f"외국인 일일 입도 ('{fmt_date(d)})","v":v+"명"};print("frn_daily:",v,d)
    # tv3 크루즈 누적
    d,v=grab(h,"크루즈")
    if v:C["tv3"]={"l":f"크루즈 누적 ('{fmt_date(d)})","v":v+"명"};print("cruise:",v,d)
except Exception as e:print("tour skip",e)

OUT.write_text(json.dumps(st,ensure_ascii=False,indent=1));print("stats saved")
