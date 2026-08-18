#!/usr/bin/env python3
"""몬딱 공고 수집기 v2 — 공고 1건=직링크 1개. EUC-KR·onclick 대응 + 자가진단 로그."""
import json, re, ssl, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST=timezone(timedelta(hours=9)); NOW=datetime.now(KST)
OUT=Path(__file__).resolve().parent.parent/"data"/"policies.json"
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126 Safari/537.36",
    "Accept-Language":"ko-KR,ko;q=0.9"}

def fetch(url):
    ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
    raw=urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=25,context=ctx).read()
    for enc in ("utf-8","euc-kr","cp949"):
        try:
            h=raw.decode(enc)
            if "" not in h and re.search(r"[가-힣]",h): return h
        except Exception: pass
    return raw.decode("utf-8","ignore")

RULES=[("welfare",r"복지|돌봄|어르신|노인|장애|아동|보육|의료|건강|바우처|지원금|생리대|임산부|수당"),
 ("agri",r"감귤|농업|농가|어업|축산|수산|가뭄|저수|월동|비료"),
 ("env",r"환경|에너지|재활용|일회용|탄소|정원|녹지|숲|생태|풍력|하수"),
 ("youth",r"학교|학생|교육|청년|장학|평생학습|수강"),
 ("tour",r"관광|축제|여행|올레|공연|문화"),
 ("ax",r"AI|인공지능|디지털|데이터|드론|ICT|스마트"),
 ("startup",r"창업|소상공인|기업|일자리|공공근로|채용|경제"),
 ("civic",r"안전|재난|훈련|점검|단속|민원|교통|주차|도로|보상|열람|공청회")]
WHO=[("이동약자·어르신",r"어르신|노인|장애|경로"),("육아·양육",r"임산부|아동|보육|육아|학부모"),
 ("청년·신혼",r"청년|신혼"),("농어업인",r"농가|농업|어업|축산"),("소상공인·창업",r"소상공인|창업|기업|업소")]
APPLY=r"모집|공모|신청|접수|지원사업|참여|수강|채용"

def item(org,t,d,url):
    t=re.sub(r"\s+"," ",t).strip()[:90]
    f=next((f for f,p in RULES if re.search(p,t)),"civic")
    w=[k for k,p in WHO if re.search(p,t)] or ["모든 도민"]
    return {"org":org,"f":f,"d":d,"t":t,"s":"기관 공고 원문(직링크)입니다. 첨부·기간은 원문에서 확인하세요.",
        "who":w,"due":"공고 원문 참조","amt":"공고 참조",
        "where":{"do":"도청","jeju":"제주시","seog":"서귀포시"}[org],
        "url":url,"apply":1 if re.search(APPLY,t) else 0}

def dates_near(html,pos,fallback):
    m=re.search(r"(20\d{2})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})",html[pos:pos+400])
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else fallback

def diag(name,html):
    print(f"--- DIAG {name}: len={len(html)}")
    print(html[:600].replace("\n"," ")[:600])
    for a in re.findall(r"<a [^>]{0,300}>",html)[:15]: print("A:",a[:200])
    for o in re.findall(r'onclick="[^"]{5,150}"',html)[:10]: print("OC:",o[:160])

def do_board():
    base="http://sido.jeju.go.kr"
    html=fetch(base+"/citynet/jsp/sap/SAPGosiBizProcess.do?command=searchList&flag=gosiGL&svp=Y")
    today=NOW.strftime("%Y-%m-%d"); out=[]
    for m in re.finditer(r'<a[^>]+(?:href|onclick)="[^"]*?(?:sno=|searchDetail\(?\'?)(\d{4,7})[^"]*"[^>]*>(.*?)</a>',html,re.S):
        sno,t=m.group(1),re.sub(r"<[^>]+>","",m.group(2)).strip()
        if len(t)<6: continue
        url=f"{base}/citynet/jsp/sap/SAPGosiBizProcess.do?command=searchDetail&flag=gosiGL&svp=Y&sido=&sno={sno}&gosiGbn=N"
        out.append(item("do",t,dates_near(html,m.end(),today),url))
    if not out: diag("do",html)
    return out

def jeju_board():
    base="https://eminwon.jejusi.go.kr"
    html=fetch(base+"/emwp/jsp/ofr/OfrNotAncmtL.jsp?not_ancmt_se_code=01,04&list_gubun=A")
    today=NOW.strftime("%Y-%m-%d"); out=[]
    for m in re.finditer(r'<a[^>]+(?:href|onclick)="[^"]*?(?:not_ancmt_mgt_no=|View\(?\'?)(\d{4,8})[^"]*"[^>]*>(.*?)</a>',html,re.S):
        no,t=m.group(1),re.sub(r"<[^>]+>","",m.group(2)).strip()
        if len(t)<6: continue
        url=f"{base}/emwp/jsp/ofr/OfrNotAncmtLView.jsp?not_ancmt_mgt_no={no}&not_ancmt_se_code=01,04&list_gubun=A"
        out.append(item("jeju",t,dates_near(html,m.end(),today),url))
    if not out: diag("jeju",html)
    return out

def seog_board():
    base="https://seogwipo.go.kr"
    html=fetch(base+"/info/news/law/law.htm")
    today=NOW.strftime("%Y-%m-%d"); out=[]
    for m in re.finditer(r'<a[^>]+href="([^"]*law\.htm\?[^"]*)"[^>]*>(.*?)</a>',html,re.S):
        href,t=m.group(1).replace("&amp;","&"),re.sub(r"<[^>]+>","",m.group(2)).strip()
        if len(t)<6 or not re.search(r"(seq|idx|no|mode|act)=",href): continue
        out.append(item("seog",t,dates_near(html,m.end(),today),base+href if href.startswith("/") else href))
    if not out: diag("seog",html)
    return out

def main():
    items=[]
    for fn,name in ((do_board,"do"),(jeju_board,"jeju"),(seog_board,"seog")):
        try:
            got=fn(); print(name,len(got),"건"); items+=got[:30]
        except Exception as e: print("ERR",name,repr(e))
    seen=set(); uniq=[]
    for it in items:
        k=re.sub(r"\s+","",it["t"])[:40]
        if k in seen: continue
        seen.add(k); uniq.append(it)
    uniq.sort(key=lambda x:x["d"],reverse=True)
    if not uniq: print("no notices; keeping previous"); return
    OUT.write_text(json.dumps({"meta":{"collected_at":NOW.strftime("%Y-%m-%d %H:%M KST"),
        "source":"도청·제주시·서귀포시 공고판 직크롤 (공고별 직링크)","count":len(uniq)},
        "items":uniq[:60]},ensure_ascii=False,indent=1),encoding="utf-8")
    print("wrote",len(uniq),"items")

if __name__=="__main__": main()
