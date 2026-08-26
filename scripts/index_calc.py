# -*- coding: utf-8 -*-
"""
제주관광 여론지수 산출 v2 — data/issue.json → data/issue_index.json

v1과 무엇이 다른가
  v1: '전체 수집글 중 부정 비중'이 지수였다.
      → 실종사건 하나가 부정의 40%를 차지해 분야 신호를 덮었다.
      → 질의어를 바꾸면 값이 통째로 흔들려 시계열로도 못 썼다.
  v2: 두 트랙을 따로 낸다.
      ① 불만 구성비 (voice) — 겪은 사람이 남긴 불만이 '어느 분야에 몰렸나'.
         분모가 '모인 불만'이라 질의어 편향에 강하고, 곧바로 정책 소관으로 이어진다.
      ② 이슈 감시 (risk)  — 사건을 건수가 아니라 '사건 단위'로 묶어 확산도를 본다.
      ③ 행정 소식 (info)  — 지수에서 제외. 건수만 표시한다.

※ 원인 해석·위험도 판단은 하지 않는다. 계산 결과만 낸다.
"""
import os, json, sys, re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

KST=timezone(timedelta(hours=9)); NOW=datetime.now(KST)
HERE=os.path.dirname(os.path.abspath(__file__))
SRC=os.path.join(HERE,"..","data","issue.json")
OUT=os.path.join(HERE,"..","data","issue_index.json")
HIST=os.path.join(HERE,"..","data","issue_history.json")

CATS=["응대·서비스","비용·상거래","환경·청결","이동·교통","숙박",
      "먹거리","볼거리·체험","치안·안전","정책·행정"]
NATS=["사건사고","불만·후기","정보·소식"]
POLICY={
 "응대·서비스":"관광종사자 응대·서비스 품질","비용·상거래":"관광 물가·요금 공정성",
 "환경·청결":"관광지 환경·위생 관리","이동·교통":"관광 교통·접근성",
 "숙박":"숙박 시설·거래 관행","먹거리":"음식점 품질·가격",
 "볼거리·체험":"관광 콘텐츠·시설 운영","치안·안전":"관광객 안전·치안",
 "정책·행정":"행정 소식",
}
VOICE_CH=("blog","cafe","threads","youtube")
# 사건을 묶는 축 — 심각한 것부터 본다
INCIDENT_KEY=[("실종","실종"),("사망","사망·변사"),("숨져","사망·변사"),("숨진","사망·변사"),
 ("익사","물놀이 사고"),("조난","조난·고립"),("고립","조난·고립"),("추락","추락"),
 ("화재","화재"),("침수","침수·수해"),("성폭행","성범죄"),("성추행","성범죄"),
 ("폭행","폭행"),("살해","살인"),("마약","마약"),("흉기","흉기"),("강도","강도"),
 ("절도","절도·도난"),("도난","절도·도난"),("음주운전","음주운전"),("무면허","무면허"),
 ("사기","사기"),("적발","단속·적발"),("단속","단속·적발")]

def dparse(s):
    try: return datetime.strptime(s,"%Y-%m-%d").replace(tzinfo=KST)
    except Exception: return None

def bucket(items, base, d0, d1):
    out=[]
    for x in items:
        dt=dparse(x.get("date") or "")
        if not dt: continue
        if d0<=(base-dt).days<d1: out.append(x)
    return out

def _trk(x):
    """트랙 필드가 없는 옛 데이터도 여기서 보정한다."""
    t=x.get("track")
    if t: return t
    if x.get("nature")=="사건사고" or x.get("type")=="사건": return "risk"
    if x.get("channel") in VOICE_CH: return "voice"
    return "info"

def _card(x):
    return {"title":x["title"][:80],"link":x.get("link",""),
            "channel":x["channel"],"date":x.get("date",""),
            "category":x.get("category"),"sentiment":x["sentiment"],
            "reasons":(x.get("reasons") or [])[:3],
            "desc":(x.get("description") or "")[:110]}

def mix_by_field(neg_items):
    """불만 구성비 — 분모는 '모인 불만'. 전체 수집량이 아니다."""
    tot=len(neg_items)
    if not tot: return []
    c=Counter(x.get("category") for x in neg_items if x.get("category"))
    out=[]
    for name,n in c.most_common():
        out.append({"name":name,"policy":POLICY.get(name,""),"n":n,
                    "share":round(n/tot*100,1)})
    return out

