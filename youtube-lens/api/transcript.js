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

function parseId(s) {
  s = String(s || '').trim();
  const m = s.match(/(?:youtu\.be\/|v=|\/embed\/|\/shorts\/|\/live\/)([A-Za-z0-9_-]{11})/) ||
            s.match(/^([A-Za-z0-9_-]{11})$/);
  return m ? m[1] : '';
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
  res.setHeader('Cache-Control', 'public, max-age=86400');
  if (req.method === 'OPTIONS') { res.status(204).end(); return; }

  const q = req.query || {};
  const id = parseId(q.id || q.url || '');
  const prefer = (q.lang || 'ko').toString().toLowerCase();
  const debug = q.debug ? [] : null;
  if (!id) { res.status(400).json({ ok: false, error: '유효한 videoId/URL이 필요합니다.' }); return; }

  // 여러 소스에서 track을 모은다 (WEB innertube → 스크레이프 → ANDROID)
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
    const body = { ok: false, error: '이 영상에는 자막(캡션)이 없거나 접근이 제한되어 있어요.', title, author };
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

  const body = { ok: false, error: '자막을 가져왔지만 내용이 비어 있어요. 붙여넣기로 진행해 주세요.', title, author };
  if (debug) body.debug = debug;
  res.status(422).json(body);
};
