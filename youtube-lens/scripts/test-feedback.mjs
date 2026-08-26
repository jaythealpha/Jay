// 필터 학습(피드백 루프) 검증 — 사람의 보관/제외 판정이 실제로 채점 프롬프트에
// 실려 나가는지 확인한다. 이 연결이 끊기면 사용자가 제외를 아무리 눌러도
// 필터는 아무것도 배우지 못하는데, 화면상으로는 티가 나지 않는다.
import { buildFeedback, scoreItem } from '../api/collect.mjs';

let fail = 0;
const check = (name, cond, extra) => {
  console.log((cond ? '✅ ' : '❌ ') + name + (cond || !extra ? '' : '\n   ' + extra));
  if (!cond) fail++;
};

// 1) 이력이 없으면 프롬프트를 늘리지 않는다 (첫 실행에서 헛돈 쓰지 않도록)
check('판정 이력이 없으면 빈 문자열', buildFeedback([], []) === '');

// 2) 제외/보관이 각각 올바른 방향 지시와 함께 들어간다
const fb = buildFeedback(['보관한 영상 A'], ['제외한 영상 B']);
check('제외 항목이 포함됨', fb.includes('제외한 영상 B'), fb);
check('보관 항목이 포함됨', fb.includes('보관한 영상 A'), fb);
check('제외는 "낮게" 지시', /제외[\s\S]*?낮게/.test(fb), fb);
check('보관은 "높게" 지시', /보관[\s\S]*?높게/.test(fb), fb);
check('이력이 프로필보다 우선한다고 명시', fb.includes('우선'), fb);

// 3) scoreItem이 feedback을 실제 Haiku 요청에 실어 보내는지
//    (buildFeedback이 맞아도 호출부에서 안 넘기면 아무 효과가 없다)
process.env.ANTHROPIC_API_KEY = 'sk-ant-test';
let sent = '';
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, opt) => {
  sent = JSON.parse(opt.body).messages[0].content;
  return { ok: true, json: async () => ({ content: [{ text: '{"score":7,"reason":"테스트"}' }] }) };
};
const item = { title: '새로 들어온 항목', desc: '설명', author: '채널' };
const res = await scoreItem('내 관심 프로필', item, '', fb);
globalThis.fetch = realFetch;

check('점수를 정상 파싱', res.score === 7, JSON.stringify(res));
check('프롬프트에 관심 프로필 포함', sent.includes('내 관심 프로필'));
check('프롬프트에 판정 이력 포함', sent.includes('제외한 영상 B') && sent.includes('보관한 영상 A'),
  sent.slice(0, 400));
check('판정 이력이 평가 대상 항목보다 앞에 온다',
  sent.indexOf('제외한 영상 B') < sent.indexOf('새로 들어온 항목'));

console.log(fail ? `\n${fail}개 실패` : '\n피드백 루프 검증 완료');
process.exit(fail ? 1 : 0);