def cluster_incidents(items):
    """
    사건을 '건수'가 아니라 '사건 단위'로 묶는다.
    같은 사건어로 묶은 근사치이며 동일 사건임을 보장하지 않는다(화면에 그대로 고지).
    """
    groups=defaultdict(list)
    for x in items:
        label=x.get("event_key")
        if not label:
            t=(x.get("title") or "")
            for w,lab in INCIDENT_KEY:
                if w in t: label=lab; break
        if not label: continue
        groups[label].append(x)
    out=[]
    for lab,g in groups.items():
        dates=sorted({x.get("date") for x in g if x.get("date")})
        media=len({(x.get("link") or "").split("/")[2] if (x.get("link") or "").startswith("http") else ""
                   for x in g})
        g2=sorted(g,key=lambda x:-(x.get("neg") or 0))
        out.append({"label":lab,"n":len(g),"media":media,
                    "from":dates[0] if dates else "","to":dates[-1] if dates else "",
                    "days":len(dates),
                    "spread":"확산" if (len(g)>=8 and media>=4) else ("주시" if len(g)>=3 else "단발"),
                    "categories":dict(Counter(x.get("category") for x in g if x.get("category"))),
                    "top":[_card(x) for x in g2[:8]]})
    out.sort(key=lambda x:(-x["n"],-x["media"]))
    return out

def collapse_events(items):
    """
    같은 사건의 중복 보도를 1건으로 축약한다.
    한 사건이 43개 매체에 실리면 지수에서는 73건이 되어 분야 신호를 덮는다.
    (실측: 축약 전 치안·안전 71% → 축약 후 24%. 교통 28%, 비용 24%가 비로소 보인다)
    사건의 실제 파급력은 건수가 아니라 risk 트랙의 '매체 수'로 따로 표시한다.
    """
    seen=set(); out=[]
    for x in sorted(items, key=lambda y: y.get("date") or ""):
        if x.get("channel")=="news":
            # LLM이 부여한 event_key가 있으면 그것을 쓴다.
            # 사건어 매칭은 "실종"이면 전부 한 덩어리로 묶지만,
            # event_key는 서로 다른 실종 사건을 구분한다.
            lab=x.get("event_key")
            if not lab:
                t=x.get("title") or ""
                for w,l in INCIDENT_KEY:
                    if w in t: lab=l; break
            if lab:
                dt=dparse(x.get("date") or "")
                wk=dt.isocalendar()[1] if dt else 0
                key=(lab,wk)
                if key in seen: continue      # 같은 주, 같은 사건 → 첫 보도만
                seen.add(key)
        out.append(x)
    return out

def stats(items):
    n=len(items)
    if not n: return None
    s=Counter(x["sentiment"] for x in items)
    f=lambda k: round(s.get(k,0)/n*100,1)
    cat={}
    for c in CATS:
        sub=[x for x in items if x.get("category")==c]
        if not sub: continue
        cn=len(sub); cneg=sum(1 for x in sub if x["sentiment"]=="부정")
        cat[c]={"n":cn,"neg":round(cneg/cn*100,1),"share":round(cn/n*100,1)}
    nat=Counter(x.get("nature") or "불만·후기" for x in items)
    return {"total":n,"neg":f("부정"),"pos":f("긍정"),"neu":f("중립"),
            "channels":dict(Counter(x["channel"] for x in items)),
            "categories":cat,
            "natures":{k:{"n":v,"share":round(v/n*100,1)} for k,v in nat.items()},
            "tracks":dict(Counter(_trk(x) for x in items))}

def top_reasons(items,k=10):
    r=Counter()
    for x in items:
        if x["sentiment"]!="부정": continue
        for s in (x.get("reasons") or []): r[s]+=1
    return [{"word":w,"n":n} for w,n in r.most_common(k)]

