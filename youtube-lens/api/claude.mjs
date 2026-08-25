// Claude 프록시 — 앱이 브라우저에 키를 두지 않고도 분석·콘텐츠 생성을 할 수 있게 한다.
//
// 같은 키를 브라우저와 서버 두 곳에 유지하다 보니, 키를 교체할 때마다 한쪽이 죽어
// "API 키가 올바르지 않아요"가 반복됐다. 키를 서버 한 곳에만 두고 앱은 이 엔드포인트로
// 요청한다. 앱 키(APP_KEY)로 인증하므로 아무나 쓸 수는 없다.
//
//   POST /api/claude  { model, max_tokens, system, messages }  → Anthropic 응답 그대로
//
// 본인 키를 쓰고 싶으면 앱 ⚙️ 설정에 넣으면 되고, 그때는 브라우저가 직접 호출한다.
import { authorized, cors } from './_notion.mjs';

export const config = { maxDuration: 60 };

const MAX_TOKENS_CAP = 16000;

async function readBody(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  const chunks = []; for await (const c of req) chunks.push(c);
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { return null; }
}

export default async function handler(req, res) {
  cors(res);
  if (req.method === 'OPTIONS') { res.status(204).end(); return; }
  if (req.method !== 'POST') { res.status(405).json({ error: { message: 'POST만 지원' } }); return; }
  if (!authorized(req)) { res.status(401).json({ error: { message: '인증 실패 — ⚙️ 설정의 수집함 앱 키를 확인하세요.' } }); return; }

  const key = (process.env.ANTHROPIC_API_KEY || '').trim();
  if (!key) { res.status(424).json({ error: { message: '서버에 ANTHROPIC_API_KEY가 없어요. Vercel 환경변수를 확인하세요.' } }); return; }
  if (/[^\x20-\x7E]/.test(key)) { res.status(424).json({ error: { message: 'ANTHROPIC_API_KEY 값이 올바르지 않아요(가려진 ●●●●를 복사하신 것 같아요).' } }); return; }

  const body = await readBody(req);
  if (!body || !Array.isArray(body.messages)) { res.status(400).json({ error: { message: 'messages가 필요합니다.' } }); return; }

  // 이 앱이 쓰는 형태만 통과시킨다 — 열린 프록시가 되지 않도록
  const payload = {
    model: String(body.model || 'claude-sonnet-5'),
    max_tokens: Math.min(Number(body.max_tokens) || 4000, MAX_TOKENS_CAP),
    messages: body.messages,
  };
  if (body.system) payload.system = String(body.system);

  try {
    const r = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const text = await r.text();
    res.status(r.status);
    res.setHeader('content-type', 'application/json; charset=utf-8');
    res.send(text);   // 오류 본문도 그대로 전달해 앱이 원인을 보여줄 수 있게 한다
  } catch (e) {
    res.status(502).json({ error: { message: 'Claude 호출 실패: ' + (e && e.message || e) } });
  }
}
