// Jina Reader 폴백 검증 — 응답 파싱과 차단 페이지 판별.
//
// 폴백의 위험은 "실패가 성공으로 위장되는 것"이다. Cloudflare 검증 페이지나
// Jina의 캡차 경고를 본문으로 넘기면 오류 없이 쓰레기가 분석까지 흘러간다.
// (api/transcript.js에서 실제로 겪은 사고와 같은 유형)
import { readFileSync } from 'node:fs';

import { createRequire } from 'node:module';
const src = readFileSync(new URL('../api/fetch-source.js', import.meta.url), 'utf8');
const { isAntibotPage, looksBlocked } = createRequire(import.meta.url)('../api/_blocked.js');

let fail = 0;
const t = (name, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`${ok ? '✅' : '❌'} ${name}`);
  if (!ok) { fail++; console.log(`   기대=${JSON.stringify(want)} 실제=${JSON.stringify(got)}`); }
};

// --- 차단 페이지 판별 ---
t('Cloudflare 챌린지', isAntibotPage(
  'Title: Just a moment...\n\n## Performing security verification\nRay ID: abc123'), true);
t('Cloudflare 차단 + Ray ID', isAntibotPage(
  'Title: Attention Required! | Cloudflare\nRay ID: 9f2b'), true);
t('Jina 캡차 경고', isAntibotPage(
  'Warning: Target URL returned a page requiring CAPTCHA\nTitle: Just a moment...'), true);
t('정상 기사', isAntibotPage(
  'Title: 1인 창업 수익화 사례\n\nMarkdown Content:\n창업 첫 해 매출은 3천만원이었다. 핵심은...'), false);
t('"warning:"만 있는 정상 본문', isAntibotPage(
  'Title: 보안 경고 대응법\n\nMarkdown Content:\n로그에 warning: 이 찍히면 먼저 확인할 것은...'), false);

// --- 회귀: Jina가 물어온 인스타 로그인 벽이 본문으로 통과하면 안 된다 ---
// 실제 프로덕션 응답(237자). isAntibotPage(클라우드플레어 전용)만으로는 못 잡아서
// looksBlocked(공용 지문)를 쓰도록 고쳤다.
t('인스타 로그인 벽 (Jina 실제 응답)', looksBlocked(
  "[](https://www.instagram.com/accounts/emailsignup/)[Log in](https://www.instagram.com/accounts/login/)\n\n" +
  "Post isn't available\n\nThe link may be broken, or the profile may have been removed.\n\nSign up for Instagram"), true);

// --- Jina 응답 파싱 (핸들러와 같은 규칙) ---
const parse = md => ({
  title: ((md.match(/^Title:\s*(.+)$/m) || [])[1] || '').trim(),
  text: (md.split(/^Markdown Content:\s*$/m)[1] || md).trim(),
});
const sample = `Title: 부업 첫 해 기록
URL Source: https://example.com/a
Markdown Content:
첫 달 매출은 0원이었다. 그다음에 바꾼 것은 세 가지다.`;
t('제목 추출', parse(sample).title, '부업 첫 해 기록');
t('본문만 남김(헤더 제거)', parse(sample).text.startsWith('첫 달 매출은 0원'), true);
t('URL Source 헤더가 본문에 안 섞임', parse(sample).text.includes('URL Source'), false);
t('헤더가 없으면 전체를 본문으로', parse('그냥 본문입니다').text, '그냥 본문입니다');

// --- 캐시 정책: 성공만 캐시 ---
t('기본이 no-store', /res\.setHeader\('Cache-Control', 'no-store'\)/.test(src), true);
t('200 응답 3곳에만 cacheOk', (src.match(/cacheOk\(\); res\.status\(200\)/g) || []).length, 3);

console.log(fail ? `\n${fail}개 실패` : '\nJina 폴백 검증 완료');
process.exit(fail ? 1 : 0);
