// 플랫폼이 본문 대신 돌려주는 로그인·차단·검증 페이지 판별 (공용).
//
// 이 판별이 없으면 실패가 "성공"으로 위장된다. 실제로 두 번 당했다.
//  1) /api/transcript — 인스타 릴스에서 "Log in / Post isn't available"이
//     정상 자막으로 통과해 Claude 분석까지 흘러갔다.
//  2) /api/fetch-source — Jina Reader 폴백을 넣으면서 (1)의 지문을 공유하지 않아
//     같은 인스타 로그인 벽이 237자짜리 본문으로 또 통과했다.
//
// 그래서 지문을 한 곳에 모은다. 새 엔드포인트를 추가할 때도 여기만 쓰면 된다.

// 소셜·일반 웹의 로그인/삭제/비공개/봇검사 안내
const BLOCKED_PATTERNS = [
  /post isn'?t available/i, /page isn'?t available/i, /content isn'?t available/i,
  /log ?in to (instagram|tiktok|facebook|x)\b/i, /sign up for instagram/i,
  /this account is private/i, /비공개 계정/,
  /(페이지|게시물).{0,6}(사용할 수 없|찾을 수 없)/,
  /are you a robot/i, /verify (that )?you'?re human/i, /enable javascript/i,
  /login[ _-]?required/i, /rate ?limit/i,
];

// Cloudflare / Jina Reader 챌린지 (Agent Reach의 _is_antibot_page 이식)
function isAntibotPage(text) {
  const s = String(text || '').slice(0, 4096).toLowerCase();
  const jinaCaptcha = s.includes('warning:') && s.includes('requiring captcha');
  const challenge = ['title: just a moment...', '## performing security verification',
    'title: attention required! | cloudflare'].some(m => s.includes(m));
  const cfBlock = s.includes('title: attention required! | cloudflare') &&
    (s.includes('ray id') || s.includes('/cdn-cgi/challenge-platform/'));
  // 원본은 Jina 경고 문구가 함께 있을 때만 챌린지로 본다. 그러면 경고 없이 오는
  // 순수 Cloudflare 대기 페이지가 본문으로 통과한다. 이 두 문구는 실제 기사에
  // 나올 일이 없으므로 단독으로도 차단으로 취급한다.
  const cfChallenge = s.includes('title: just a moment...') ||
    s.includes('## performing security verification');
  return (jinaCaptcha && challenge) || cfBlock || cfChallenge;
}

// 짧은 응답에만 지문을 적용한다 — 긴 본문 안에 우연히 섞인 문구까지 막지 않도록.
// (예: "비공개 계정으로 바꾸면 도달이 어떻게 되나" 같은 정상 기사)
const SHORT_MAX = 1200;

function looksBlocked(text) {
  const s = String(text || '');
  if (isAntibotPage(s)) return true;              // 챌린지는 길이와 무관하게 차단
  if (s.length > SHORT_MAX) return false;
  return BLOCKED_PATTERNS.some(re => re.test(s));
}

const BLOCKED_MSG = '플랫폼이 본문 대신 로그인·차단 페이지를 돌려줬어요';

module.exports = { looksBlocked, isAntibotPage, BLOCKED_PATTERNS, BLOCKED_MSG, SHORT_MAX };
