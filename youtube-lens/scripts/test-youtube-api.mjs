// 유튜브 Data API 경로 검증 — '전일 기준 조회수 상위' 수집과 RSS 차단 우회.
//
// RSS는 데이터센터 IP가 막히고(실제로 잘 되던 채널이 갑자기 끊겼다), '인기 영상'
// 목록은 아예 제공하지 않는다. 이 경로가 조용히 잘못 호출되면 엉뚱한 걸 수집한다.
import { ytSearchItems, ytTopVideos, ytChannelVideos } from '../api/collect.mjs';

let fail = 0;
const t = (name, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`${ok ? '✅' : '❌'} ${name}`);
  if (!ok) { fail++; console.log(`   기대=${JSON.stringify(want)}\n   실제=${JSON.stringify(got)}`); }
};

// --- 응답 → 항목 변환 (RSS 파서와 같은 모양이어야 파이프라인이 그대로 돈다) ---
const sample = { items: [
  { id: { videoId: 'abc12345678' }, snippet: {
      title: '연 매출 10억 만든 &quot;오퍼&quot; 설계법', publishedAt: '2026-08-27T09:00:00Z',
      description: '가격 책정과 보장 구조를 실제 수치로 설명합니다.', channelTitle: '비즈니스 렌즈' } },
  { id: { kind: 'youtube#channel' }, snippet: { title: '채널은 걸러야 함' } },   // videoId 없음
]};
const items = ytSearchItems(sample);
t('영상만 통과 (채널 결과 제외)', items.length, 1);
t('HTML 엔티티 해제', items[0].title, '연 매출 10억 만든 "오퍼" 설계법');
t('watch URL 구성', items[0].link, 'https://www.youtube.com/watch?v=abc12345678');
t('썸네일 구성', items[0].thumb, 'https://i.ytimg.com/vi/abc12345678/hqdefault.jpg');
t('게시 시각 파싱', items[0].ts, Date.parse('2026-08-27T09:00:00Z'));
t('채널명이 author로', items[0].author, '비즈니스 렌즈');

// --- 요청 파라미터 (여기가 틀리면 엉뚱한 영상을 모은다) ---
process.env.YOUTUBE_API_KEY = 'test-key';
let lastUrl = '';
const realFetch = globalThis.fetch;
globalThis.fetch = async (u) => { lastUrl = String(u); return { ok: true, json: async () => sample }; };
const q = () => Object.fromEntries(new URL(lastUrl).searchParams);

const since = Date.parse('2026-08-27T00:00:00Z');
await ytTopVideos('1인 창업 수익화', since, 10);
let p = q();
t('조회수 순 정렬', p.order, 'viewCount');
t('전일 기준(publishedAfter)', p.publishedAfter, '2026-08-27T00:00:00.000Z');
t('상위 10개', p.maxResults, '10');
t('키워드 전달', p.q, '1인 창업 수익화');
t('영상만', p.type, 'video');
t('키워드가 있으면 지역 고정 안 함', p.regionCode, undefined);

await ytTopVideos('', since, 10);
p = q();
t('키워드가 없으면 국내 인기', p.regionCode, 'KR');
t('키워드 없으면 q 미전송', p.q, undefined);

await ytChannelVideos('UCUyDOdBWhC1MCxEjC46d-zw', 10);
p = q();
t('채널 폴백은 최신순', p.order, 'date');
t('채널 ID 전달', p.channelId, 'UCUyDOdBWhC1MCxEjC46d-zw');

// maxResults는 API 상한(50)을 넘으면 안 된다
await ytTopVideos('x', since, 999); t('maxResults 상한 50', q().maxResults, '50');
await ytTopVideos('x', since, 0);   t('maxResults 하한 1', q().maxResults, '1');

// 키가 없으면 조용히 엉뚱하게 동작하지 말고 분명히 실패해야 한다
delete process.env.YOUTUBE_API_KEY;
let threw = '';
try { await ytTopVideos('x', since, 10); } catch (e) { threw = e.message; }
t('키 없으면 명확히 실패', /YOUTUBE_API_KEY/.test(threw), true);
globalThis.fetch = realFetch;

console.log(fail ? `\n${fail}개 실패` : '\n유튜브 API 경로 검증 완료');
process.exit(fail ? 1 : 0);
