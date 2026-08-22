// Vercel serverless function — YouTube 자막을 서버에서 추출해 반환.
// 서버는 CORS 제약이 없고 유튜브 innertube(player) API를 직접 호출할 수 있어
// 브라우저 CORS 프록시보다 훨씬 안정적입니다.
//
//   GET /api/transcript?id=VIDEOID  또는  ?url=<youtube url>&lang=ko[&debug=1]
//   → { ok, transcript, lang, title, author, durationSec, source }
//
// 배포: 이 파일을 Vercel 프로젝트의 /api 폴더에 두면 자동으로 함수로 인식됩니다.

// 공개 innertube 키 (WEB / ANDROID)
const IK_WEB = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8';
const IK_ANDROID = 'AIzaSyA8eiZmM1FaDVjRy-df2KTyQ_vz_yYM39w';

// ---- 1순위: 외부 자막 API (Supadata) ----
// YouTube가 데이터센터 IP의 자막 다운로드를 막기 때문에, 레지던셜 IP/PO 토큰을
// 대신 처리해 주는 유지보수 서비스를 통해야 안정적입니다. 사용자 본인 키 필요.
// 키 발급: https://supadata.ai (무료 티어 제공)
async function supadata(id, key, prefer) {
  const yurl = 'https://youtu.be/' + id;
  // 여러 문서 버전에 대응해 요청 형태를 순서대로 시도
  // mode=auto: 업로더 자막이 없으면 Supadata가 AI 자막을 생성해 폴백 (크레딧 추가 소모)
  const endpoints = [
    'https://api.supadata.ai/v1/youtube/transcript?videoId=' + encodeURIComponent(id) + '&lang=' + prefer + '&text=true&mode=auto',
    'https://api.supadata.ai/v1/youtube/transcript?url=' + encodeURIComponent(yurl) + '&lang=' + prefer + '&text=true&mode=auto',
    'https://api.supadata.ai/v1/transcript?url=' + encodeURIComponent(yurl) + '&lang=' + prefer + '&text=true&mode=auto',
  ];
  const pickText = j => {
    const c = j.content ?? j.transcript ?? j.text;
    const t = typeof c === 'string' ? c : Array.isArray(c) ? c.map(x => x.text || x.content || '').join(' ') : '';
    return String(t).replace(/\s+/g, ' ').trim();
  };
  let lastErr = 'supadata 실패';
  for (const url of endpoints) {
    try {
      const r = await fetch(url, { headers: { 'x-api-key': key, 'accept': 'application/json' } });
      if (!r.ok) {
        let m = 'HTTP ' + r.status;
        try { const e = await r.json(); if (e && (e.message || e.error)) m += ' ' + (e.message || e.error); } catch {}
        lastErr = m;
        if (r.status === 401 || r.status === 403) throw new Error(m); // 키 문제면 즉시 중단
        continue;
      }
      let j = await r.json();
      let clean = pickText(j);
      // AI 자막 생성은 비동기(jobId) — 잠시 폴링
      if (!clean && j.jobId) {
        for (let i = 0; i < 5; i++) {
          await sleep(2000);
          const jr = await fetch('https://api.supadata.ai/v1/transcript/' + j.jobId, { headers: { 'x-api-key': key, 'accept': 'application/json' } });
          if (!jr.ok) continue;
          const jj = await jr.json();
          if (jj.status === 'failed') { lastErr = 'AI 자막 생성 실패'; break; }
          clean = pickText(jj);
          if (clean) { j = jj; break; }
        }
      }
      if (clean.length >= 20) return { text: clean, lang: j.lang || prefer };
      lastErr = j.jobId ? 'AI 자막 생성이 아직 안 끝났어요. 잠시 후 다시 시도해 주세요.' : '빈 응답';
    } catch (e) { lastErr = String(e && e.message || e); if (/HTTP 40[13]/.test(lastErr)) break; }
  }
  throw new Error(lastErr);
}

