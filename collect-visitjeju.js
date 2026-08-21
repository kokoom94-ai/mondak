/**
 * 비짓제주 관광정보 수집기 (AI 제주정책 보부상)
 * ────────────────────────────────────────────────
 * api.visitjeju.net/vsjApi/contents/searchList 를 카테고리·페이지별로 순회하여
 * data/visitjeju.json 으로 저장한다. (정적 JSON = 해외 IP·API 한도 걱정 없음)
 *
 * 실행:  VISITJEJU_KEY=발급키 node scripts/collect-visitjeju.js
 * 환경:  Node 18+ (전역 fetch 사용) · GitHub Actions ubuntu-latest OK
 */

const fs = require('fs');
const path = require('path');

const KEY = process.env.VISITJEJU_KEY;
const BASE = 'https://api.visitjeju.net/vsjApi/contents/searchList';
const LOCALE = 'kr';

// 수집할 카테고리 (확인됨: c1 관광지 / c4 음식). 필요시 여기에 추가.
const CATS = [
  { code: 'c1', label: '관광지' },
  { code: 'c4', label: '음식' },
];

const SLEEP = ms => new Promise(r => setTimeout(r, ms));

// 안전한 깊은 값 추출 (필드 위치가 응답마다 다를 수 있어 방어적으로)
function pick(obj, ...keys) {
  for (const k of keys) {
    if (obj && obj[k] != null && obj[k] !== '') return obj[k];
  }
  return null;
}
function label(v) { // {value,label} 형태면 label만, 문자열이면 그대로
  if (v == null) return null;
  if (typeof v === 'object') return v.label || v.value || null;
  return v;
}
function imgOf(rep) {
  if (!rep) return null;
  // repPhoto.photoid.imgpath / repPhoto.imgpath 등 다양한 구조 방어
  const p = rep.photoid || rep;
  return p.imgpath || p.thumbnailpath || p.imgPath || null;
}
function clip(s, n) { s = (s || '').replace(/\s+/g, ' ').trim(); return s.length > n ? s.slice(0, n) + '…' : s; }

// 한 항목 정규화 (원본에 어떤 필드가 오든 핵심만 뽑고, 평점류는 자동 탐지)
function normalize(it, catCode, catLabel) {
  // 평점/점수류 필드 자동 탐지 (있으면 잡고, 없으면 null)
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
    rating, // 평점 자동탐지 결과 (없으면 null)
  };
}

async function fetchPage(catCode, page) {
  const url = `${BASE}?apiKey=${encodeURIComponent(KEY)}&locale=${LOCALE}&category=${catCode}&page=${page}`;
  const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
  if (!res.ok) throw new Error(`HTTP ${res.status} (cat=${catCode} page=${page})`);
  const text = await res.text();
  let j;
  try { j = JSON.parse(text); }
  catch (e) { throw new Error(`JSON 파싱 실패 (cat=${catCode} page=${page}): ${text.slice(0, 200)}`); }
  return j;
}

async function collectCat(cat) {
  const out = [];
  // 1페이지로 총량 파악
  const first = await fetchPage(cat.code, 1);
  const pageCount = Number(first.pageCount || first.pagecount || 1);
  const total = Number(first.totalCount || first.totalcount || (first.items || []).length);
  console.log(`  [${cat.code} ${cat.label}] total=${total}, pageCount=${pageCount}`);
  (first.items || []).forEach(it => out.push(normalize(it, cat.code, cat.label)));

  // 첫 실행 시 원본 필드 확인용 (평점 유무 등 진단)
  if ((first.items || [])[0]) {
    console.log(`  [${cat.code}] 원본 필드 예시:`, Object.keys(first.items[0]).join(', '));
  }

  const cap = Math.min(pageCount, 200); // 안전 상한
  for (let p = 2; p <= cap; p++) {
    try {
      const j = await fetchPage(cat.code, p);
      const items = j.items || [];
      if (!items.length) break;
      items.forEach(it => out.push(normalize(it, cat.code, cat.label)));
      if (p % 10 === 0) console.log(`    …${p}/${cap} 페이지 (누적 ${out.length}건)`);
      await SLEEP(150); // 예의상 간격
    } catch (e) {
      console.warn(`    ⚠ ${cat.code} page ${p} 실패: ${e.message} (건너뜀)`);
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
    try {
      const items = await collectCat(cat);
      stats[cat.code] = items.length;
      all.push(...items);
    } catch (e) {
      console.error(`❌ [${cat.code}] 수집 실패: ${e.message}`);
      stats[cat.code] = 0;
    }
  }

  // 좌표 없는 항목 제외(위치 필터링이 핵심이므로)
  const withGeo = all.filter(x => x.lat && x.lng);
  const hasRating = withGeo.some(x => x.rating != null);

  const outObj = {
    meta: {
      collected_at: new Date().toISOString().slice(0, 16).replace('T', ' ') + ' UTC',
      count: withGeo.length,
      total_fetched: all.length,
      by_category: stats,
      has_rating: hasRating,      // ← 평점 필드 실제 존재 여부
      source: 'api.visitjeju.net/vsjApi/contents/searchList',
      note: '제주관광공사 비짓제주 오픈API. 위치·태그 기반 필터용 정적 스냅샷.',
    },
    items: withGeo,
  };

  const dir = path.join(process.cwd(), 'data');
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, 'visitjeju.json');
  fs.writeFileSync(file, JSON.stringify(outObj), 'utf8');

  console.log('────────────────────────────────');
  console.log(`✅ 저장: data/visitjeju.json`);
  console.log(`   총 ${all.length}건 수집 → 좌표 보유 ${withGeo.length}건`);
  console.log(`   평점 필드 존재: ${hasRating ? 'YES (평점순 정렬 가능!)' : 'NO (위치·태그 필터만 가능)'}`);
  console.log(`   카테고리별:`, stats);
}

main().catch(e => { console.error('❌ 실패:', e); process.exit(1); });
