# -*- coding: utf-8 -*-
"""
제주관광 여론지수 산출 — data/issue.json → data/issue_index.json
※ 절대 건수가 아니라 '비중'을 지수로 삼는다(검색 API는 전수가 아님).
※ 원인 해석·위험도 판단은 하지 않는다.
"""
import os, json, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

KST=timezone(timedelta(hours=9)); NOW=datetime.now(KST)
HERE=os.path.dirname(os.path.abspath(__file__))
SRC=os.path.join(HERE,"..","data","issue.json")
OUT=os.path.join(HERE,"..","data","issue_index.json")
HIST=os.path.join(HERE,"..","data","issue_history.json")

CATS=["이동·교통","숙박","먹거리","볼거리·체험","비용·상거래",
      "응대·서비스","치안·안전","환경·청결","정책·행정"]
NATS=["사건사고","불만·후기","정보·소식"]

def dparse(s):
    try: return datetime.strptime(s,"%Y-%m-%d").replace(tzinfo=KST)
    except Exception: return None

def bucket(items, base, d0, d1):
    """base로부터 d0~d1일 전 구간"""
    out=[]
    for x in items:
        dt=dparse(x.get("date") or "")
        if not dt: continue
        gap=(base-dt).days
        if d0<=gap<d1: out.append(x)
    return out

def stats(items):
    n=len(items)
    if not n: return None
    s=Counter(x["sentiment"] for x in items)
    neg=round(s.get("부정",0)/n*100,1)
    pos=round(s.get("긍정",0)/n*100,1)
    neu=round(s.get("중립",0)/n*100,1)
    # 카테고리별 부정 비중 (해당 카테고리 안에서 부정이 차지하는 비율)
    cat={}
    for c in CATS:
        sub=[x for x in items if x.get("category")==c]
        if not sub: continue
        cn=len(sub); cneg=sum(1 for x in sub if x["sentiment"]=="부정")
        cat[c]={"n":cn,"neg":round(cneg/cn*100,1),"share":round(cn/n*100,1)}
    ch=Counter(x["channel"] for x in items)
    nat=Counter(x.get("nature") or "불만·후기" for x in items)
    natures={k:{"n":v,"share":round(v/n*100,1)} for k,v in nat.items()}
    return {"total":n,"neg":neg,"pos":pos,"neu":neu,
            "channels":dict(ch),"categories":cat,"natures":natures}

def top_reasons(items, k=8):
    r=Counter()
    for x in items:
        if x["sentiment"]!="부정": continue
        for s in (x.get("reasons") or []): r[s]+=1
    return [{"word":w,"n":n} for w,n in r.most_common(k)]

def _card(x):
    return {"title":x["title"][:80],"link":x.get("link",""),
            "channel":x["channel"],"date":x.get("date",""),
            "category":x.get("category"),"sentiment":x["sentiment"],
            "reasons":(x.get("reasons") or [])[:3],
            "desc":(x.get("description") or "")[:110]}

