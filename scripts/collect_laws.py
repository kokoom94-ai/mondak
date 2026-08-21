#!/usr/bin/env python3
"""제주 법령·자치법규 전량 수집 — 법제처 국가법령정보 OPEN API.
target=ordin(자치법규)·law(법령). 필요: LAW_OC (open.law.go.kr 회원 아이디)"""
import json, os, re, ssl, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
KST=timezone(timedelta(hours=9)); NOW=datetime.now(KST)
OUT=Path(__file__).resolve().parent.parent/"data"/"laws.json"
OC=os.environ.get("LAW_OC","").strip()
RULES=[("문화/관광",r"관광|축제|문화|공연|박물관|해녀|올레"),("복지/사회보험",r"복지|돌봄|어르신|노인|장애|아동|보육|의료|건강|수당|바우처"),
 ("신산업/AX",r"인공지능|디지털|데이터|드론|우주|정보화|과학"),("1차산업",r"감귤|농업|농어|어업|축산|수산|산림|말산업"),
 ("환경/에너지",r"환경|에너지|풍력|자원|재활용|공원|녹지|곶자왈|지하수|생태"),("교육/청년",r"교육|학교|청년|장학|평생|도서관"),
 ("안전/민원행정",r"안전|재난|소방|교통|주차|도시|건축|민원|소비자")]
def cls(t):
    for f,p in RULES:
        if re.search(p,t): return f
    return "행정"
def call(target,query,page):
    q={"OC":OC,"target":target,"type":"JSON","query":query,"display":100,"page":page}
    url="https://www.law.go.kr/DRF/lawSearch.do?"+urllib.parse.urlencode(q)
    ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
    raw=urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"mondak"}),timeout=30,context=ctx).read().decode("utf-8","ignore")
    try: return json.loads(raw)
    except Exception:
        print(f"파싱실패 {target} p{page} 응답앞부분:",raw[:400]); return None
def gv(d,*keys):
    for k in keys:
        if d.get(k): return str(d[k]).strip()
    return ""
def dt(v): return f"{v[:4]}-{v[4:6]}-{v[6:8]}" if v and len(v)>=8 and v.isdigit() else ""
def main():
    if not OC: print("LAW_OC 미설정 — open.law.go.kr 아이디를 Secrets에 등록"); return
    items=[]
    seen_ids=set()
    def add_ordin(r):
        t=gv(r,"자치법규명","법령명한글","법령명")
        if not t: return
        org=gv(r,"지자체기관명","지자체명","소관부처명","기관명","기관","지방자치단체명","제정개정부처명")
        # 명칭에 '제주'가 있거나, 발령 지자체가 '제주'면 채택 (관광공사처럼 명칭에 특별자치도 없는 것 포함)
        if "제주" not in t and "제주" not in org: return
        oid=gv(r,"자치법규일련번호","자치법규ID","법령일련번호","MST","ID") or t
        if oid in seen_ids: return
        seen_ids.add(oid)
        ty=gv(r,"자치법규종류","법령구분명") or "조례"
        link=gv(r,"자치법규상세링크","법령상세링크")
        url=("https://www.law.go.kr"+link) if link.startswith("/") else "https://www.law.go.kr/자치법규/"+urllib.parse.quote(t.replace(" ",""))
        items.append({"ty":ty if ty in("조례","규칙","훈령","예규") else "조례",
            "f":cls(t),"t":t,"d":dt(gv(r,"공포일자")),"url":url})
    # ① 자치법규 — 메인 스윕(제주) + 산하기관 타깃 스윕(명칭에 '제주' 없는 조례 대비)
    ORD_QUERIES=[("제주",80),("관광공사",3),("개발공사",3),("에너지공사",3),
        ("국제자유도시",3),("테크노파크",3),("출자출연",3),("공사 설립",3),("공단 설립",3),("재단 설립",3)]
    dbg=True
    for qword,maxpg in ORD_QUERIES:
        for pg in range(1,maxpg+1):
            j=call("ordin",qword,pg)
            if not j: break
            body=j.get("OrdinSearch") or j.get("Law") or {}
            rows=body.get("law") or body.get("ordin") or []
            if isinstance(rows,dict): rows=[rows]
            tot=body.get("totalCnt","?")
            print(f"ordin[{qword}] p{pg} : {len(rows)}건 / 총 {tot}")
            if dbg and rows:
                print("★ 첫 행 실제필드:", json.dumps(rows[0],ensure_ascii=False)[:500]); dbg=False
            if not rows: break
            for r in rows: add_ordin(r)
            if len(rows)<100: break
    # ② 국가 법령(법률·시행령·시행규칙 중 '제주' 포함)
    for pg in (1,2):
        j=call("law","제주",pg)
        if not j: break
        body=j.get("LawSearch") or {}
        rows=body.get("law") or []
        if isinstance(rows,dict): rows=[rows]
        print("law p",pg,":",len(rows),"건 / 총",body.get("totalCnt","?"))
        for r in rows:
            t=gv(r,"법령명한글","법령명")
            if not t or "제주" not in t: continue
            g=gv(r,"법령구분명")
            ty="법률" if "법률" in g else "시행령" if "대통령령" in g else "시행규칙" if ("부령" in g or "총리령" in g) else ""
            if not ty: continue
            link=gv(r,"법령상세링크")
            url=("https://www.law.go.kr"+link) if link.startswith("/") else                 "https://www.law.go.kr/법령/"+urllib.parse.quote(t.replace(" ",""))
            items.append({"ty":ty,"f":cls(t),"t":t,"d":dt(gv(r,"공포일자")),"url":url})
        if len(rows)<100: break
    seen=set(); uniq=[]
    for it in items:
        if it["t"] in seen: continue
        seen.add(it["t"]); uniq.append(it)
    if not uniq: print("0건 — 위 진단 출력 확인"); return
    uniq.sort(key=lambda x:x["d"],reverse=True)
    by={}
    for it in uniq: by[it["ty"]]=by.get(it["ty"],0)+1
    OUT.write_text(json.dumps({"meta":{"collected_at":NOW.strftime("%Y-%m-%d %H:%M KST"),
        "source":"법제처 국가법령정보 OPEN API","count":len(uniq),"by":by},
        "items":uniq},ensure_ascii=False,indent=1),encoding="utf-8")
    print("wrote",len(uniq),"건 · 구성:",by)
if __name__=="__main__": main()
