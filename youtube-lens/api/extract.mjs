// Vercel serverless function (ESM) — PDF에서 텍스트를 추출.
//   GET  /api/extract?url=<pdf 링크>       → 서버가 PDF를 받아 추출 (테스트/링크용)
//   POST /api/extract  { data: <base64>, name } → 업로드한 PDF 추출
// unpdf(서버리스용 pdf.js 번들)를 사용. 스캔 이미지 PDF는 텍스트가 거의 없을 수 있음.
import { extractText, getDocumentProxy } from 'unpdf';

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'content-type');
}
async function readRawBody(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  return Buffer.concat(chunks).toString('utf8');
}
async function extractFromBuffer(buf) {
  const pdf = await getDocumentProxy(new Uint8Array(buf));
  const out = await extractText(pdf, { mergePages: true });
  const text = String(out && out.text || '').replace(/[ \t]+/g, ' ').replace(/\s+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  return { text, pages: (out && out.totalPages) || 0 };
}

export default async function handler(req, res) {
  cors(res);
  if (req.method === 'OPTIONS') { res.status(204).end(); return; }
  try {
    let buf, srcName = '';
    if (req.method === 'GET') {
      const url = (req.query && (req.query.url || req.query.u)) || '';
      if (!/^https?:\/\//i.test(url)) { res.status(400).json({ ok: false, error: '유효한 PDF URL이 필요합니다.' }); return; }
      const r = await fetch(url, { headers: { 'user-agent': 'Mozilla/5.0' } });
      if (!r.ok) { res.status(502).json({ ok: false, error: `PDF 가져오기 실패 (HTTP ${r.status})` }); return; }
      buf = Buffer.from(await r.arrayBuffer());
      srcName = url.split('/').pop() || 'pdf';
      // raw=1: 텍스트 추출 대신 PDF 원본(base64)을 반환 — 스캔 PDF를 Claude 비전으로
      // 직접 분석하는 폴백용 (브라우저는 CORS로 외부 PDF를 못 받으므로 서버가 중개)
      if (req.query && req.query.raw) {
        if (buf.length > 3.5 * 1024 * 1024) { res.status(413).json({ ok: false, error: 'PDF가 너무 커요(3.5MB 초과). 파일로 직접 업로드해 주세요.' }); return; }
        res.setHeader('Cache-Control', 'public, max-age=3600');
        res.status(200).json({ ok: true, data: buf.toString('base64'), name: srcName });
        return;
      }
    } else if (req.method === 'POST') {
      let body = req.body;
      if (!body || typeof body !== 'object') { try { body = JSON.parse(await readRawBody(req)); } catch { body = {}; } }
      const b64 = (body && body.data) || '';
      srcName = (body && body.name) || 'pdf';
      if (!b64) { res.status(400).json({ ok: false, error: 'PDF 데이터가 필요합니다.' }); return; }
      buf = Buffer.from(String(b64), 'base64');
    } else { res.status(405).json({ ok: false, error: 'GET 또는 POST만 지원' }); return; }

    if (!buf || buf.length < 100) { res.status(400).json({ ok: false, error: 'PDF가 비어 있어요.' }); return; }
    const { text, pages } = await extractFromBuffer(buf);
    if (text.length < 20) { res.status(422).json({ ok: false, error: 'PDF에서 텍스트를 거의 추출하지 못했어요(스캔 이미지 PDF일 수 있어요). 이미지로 분석하거나 텍스트를 붙여넣어 주세요.', pages }); return; }
    res.setHeader('Cache-Control', 'public, max-age=3600');
    res.status(200).json({ ok: true, text: text.slice(0, 60000), pages, name: srcName });
  } catch (e) {
    res.status(500).json({ ok: false, error: 'PDF 처리 실패: ' + (e && e.message || e) });
  }
}
