// Vercel Cron — 워치리스트(Notion)의 유튜브 채널·RSS·키워드에서 새 항목을 수집,
// Haiku로 관심 프로필과 대조해 필터링한 뒤 수집함(Notion)에 적재.
//
//   GET /api/collect            → 크론/수동 실행 (x-app-key 또는 CRON_SECRET)
//   GET /api/collect?dry=1      → 수집만 하고 저장 안 함 (테스트)
//
// env: NOTION_TOKEN(필수), ANTHROPIC_API_KEY(필터링·요약, 없으면 필터 없이 적재),
//      SUPADATA_API_KEY(유튜브 자막), APP_KEY/CRON_SECRET(선택)
import { INBOX_DB, WATCH_DB, notion, queryDb, readProps, P, authorized, cors } from './_notion.mjs';
import { upsertProject } from './_projects.mjs';
import { analyzeSource } from './_analyze.mjs';

export const config = { maxDuration: 60 };

const MAX_NEW_PER_RUN = 10;      // 한 번 실행당 적재 상한 (시간·비용 보호)
const FIRST_RUN_PER_SOURCE = 3;  // 처음 보는 소스는 최신 N개만
const SCORE_THRESHOLD = 6;       // 이 점수 미만은 버림 (0~10)
const HOPELESS_SCORE = 3;        // 제목 단계에서 이 점수 이하면 본문도 받지 않고 폐기
const AUTO_ANALYZE_SCORE = 8;    // 이 점수 이상이면 수집 단계에서 전체 분석까지 수행
const MAX_AUTO_ANALYZE = 1;      // 회차당 자동 분석 상한 (Sonnet 호출이라 비용·시간 보호)
// 서버리스 함수는 60초에 강제 종료된다. 분석 한 건이 30~40초라 수집과 겹치면 넘치므로,
// 남은 시간이 충분할 때만 시작한다. 건너뛴 항목은 '새 항목'으로 남아 앱에서 분석하면 된다.
const FN_BUDGET_MS = 55000;
const ANALYZE_NEEDS_MS = 32000;
const FEEDBACK_N = 12;           // 채점에 넣을 최근 판정 사례 수 (긍정·부정 각각)

// ---- RSS/Atom 파서 (의존성 없이 정규식으로 최소 파싱) ----
function dec(s) {
  return String(s || '')
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => { try { return String.fromCodePoint(+n); } catch { return ''; } })
    .replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}
