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

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'content-type');
  res.setHeader('Cache-Control', 'public, max-age=3600');
  if (req.method === 'OPTIONS') { res.status(204).end(); return; }

  const raw = (req.query && (req.query.url || req.query.u)) || '';
  let url = String(raw).trim();
  if (!/^https?:\/\//i.test(url)) url = 'https://' + url;
  if (!/^https?:\/\/[^\s.]+\.[^\s]+/i.test(url)) { res.status(400).json({ ok: false, error: '유효한 URL이 필요합니다.' }); return; }

  try {
    const r = await fetch(url, {
      redirect: 'follow',
      headers: {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'accept-language': 'ko,en;q=0.9',
      },
    });
    if (!r.ok) { res.status(502).json({ ok: false, error: `가져오기 실패 (HTTP ${r.status})` }); return; }
    const ctype = r.headers.get('content-type') || '';
    const html = await r.text();

    if (/application\/json/i.test(ctype)) {
      const text = html.slice(0, 48000);
      res.status(200).json({ ok: true, title: url, siteName: '', text, url, chars: text.length });
      return;
    }

    const title = metaOf(html, 'og:title') || (html.match(/<title[^>]*>([\s\S]*?)<\/title>/i) ? decodeEntities(html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)[1]).trim() : '');
    const siteName = metaOf(html, 'og:site_name');
    const desc = metaOf(html, 'og:description') || metaOf(html, 'description');
    let text = extractReadable(html);
    if (desc && !text.includes(desc.slice(0, 40))) text = desc + '\n\n' + text;
    text = text.slice(0, 48000);

    if (text.replace(/\s/g, '').length < 120) {
      res.status(422).json({ ok: false, error: '본문을 충분히 추출하지 못했어요. 페이지 텍스트를 직접 붙여넣어 주세요.', title, url });
      return;
    }
    res.status(200).json({ ok: true, title, siteName, text, url, chars: text.length });
  } catch (e) {
    res.status(502).json({ ok: false, error: '가져오기 오류: ' + (e && e.message || e) });
  }
};