def top_titles(items,cat=None,k=5,sent="부정"):
    sub=[x for x in items if (sent is None or x["sentiment"]==sent)
         and (cat is None or x.get("category")==cat)]
    sub.sort(key=lambda x:(-(x.get("neg") or 0), x.get("date") or ""))
    out,used=[],{}; cap=max(2,k//2)
    for x in sub:
        ch=x["channel"]
        if used.get(ch,0)>=cap and len(out)<k: continue
        used[ch]=used.get(ch,0)+1; out.append(_card(x))
        if len(out)>=k: break
    if len(out)<k:
        for x in sub:
            c=_card(x)
            if c not in out: out.append(c)
            if len(out)>=k: break
    return out[:k]

def main():
    d=json.load(open(SRC,encoding="utf-8"))
    items=[x for x in d["items"] if x.get("date")]
    if not items: print("데이터 없음"); sys.exit(1)
    base=max(dparse(x["date"]) for x in items if dparse(x["date"]))

    cur=bucket(items,base,0,7); prv=bucket(items,base,7,14)
    C=stats(cur); P=stats(prv)
    if not C: print("최근 7일 데이터 없음"); sys.exit(1)

    # ── 트랙 분리
    cv=[x for x in cur if _trk(x)=="voice"]
    cr=[x for x in cur if _trk(x)=="risk"]
    ci=[x for x in cur if _trk(x)=="info"]
    pv=[x for x in prv if _trk(x)=="voice"]

    cv_neg=[x for x in cv if x["sentiment"]=="부정"]
    pv_neg=[x for x in pv if x["sentiment"]=="부정"]
    mix=mix_by_field(collapse_events(cv_neg))
    pmix={m["name"]:m["share"] for m in mix_by_field(collapse_events(pv_neg))}
    for m in mix:
        m["prev"]=pmix.get(m["name"])
        m["delta"]=round(m["share"]-m["prev"],1) if m["prev"] is not None else None
        m["top"]=top_titles(cv,m["name"],10)

    voice={"total":len(cv),"neg_n":len(cv_neg),
           "neg_rate":round(len(cv_neg)/len(cv)*100,1) if cv else 0,
           "channels":dict(Counter(x["channel"] for x in cv)),
           "mix":mix,
           "sample_ok":len(cv_neg)>=30,          # 표본이 정책 판단에 충분한가
           "top":top_titles(cv,None,20)}

    risk={"total":len(cr),
          "neg_n":sum(1 for x in cr if x["sentiment"]=="부정"),
          "clusters":cluster_incidents(cr)[:8],
          "top":top_titles(cr,None,16)}

    info={"total":len(ci)}

    # ── 최근 30일 창 — 주간은 그 주의 사건에 휘둘리므로 넓은 창을 함께 낸다
    m30=bucket(items,base,0,30)
    M30=stats(collapse_events(m30))
    m30_neg=collapse_events([x for x in m30 if x["sentiment"]=="부정"])
    # 30일 기준 분야 순위 — rank와 완전히 같은 구조. 화면이 그대로 재사용한다.
    rank30=[]
    if M30:
        n30={c:sum(1 for x in m30_neg if x.get("category")==c) for c in M30["categories"]}
        for c,v in sorted(M30["categories"].items(), key=lambda x:(-n30.get(x[0],0),-x[1]["n"])):
            sub=[x for x in m30 if x.get("category")==c]
            nc=Counter(x.get("nature") or "불만·후기" for x in sub)
            rank30.append({"name":c,"policy":POLICY.get(c,""),"n":v["n"],
                           "neg_n":n30.get(c,0),"share":v["share"],"neg":v["neg"],
                           "prev_neg":None,"delta":None,
                           "natures":{k:nc.get(k,0) for k in NATS if nc.get(k)},
                           "top":top_titles(m30,c,40)})
    window30={"total":len(m30),"neg_n":len(m30_neg),
              "from":(base-timedelta(days=29)).strftime("%Y-%m-%d"),
              "to":base.strftime("%Y-%m-%d"),
              "stats":M30,
              "rank":rank30,
              "reasons":top_reasons(m30,12),
              "top_negative":top_titles(m30,None,60),
              "all_recent":top_titles(m30,None,120,None),
              "mix":mix_by_field(m30_neg),
              "clusters":cluster_incidents([x for x in m30 if _trk(x)=="risk"])[:8]}

    # ── 기존 화면 호환용 (전체 기준 순위)
    rank=[]
    cur_neg_c=collapse_events([x for x in cur if x["sentiment"]=="부정"])
    negcnt={c:sum(1 for x in cur_neg_c if x.get("category")==c) for c in C["categories"]}
    for c,v in sorted(C["categories"].items(), key=lambda x:(-negcnt.get(x[0],0),-x[1]["n"])):
        pvv=(P or {}).get("categories",{}).get(c)
        sub=[x for x in cur if x.get("category")==c]
        nc=Counter(x.get("nature") or "불만·후기" for x in sub)
        rank.append({"name":c,"policy":POLICY.get(c,""),"n":v["n"],"neg_n":negcnt.get(c,0),
                     "share":v["share"],"neg":v["neg"],
                     "prev_neg":pvv["neg"] if pvv else None,
                     "delta":round(v["neg"]-pvv["neg"],1) if pvv else None,
                     "natures":{k:nc.get(k,0) for k in NATS if nc.get(k)},
                     "top":top_titles(cur,c,12)})

    bym=defaultdict(list)
    for x in items:
        dt=dparse(x.get("date") or "")
        if dt: bym[dt.strftime("%Y-%m")].append(x)
    mstats=[]
    for ym in sorted(bym):
        # 월간도 사건 축약 기준. 그래야 9월에 8월과 비교할 때
        # 한 사건의 중복 보도량이 그 달 전체를 지배하지 않는다.
        st=stats(collapse_events(bym[ym]))
        if st: mstats.append({"month":ym,"total":st["total"],"neg":st["neg"],
                              "neu":st["neu"],"pos":st["pos"]})
    cur_m=mstats[-1] if mstats else None
    prv_m=mstats[-2] if len(mstats)>=2 else None
    m_ready=bool(prv_m)
    monthly={"items":mstats,"current":cur_m,"previous":prv_m,"ready":m_ready,
             "note":"" if m_ready else "월간 비교는 두 달치가 쌓여야 산출됩니다.",
             "delta":{"neg":round(cur_m["neg"]-prv_m["neg"],1),
                      "pos":round(cur_m["pos"]-prv_m["pos"],1)} if m_ready else None}

    out={"meta":{"updated":NOW.strftime("%Y-%m-%d %H:%M"),
         "period":{"from":(base-timedelta(days=6)).strftime("%Y-%m-%d"),
                   "to":base.strftime("%Y-%m-%d")},
         "prev_period":{"from":(base-timedelta(days=13)).strftime("%Y-%m-%d"),
                        "to":(base-timedelta(days=7)).strftime("%Y-%m-%d")} if P else None,
         "engine":d["meta"].get("engine"),"source":d["meta"].get("source"),
         "note":"불만 구성비는 '모인 불만' 안에서의 비율입니다. 수집량이 전수가 아니므로 건수 자체는 지표로 쓰지 않습니다.",
         "disclaimer":"자체 수집·분류한 참고자료이며 일부 오류가 있을 수 있습니다.",
         "judge":d["meta"].get("llm")},
      "voice":voice,"risk":risk,"info":info,"window30":window30,
      "current":C,"previous":P,
      "delta":{"neg":round(C["neg"]-P["neg"],1) if P else None,
               "pos":round(C["pos"]-P["pos"],1) if P else None} if P else None,
      "monthly":monthly,"rank":rank,
      "daily":[{"date":dd,"total":len(v),
                "neg_n":sum(1 for x in v if x["sentiment"]=="부정"),
                "neu_n":sum(1 for x in v if x["sentiment"]=="중립"),
                "pos_n":sum(1 for x in v if x["sentiment"]=="긍정"),
                "neg":round(sum(1 for x in v if x["sentiment"]=="부정")/len(v)*100,1),
                "pos":round(sum(1 for x in v if x["sentiment"]=="긍정")/len(v)*100,1)}
               for dd,v in ((dd,[x for x in cur if x.get("date")==dd])
                            for dd in sorted({x["date"] for x in cur})) if v],
      "reasons":top_reasons(cur),
      "top_negative":top_titles(cur,None,40),
      "top_positive":top_titles(cur,None,12,"긍정"),
      "all_recent":top_titles(cur,None,80,None)}

    json.dump(out,open(OUT,"w",encoding="utf-8"),ensure_ascii=False,indent=1)

    hist=[]
    if os.path.exists(HIST):
        try: hist=json.load(open(HIST,encoding="utf-8")).get("items",[])
        except Exception: hist=[]
    key=base.strftime("%Y-%m-%d")
    hist=[h for h in hist if h.get("date")!=key]
    hist.append({"date":key,"neg":C["neg"],"pos":C["pos"],"neu":C["neu"],"total":C["total"],
                 "voice_neg":voice["neg_n"],"risk_n":risk["total"]})
    hist.sort(key=lambda x:x["date"])
    json.dump({"meta":{"updated":NOW.strftime("%Y-%m-%d %H:%M")},"items":hist[-52:]},
              open(HIST,"w",encoding="utf-8"),ensure_ascii=False,indent=1)

    print(f"기간 {out['meta']['period']['from']}~{out['meta']['period']['to']}")
    print(f"  수요자 {voice['total']}건 · 불만 {voice['neg_n']}건"
          f" ({'표본 충분' if voice['sample_ok'] else '표본 부족 — 정책 판단 보류'})")
    for m in mix[:5]: print(f"     {m['name']:10s} {m['share']:5.1f}%  ({m['n']}건)  → {m['policy']}")
    print(f"  이슈 {risk['total']}건 · 사건묶음 {len(risk['clusters'])}개")
    for c in risk["clusters"][:4]:
        print(f"     {c['label']:10s} {c['n']:3d}건 · 매체 {c['media']} · {c['spread']}")
    print(f"  행정소식 {info['total']}건 (지수 제외)")
    print(f"  최근 30일 창 · 전체 {window30['total']}건 · 축약 불만 {window30['neg_n']}건")
    for m in window30["mix"][:5]:
        print(f"     {m['name']:10s} {m['share']:5.1f}%  ({m['n']}건)")
    print("저장:", os.path.relpath(OUT))

if __name__=="__main__": main()
