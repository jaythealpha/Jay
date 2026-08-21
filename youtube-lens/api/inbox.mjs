// 수집함/워치리스트 프록시 — 앱(브라우저) ↔ Notion 사이를 중개.
// 브라우저에서 Notion API를 직접 못 부르므로(CORS/토큰 보안) 서버가 대신 호출.
//
//   GET  /api/inbox                     → 수집함 목록 (기본: 제외 제외, 최신순 40개)
//   GET  /api/inbox?watchlist=1         → 워치리스트 목록
//   POST /api/inbox {action:'status', id, status}            → 항목 상태 변경
//   POST /api/inbox {action:'watch-add', name, type, value}  → 워치 추가
//   POST /api/inbox {action:'watch-remove', id}              → 워치 삭제(보관)
//
// env: NOTION_TOKEN(필수), APP_KEY(선택 — 설정 시 x-app-key 헤더 필요)
import { INBOX_DB, WATCH_DB, notion, queryDb, readProps, P, authorized, cors } from './_notion.mjs';

export const config = { maxDuration: 30 };

async function readBody(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  const chunks = []; for await (const c of req) chunks.push(c);
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { return {}; }
}

export default async function handler(req, res) {
  cors(res);
  if (req.method === 'OPTIONS') { res.status(204).end(); return; }
  if (!authorized(req)) { res.status(401).json({ ok: false, error: '인증 실패 (설정의 앱 키를 확인하세요)' }); return; }
  try {
    if (req.method === 'GET') {
      if (req.query && req.query.watchlist) {
        const rows = (await queryDb(WATCH_DB)).results.map(readProps);
        res.status(200).json({ ok: true, watchlist: rows.map(w => ({ id: w.id, name: w['이름'], type: w['유형'], value: w['값'], active: !!w['활성'] })) });
        return;
      }
      const showAll = !!(req.query && req.query.all);
      const body = {
        sorts: [{ timestamp: 'created_time', direction: 'descending' }],
        page_size: Math.min(60, +(req.query && req.query.limit) || 40),
      };
      if (!showAll) body.filter = { property: '상태', select: { does_not_equal: '제외' } };
      const rows = (await queryDb(INBOX_DB, body)).results.map(readProps);
      res.status(200).json({
        ok: true,
        items: rows.map(r => ({
          id: r.id, title: r['제목'], url: r['URL'], source: r['출처'], channel: r['채널/매체'],
          score: r['점수'], summary: r['요약'], status: r['상태'], date: r['수집일'],
          excerpt: String(r['본문'] || '').slice(0, 6000),
        })),
      });
      return;
    }
    if (req.method === 'POST') {
      const b = await readBody(req);
      if (b.action === 'status' && b.id && b.status) {
        await notion('/pages/' + b.id, 'PATCH', { properties: { '상태': P.select(b.status) } });
        res.status(200).json({ ok: true }); return;
      }
      if (b.action === 'watch-add' && b.type && b.value) {
        await notion('/pages', 'POST', {
          parent: { database_id: WATCH_DB },
          properties: {
            '이름': P.title(b.name || b.value), '유형': P.select(b.type),
            '값': P.text(b.value), '활성': { checkbox: true },
          },
        });
        res.status(200).json({ ok: true }); return;
      }
      if (b.action === 'watch-remove' && b.id) {
        await notion('/pages/' + b.id, 'PATCH', { archived: true });
        res.status(200).json({ ok: true }); return;
      }
      if (b.action === 'watch-toggle' && b.id) {
        await notion('/pages/' + b.id, 'PATCH', { properties: { '활성': { checkbox: !!b.active } } });
        res.status(200).json({ ok: true }); return;
      }
      res.status(400).json({ ok: false, error: '알 수 없는 action' }); return;
    }
    res.status(405).json({ ok: false, error: 'GET 또는 POST만 지원' });
  } catch (e) {
    const msg = String(e && e.message || e);
    const setup = /NOTION_TOKEN|Notion 40[134]/.test(msg);
    res.status(setup ? 424 : 500).json({ ok: false, error: msg, needSetup: setup });
  }
}
