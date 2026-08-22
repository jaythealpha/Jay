// Notion REST 공용 헬퍼 (collect.mjs / inbox.mjs에서 사용)
// 필요 env: NOTION_TOKEN — Notion 내부 통합(integration) 토큰.
//   통합을 만들고( https://www.notion.so/my-integrations ) "유튜브 렌즈" 페이지에 연결하면
//   하위의 수집함/워치리스트 DB 접근 권한이 생깁니다.

export const INBOX_DB = (process.env.NOTION_INBOX_DB || '52e78a52a06e4bd39b34b32a909a78fd').replace(/-/g, '');
export const WATCH_DB = (process.env.NOTION_WATCH_DB || '354f80b3053348358410a5b724795ce8').replace(/-/g, '');

export function notionHeaders() {
  const token = (process.env.NOTION_TOKEN || '').trim();
  if (!token) throw new Error('NOTION_TOKEN이 설정되지 않았어요. Vercel 환경변수에 Notion 통합 토큰을 넣어주세요.');
  // 마스킹된 화면 값(●●●●)을 복사해 넣은 경우를 원인 불명 오류 대신 명확히 알려준다
  if (/[^\x20-\x7E]/.test(token)) throw new Error('NOTION_TOKEN 값이 올바르지 않아요. 화면에 가려져 보이던 ●●●● 를 복사하신 것 같아요 — 실제 토큰으로 다시 저장한 뒤 재배포해 주세요.');
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
// Notion rich_text는 요소당 2000자, 배열 100개가 상한 → 1900자씩 최대 100조각(약 190K)
export const TEXT_MAX = 1900 * 100;
const chunk = (s, n = 1900) => {
  const out = []; s = String(s || '');
  for (let i = 0; i < s.length && out.length < 100; i += n) out.push({ text: { content: s.slice(i, i + n) } });
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

// 100건 상한을 넘는 DB에서 뒷부분이 조용히 빠지지 않도록 커서를 따라간다.
// (중복 방지용 URL 셋이 최근 100건만 보던 탓에 같은 항목이 다시 적재될 수 있었다)
export async function queryDb(dbId, body = {}, maxPages = 5) {
  let out = null, cursor;
  for (let i = 0; i < maxPages; i++) {
    const page = await notion('/databases/' + dbId + '/query', 'POST',
      { page_size: 100, ...body, ...(cursor ? { start_cursor: cursor } : {}) });
    if (!out) out = page; else out.results = out.results.concat(page.results || []);
    if (!page.has_more || !page.next_cursor) { out.has_more = false; break; }
    cursor = page.next_cursor;
  }
  return out || { results: [] };
}

// ---- 요청 인증 ----
// APP_KEY를 설정하면 앱(x-app-key 헤더)만 호출할 수 있다. 설정하지 않으면 누구나
// 수집함을 읽고 수집을 실행(=크레딧 소모)할 수 있으므로, locked=false를 응답에 실어
// 앱이 경고를 띄우게 한다.
export function isLocked() { return !!(process.env.APP_KEY || '').trim(); }

// Vercel 예약 실행(크론) 판별.
// user-agent는 누구나 위조할 수 있으므로 신뢰하지 않는다. 예전에 UA 폴백을 두었더니
// `user-agent: vercel-cron/1.0` 한 줄로 APP_KEY 잠금이 통째로 우회됐다.
// CRON_SECRET을 설정하면 Vercel이 Authorization: Bearer <값>을 붙여 보낸다.
export function isCron(req) {
  const cronSecret = (process.env.CRON_SECRET || '').trim();
  if (!cronSecret) return false;
  return String(req.headers['authorization'] || '') === 'Bearer ' + cronSecret;
}
// 잠금은 걸었는데 CRON_SECRET이 없으면 예약 수집이 인증에 막힌다 → 앱이 경고하도록 노출
export function cronReady() { return !!(process.env.CRON_SECRET || '').trim(); }

export function authorized(req) {
  if (isCron(req)) return true;
  const appKey = (process.env.APP_KEY || '').trim();
  if (!appKey) return true; // 미설정 = 공개. 앱이 locked:false 경고를 표시한다
  return String(req.headers['x-app-key'] || (req.query && req.query.appkey) || '') === appKey;
}

export function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'content-type, x-app-key');
}
