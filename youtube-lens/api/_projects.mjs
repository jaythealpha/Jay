// 프로젝트 DB 공용 로직 — projects.mjs(앱 동기화)와 collect.mjs(자동 분석)가 함께 쓴다.
import { notion, queryDb, P, TEXT_MAX } from './_notion.mjs';

export const PROJ_DB = (process.env.NOTION_PROJECT_DB || 'a1e1b93e71274e4d957e6ba260d6cabb').replace(/-/g, '');
export const SRC_LABEL = { youtube: '유튜브', web: '웹', text: '텍스트', file: '파일', image: '이미지' };

export async function findByPid(pid) {
  const r = await queryDb(PROJ_DB, { filter: { property: '프로젝트ID', rich_text: { equals: pid } }, page_size: 1 });
  return r.results[0] || null;
}

// 저장 한도를 넘으면 잘린 JSON이 저장돼 다음 읽기에서 콘텐츠가 통째로 유실된다.
// 오래된 것부터 덜어내 항상 온전한 JSON이 되게 한다.
export function fitContents(list) {
  let items = Array.isArray(list) ? list.slice() : [];
  let json = JSON.stringify(items), dropped = 0;
  while (json.length > TEXT_MAX && items.length > 1) { items.shift(); dropped++; json = JSON.stringify(items); }
  if (json.length > TEXT_MAX) { items = []; json = '[]'; dropped = (list || []).length; }
  return { json, dropped };
}

export async function upsertProject(p) {
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
  return { created: !page, dropped: fit.dropped };
}
