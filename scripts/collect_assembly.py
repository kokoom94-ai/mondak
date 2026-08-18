#!/usr/bin/env python3
"""제주 국회의원 3인 현황·발의법률안 수집 — 국회사무처(data.go.kr) OPEN API.
지역구(제주시갑/을·서귀포시) 현직 의원을 API에서 직접 찾아 22대 발의법률안까지.
Secrets: ASM_MEMBER_KEY(국회의원정보), ASM_BILL_KEY(발의법률안)"""
import json, os, re, ssl, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
KST=timezone(timedelta(hours=9)); NOW=datetime.now(KST)
OUT=Path(__file__).resolve().parent.parent/"data"/"assembly.json"
MKEY=os.environ.get("ASM_MEMBER_KEY","").strip()
BKEY=os.environ.get("ASM_BILL_KEY","").strip()
DISTRICTS=["제주시갑","제주시을","서귀포시"]

import time
def get(url,tries=3):
    ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
    last=None
    for i in range(tries):
        try:
            raw=urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (mondak)"}),timeout=45,context=ctx).read()
            return raw.decode("utf-8","ignore")
        except Exception as e:
            last=e; time.sleep(3*(i+1))
    raise last

def try_json(t):
    try: return json.loads(t)
    except Exception: return None

def rows_from(j):
    """열린국회정보/공공데이터포털 공통 파싱"""
    if not j: return []
    if isinstance(j,dict):
        # 열린국회 스타일: {SVCNAME:[{head},{row:[...]}]}
        for k,v in j.items():
            if isinstance(v,list) and len(v)>=2 and isinstance(v[1],dict) and "row" in v[1]:
                return v[1]["row"]
        # 표준 공공데이터 스타일
        body=j.get("response",{}).get("body",{}) if "response" in j else j
        items=body.get("items")
        if isinstance(items,dict): items=items.get("item")
        if isinstance(items,list): return items
        if isinstance(items,dict): return [items]
    return []

def stage_of(res):
    if not res: return "계류"
    if any(k in res for k in ("가결","공포","통과","반영")): return "통과"
    if any(k in res for k in ("폐기","부결","철회","임기만료")): return "종료"
    return "계류"

def gv(d,*ks):
    for k in ks:
        if isinstance(d,dict) and d.get(k) not in (None,""): return str(d[k]).strip()
    return ""

def find_member(dist):
    """국회의원 정보 API에서 지역구로 현직 검색 (엔드포인트 후보 순차 시도)"""
    ep=[
     "https://open.assembly.go.kr/portal/openapi/nwvrqwxyaytdsfvhu?KEY={k}&Type=json&pIndex=1&pSize=100&ORIG_NM={d}",
     "https://open.assembly.go.kr/portal/openapi/ALLNAMEMBER?KEY={k}&Type=json&pIndex=1&pSize=100&ORIG_NM={d}",
    ]
    for tmpl in ep:
        try:
            u=tmpl.format(k=urllib.parse.quote(MKEY),d=urllib.parse.quote(dist))
            j=try_json(get(u)); rows=rows_from(j)
            for r in rows:
                nm=gv(r,"HG_NM","NAAS_NM","EMP_NM","MEMBER_NM")
                orig=gv(r,"ORIG_NM","GTELT_ERACO","ELECD_NM")
                if nm: 
                    return {"dist":dist,"name":nm,"party":gv(r,"POLY_NM","PLPT_NM","PARTY_NM"),
                            "cmit":gv(r,"CMIT_NM","BLNG_CMIT_NM"),"since":gv(r,"UNITS","GTELT_ERACO"),
                            "photo":gv(r,"JPG_LINK","NAAS_PIC")}
        except Exception as e: print("member ep err",dist,e)
    return {"dist":dist,"name":"","party":"","cmit":"","since":"","photo":""}

def bills_for(name):
    if not name: return []
    for tmpl in [
     "https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn?KEY={k}&Type=json&pIndex=1&pSize=60&AGE=22&RST_PROPOSER={n}",
    ]:
        try:
            u=tmpl.format(k=urllib.parse.quote(BKEY),n=urllib.parse.quote(name))
            j=try_json(get(u)); rows=rows_from(j); out=[]
            for r in rows:
                out.append({"t":gv(r,"BILL_NAME"),"no":gv(r,"BILL_NO"),
                    "d":gv(r,"PROPOSE_DT"),"result":gv(r,"PROC_RESULT") or "계류",
                    "stage":stage_of(gv(r,"PROC_RESULT")),
                    "cmit":gv(r,"COMMITTEE"),"url":gv(r,"DETAIL_LINK")})
            if out: return out
        except Exception as e: print("bill err",name,e)
    return []

def main():
    if not MKEY: print("ASM_MEMBER_KEY 미설정"); 
    mems=[]
    for d in DISTRICTS:
        m=find_member(d) if MKEY else {"dist":d,"name":""}
        if m["name"] and BKEY:
            m["bills"]=bills_for(m["name"])
            print(d,"→",m["name"],"발의",len(m.get("bills",[])),"건")
        else:
            m["bills"]=[]; print(d,"→",m["name"] or "미확인")
        mems.append(m)
    OUT.write_text(json.dumps({"meta":{"collected_at":NOW.strftime("%Y-%m-%d %H:%M KST"),
        "source":"국회사무처 열린국회정보 OPEN API · 22대","note":"지역구 현직 의원 및 대표발의 최근 15건"},
        "members":mems},ensure_ascii=False,indent=1),encoding="utf-8")
    print("wrote assembly.json")
if __name__=="__main__": main()