function parseId(s) {
  s = String(s || '').trim();
  const m = s.match(/(?:youtu\.be\/|v=|\/embed\/|\/shorts\/|\/live\/)([A-Za-z0-9_-]{11})/) ||
            s.match(/^([A-Za-z0-9_-]{11})$/);
  return m ? m[1] : '';
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

// Supadata 유니버설: 임의 URL(Instagram/TikTok/X/파일 등)의 전사/자막을 URL로 요청.
// 일부 플랫폼은 비동기(jobId) 응답 → 몇 번 폴링.
async function supadataByUrl(url, key, prefer) {
  const headers = { 'x-api-key': key, 'accept': 'application/json' };
  const endpoints = [
    'https://api.supadata.ai/v1/transcript?url=' + encodeURIComponent(url) + '&lang=' + prefer + '&text=true',
    'https://api.supadata.ai/v1/web/scrape?url=' + encodeURIComponent(url),
  ];
  const pickText = j => {
    const c = j.content ?? j.transcript ?? j.text;
    const t = typeof c === 'string' ? c : Array.isArray(c) ? c.map(x => x.text || x.content || '').join(' ') : '';
    return String(t).replace(/\s+/g, ' ').trim();
  };
  let lastErr = 'supadata 실패';
  for (const ep of endpoints) {
    try {
      const r = await fetch(ep, { headers });
      if (!r.ok) { let m = 'HTTP ' + r.status; try { const e = await r.json(); if (e && (e.message || e.error)) m += ' ' + (e.message || e.error); } catch {} lastErr = m; if (r.status === 401 || r.status === 403) throw new Error(m); continue; }
      let j = await r.json();
      let text = pickText(j);
      // 비동기 job 처리
      if (!text && j.jobId) {
        for (let i = 0; i < 4; i++) {
          await sleep(1600);
          const jr = await fetch('https://api.supadata.ai/v1/transcript/' + j.jobId, { headers });
          if (!jr.ok) continue;
          const jj = await jr.json();
          if (jj.status === 'failed') { lastErr = 'job failed'; break; }
          text = pickText(jj);
          if (text) { j = jj; break; }
        }
      }
      if (text && text.length >= 20) return { text, lang: j.lang || prefer, title: j.title || j.name || '' };
      lastErr = '빈 응답';
    } catch (e) { lastErr = String(e && e.message || e); if (/HTTP 40[13]/.test(lastErr)) break; }
  }
  throw new Error(lastErr);
}

// ---- caption track 수집 ----
async function innertube(id, client) {
  const clients = {
    web:     { key: IK_WEB,     ctx: { clientName: 'WEB', clientVersion: '2.20240726.00.00', hl: 'ko', gl: 'KR' },
               ua: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36' },
    android: { key: IK_ANDROID, ctx: { clientName: 'ANDROID', clientVersion: '19.09.37', androidSdkVersion: 30, hl: 'ko', gl: 'KR' },
               ua: 'com.google.android.youtube/19.09.37 (Linux; U; Android 11) gzip' },
  };
  const c = clients[client];
  const r = await fetch('https://www.youtube.com/youtubei/v1/player?key=' + c.key, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'user-agent': c.ua, 'x-goog-api-format-version': '2', 'accept-language': 'ko,en;q=0.9' },
    body: JSON.stringify({ context: { client: c.ctx }, videoId: id }),
  });
  if (!r.ok) throw new Error(client + ' ' + r.status);
  const j = await r.json();
  return {
    tracks: j?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [],
    title: j?.videoDetails?.title || '',
    author: j?.videoDetails?.author || '',
    durationSec: Number(j?.videoDetails?.lengthSeconds || 0) || 0,
  };
}

