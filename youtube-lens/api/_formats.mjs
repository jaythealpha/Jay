// 서버가 무인으로 초안을 만들 수 있는 포맷 정의.
//
// 앱(index.html)에는 12개 포맷이 있지만, 여기에는 **사람 설정 없이도 좋은 결과가 나오는 3종만**
// 둔다. 분량·타깃 독자·난이도 같은 선택이 필요한 포맷(블로그·퀴즈 등)은 사람이 고르는 게 맞고,
// 12개를 전부 복제하면 앱과 갈라질 위험만 커진다.
//
// ⚠️ guide/schema/expert 문자열은 index.html의 같은 포맷과 **한 글자도 달라선 안 된다**.
//    scripts/check-schema-sync.mjs가 검사한다.

const S_SNS = `{ "format":"<라벨>","title":"관리용 제목","hooks":["스크롤을 멈추게 하는 훅 후보 3개"],"script":[{"scene":"장면/시간(예 0-2초) 또는 슬라이드 번호","visual":"화면·비주얼·자막 배치 지시","voiceover":"나레이션 또는 화면 텍스트"}],"caption":"게시물 캡션(줄바꿈, 첫 줄 후킹, 이모지)","hashtags":["#해시태그 8~12개"],"cta":"저장/공유/팔로우 유도 한 문장" }`;

export const SERVER_FORMATS = {
  reels: {
    label: '릴스 대본',
    guide: '15~40초 릴스용. script는 시간 단위(0-2초 등) 5~8개, 첫 장면은 강한 훅.',
    schema: S_SNS,
    expert: '훅 공식으로 첫 1~2초 설계: ①궁금증 갭(결말·비밀 암시) ②강한 이득/손실 ③상식 반전 ④구체적 숫자. 3초 안에 스크롤을 멈추게 하고, 매 3~5초 새 정보(오픈루프)로 리텐션 유지. CTA는 저장·공유를 겨냥. 자막 친화적 짧은 문장. 금지: "안녕하세요 오늘은", 형용사 나열, 뻔한 도입.',
  },
  cards: {
    label: '카드뉴스',
    guide: '인스타 카드뉴스. script는 슬라이드 단위(1,2,…6~9장), 1번 표지(훅), 마지막 CTA. voiceover=슬라이드 텍스트.',
    schema: S_SNS,
    expert: '1번 표지=강한 훅(숫자·결과 약속). 각 카드=1아이디어(한 줄 헤드라인 + 짧은 부연). 카드 간 오픈루프로 스와이프 유지. 마지막=요약+저장 유도. 정보 밀도를 높여 "저장"을 유발.',
  },
  summary: {
    label: '요약노트',
    guide: '핵심을 구조화한 학습 요약. 원문 근거에 충실하게.',
    schema: `{ "format":"요약노트","title":"제목","tldr":["3~5줄 핵심 요약"],"keyPoints":[{"point":"핵심 개념","detail":"1~2문장 설명"}],"glossary":[{"term":"용어","def":"정의"}],"takeaways":["실행/기억 포인트 3~5개"] }`,
    expert: '원문의 주장→근거→예시 구조를 보존. tldr은 결론 먼저. keyPoints는 MECE(상호배타·전체포괄). glossary는 원문에 실제 등장한 용어만. takeaways는 행동 동사로 시작. 원문에 없는 내용 추가 금지.',
  },
};

export const DEFAULT_DRAFT_FORMATS = ['reels', 'summary'];

// 앱의 콘텐츠 시스템 프롬프트와 같은 역할
export const CONTENT_SYSTEM = `당신은 한국어 콘텐츠를 만드는 정상급 전문 카피라이터이자 크리에이터입니다.
각 포맷의 모범 사례를 정확히 따르고, 상투적 표현을 피하며, 주어진 근거를 벗어난 사실을 지어내지 않습니다.
반드시 지정된 JSON 스키마로만, 한국어로 응답합니다.`;

// 앱의 contentPrompt와 같은 구조. 서버에는 사람이 고른 설정이 없으므로 기본값을 쓴다.
export function draftPrompt(data, fmt, sourceExcerpt) {
  const kh = (Array.isArray(data.knowhow) ? data.knowhow : [])
    .map(k => `- (${k.category}) ${k.title}: ${k.detail}`).join('\n') || '(노하우 항목 없음)';
  const topic = (data.video && (data.video.topic || data.video.title)) || '이 소스의 주제';
  const grounding = sourceExcerpt
    ? `\n[원문 발췌 — 사실 근거로만 사용, 없는 내용을 지어내지 말 것]\n${String(sourceExcerpt).slice(0, 6000)}\n` : '';
  return `아래 인사이트를 바탕으로 "${fmt.label}" 콘텐츠를 만들어 주세요.\n\n` +
    `[요약]\n${data.summary || ''}\n\n[핵심 노하우·인사이트]\n${kh}\n${grounding}\n` +
    `[주제·키워드] ${topic}\n[설정]\n- 톤: 정보형(깔끔·정확)\n- 개수: 1\n\n[형식 가이드] ${fmt.guide}\n` +
    `\n[전문가 지침 — 반드시 적용]\n${fmt.expert}\n\n` +
    `과장·허위 표현을 쓰지 말고 원문 근거를 벗어난 사실은 만들지 마세요. 반드시 아래 JSON 스키마로만 한국어로 응답하세요.\n\n` +
    `{ "pieces": [ ${fmt.schema.replace('<라벨>', fmt.label)} ] }`;
}
