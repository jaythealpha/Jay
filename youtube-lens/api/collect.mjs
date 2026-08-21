// Vercel Cron — 워치리스트(Notion)의 유튜브 채널·RSS·키워드에서 새 항목을 수집,
// Haiku로 관심 프로필과 대조해 필터링한 뒤 수집함(Notion)에 적재.
//
//   GET /api/collect            → 크론/수동 실행 (x-app-key 또는 CRON_SECRET)
//   GET /api/collect?dry=1      → 수집만 하고 저장 안 함 (테스트)
//
// env: NOTION_TOKEN(필수), ANTHROPIC_API_KEY(필터링·요약, 없으면 필터 없이 적재),
//      SUPADATA_API_KEY(유튜브 자막), APP_KEY/CRON_SECRET(선택)
import { INBOX_DB, WATCH_DB, notion, queryDb, readProps, P, authorized, cors } from './_notion.mjs';

export const config = { maxDuration: 60 };

const MAX_NEW_PER_RUN = 10;      // 한 번 실행당 적재 상한 (시간·비용 보호)
const FIRST_RUN_PER_SOURCE = 3;  // 처음 보는 소스는 최신 N개만
const SCORE_THRESHOLD = 6;       // 이 점수 미만은 버림 (0~10)

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
    if (title && link) items.push({ title, link: link.trim(), ts: isNaN(ts) ? 0 : ts, desc, author });
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
async function resolveChannelId(value) {
  const v = String(value || '').trim();
  const m = v.match(/(UC[0-9A-Za-z_-]{22})/);
  if (m) return m[1];
  let url = v;
  if (!/^https?:\/\//i.test(url)) url = 'https://www.youtube.com/' + (url.startsWith('@') ? url : '@' + url);
  const html = await fetchText(url);
  const c = html.match(/"channelId":"(UC[0-9A-Za-z_-]{22})"/) || html.match(/channel\/(UC[0-9A-Za-z_-]{22})/);
  if (!c) throw new Error('채널 ID를 찾지 못했어요: ' + v);
  return c[1];
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
async function scoreItem(profile, item) {
  if (!(process.env.ANTHROPIC_API_KEY || '').trim()) return { score: null, reason: '필터 미사용(ANTHROPIC_API_KEY 없음)' };
  const out = await haiku(
    '당신은 콘텐츠 큐레이터입니다. 아래 관심 프로필과 새 콘텐츠를 대조해 관련성·유용성을 0~10 점수로 평가하세요.\n\n' +
    '[관심 프로필]\n' + profile + '\n\n[콘텐츠]\n제목: ' + item.title + '\n출처: ' + (item.author || item.sourceName || '') + '\n설명: ' + (item.desc || '(없음)') + '\n\n' +
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
  const dry = !!(req.query && req.query.dry);
  const report = { ok: true, sources: 0, found: 0, kept: 0, skipped: 0, errors: [] };
  try {
    // 잘못 붙여넣은 키는 항목마다 같은 오류를 내므로 시작 전에 한 번에 걸러낸다
    apiKey('ANTHROPIC_API_KEY'); apiKey('SUPADATA_API_KEY');
    // 1) 워치리스트 로드
    const wl = (await queryDb(WATCH_DB)).results.map(readProps).filter(w => w['활성']);
    const profileRows = wl.filter(w => w['유형'] === '관심 프로필');
    const profile = profileRows.map(w => w['값']).join('\n') || '실전 노하우, 구체적 사례, 실행 가능한 전략이 있는 콘텐츠';
    const sources = wl.filter(w => w['유형'] !== '관심 프로필');
    report.sources = sources.length;
    if (!sources.length) { res.status(200).json({ ...report, note: '워치리스트에 활성 소스가 없어요.' }); return; }

    // 2) 기존 수집함 URL 셋 (중복 방지)
    const seen = new Set();
    const recent = await queryDb(INBOX_DB, { sorts: [{ timestamp: 'created_time', direction: 'descending' }] });
    for (const p of recent.results) { const u = readProps(p)['URL']; if (u) seen.add(u); }

    // 3) 소스별 새 항목 수집
    const candidates = [];
    for (const src of sources) {
      try {
        let items = [], sourceType = 'RSS', sourceName = src['이름'] || src['값'];
        if (src['유형'] === '유튜브 채널') {
          sourceType = '유튜브';
          let cid = (src['채널ID'] || '').trim();
          if (!cid) {
            cid = await resolveChannelId(src['값']);
            if (!dry) await notion('/pages/' + src.id, 'PATCH', { properties: { '채널ID': P.text(cid) } });
          }
          items = parseFeed(await fetchText('https://www.youtube.com/feeds/videos.xml?channel_id=' + cid));
        } else if (src['유형'] === '키워드') {
          sourceType = '뉴스';
          items = parseFeed(await fetchText('https://news.google.com/rss/search?q=' + encodeURIComponent(src['값']) + '&hl=ko&gl=KR&ceid=KR:ko'));
        } else { // RSS
          items = parseFeed(await fetchText(src['값']));
        }
        const lastSeen = Date.parse(src['마지막수집'] || '') || 0;
        let fresh = items.filter(it => !seen.has(it.link) && (lastSeen ? it.ts > lastSeen : true));
        if (!lastSeen) fresh = fresh.slice(0, FIRST_RUN_PER_SOURCE);
        else fresh = fresh.slice(0, 6);
        for (const it of fresh) candidates.push({ ...it, sourceType, sourceName, watchId: src.id });
        if (items.length && !dry) {
          const newest = new Date(Math.max(items[0].ts || 0, lastSeen)).toISOString();
          await notion('/pages/' + src.id, 'PATCH', { properties: { '마지막수집': P.text(newest) } });
        }
      } catch (e) { report.errors.push(sourceLabel(src) + ': ' + String(e.message || e)); }
    }
    report.found = candidates.length;

    // 4) 점수화 → 임계 통과분만 본문 추출·요약·적재
    let kept = 0;
    for (const item of candidates) {
      if (kept >= MAX_NEW_PER_RUN) break;
      try {
        const { score, reason } = await scoreItem(profile, item);
        if (score !== null && score < SCORE_THRESHOLD) { report.skipped++; continue; }
        let excerpt = '';
        if (item.sourceType === '유튜브') excerpt = await ytTranscript(item.link);
        else { try { excerpt = extractReadable(await fetchText(item.link)); } catch {} }
        excerpt = String(excerpt || '').slice(0, 5500);
        const summary = await summarize({ ...item, reason }, excerpt);
        if (!dry) {
          await notion('/pages', 'POST', {
            parent: { database_id: INBOX_DB },
            properties: {
              '제목': P.title(item.title), 'URL': P.url(item.link), '출처': P.select(item.sourceType),
              '채널/매체': P.text(item.author || item.sourceName), '점수': P.number(score),
              '요약': P.text((reason ? '[' + (score ?? '-') + '점] ' + reason + '\n' : '') + summary),
              '본문': P.text(excerpt), '상태': P.select('새 항목'),
              '수집일': P.date(new Date(item.ts || Date.now()).toISOString()),
            },
          });
        }
        seen.add(item.link); kept++;
      } catch (e) { report.errors.push(item.title.slice(0, 40) + ': ' + String(e.message || e)); }
    }
    report.kept = kept;
    res.status(200).json(report);
  } catch (e) {
    res.status(500).json({ ...report, ok: false, error: String(e && e.message || e) });
  }
}
function sourceLabel(src) { return (src['이름'] || src['값'] || '').slice(0, 40); }