def top_titles(items, cat=None, k=5, sent="부정"):
    """대표글 — 채널이 한쪽에 쏠리지 않게 뉴스/블로그/카페를 섞는다."""
    sub=[x for x in items if (sent is None or x["sentiment"]==sent)
         and (cat is None or x.get("category")==cat)]
    sub.sort(key=lambda x:(-(x.get("neg") or 0), x.get("date") or ""))
    out, used = [], {"news":0,"blog":0,"cafe":0}
    cap = max(2, k//2)
    for x in sub:
        ch=x["channel"]
        if used.get(ch,0) >= cap and len(out) < k: continue
        used[ch]=used.get(ch,0)+1; out.append(_card(x))
        if len(out)>=k: break
    if len(out)<k:                       # 못 채우면 순서대로 보충
        for x in sub:
            c=_card(x)
            if c not in out: out.append(c)
            if len(out)>=k: break
    return out[:k]

def main():
    d=json.load(open(SRC,encoding="utf-8"))
    items=[x for x in d["items"] if x.get("date")]
    if not items:
        print("데이터 없음"); sys.exit(1)
    base=max(dparse(x["date"]) for x in items if dparse(x["date"]))

    cur=bucket(items,base,0,7)
    prv=bucket(items,base,7,14)
    C=stats(cur); P=stats(prv)
    if not C: print("최근 7일 데이터 없음"); sys.exit(1)

    # 카테고리 순위 — 건수 기준, 부정비중 함께
    rank=[]
    for c,v in sorted(C["categories"].items(), key=lambda x:-x[1]["n"]):
        pv=(P or {}).get("categories",{}).get(c)
        sub=[x for x in cur if x.get("category")==c]
        nc=Counter(x.get("nature") or "불만·후기" for x in sub)
        rank.append({"name":c,"n":v["n"],"share":v["share"],"neg":v["neg"],
                     "prev_neg":pv["neg"] if pv else None,
                     "delta":round(v["neg"]-pv["neg"],1) if pv else None,
                     "natures":{k:nc.get(k,0) for k in NATS if nc.get(k)},
                     "top":top_titles(cur,c,6)})

    # ── 월간 집계 (전월 대비는 데이터가 두 달 쌓여야 산출됨)
    bym=defaultdict(list)
    for x in items:
        dt=dparse(x.get("date") or "")
        if dt: bym[dt.strftime("%Y-%m")].append(x)
    months=sorted(bym.keys())
    mstats=[]
    for ym in months:
        st=stats(bym[ym])
        if st: mstats.append({"month":ym,"total":st["total"],
                              "neg":st["neg"],"neu":st["neu"],"pos":st["pos"]})
    cur_m = mstats[-1] if mstats else None
    prv_m = mstats[-2] if len(mstats)>=2 else None
    # 이번 달이 아직 진행 중이면 비교가 부정확 → 완결 여부 표시
    m_ready = bool(prv_m)
    monthly={"items":mstats,"current":cur_m,"previous":prv_m,
             "ready":m_ready,
             "note":"월간 비교는 두 달치가 쌓여야 산출됩니다. 2026년 9월부터 제공됩니다." if not m_ready else "",
             "delta":{"neg":round(cur_m["neg"]-prv_m["neg"],1),
                      "pos":round(cur_m["pos"]-prv_m["pos"],1)} if m_ready else None}

    out={"meta":{"updated":NOW.strftime("%Y-%m-%d %H:%M"),
         "period":{"from":(base-timedelta(days=6)).strftime("%Y-%m-%d"),
                   "to":base.strftime("%Y-%m-%d")},
         "prev_period":{"from":(base-timedelta(days=13)).strftime("%Y-%m-%d"),
                        "to":(base-timedelta(days=7)).strftime("%Y-%m-%d")} if P else None,
         "engine":d["meta"].get("engine"),
         "source":d["meta"].get("source"),
         "note":"검색 결과는 전수가 아니므로 건수가 아닌 비중으로 봅니다. 원인 해석은 포함하지 않습니다."},
      "current":C, "previous":P,
      "delta":{"neg":round(C["neg"]-P["neg"],1) if P else None,
               "pos":round(C["pos"]-P["pos"],1) if P else None} if P else None,
      "monthly":monthly,
      "rank":rank,
      "daily":[{"date":k,"total":len(v),
                "neg":round(sum(1 for x in v if x["sentiment"]=="부정")/len(v)*100,1),
                "pos":round(sum(1 for x in v if x["sentiment"]=="긍정")/len(v)*100,1)}
               for k,v in sorted(
                   ((dd, [x for x in cur if x.get("date")==dd])
                    for dd in sorted({x["date"] for x in cur}))
               ) if v],
      "reasons":top_reasons(cur),
      "top_negative":top_titles(cur,None,10),
      "top_positive":top_titles(cur,None,6,"긍정")}

    json.dump(out,open(OUT,"w",encoding="utf-8"),ensure_ascii=False,indent=1)

    # 히스토리 누적 (주차별 지수 추이)
    hist=[]
    if os.path.exists(HIST):
        try: hist=json.load(open(HIST,encoding="utf-8")).get("items",[])
        except Exception: hist=[]
    key=base.strftime("%Y-%m-%d")
    hist=[h for h in hist if h.get("date")!=key]
    hist.append({"date":key,"neg":C["neg"],"pos":C["pos"],"neu":C["neu"],"total":C["total"]})
    hist.sort(key=lambda x:x["date"])
    json.dump({"meta":{"updated":NOW.strftime("%Y-%m-%d %H:%M")},"items":hist[-52:]},
              open(HIST,"w",encoding="utf-8"),ensure_ascii=False,indent=1)

    print(f"기간 {out['meta']['period']['from']}~{out['meta']['period']['to']} · {C['total']}건")
    print(f"  부정 {C['neg']}%  중립 {C['neu']}%  긍정 {C['pos']}%", end="")
    if out.get("delta"): print(f"  (부정 {out['delta']['neg']:+}%p)")
    else: print()
    print("  카테고리:", ", ".join(f"{r['name']} {r['n']}건" for r in rank[:5]))
    print(f"  월간: {len(mstats)}개월 · 전월 비교 {'가능' if m_ready else '2026년 9월부터'}")
    print("저장:", os.path.relpath(OUT))

if __name__=="__main__": main()
