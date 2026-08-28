// 차단·로그인 페이지가 정상 자막으로 통과하지 않는지 검사.
//
// 실제로 인스타 릴스 링크에서 Supadata의 web/scrape 폴백이
//   "Log in  Post isn't available  ... Sign up for Instagram"
// 을 돌려줬는데, 길이(110자)가 최소 기준 20자를 넘어 ok:true로 나갔다.
// 오류도 없이 이 쓰레기 텍스트가 Claude 분석까지 흘러갔다.
import { createRequire } from 'node:module';
const { looksBlocked } = createRequire(import.meta.url)('../api/_blocked.js');

let fail = 0;
const t = (name, got, want) => {
  const ok = got === want;
  console.log(`${ok ? '✅' : '❌'} ${name}`);
  if (!ok) fail++;
};

// 실제로 프로덕션에서 통과해 버렸던 응답
t('인스타 로그인 차단 페이지 (실제 사례)', looksBlocked(
  "Log in Post isn't available The link may be broken, or the profile may have been removed. Sign up for Instagram"), true);
t('페이지 없음(영문)', looksBlocked("This page isn't available."), true);
t('비공개 계정(영문)', looksBlocked('This account is private. Follow to see their photos.'), true);
t('비공개 계정(국문)', looksBlocked('비공개 계정입니다'), true);
t('게시물 사용 불가(국문)', looksBlocked('이 게시물은 사용할 수 없습니다'), true);
t('봇 검사', looksBlocked('Are you a robot? Please verify.'), true);
t('자바스크립트 필요', looksBlocked('Please enable JavaScript to continue.'), true);

// 정상 본문은 통과해야 한다
t('정상 릴스 전사', looksBlocked(
  '오늘은 부업으로 인스타 계정을 키우는 방법을 이야기해볼게요. 처음에는 팔로워보다 저장률을 봐야 합니다. ' +
  '제가 3개월간 테스트한 결과 저장률이 5%를 넘으면 도달이 급격히 늘었습니다.'), false);
t('길이가 긴 본문에 우연히 섞인 문구는 통과', looksBlocked(
  '이 영상에서는 계정이 비공개 계정으로 전환되면 도달이 어떻게 변하는지 다룹니다. ' + 'x'.repeat(1300)), false);

console.log(fail ? `\n${fail}개 실패` : '\n차단 페이지 판별 검증 완료');
process.exit(fail ? 1 : 0);
