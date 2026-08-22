// 자동 초안 — 분석은 끝났지만 콘텐츠가 아직 없는 프로젝트에 기본 포맷 초안을 붙인다.
// 수집(collect)과 같은 함수에 넣으면 60초 제한을 넘기므로 별도 함수 + 별도 크론으로 분리했다.
//
//   GET /api/generate            → 초안이 없는 최신 프로젝트 1건 처리 (크론/수동)
//   GET /api/generate?dry=1      → 대상만 보고 생성하지 않음
//   GET /api/generate?id=<pid>   → 특정 프로젝트 지정
//
// Notion 워치리스트에 '✍️ 자동 초안' 설정 행을 만들고 체크를 해제하면 끌 수 있다(기본 켜짐).
// 그 행의 `값`에 포맷 id를 쉼표로 적으면 그것을 쓴다(예: reels,cards).
import { WATCH_DB, queryDb, readProps, authorized, cors } from './_notion.mjs';
import { PROJ_DB, upsertProject } from './_projects.mjs';
import { SERVER_FORMATS, DEFAULT_DRAFT_FORMATS, CONTENT_SYSTEM, draftPrompt } from './_formats.mjs';

export const config = { maxDuration: 60 };

const FN_BUDGET_MS = 52000;
const DRAFT_NEEDS_MS = 22000;   // 포맷 1개 생성에 필요한 여유

function parseJson(text) {
  const t = String(text).replace(/```json/gi, '').replace(/```/g, '').trim();
  const s = t.indexOf('{'), e = t.lastIndexOf('}');
  if (s === -1 || e === -1) throw new Error('JSON을 찾지 못했어요');
  return JSON.parse(t.slice(s, e + 1));
}

async function claude(key, model, prompt) {
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
    body: JSON.stringify({ model, max_tokens: 6000, system: CONTENT_SYSTEM, messages: [{ role: 'user', content: prompt }] }),
  });
  if (!r.ok) {
    let m = 'Claude HTTP ' + r.status;
    try { const j = await r.json(); if (j.error && j.error.message) m += ': ' + j.error.message; } catch {}
    throw new Error(m);
  }
  const j = await r.json();
  if (j.stop_reason === 'max_tokens') throw new Error('응답이 잘렸어요');
  return parseJson((j.content || []).filter(c => c.type === 'text').map(c => c.text || '').join('\n'));
}

const flat = rt => (rt || []).map(x => (x.plain_text != null ? x.plain_text : (x.text && x.text.content) || '')).join('');

export default async function handler(req, res) {
  cors(res);
  if (req.method === 'OPTIONS') { res.status(204).end(); return; }
  if (!authorized(req)) { res.status(401).json({ ok: false, error: '인증 실패 (설정의 앱 키를 확인하세요)' }); return; }

  const T0 = Date.now();
  const timeLeft = () => FN_BUDGET_MS - (Date.now() - T0);
  const dry = !!(req.query && req.query.dry);
  const report = { ok: true, target: null, drafted: [], skipped: [], errors: [] };
  try {
    const key = (process.env.ANTHROPIC_API_KEY || '').trim();
    if (!key) { res.status(424).json({ ok: false, error: 'ANTHROPIC_API_KEY가 없어 초안을 만들 수 없어요.', needSetup: true }); return; }

    // 설정 행: 끄기 + 포맷 지정
    const wl = (await queryDb(WATCH_DB)).results.map(readProps);
    const cfgRow = wl.find(w => w['유형'] === '설정' && /자동 초안/.test(w['이름'] || ''));
    if (cfgRow && !cfgRow['활성']) { res.status(200).json({ ...report, paused: true, note: '자동 초안이 꺼져 있어요.' }); return; }
    let formats = DEFAULT_DRAFT_FORMATS;
    if (cfgRow && cfgRow['값']) {
      const picked = String(cfgRow['값']).split(/[,\s]+/).map(s => s.trim()).filter(f => SERVER_FORMATS[f]);
      if (picked.length) formats = picked;
    }
    report.formats = formats;

    // 대상: 콘텐츠가 없는 프로젝트 중 가장 최근 것 (자동 분석 결과가 여기 해당)
    const wantId = String((req.query && req.query.id) || '').trim();
    const rows = (await queryDb(PROJ_DB, { sorts: [{ property: '수정일', direction: 'descending' }], page_size: 100 })).results;
    const cand = rows.map(p => ({ page: p, props: readProps(p) }))
      .filter(x => x['props'] && x.props['프로젝트ID'])
      .filter(x => (wantId ? x.props['프로젝트ID'] === wantId : !(x.props['콘텐츠수'] > 0)));
    if (!cand.length) { res.status(200).json({ ...report, note: '초안이 필요한 프로젝트가 없어요.' }); return; }

    const t = cand[0];
    const pid = t.props['프로젝트ID'];
    report.target = { id: pid, title: t.props['제목'] };
    // 목록 조회는 rich_text를 잘라 오지 않으므로 그대로 쓸 수 있다
    let data = {}; try { data = JSON.parse(flat(t.page.properties['분석'] && t.page.properties['분석'].rich_text) || '{}'); } catch {}
    const excerpt = flat(t.page.properties['소스발췌'] && t.page.properties['소스발췌'].rich_text) || '';
    if (!data || !data.summary) { res.status(200).json({ ...report, note: '분석 내용이 비어 있어 건너뜁니다.' }); return; }

    const pieces = [];
    for (const fid of formats) {
      const fmt = SERVER_FORMATS[fid];
      if (!fmt) continue;
      if (timeLeft() < DRAFT_NEEDS_MS) { report.skipped.push(fid); continue; }  // 다음 회차에
      try {
        const out = await claude(key, process.env.CONTENT_MODEL || 'claude-sonnet-5', draftPrompt(data, fmt, excerpt));
        for (const p of (Array.isArray(out.pieces) ? out.pieces : [])) {
          pieces.push({ ...p, format: fmt.label, formatId: fid, auto: true, savedAt: new Date().toISOString() });
        }
        report.drafted.push(fid);
      } catch (e) { report.errors.push(fid + ': ' + String(e.message || e)); }
    }

    if (pieces.length && !dry) {
      const prev = (() => { try { return JSON.parse(flat(t.page.properties['콘텐츠'] && t.page.properties['콘텐츠'].rich_text) || '[]'); } catch { return []; } })();
      await upsertProject({
        id: pid, at: t.props['수정일'], updatedAt: new Date().toISOString(),
        sourceType: t.props['출처'] === '유튜브' ? 'youtube' : 'web',
        sourceUrl: t.props['URL'] || '', title: t.props['제목'], channel: t.props['채널'] || '',
        data, sourceExcerpt: excerpt,
        contents: (Array.isArray(prev) ? prev : []).concat(pieces),
      });
    }
    report.pieces = pieces.length;
    res.status(200).json(report);
  } catch (e) {
    res.status(500).json({ ...report, ok: false, error: String(e && e.message || e) });
  }
}