async function scrape(id) {
  const r = await fetch('https://www.youtube.com/watch?v=' + id + '&hl=en&bpctr=9999999999&has_verified=1', {
    headers: {
      'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36',
      'accept-language': 'en-US,en;q=0.9',
      'cookie': 'CONSENT=YES+cb.20210328-17-p0.en+FX+678; SOCS=CAISEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg;',
    },
  });
  const html = await r.text();
  const title = (html.match(/<meta name="title" content="([^"]*)"/) || [])[1] || '';
  const m = html.match(/"captionTracks":(\[.*?\])/s);
  let tracks = [];
  if (m) { try { tracks = JSON.parse(m[1].replace(/\\u0026/g, '&')); } catch {} }
  return { tracks, title, author: '', durationSec: 0 };
}

function normBase(u) { return String(u || '').replace(/\\u0026/g, '&').replace(/&amp;/g, '&'); }

function langScore(t, prefer) {
  const lc = (t.languageCode || '').toLowerCase();
  let s = 0;
  if (lc === prefer) s += 100; else if (lc.startsWith(prefer)) s += 80;
  else if (lc === 'ko') s += 60; else if (lc.startsWith('en')) s += 40;
  if (t.kind !== 'asr') s += 5; // 수동 자막 우선
  return s;
}

function timedTextToText(raw) {
  const s = String(raw).trim();
  if (!s) return '';
  if (s.startsWith('{')) {
    try {
      const j = JSON.parse(s);
      return (j.events || []).map(ev => (ev.segs || []).map(sg => sg.utf8 || '').join('')).join(' ')
        .replace(/\s+/g, ' ').trim();
    } catch { /* fall through */ }
  }
  const texts = [...s.matchAll(/<text[^>]*>([\s\S]*?)<\/text>/g)].map(x => x[1]);
  const decode = t => t
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&#39;|&apos;/g, "'").replace(/&quot;/g, '"').replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n));
  return texts.map(decode).join(' ').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
}

