// Vercel serverless function — 웹 링크의 본문 텍스트를 서버에서 추출해 반환.
// 브라우저는 CORS로 임의 사이트를 못 읽지만 서버는 가능. (유튜브는 /api/transcript 사용)
//
//   GET /api/fetch-source?url=https://example.com/article
//   → { ok, title, siteName, text, url, chars }

function decodeEntities(s) {
  return String(s)
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => { try { return String.fromCodePoint(+n); } catch { return ''; } })
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => { try { return String.fromCodePoint(parseInt(n, 16)); } catch { return ''; } });
}

function metaOf(html, prop) {
  const re = new RegExp(`<meta[^>]+(?:property|name)=["']${prop}["'][^>]*content=["']([^"']*)["']`, 'i');
  const re2 = new RegExp(`<meta[^>]+content=["']([^"']*)["'][^>]*(?:property|name)=["']${prop}["']`, 'i');
  const m = html.match(re) || html.match(re2);
  return m ? decodeEntities(m[1]).trim() : '';
}

function extractReadable(html) {
  let h = html;
  // 통짜 제거: 스크립트/스타일/헤드/네비 등 비본문
  h = h.replace(/<!--[\s\S]*?-->/g, ' ');
  h = h.replace(/<(script|style|noscript|svg|template|iframe|head|nav|header|footer|aside|form)\b[\s\S]*?<\/\1>/gi, ' ');
  // 본문 후보: <article> 또는 <main> 우선
  let body = '';
  const art = h.match(/<article\b[\s\S]*?<\/article>/i);
  const main = h.match(/<main\b[\s\S]*?<\/main>/i);
  body = (art && art[0]) || (main && main[0]) || h;
  // 블록 경계를 줄바꿈으로
  body = body.replace(/<\/(p|div|section|li|h[1-6]|br|tr|blockquote)>/gi, '\n');
  body = body.replace(/<br\s*\/?>/gi, '\n');
  // 남은 태그 제거
  body = body.replace(/<[^>]+>/g, ' ');
  body = decodeEntities(body);
  // 공백 정리 (줄 단위)
  const lines = body.split('\n').map(l => l.replace(/[ \t ]+/g, ' ').trim()).filter(l => l.length > 1);
  // 반복/네비 잔여 짧은 줄 다수 제거는 생략(간단 버전) — 그대로 합침
  return lines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

/* Jina Reader 폴백 — Agent Reach(github.com/Panniantong/Agent-Reach)의 웹 채널 방식.
   직접 HTML을 파싱하면 본문을 JS로 그리는 사이트에서 빈손이 된다. r.jina.ai는
   페이지를 렌더링해 마크다운으로 돌려주고 키가 필요 없다. */
const JINA_TIMEOUT_MS = 20000;

// Jina/Cloudflare가 본문 대신 돌려주는 차단·검증 페이지.
// 이걸 그대로 본문으로 넘기면 "성공"으로 위장된 쓰레기가 분석까지 흘러간다.
function isAntibotPage(text) {
  const s = String(text || '').slice(0, 4096).toLowerCase();
  const jinaCaptcha = s.includes('warning:') && s.includes('requiring captcha');
  const challenge = ['title: just a moment...', '## performing security verification',
    'title: attention required! | cloudflare'].some(m => s.includes(m));
  const cfBlock = s.includes('title: attention required! | cloudflare') &&
    (s.includes('ray id') || s.includes('/cdn-cgi/challenge-platform/'));
  // 원본(Agent Reach)은 Jina 경고 문구가 함께 있을 때만 챌린지로 본다. 그러면
  // 경고 없이 오는 순수 Cloudflare 대기 페이지가 본문으로 통과한다. 이 두 문구는
  // 실제 기사에 나올 일이 없으므로 단독으로도 차단으로 취급한다.
  const cfChallenge = s.includes('title: just a moment...') ||
    s.includes('## performing security verification');
  return (jinaCaptcha && challenge) || cfBlock || cfChallenge;
}

async function jinaReader(url) {
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), JINA_TIMEOUT_MS);
  try {
    const r = await fetch('https://r.jina.ai/' + url, {
      signal: ac.signal,
      headers: { 'accept': 'text/plain', 'x-return-format': 'markdown' },
    });
    if (!r.ok) throw new Error('Jina HTTP ' + r.status);
    const md = await r.text();
    if (isAntibotPage(md)) throw new Error('차단·검증 페이지');
    // Jina는 본문 앞에 Title/URL Source/Markdown Content 헤더를 붙인다
    const title = ((md.match(/^Title:\s*(.+)$/m) || [])[1] || '').trim();
    const body = (md.split(/^Markdown Content:\s*$/m)[1] || md).trim();
    return { title, text: body };
  } finally { clearTimeout(timer); }
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'content-type');
  // 성공한 응답만 캐시한다. 모든 응답에 걸면 일시적 실패까지 CDN에 굳어
  // 사용자가 다시 시도할 방법이 없어진다. (api/transcript.js와 같은 이유)
  const cacheOk = () => res.setHeader('Cache-Control', 'public, max-age=3600');
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'OPTIONS') { res.status(204).end(); return; }

  const raw = (req.query && (req.query.url || req.query.u)) || '';
  let url = String(raw).trim();
  if (!/^https?:\/\//i.test(url)) url = 'https://' + url;
  if (!/^https?:\/\/[^\s.]+\.[^\s]+/i.test(url)) { res.status(400).json({ ok: false, error: '유효한 URL이 필요합니다.' }); return; }

  // 직접 추출이 실패하거나 본문이 빈약하면 Jina Reader로 한 번 더 시도한다.
  const viaJina = async (why) => {
    try {
      const j = await jinaReader(url);
      const text = j.text.slice(0, 48000);
      if (text.replace(/\s/g, '').length < 120) throw new Error('본문이 너무 짧아요');
      cacheOk(); res.status(200).json({ ok: true, title: j.title || url, siteName: '', text, url, chars: text.length, source: 'jina' });
      return true;
    } catch (e) {
      res.status(502).json({ ok: false, error: `${why} 그리고 리더 폴백도 실패했어요 (${e && e.message || e}). 페이지 텍스트를 직접 붙여넣어 주세요.`, url });
      return true;
    }
  };

  try {
    const r = await fetch(url, {
      redirect: 'follow',
      headers: {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'accept-language': 'ko,en;q=0.9',
      },
    });
    if (!r.ok) { await viaJina(`가져오기 실패 (HTTP ${r.status}).`); return; }
    const ctype = r.headers.get('content-type') || '';
    const html = await r.text();

    if (/application\/json/i.test(ctype)) {
      const text = html.slice(0, 48000);
      cacheOk(); res.status(200).json({ ok: true, title: url, siteName: '', text, url, chars: text.length });
      return;
    }

    const title = metaOf(html, 'og:title') || (html.match(/<title[^>]*>([\s\S]*?)<\/title>/i) ? decodeEntities(html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)[1]).trim() : '');
    const siteName = metaOf(html, 'og:site_name');
    const desc = metaOf(html, 'og:description') || metaOf(html, 'description');
    let text = extractReadable(html);
    if (desc && !text.includes(desc.slice(0, 40))) text = desc + '\n\n' + text;
    text = text.slice(0, 48000);

    // 본문이 빈약하면 대개 JS로 그리는 페이지다 → 리더로 재시도
    if (text.replace(/\s/g, '').length < 120) { await viaJina('본문을 충분히 추출하지 못했어요.'); return; }
    cacheOk(); res.status(200).json({ ok: true, title, siteName, text, url, chars: text.length });
  } catch (e) {
    await viaJina('가져오기 오류(' + (e && e.message || e) + ').');
  }
};