function tag(block, name) {
  const m = block.match(new RegExp('<' + name + '[^>]*>([\\s\\S]*?)</' + name + '>', 'i'));
  return m ? m[1] : '';
}
// 썸네일: 유튜브는 영상 ID로 생성(항상 존재), 그 외는 RSS의 media:thumbnail·enclosure를 사용.
// 이미지를 저장하지 않고 원본 URL만 참조하므로 저장 공간을 쓰지 않는다.
function ytIdOf(url) {
  const m = String(url || '').match(/(?:youtu\.be\/|[?&]v=|\/embed\/|\/shorts\/|\/live\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : '';
}
function thumbOf(entry, link) {
  const vid = ytIdOf(link);
  if (vid) return 'https://i.ytimg.com/vi/' + vid + '/hqdefault.jpg';
  const m = entry.match(/<media:thumbnail[^>]+url=["']([^"']+)["']/i)
        || entry.match(/<media:content[^>]+url=["']([^"']+\.(?:jpe?g|png|webp)[^"']*)["']/i)
        || entry.match(/<enclosure[^>]+url=["']([^"']+\.(?:jpe?g|png|webp)[^"']*)["']/i)
        || entry.match(/<img[^>]+src=["']([^"']+)["']/i);
  return m ? dec(m[1]) : '';
}
function parseFeed(xml) {
  const items = [];
  const entries = xml.match(/<entry[\s>][\s\S]*?<\/entry>/gi) || xml.match(/<item[\s>][\s\S]*?<\/item>/gi) || [];
  for (const e of entries) {
    const title = dec(tag(e, 'title'));
    let link = '';
    const lh = e.match(/<link[^>]+href=["']([^"']+)["']/i);
    if (lh) link = lh[1]; else link = dec(tag(e, 'link')) || dec(tag(e, 'guid'));
    const published = tag(e, 'published') || tag(e, 'pubDate') || tag(e, 'updated') || tag(e, 'dc:date');
    const desc = dec(tag(e, 'media:description') || tag(e, 'description') || tag(e, 'summary') || tag(e, 'content')).slice(0, 800);
    const author = dec(tag(e, 'author') ? tag(tag(e, 'author'), 'name') || tag(e, 'author') : tag(e, 'source'));
    const ts = published ? Date.parse(published.trim()) : NaN;
    if (title && link) items.push({ title, link: link.trim(), ts: isNaN(ts) ? 0 : ts, desc, author, thumb: thumbOf(e, link) });
  }
  items.sort((a, b) => b.ts - a.ts);
  return items;
}
async function fetchText(url, headers = {}) {
  const r = await fetch(url, { redirect: 'follow', headers: { 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36', 'accept-language': 'ko,en;q=0.9', ...headers } });
  if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + url.slice(0, 80));
  return r.text();
}

// ---- 유튜브 채널 → channel_id 해석 (@handle/URL 지원, 워치 행에 캐시) ----
// 예전에는 페이지 HTML의 "첫 번째" channelId를 잡았는데, 그 값은 추천 채널 등
// 남의 채널일 수 있다. 실제로 @AlexHormozi를 등록했더니 다른 채널이 잡혔고,
// 나중엔 그 ID의 피드가 404가 나면서 유튜브 수집이 통째로 멈췄다.
// → 페이지 "자신"을 가리키는 표식(canonical·externalId·identifier)을 우선 쓴다.
function pickChannelId(html) {
  const pats = [
    /<link[^>]+rel=["']canonical["'][^>]+href=["'][^"']*\/channel\/(UC[0-9A-Za-z_-]{22})/i,
    /<meta[^>]+itemprop=["']identifier["'][^>]+content=["'](UC[0-9A-Za-z_-]{22})["']/i,
    /<meta[^>]+property=["']og:url["'][^>]+content=["'][^"']*\/channel\/(UC[0-9A-Za-z_-]{22})/i,
    /"externalId"\s*:\s*"(UC[0-9A-Za-z_-]{22})"/,
    /"channelId"\s*:\s*"(UC[0-9A-Za-z_-]{22})"/,   // 최후의 수단
  ];
  for (const re of pats) { const m = html.match(re); if (m) return m[1]; }
  return '';
}
// 해석한 ID가 실제로 피드를 주는지 확인한다. 확인 없이 캐시하면 잘못된 ID가
// 굳어져서 매일 404만 반복한다.
// 상태 코드를 그대로 돌려준다 — 예전엔 boolean만 봐서, 유튜브가 데이터센터 IP를
// 일시적으로 막은 것까지 "채널 주소를 확인하세요"라고 안내했다. 멀쩡한 주소를
// 붙잡고 헤매게 만드는 오진이다. (0 = 네트워크 실패)
async function feedStatus(cid) {
  try {
    const r = await fetch('https://www.youtube.com/feeds/videos.xml?channel_id=' + cid, {
      headers: { 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36' },
    });
    return r.status;
  } catch { return 0; }
}
async function resolveChannelId(value) {
  const v = String(value || '').trim();
  const direct = v.match(/\/channel\/(UC[0-9A-Za-z_-]{22})/) || v.match(/^(UC[0-9A-Za-z_-]{22})$/);
  if (direct) return direct[1];
  let url = v;
  if (!/^https?:\/\//i.test(url)) url = 'https://www.youtube.com/' + (url.startsWith('@') ? url : '@' + url);
  const html = await fetchText(url);
  const cid = pickChannelId(html);
  if (!cid) throw new Error('채널 ID를 찾지 못했어요: ' + v);
  const st = await feedStatus(cid);
  if (st === 200) return cid;
  if (st === 404) throw new Error(`채널 ID(${cid})의 피드가 없어요(404). 채널 주소를 확인해 주세요: ${v}`);
  // 429·403·5xx·네트워크 오류는 유튜브 쪽 사정이다. 주소를 고치라고 하면 안 된다.
  throw new Error(`유튜브가 피드 요청을 거부했어요(${st || '네트워크 오류'}) — 채널 주소 문제가 아닐 수 있어요. 다음 회차에 다시 시도합니다: ${v}`);
}

// ---- 웹 본문 추출 (fetch-source.js의 축약판) ----
function extractReadable(html) {
  let h = html.replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<(script|style|noscript|svg|template|iframe|head|nav|header|footer|aside|form)\b[\s\S]*?<\/\1>/gi, ' ');
  const art = h.match(/<article\b[\s\S]*?<\/article>/i); const main = h.match(/<main\b[\s\S]*?<\/main>/i);
  let body = (art && art[0]) || (main && main[0]) || h;
  body = body.replace(/<\/(p|div|section|li|h[1-6]|br|tr|blockquote)>/gi, '\n').replace(/<br\s*\/?>/gi, '\n');
  body = dec(body.replace(/\n/g, ' __NL__ ')).replace(/ ?__NL__ ?/g, '\n');
  const lines = body.split('\n').map(l => l.trim()).filter(l => l.length > 1);
  return lines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

// ---- API 키 검증 ----
// 마스킹된 화면 값(●●●●)을 그대로 복사해 붙여넣는 실수가 잦다. 그대로 두면 HTTP 헤더
// 변환 단계에서 "Cannot convert argument to a ByteString" 같은 알 수 없는 오류로 실패하므로,
// 여기서 먼저 걸러 한국어로 원인을 알려준다.
function apiKey(name) {
  const v = (process.env[name] || '').trim();
  if (v && /[^\x20-\x7E]/.test(v)) {
    throw new Error(`${name} 값이 올바르지 않아요. 화면에 가려져 보이던 ●●●● 를 복사하신 것 같아요 — Vercel 환경변수에 실제 키를 다시 저장한 뒤 재배포해 주세요.`);
  }
  return v;
}

// ---- Supadata 유튜브 자막 (mode=auto: 자막 없으면 AI 생성 폴백) ----
async function ytTranscript(videoUrl) {
  const key = apiKey('SUPADATA_API_KEY');
  if (!key) return '';
  try {
    const r = await fetch('https://api.supadata.ai/v1/transcript?url=' + encodeURIComponent(videoUrl) + '&lang=ko&text=true&mode=auto', {
      headers: { 'x-api-key': key, 'accept': 'application/json' } });
    if (!r.ok) return '';
    let j = await r.json();
    const pick = o => { const c = o.content ?? o.transcript ?? o.text; return typeof c === 'string' ? c : Array.isArray(c) ? c.map(x => x.text || '').join(' ') : ''; };
    let text = pick(j);
    if (!text && j.jobId) {
      for (let i = 0; i < 3; i++) {
        await new Promise(s => setTimeout(s, 2000));
        const jr = await fetch('https://api.supadata.ai/v1/transcript/' + j.jobId, { headers: { 'x-api-key': key } });
        if (jr.ok) { const jj = await jr.json(); if (jj.status === 'failed') break; text = pick(jj); if (text) break; }
      }
    }
    return String(text).replace(/\s+/g, ' ').trim();
  } catch { return ''; }
}

// ---- Haiku 필터링·요약 ----
async function haiku(prompt, maxTokens = 500) {
  const key = apiKey('ANTHROPIC_API_KEY');
  if (!key) return '';
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
    body: JSON.stringify({ model: 'claude-haiku-4-5-20251001', max_tokens: maxTokens, messages: [{ role: 'user', content: prompt }] }),
  });
  if (!r.ok) throw new Error('Claude HTTP ' + r.status);
  const j = await r.json();
  return (j.content && j.content[0] && j.content[0].text) || '';
}
/* 사람의 판정을 채점에 되먹인다.
   수집함의 '제외'는 필터가 통과시켰는데 사람이 버린 것 — 곧 필터의 오탐이다.
   '보관'·'분석됨'은 실제로 쓸모 있었다는 확인이다. 이 둘을 예시로 주지 않으면
   사용자가 제외를 백 번 눌러도 필터는 아무것도 배우지 못하고 같은 것을 계속 올린다. */
export function buildFeedback(liked, disliked) {
  if (!liked.length && !disliked.length) return '';
  const L = ['\n[이 사용자의 실제 판정 이력]',
    '관심 프로필과 충돌하면 이 이력을 우선하세요. 아래와 성격이 비슷한 콘텐츠는 같은 방향으로 판정합니다.'];
  if (disliked.length) L.push('\n▼ 사용자가 직접 "제외"함 (필터는 통과시켰으나 사람이 버림 → 이런 유형은 낮게)\n' + disliked.map(t => '· ' + t).join('\n'));
  if (liked.length) L.push('\n▲ 사용자가 "보관"하거나 분석까지 함 (실제로 유용했음 → 이런 유형은 높게)\n' + liked.map(t => '· ' + t).join('\n'));
  return L.join('\n') + '\n';
}
export async function scoreItem(profile, item, body, feedback) {
  if (!(process.env.ANTHROPIC_API_KEY || '').trim()) return { score: null, reason: '필터 미사용(ANTHROPIC_API_KEY 없음)' };
  const out = await haiku(
    '당신은 콘텐츠 큐레이터입니다. 아래 관심 프로필과 새 콘텐츠를 대조해 관련성·유용성을 0~10 점수로 평가하세요.\n\n' +
    '[관심 프로필]\n' + profile + '\n' + (feedback || '') +
    '\n[콘텐츠]\n제목: ' + item.title + '\n출처: ' + (item.author || item.sourceName || '') + '\n설명: ' + (item.desc || '(없음)') +
    (body ? '\n\n[본문 발췌]\n' + body.slice(0, 3000) : '') + '\n\n' +
    'JSON만 출력: {"score": 0-10 정수, "reason": "근거 한 문장(한국어)"}', 200);
  try { const j = JSON.parse(out.match(/\{[\s\S]*\}/)[0]); return { score: Math.max(0, Math.min(10, +j.score || 0)), reason: String(j.reason || '') }; }
  catch { return { score: 5, reason: '평가 파싱 실패 — 보류 점수' }; }
}
async function summarize(item, excerpt) {
  if (!(process.env.ANTHROPIC_API_KEY || '').trim() || !excerpt) return item.reason || item.desc || '';
  try {
    const out = await haiku('아래 콘텐츠를 한국어 불릿 3개(각 한 문장, 핵심 노하우/사실 위주)로 요약하세요. 불릿 외 다른 말 금지.\n\n제목: ' + item.title + '\n\n' + excerpt.slice(0, 6000), 400);
    return out.trim().slice(0, 1800);
  } catch { return item.reason || item.desc || ''; }
}

export default async function handler(req, res) {
  cors(res);
  if (req.method === 'OPTIONS') { res.status(204).end(); return; }
  if (!authorized(req)) { res.status(401).json({ ok: false, error: '인증 실패 (x-app-key 필요)' }); return; }
  const T0 = Date.now();
  const timeLeft = () => FN_BUDGET_MS - (Date.now() - T0);
  const dry = !!(req.query && req.query.dry);
  const report = { ok: true, sources: 0, found: 0, kept: 0, skipped: 0, analyzed: 0, threshold: SCORE_THRESHOLD, rejected: [], errors: [] };
  try {
    // 잘못 붙여넣은 키는 항목마다 같은 오류를 내므로 시작 전에 한 번에 걸러낸다
    apiKey('ANTHROPIC_API_KEY'); apiKey('SUPADATA_API_KEY');
    // 1) 워치리스트 로드
    const all = (await queryDb(WATCH_DB)).results.map(readProps);
    const wl = all.filter(w => w['활성']);
    const profileRows = wl.filter(w => w['유형'] === '관심 프로필');
    const profile = profileRows.map(w => w['값']).join('\n') || '실전 노하우, 구체적 사례, 실행 가능한 전략이 있는 콘텐츠';

    // 자동 수집 스위치: '설정' 행의 활성 체크가 꺼져 있으면 예약 실행을 건너뛴다.
    // 앱에서 누르는 수동 실행(manual=1)은 스위치와 무관하게 항상 동작한다.
    const manual = !!(req.query && (req.query.manual || req.query.only));
    const settingRows = all.filter(w => w['유형'] === '설정');
    const autoRow = settingRows.find(w => /자동 수집/.test(w['이름'] || '')) || settingRows[0];
    // 자동 분석 설정 행이 없으면 기본 켜짐. 끄고 싶으면 Notion에 '⚡ 자동 분석' 행을 만들고 체크 해제
    const analyzeRow = settingRows.find(w => /자동 분석/.test(w['이름'] || ''));
    const autoAnalyze = analyzeRow ? !!analyzeRow['활성'] : true;
    if (!manual && autoRow && !autoRow['활성']) {
      res.status(200).json({ ...report, ok: true, paused: true, note: '자동 수집이 꺼져 있어요. 앱에서 수동 실행하거나 설정을 켜주세요.' });
      return;
    }

    // 이번 회차에 사용할 소스. only=id,id 가 오면 그 소스만 (앱의 소스 선택 수집)
    const only = String((req.query && req.query.only) || '').split(',').map(s => s.trim().replace(/-/g, '')).filter(Boolean);
    let sources = wl.filter(w => w['유형'] !== '관심 프로필' && w['유형'] !== '설정');
    if (only.length) sources = sources.filter(s => only.includes(String(s.id).replace(/-/g, '')));
    report.sources = sources.length;
    if (!sources.length) { res.status(200).json({ ...report, note: only.length ? '선택한 소스를 찾지 못했어요.' : '워치리스트에 활성 소스가 없어요.' }); return; }

    // 2) 기존 수집함 — URL 셋(중복 방지) + 사람의 판정 이력(필터 학습)
    const seen = new Set();
    const liked = [], disliked = [];
    const recent = await queryDb(INBOX_DB, { sorts: [{ timestamp: 'created_time', direction: 'descending' }] });
    for (const p of recent.results) {
      const r = readProps(p);
      if (r['URL']) seen.add(r['URL']);
      const t = String(r['제목'] || '').trim().slice(0, 90);
      if (!t) continue;
      const st = r['상태'];
      if (st === '제외') { if (disliked.length < FEEDBACK_N) disliked.push(t); }
      else if (st === '보관' || st === '분석됨') { if (liked.length < FEEDBACK_N) liked.push(t); }
    }
    const feedback = buildFeedback(liked, disliked);
    report.learned = { liked: liked.length, disliked: disliked.length };

    // 3) 소스별 새 항목 수집
    // '마지막수집'(워터마크)은 여기서 올리지 않는다. 처리에 실패한 항목까지 "지나간 것"으로
    // 표시되어 영구 유실되기 때문. 실제 처리가 끝난 뒤, 실패·미처리가 없는 소스만 갱신한다.
    const candidates = [];
    const watermarks = new Map(); // watchId -> 이번 회차에 본 가장 최신 항목 시각(ms)
    const unfinished = new Set(); // 실패했거나 이번 회차에 다 못 본 소스
    // 소스별 건강 상태. 소스가 조용히 죽어도 알 수 없던 문제(채널 ID가 잘못돼
    // 며칠간 0건이었는데 아무 표시가 없었다)를 화면에 드러내기 위해 기록한다.
    const health = new Map(); // watchId -> { found, kept, error }
    for (const src of sources) {
      try {
        let items = [], sourceType = 'RSS', sourceName = src['이름'] || src['값'];
        if (src['유형'] === '유튜브 채널') {
          sourceType = '유튜브';
          let cid = (src['채널ID'] || '').trim();
          const feedOf = c => 'https://www.youtube.com/feeds/videos.xml?channel_id=' + c;
          if (!cid) {
            cid = await resolveChannelId(src['값']);
            if (!dry) await notion('/pages/' + src.id, 'PATCH', { properties: { '채널ID': P.text(cid) } });
          }
          try {
            items = parseFeed(await fetchText(feedOf(cid)));
          } catch (e) {
            // 캐시된 ID가 낡거나 잘못됐으면(피드 404) 한 번 다시 해석해 스스로 고친다.
            // 안 그러면 잘못된 ID가 굳어져 매일 404만 반복한다.
            if (!/HTTP 40[04]/.test(String(e.message || e))) throw e;
            const fresh = await resolveChannelId(src['값']);
            if (fresh === cid) throw e;
            cid = fresh;
            if (!dry) await notion('/pages/' + src.id, 'PATCH', { properties: { '채널ID': P.text(cid) } });
            report.rechecked = (report.rechecked || 0) + 1;
            items = parseFeed(await fetchText(feedOf(cid)));
          }
        } else if (src['유형'] === '키워드') {
          sourceType = '뉴스';
          items = parseFeed(await fetchText('https://news.google.com/rss/search?q=' + encodeURIComponent(src['값']) + '&hl=ko&gl=KR&ceid=KR:ko'));
        } else { // RSS
          items = parseFeed(await fetchText(src['값']));
        }
        const lastSeen = Date.parse(src['마지막수집'] || '') || 0;
        const eligible = items.filter(it => !seen.has(it.link) && (lastSeen ? it.ts > lastSeen : true));
        const cap = lastSeen ? 6 : FIRST_RUN_PER_SOURCE;
        const fresh = eligible.slice(0, cap);   // parseFeed가 최신순 정렬 → 최신 cap개만
        for (const it of fresh) candidates.push({ ...it, sourceType, sourceName, watchId: src.id });
        // 상한에 걸려 뒤로 밀린 항목이 있으면 워터마크를 올리면 안 된다.
        // 올리면 밀린 항목이 "이미 지나간 것"이 되어 영영 수집되지 않는다.
        if (eligible.length > fresh.length) unfinished.add(src.id);
        health.set(src.id, { found: fresh.length, kept: 0, error: '' });
        if (items.length) watermarks.set(src.id, Math.max(items[0].ts || 0, lastSeen));
      } catch (e) {
        const msg = String(e.message || e);
        report.errors.push(sourceLabel(src) + ': ' + msg);
        unfinished.add(src.id);
        health.set(src.id, { found: 0, kept: 0, error: msg });
      }
    }
    report.found = candidates.length;

    // 4) 점수화 → 임계 통과분만 본문 추출·요약·적재
    let kept = 0;
    for (const item of candidates) {
      // 회차 상한이거나 함수 시간이 얼마 안 남았으면 남은 항목은 다음 회차로 미룬다.
      // (시간 초과로 강제 종료되면 아무것도 보고되지 않고 워터마크도 어긋난다)
      // 한 항목의 최악 소요: 유튜브는 점수화 + 자막(폴링 6초 포함) + 재판정 + 요약 ≈ 25초,
      // 그 외는 ≈ 12초. 남은 시간이 그보다 적으면 시작하지 않는다.
      const needMs = item.sourceType === '유튜브' ? 25000 : 12000;
      if (kept >= MAX_NEW_PER_RUN || timeLeft() < needMs) { unfinished.add(item.watchId); continue; }
      try {
        let { score, reason } = await scoreItem(profile, item, '', feedback);
        // 명백히 무관한 것은 본문을 받지 않고 바로 버린다 (크레딧 절약)
        if (score !== null && score <= HOPELESS_SCORE) {
          report.skipped++;
          if (report.rejected.length < 12) report.rejected.push({ title: item.title.slice(0, 80), score, reason: String(reason || '').slice(0, 160), source: item.sourceName });
          continue;
        }
        // 본문 확보. 유튜브 제목은 후킹용이라 정보를 감춰서 제목만으로는 거의 항상
        // "판단 불가(5점)"가 나온다 → 애매한 구간은 본문을 받아 2차 판정한다.
        let body = '';
        if (item.sourceType === '유튜브') body = await ytTranscript(item.link);
        else { try { body = extractReadable(await fetchText(item.link)); } catch {} }
        body = String(body || '');
        // Notion 저장·점수화·요약에는 발췌(5,500자)를 쓰되, 전체 분석에는 원문을 최대한 넘긴다.
        // 발췌만 넘기면 자동 분석이 소스의 일부만 보고 판단해 수동 분석보다 품질이 떨어진다.
        const full = body.slice(0, 40000);
        const excerpt = body.slice(0, 5500);

        if (score !== null && score < SCORE_THRESHOLD) {
          if (excerpt.length < 200) { // 재판정할 근거가 없으면 1차 판정을 따른다
            report.skipped++;
            if (report.rejected.length < 12) report.rejected.push({ title: item.title.slice(0, 80), score, reason: String(reason || '').slice(0, 160), source: item.sourceName });
            continue;
          }
          const second = await scoreItem(profile, item, excerpt, feedback);
          report.rescored = (report.rescored || 0) + 1;
          score = second.score; reason = second.reason;
          if (score !== null && score < SCORE_THRESHOLD) {
            report.skipped++;
            if (report.rejected.length < 12) report.rejected.push({ title: item.title.slice(0, 80), score, reason: String(reason || '').slice(0, 160), source: item.sourceName, stage: '본문 확인 후' });
            continue;
          }
        }
        const summary = await summarize({ ...item, reason }, excerpt);

        // 확실히 좋은 것(8점 이상)은 여기서 전체 분석까지 끝내 프로젝트로 만든다.
        // 아침에 앱을 열면 이미 완성된 결과가 기다린다. Sonnet 호출이라 회차당 상한을 둔다.
        let analyzed = false;
        const canAnalyze = autoAnalyze && score >= AUTO_ANALYZE_SCORE && report.analyzed < MAX_AUTO_ANALYZE
          && excerpt.length >= 400 && (process.env.ANTHROPIC_API_KEY || '').trim() && !dry;
        if (canAnalyze && timeLeft() < ANALYZE_NEEDS_MS) {
          report.analyzeSkipped = (report.analyzeSkipped || 0) + 1;  // 시간 부족 → 앱에서 수동 분석
        } else if (canAnalyze) {
          try {
            const data = await analyzeSource({
              key: apiKey('ANTHROPIC_API_KEY'), model: process.env.ANALYSIS_MODEL || 'claude-sonnet-5',
              title: item.title, channel: item.author || item.sourceName, url: item.link, transcript: full,
            });
            const now = new Date().toISOString();
            await upsertProject({
              id: 's_auto_' + Date.now().toString(36) + '_' + report.analyzed,
              at: now, updatedAt: now,
              sourceType: item.sourceType === '유튜브' ? 'youtube' : 'web',
              sourceUrl: item.link, title: item.title, channel: item.author || item.sourceName,
              data, sourceExcerpt: excerpt, contents: [],
            });
            report.analyzed++; analyzed = true;
          } catch (e) { report.errors.push('자동 분석 실패(' + item.title.slice(0, 30) + '): ' + String(e.message || e)); }
        }

        if (!dry) {
          await notion('/pages', 'POST', {
            parent: { database_id: INBOX_DB },
            properties: {
              '제목': P.title(item.title), 'URL': P.url(item.link), '출처': P.select(item.sourceType),
              '채널/매체': P.text(item.author || item.sourceName), '점수': P.number(score),
              '요약': P.text((reason ? '[' + (score ?? '-') + '점] ' + reason + '\n' : '') + summary),
              '본문': P.text(excerpt), '상태': P.select(analyzed ? '분석됨' : '새 항목'), '썸네일': P.url(item.thumb || ''),
              '수집일': P.date(new Date(item.ts || Date.now()).toISOString()),
            },
          });
        }
        seen.add(item.link); kept++;
        const h = health.get(item.watchId); if (h) h.kept++;
      } catch (e) {
        report.errors.push(item.title.slice(0, 40) + ': ' + String(e.message || e));
        unfinished.add(item.watchId); // 이 소스는 워터마크를 올리지 않아 다음 회차에 재시도
      }
    }
    report.kept = kept;

    // 5) 소스별 워터마크 + 건강 상태 기록
    if (!dry) {
      const nowIso = new Date().toISOString();
      for (const src of sources) {
        const h = health.get(src.id) || { found: 0, kept: 0, error: '' };
        const props = {};
        // 워터마크는 끝까지 처리된 소스만 — 밀린 항목이 영영 유실되지 않도록
        const ts = watermarks.get(src.id);
        if (ts && !unfinished.has(src.id)) props['마지막수집'] = P.text(new Date(ts).toISOString());
        else if (ts) report.retry = (report.retry || 0) + 1;

        if (h.error) {
          props['연속실패'] = P.number((Number(src['연속실패']) || 0) + 1);
          props['최근결과'] = P.text('실패: ' + h.error.slice(0, 300));
        } else {
          props['마지막성공'] = P.text(nowIso);
          props['연속실패'] = P.number(0);
          props['누적통과'] = P.number((Number(src['누적통과']) || 0) + h.kept);
          props['최근결과'] = P.text('신규 ' + h.found + '건 · 통과 ' + h.kept + '건');
        }
        try { await notion('/pages/' + src.id, 'PATCH', { properties: props }); }
        catch (e) { report.errors.push('상태 기록 실패(' + sourceLabel(src) + '): ' + String(e.message || e)); }
      }
    }
    res.status(200).json(report);
  } catch (e) {
    res.status(500).json({ ...report, ok: false, error: String(e && e.message || e) });
  }
}
function sourceLabel(src) { return (src['이름'] || src['값'] || '').slice(0, 40); }
