/**
 * 비짓제주 관광정보 수집기 v2 (자가치유형)
 * ────────────────────────────────────────────────
 * api.visitjeju.net/vsjApi/contents/searchList 순회 → data/visitjeju.json 저장
 *
 * 핵심: 표준 fetch가 실패하면 (한국 공공서버의 TLS/인증서 문제일 수 있음)
 *       자동으로 Node의 https 모듈(인증서 우회)로 재시도한다.
 *
 * 실행:  VISITJEJU_KEY=발급키 node collect-visitjeju.js
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

const KEY = process.env.VISITJEJU_KEY;
const BASE = 'https://api.visitjeju.net/vsjApi/contents/searchList';
const LOCALE = 'kr';
const UA = 'Mozilla/5.0 (compatible; JejuBobusang/1.0)';

const CATS = [
  { code: 'c1', label: '관광지' },
  { code: 'c4', label: '음식' },
];

const SLEEP = ms => new Promise(r => setTimeout(r, ms));

function errCause(e) {
  const c = e && e.cause ? e.cause : null;
  if (c) return `${e.message} → cause: ${c.code || ''} ${c.message || c}`.trim();
  return e && e.message ? e.message : String(e);
}

// 네이티브 https GET (인증서 검증 완화 — 신뢰된 정부 공개 API 한정)
function httpsGet(url) {
  return new Promise((resolve, reject) => {
    const agent = new https.Agent({ rejectUnauthorized: false, keepAlive: true });
    const req = https.get(url, { agent, headers: { 'Accept': 'application/json', 'User-Agent': UA }, timeout: 20000 }, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => resolve({ status: res.statusCode, text: data }));
    });
    req.on('timeout', () => { req.destroy(new Error('timeout(20s)')); });
    req.on('error', reject);
  });
}

let VIA = null;
async function fetchJson(url) {
  try {
    const r = await fetch(url, { headers: { 'Accept': 'application/json', 'User-Agent': UA } });
    const text = await r.text();
    if (!VIA) { VIA = 'fetch'; console.log('  ✔ 연결 경로: 표준 fetch'); }
    return { status: r.status, text };
  } catch (e) {
    if (VIA !== 'https') console.warn(`  ⚠ 표준 fetch 실패 (${errCause(e)}) → https 모듈로 재시도`);
    const r = await httpsGet(url);
    if (VIA !== 'https') { VIA = 'https'; console.log('  ✔ 연결 경로: https 모듈(인증서 우회)로 성공'); }
    return r;
  }
}

function pick(obj, ...keys) { for (const k of keys) { if (obj && obj[k] != null && obj[k] !== '') return obj[k]; } return null; }
function label(v) { if (v == null) return null; if (typeof v === 'object') return v.label || v.value || null; return v; }
function imgOf(rep) { if (!rep) return null; const p = rep.photoid || rep; return p.imgpath || p.thumbnailpath || p.imgPath || null; }
function clip(s, n) { s = (s || '').replace(/\s+/g, ' ').trim(); return s.length > n ? s.slice(0, n) + '…' : s; }

function normalize(it, catCode, catLabel) {
  let rating = null;
  for (const k of Object.keys(it)) {
    if (/rat(ing)?|score|star|평점|점수/i.test(k) && (typeof it[k] === 'number' || /^[0-9.]+$/.test(String(it[k])))) {
      rating = Number(it[k]); break;
    }
  }
  return {
    id: pick(it, 'contentsid', 'contentid', 'cid'),
    cat: label(it.contentscd) || catCode,
    catLabel: label(it.contentscd) ? (it.contentscd.label || catLabel) : catLabel,
    title: pick(it, 'title', 'name'),
    addr: pick(it, 'roadaddress', 'roadAddress', 'address', 'addr'),
    region: label(pick(it, 'region2cd')) || label(pick(it, 'region1cd')) || null,
    lat: Number(pick(it, 'latitude', 'lat')) || null,
    lng: Number(pick(it, 'longitude', 'lng', 'lon')) || null,
    phone: pick(it, 'phoneno', 'phone', 'tel'),
    tags: pick(it, 'alltag', 'tag', 'tags'),
    intro: clip(pick(it, 'introduction', 'intro', 'desc'), 180),
    img: imgOf(it.repPhoto) || pick(it, 'imgpath', 'thumbnail'),
    rating,
  };
}

async function fetchPage(catCode, page) {
  const url = `${BASE}?apiKey=${encodeURIComponent(KEY)}&locale=${LOCALE}&category=${catCode}&page=${page}`;
  const { status, text } = await fetchJson(url);
  if (status && status >= 400) throw new Error(`HTTP ${status} (cat=${catCode} page=${page}) 본문앞: ${text.slice(0, 150)}`);
  let j;
  try { j = JSON.parse(text); }
  catch (e) { throw new Error(`JSON 파싱 실패 (cat=${catCode} page=${page}): ${text.slice(0, 200)}`); }
  return j;
}

async function collectCat(cat) {
  const out = [];
  let first;
  try {
    first = await fetchPage(cat.code, 1);
  } catch (e) {
    console.error(`  ❌ [${cat.code}] 첫 요청 실패 원인: ${errCause(e)}`);
    throw e;
  }
  const pageCount = Number(first.pageCount || first.pagecount || 1);
  const total = Number(first.totalCount || first.totalcount || (first.items || []).length);
  console.log(`  [${cat.code} ${cat.label}] total=${total}, pageCount=${pageCount}`);
  (first.items || []).forEach(it => out.push(normalize(it, cat.code, cat.label)));
  if ((first.items || [])[0]) console.log(`  [${cat.code}] 원본 필드 예시:`, Object.keys(first.items[0]).join(', '));

  const cap = Math.min(pageCount, 200);
  for (let p = 2; p <= cap; p++) {
    try {
      const j = await fetchPage(cat.code, p);
      const items = j.items || [];
      if (!items.length) break;
      items.forEach(it => out.push(normalize(it, cat.code, cat.label)));
      if (p % 10 === 0) console.log(`    …${p}/${cap} 페이지 (누적 ${out.length}건)`);
      await SLEEP(150);
    } catch (e) {
      console.warn(`    ⚠ ${cat.code} page ${p} 실패: ${errCause(e)} (건너뜀)`);
      await SLEEP(300);
    }
  }
  return out;
}

async function main() {
  if (!KEY) { console.error('❌ VISITJEJU_KEY 환경변수가 없습니다.'); process.exit(1); }
  const all = [];
  const stats = {};
  for (const cat of CATS) {
    try { const items = await collectCat(cat); stats[cat.code] = items.length; all.push(...items); }
    catch (e) { console.error(`❌ [${cat.code}] 수집 실패: ${errCause(e)}`); stats[cat.code] = 0; }
  }
  const withGeo = all.filter(x => x.lat && x.lng);
  const hasRating = withGeo.some(x => x.rating != null);
  const outObj = {
    meta: {
      collected_at: new Date().toISOString().slice(0, 16).replace('T', ' ') + ' UTC',
      count: withGeo.length, total_fetched: all.length, by_category: stats,
      has_rating: hasRating, connected_via: VIA || 'none',
      source: 'api.visitjeju.net/vsjApi/contents/searchList',
    },
    items: withGeo,
  };
  const dir = path.join(process.cwd(), 'data');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'visitjeju.json'), JSON.stringify(outObj), 'utf8');
  console.log('────────────────────────────────');
  console.log(`✅ 저장: data/visitjeju.json  (연결경로: ${VIA || 'none'})`);
  console.log(`   총 ${all.length}건 수집 → 좌표 보유 ${withGeo.length}건`);
  console.log(`   평점 필드 존재: ${hasRating ? 'YES (평점순 정렬 가능!)' : 'NO (위치·태그 필터만)'}`);
  console.log(`   카테고리별:`, stats);
}

main().catch(e => { console.error('❌ 실패:', errCause(e)); process.exit(1); });
