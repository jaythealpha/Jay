// 프로젝트(분석 결과 + 생성 콘텐츠) 클라우드 동기화 — 앱 ↔ Notion.
// 앱의 작업 저장소는 브라우저(localStorage)이고, 이 DB는 기기 간 백본이다.
// 충돌은 수정일 기준 last-write-wins (개인용 단일 사용자 가정).
//
//   GET  /api/projects                → 목록(가벼움: id·제목·수정일·콘텐츠수)
//   GET  /api/projects?id=<pid>       → 그 프로젝트 전체(분석·콘텐츠 JSON 포함)
//   POST /api/projects {action:'upsert', project}  → 생성 또는 갱신(프로젝트ID 기준)
//   POST /api/projects {action:'delete', id}       → 보관 처리
import { notion, queryDb, readProps, authorized, isLocked, cors } from './_notion.mjs';
import { PROJ_DB, findByPid, upsertProject } from './_projects.mjs';

export const config = { maxDuration: 60 };

async function readBody(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  const chunks = []; for await (const c of req) chunks.push(c);
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { return {}; }
}
const parse = s => { try { return JSON.parse(s || ''); } catch { return null; } };

export default async function handler(req, res) {
  cors(res);
  if (req.method === 'OPTIONS') { res.status(204).end(); return; }
  if (!authorized(req)) { res.status(401).json({ ok: false, error: '인증 실패 (설정의 앱 키를 확인하세요)' }); return; }
  try {
    if (req.method === 'GET') {
      const wantId = String((req.query && req.query.id) || '').trim();
      const rows = (await queryDb(PROJ_DB, {
        sorts: [{ property: '수정일', direction: 'descending' }],
        page_size: 100,
      })).results.map(readProps);

      if (wantId) {
        const r = rows.find(x => x['프로젝트ID'] === wantId);
        if (!r) { res.status(404).json({ ok: false, error: '프로젝트를 찾지 못했어요' }); return; }
        res.status(200).json({ ok: true, project: {
          id: r['프로젝트ID'], title: r['제목'], channel: r['채널'], sourceUrl: r['URL'] || '',
          updatedAt: r['수정일'] || '', data: parse(r['분석']), contents: parse(r['콘텐츠']) || [],
          sourceExcerpt: r['소스발췌'] || '',
        } });
        return;
      }
      // 목록은 큰 JSON을 빼고 반환 — 앱이 수정일만 비교해 필요한 것만 내려받는다
      res.status(200).json({ ok: true, locked: isLocked(), projects: rows.map(r => ({
        id: r['프로젝트ID'], title: r['제목'], channel: r['채널'], sourceUrl: r['URL'] || '',
        updatedAt: r['수정일'] || '', contentCount: r['콘텐츠수'] || 0,
      })).filter(p => p.id) });
      return;
    }

    if (req.method === 'POST') {
      const b = await readBody(req);
      if (b.action === 'delete' && b.id) {
        const page = await findByPid(String(b.id));
        if (page) await notion('/pages/' + page.id, 'PATCH', { archived: true });
        res.status(200).json({ ok: true }); return;
      }
      if (b.action === 'upsert' && b.project && b.project.id) {
        const out = await upsertProject(b.project);
        res.status(200).json({ ok: true, ...out }); return;
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