// 하나의 track baseUrl에서 자막 텍스트를 여러 포맷으로 시도
async function fetchTrackText(baseUrl) {
  const base = normBase(baseUrl);
  const variants = [
    base.includes('fmt=') ? base : base + '&fmt=json3',
    base.replace(/&fmt=\w+/, ''), // 기본(XML)
  ];
  for (const u of variants) {
    try {
      const r = await fetch(u, { headers: { 'user-agent': 'Mozilla/5.0', 'accept-language': 'ko,en;q=0.9' } });
      if (!r.ok) continue;
      const text = timedTextToText(await r.text());
      if (text.length >= 20) return text;
    } catch { /* next */ }
  }
  return '';
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'x-transcript-key, x-app-key, content-type');
  // 인증 여부에 따라 응답이 달라지므로 캐시가 키를 구분하게 한다
  res.setHeader('Cache-Control', 'public, max-age=86400');
  res.setHeader('Vary', 'x-app-key, x-transcript-key');
  if (req.method === 'OPTIONS') { res.status(204).end(); return; }

  const q = req.query || {};
  const rawUrl = (q.url || '').toString().trim();
  const id = parseId(q.id || rawUrl);
  const prefer = (q.lang || 'ko').toString().toLowerCase();
  const debug = q.debug ? [] : null;

  // 서버에 저장된 SUPADATA_API_KEY(=내 크레딧)는 인증된 요청에만 빌려준다.
  // 아니면 주소만 아는 사람이 임의 링크로 무제한 호출해 크레딧을 태울 수 있다.
  // 사용자가 본인 키를 직접 보내는 경우(x-transcript-key)는 인증 없이도 허용.
  const appKey = (process.env.APP_KEY || '').trim();
  const ownKey = (q.key || req.headers['x-transcript-key'] || '').toString().trim();
  const trusted = !appKey || String(req.headers['x-app-key'] || q.appkey || '') === appKey;
  const txKey = ownKey || (trusted ? (process.env.SUPADATA_API_KEY || '').trim() : '');

  // 유튜브가 아닌 URL(Instagram/TikTok/X 등) → Supadata 유니버설 (키 필요)
  if (!id && rawUrl) {
    if (!txKey) { res.status(400).json({ ok: false, needKey: true, error: '이 링크 유형은 자막 API 키(Supadata)가 필요해요. ⚙️ 설정에 넣어주세요.' }); return; }
    try {
      const s = await supadataByUrl(rawUrl, txKey, prefer);
      res.status(200).json({ ok: true, transcript: s.text, lang: s.lang, title: s.title || '', author: '', source: 'supadata-url' }); return;
    } catch (e) {
      res.status(502).json({ ok: false, error: '자막 API로 못 가져왔어요 (' + String(e && e.message || e) + '). 텍스트를 직접 붙여넣어 주세요.' }); return;
    }
  }
  if (!id) { res.status(400).json({ ok: false, error: '유효한 videoId/URL이 필요합니다.' }); return; }

  // 0순위: 외부 자막 API (키가 있을 때) — 데이터센터 IP 차단을 우회하는 유일하게 안정적인 경로
  let sdErr = '';
  if (txKey) {
    try {
      const s = await supadata(id, txKey, prefer);
      const body = { ok: true, transcript: s.text, lang: s.lang, title: '', author: '', source: 'supadata' };
      if (debug) body.debug = [{ src: 'supadata', chars: s.text.length }];
      res.status(200).json(body); return;
    } catch (e) { sdErr = String(e && e.message || e); if (debug) debug.push({ src: 'supadata', error: sdErr }); /* 폴백 진행 */ }
  }

  // 여러 소스에서 track을 모은다 (WEB innertube → 스크레이프 → ANDROID) — 키 없을 때 best-effort
  const sources = [['web', innertube], ['scrape', scrape], ['android', innertube]];
  let title = '', author = '', durationSec = 0;
  const all = []; // { track, from }
  for (const [name, fn] of sources) {
    try {
      const out = name === 'scrape' ? await scrape(id) : await innertube(id, name);
      title = title || out.title; author = author || out.author; durationSec = durationSec || out.durationSec;
      (out.tracks || []).forEach(t => all.push({ track: t, from: name }));
      if (debug) debug.push({ src: name, tracks: (out.tracks || []).length, title: out.title });
    } catch (e) { if (debug) debug.push({ src: name, error: String(e && e.message || e) }); }
  }

  if (!all.length) {
    const body = { ok: false, needKey: !txKey,
      error: txKey ? ('자막 API로 못 가져왔어요' + (sdErr ? ' (' + sdErr + ')' : '') + '. 이 영상에 자막이 없거나 키/요청에 문제가 있을 수 있어요.')
                   : '무료 추출이 차단됐어요. ⚙️ 설정에 자막 API 키(Supadata)를 넣거나 스크립트를 붙여넣어 주세요.',
      title, author };
    if (debug) body.debug = debug;
    res.status(404).json(body); return;
  }

  // 언어 우선순위로 정렬 후, 텍스트가 나올 때까지 순서대로 시도
  all.sort((a, b) => langScore(b.track, prefer) - langScore(a.track, prefer));
  for (const cand of all) {
    const text = await fetchTrackText(cand.track.baseUrl);
    if (text) {
      const body = { ok: true, transcript: text, lang: cand.track.languageCode || prefer, title, author, durationSec, source: cand.from };
      if (debug) body.debug = debug;
      res.status(200).json(body); return;
    }
  }

  const body = { ok: false, needKey: !txKey,
    error: txKey ? '자막을 가져왔지만 내용이 비어 있어요. 붙여넣기로 진행해 주세요.'
                 : '유튜브가 자막 다운로드를 차단했어요. ⚙️ 설정에 자막 API 키(Supadata)를 넣으면 안정적으로 됩니다.',
    title, author };
  if (debug) body.debug = debug;
  res.status(422).json(body);
};
