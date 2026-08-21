// Notion REST 공용 헬퍼 (collect.mjs / inbox.mjs에서 사용)
// 필요 env: NOTION_TOKEN — Notion 내부 통합(integration) 토큰.
//   통합을 만들고( https://www.notion.so/my-integrations ) "유튜브 렌즈" 페이지에 연결하면
//   하위의 수집함/워치리스트 DB 접근 권한이 생깁니다.

export const INBOX_DB = (process.env.NOTION_INBOX_DB || '52e78a52a06e4bd39b34b32a909a78fd').replace(/-/g, '');
export const WATCH_DB = (process.env.NOTION_WATCH_DB || '354f80b3053348358410a5b724795ce8').replace(/-/g, '');

export function notionHeaders() {
  const token = (process.env.NOTION_TOKEN || '').trim();
  if (!token) throw new Error('NOTION_TOKEN이 설정되지 않았어요. Vercel 환경변수에 Notion 통합 토큰을 넣어주세요.');
  return {
    'authorization': 'Bearer ' + token,
    'notion-version': '2022-06-28',
    'content-type': 'application/json',
  };
}

export async function notion(path, method = 'GET', body) {
  const r = await fetch('https://api.notion.com/v1' + path, {
    method,
    headers: notionHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error('Notion ' + r.status + ': ' + (j.message || path));
  return j;
}

// ---- property 빌더 (Notion API 형식) ----
const chunk = (s, n = 1900) => {
  const out = []; s = String(s || '');
  for (let i = 0; i < s.length && out.length < 40; i += n) out.push({ text: { content: s.slice(i, i + n) } });
  return out;
};
export const P = {
  title: s => ({ title: chunk(String(s || '').slice(0, 1900)) }),
  text: s => ({ rich_text: chunk(s) }),
  url: s => ({ url: s ? String(s).slice(0, 1900) : null }),
  select: s => (s ? { select: { name: String(s) } } : { select: null }),
  number: n => ({ number: (typeof n === 'number' && isFinite(n)) ? n : null }),
  date: iso => ({ date: iso ? { start: iso } : null }),
};

// ---- property 리더 (Notion 페이지 → 평범한 값) ----
const flat = rt => (rt || []).map(x => (x.plain_text != null ? x.plain_text : (x.text && x.text.content) || '')).join('');
export function readProps(page) {
  const out = { id: page.id };
  const props = page.properties || {};
  for (const [k, v] of Object.entries(props)) {
    if (!v) continue;
    if (v.type === 'title') out[k] = flat(v.title);
    else if (v.type === 'rich_text') out[k] = flat(v.rich_text);
    else if (v.type === 'url') out[k] = v.url || '';
    else if (v.type === 'select') out[k] = (v.select && v.select.name) || '';
    else if (v.type === 'number') out[k] = v.number;
    else if (v.type === 'checkbox') out[k] = !!v.checkbox;
    else if (v.type === 'date') out[k] = (v.date && v.date.start) || '';
  }
  return out;
}

export async function queryDb(dbId, body = {}) {
  return notion('/databases/' + dbId + '/query', 'POST', { page_size: 100, ...body });
}

// ---- 요청 인증: APP_KEY(선택) 또는 Vercel CRON_SECRET ----
export function authorized(req) {
  const appKey = (process.env.APP_KEY || '').trim();
  const cronSecret = (process.env.CRON_SECRET || '').trim();
  const auth = String(req.headers['authorization'] || '');
  if (cronSecret && auth === 'Bearer ' + cronSecret) return true;
  if (!appKey) return true; // APP_KEY 미설정 = 공개 (개인용 소규모 앱 기본값)
  return String(req.headers['x-app-key'] || (req.query && req.query.appkey) || '') === appKey;
}

export function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'content-type, x-app-key');
}
