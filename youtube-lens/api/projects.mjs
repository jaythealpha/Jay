// 프로젝트(분석 결과 + 생성 콘텐츠) 클라우드 동기화 — 앱 ↔ Notion.
// 앱의 작업 저장소는 브라우저(localStorage)이고, 이 DB는 기기 간 백본이다.
// 충돌은 수정일 기준 last-write-wins (개인용 단일 사용자 가정).
//
//   GET  /api/projects                → 목록(가벼움: id·제목·수정일·콘텐츠수)
//   GET  /api/projects?id=<pid>       → 그 프로젝트 전체(분석·콘텐츠 JSON 포함)
//   POST /api/projects {action:'upsert', project}  → 생성 또는 갱신(프로젝트ID 기준)
//   POST /api/projects {action:'delete', id}       → 보관 처리
import { notion, queryDb, readProps, P, authorized, isLocked, cors, TEXT_MAX } from './_notion.mjs';

export const config = { maxDuration: 60 };

const PROJ_DB = (process.env.NOTION_PROJECT_DB || 'a1e1b93e71274e4d957e6ba260d6cabb').replace(/-/g, '');
const SRC_LABEL = { youtube: '유튜브', web: '웹', text: '텍스트', file: '파일', image: '이미지' };

async function readBody(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  const chunks = []; for await (const c of req) chunks.push(c);
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { return {}; }
}
const parse = s => { try { return JSON.parse(s || ''); } catch { return null; } };

// 저장 한도를 넘으면 잘린 JSON이 저장돼 다음 읽기에서 전부 유실된다.
// 오래된 콘텐츠부터 덜어내 항상 온전한 JSON이 되게 한다.
function fitContents(list) {
  let items = Array.isArray(list) ? list.slice() : [];
  let json = JSON.stringify(items), dropped = 0;
  while (json.length > TEXT_MAX && items.length > 1) { items.shift(); dropped++; json = JSON.stringify(items); }
  if (json.length > TEXT_MAX) { items = []; json = '[]'; dropped = (list || []).length; }
  return { json, dropped };
}

async function findByPid(pid) {
  const r = await queryDb(PROJ_DB, { filter: { property: '프로젝트ID', rich_text: { equals: pid } }, page_size: 1 });
  return r.results[0] || null;
}

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
        const p = b.project;
        const contents = Array.isArray(p.contents) ? p.contents : [];
        const fit = fitContents(contents);
        const properties = {
          '제목': P.title(p.title || '(제목 없음)'),
          '프로젝트ID': P.text(String(p.id)),
          '출처': P.select(SRC_LABEL[p.sourceType] || '텍스트'),
          'URL': P.url(p.sourceUrl || ''),
          '채널': P.text(p.channel || ''),
          '수정일': P.date(p.updatedAt || p.at || new Date().toISOString()),
          '콘텐츠수': P.number(contents.length),
          '분석': P.text(JSON.stringify(p.data || {}).slice(0, TEXT_MAX)),
          '콘텐츠': P.text(fit.json),
          '소스발췌': P.text(String(p.sourceExcerpt || '').slice(0, 8000)),
        };
        const page = await findByPid(String(p.id));
        if (page) await notion('/pages/' + page.id, 'PATCH', { properties });
        else await notion('/pages', 'POST', { parent: { database_id: PROJ_DB }, properties });
        res.status(200).json({ ok: true, created: !page, dropped: fit.dropped }); return;
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
