// Vercel serverless function — YouTube 자막(자동/수동)을 서버에서 추출해 반환.
// 서버는 CORS 제약이 없고 유튜브 innertube(player) API를 직접 호출할 수 있어
// 브라우저 CORS 프록시보다 훨씬 안정적입니다.
//
//   GET /api/transcript?id=VIDEOID   또는   ?url=<youtube url>&lang=ko
//   → { ok, transcript, lang, title, author, durationSec, source }
//
// 배포: 이 파일을 Vercel 프로젝트의 /api 폴더에 두면 자동으로 함수로 인식됩니다.

const IK_ANDROID = 'AIzaSyA8eiZmM1FaDVjRy-df2KTyQ_vz_yYM39w'; // 공개 ANDROID innertube 키

function parseId(s) {
  s = String(s || '').trim();
  const m = s.match(/(?:youtu\.be\/|v=|\/embed\/|\/shorts\/|\/live\/)([A-Za-z0-9_-]{11})/) ||
            s.match(/^([A-Za-z0-9_-]{11})$/);
  return m ? m[1] : '';
}

function pickTrack(tracks, prefer) {
  const has = pred => tracks.find(pred);
  const p = (prefer || 'ko').toLowerCase();
  return has(t => t.languageCode === p && t.kind !== 'asr')
      || has(t => t.languageCode === p)
      || has(t => (t.languageCode || '').startsWith(p))
      || has(t => t.languageCode === 'ko' && t.kind !== 'asr')
      || has(t => t.languageCode === 'ko')
      || has(t => (t.languageCode || '').startsWith('en') && t.kind !== 'asr')
      || has(t => (t.languageCode || '').startsWith('en'))
      || tracks[0];
}

async function innertubePlayer(id) {
  const body = {
    context: { client: { clientName: 'ANDROID', clientVersion: '19.09.37', androidSdkVersion: 30, hl: 'ko', gl: 'KR' } },
    videoId: id,
  };
  const r = await fetch('https://www.youtube.com/youtubei/v1/player?key=' + IK_ANDROID, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'user-agent': 'com.google.android.youtube/19.09.37 (Linux; U; Android 11) gzip',
      'x-goog-api-format-version': '2',
    },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error('innertube ' + r.status);
  return r.json();
}

// watch 페이지 스크레이프 폴백 (innertube가 자막을 못 줄 때)
async function scrapeCaptionTracks(id) {
  const r = await fetch('https://www.youtube.com/watch?v=' + id + '&hl=en', {
    headers: {
      'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36',
      'accept-language': 'en-US,en;q=0.9',
      'cookie': 'CONSENT=YES+1; SOCS=CAI;',
    },
  });
  const html = await r.text();
  const m = html.match(/"captionTracks":(\[.*?\])/s);
  const title = (html.match(/<meta name="title" content="([^"]*)"/) || [])[1] || '';
  if (!m) return { tracks: [], title };
  try { return { tracks: JSON.parse(m[1].replace(/\\u0026/g, '&')), title }; }
  catch { return { tracks: [], title }; }
}

function timedTextToText(raw) {
  const s = String(raw).trim();
  if (s.startsWith('{')) {
    try {
      const j = JSON.parse(s);
      return (j.events || []).map(ev => (ev.segs || []).map(sg => sg.utf8 || '').join('')).join(' ')
        .replace(/\s+/g, ' ').trim();
    } catch { /* fall through */ }
  }
  // xml
  const texts = [...s.matchAll(/<text[^>]*>([\s\S]*?)<\/text>/g)].map(x => x[1]);
  const decode = t => t
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&#39;|&apos;/g, "'").replace(/&quot;/g, '"').replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n));
  return texts.map(decode).join(' ').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Cache-Control', 'public, max-age=86400');
  if (req.method === 'OPTIONS') { res.status(204).end(); return; }

  const q = req.query || {};
  const id = parseId(q.id || q.url || '');
  const prefer = (q.lang || 'ko').toString();
  if (!id) { res.status(400).json({ ok: false, error: '유효한 videoId/URL이 필요합니다.' }); return; }

  try {
    let tracks = [], title = '', author = '', durationSec = 0, source = 'innertube';
    try {
      const pj = await innertubePlayer(id);
      tracks = pj?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
      title = pj?.videoDetails?.title || '';
      author = pj?.videoDetails?.author || '';
      durationSec = Number(pj?.videoDetails?.lengthSeconds || 0) || 0;
    } catch (e) { /* try scrape */ }

    if (!tracks.length) {
      const sc = await scrapeCaptionTracks(id);
      tracks = sc.tracks; title = title || sc.title; source = 'scrape';
    }
    if (!tracks.length) {
      res.status(404).json({ ok: false, error: '이 영상에는 자막(캡션)이 없어요.', title, author });
      return;
    }

    const track = pickTrack(tracks, prefer);
    let base = String(track.baseUrl || '').replace(/\\u0026/g, '&').replace(/&amp;/g, '&');
    if (!base) { res.status(404).json({ ok: false, error: '자막 주소를 찾지 못했어요.', title, author }); return; }
    const ttUrl = base + (base.includes('fmt=') ? '' : '&fmt=json3');
    const ttr = await fetch(ttUrl, { headers: { 'user-agent': 'Mozilla/5.0' } });
    const transcript = timedTextToText(await ttr.text());
    if (transcript.length < 20) { res.status(422).json({ ok: false, error: '자막이 비어 있어요.', title, author }); return; }

    res.status(200).json({ ok: true, transcript, lang: track.languageCode || prefer, title, author, durationSec, source });
  } catch (e) {
    res.status(502).json({ ok: false, error: '서버에서 자막 추출 실패: ' + (e && e.message || e) });
  }
};
