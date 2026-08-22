// 서버 측 전체 분석 — 수집 단계에서 고득점 항목을 사람 손 없이 분석까지 끝낸다.
//
// ⚠️ 프롬프트·스키마는 index.html의 SYSTEM_PROMPT / JSON_SCHEMA와 같은 내용이어야 한다.
//    (앱은 단일 HTML 파일이라 import를 공유할 수 없어 부득이 중복. 한쪽을 고치면 다른 쪽도 고칠 것)

export const SYSTEM_PROMPT = `당신은 다양한 소스(유튜브 영상 자막, 웹 아티클, 사용자 노트 등)를 분석해
핵심 노하우·인사이트를 실제로 따라 할 수 있게 정리하고, 가능한 부분은 자동화·콘텐츠화하도록
돕는 한국어 전략가이자 자동화 컨설턴트입니다.
주어진 소스 텍스트만을 근거로 분석하세요. 없는 사실을 지어내지 말고, 불확실하면 그렇게 표시합니다.
저자/화자가 여럿이면 핵심 인물 위주로 정리하고, 정보성 아티클처럼 특정 인물이 없으면 인물 항목은 비워둡니다.
자동화 제안은 실제 존재하는 도구(예: Make, Zapier, n8n, Google Sheets, Notion, 버퍼/메타 비즈니스 스위트,
캡컷, ChatGPT/Claude API, 유튜브·인스타 API 등)를 근거로 현실적으로 제시하세요.
반드시 지정된 JSON 스키마로만, 한국어로 응답합니다.`;

// ⚠️ index.html의 JSON_SCHEMA와 **한 글자도 다르면 안 된다**.
// 앱의 renderResult가 tldr·interviewee·playbook·knowhow[].category·knowhow[].why를 직접 읽기 때문에,
// 여기서 필드가 빠지면 자동 분석 결과만 화면에서 텅 비어 보인다.
// scripts/check-schema-sync.mjs가 두 파일의 일치를 검사한다.
export const JSON_SCHEMA = `{
  "video": { "title": "영상 제목(모르면 '')", "creator": "채널/인터뷰이(모르면 '')", "topic": "한 문장 주제", "oneLine": "이 영상의 핵심을 한 줄로" },
  "summary": "3~5문장 핵심 요약",
  "tldr": ["가장 중요한 시사점 5개 내외, 각 한 문장"],
  "interviewee": { "who": "인터뷰이가 누구인지/무엇을 하는 사람인지", "credibility": "왜 이 사람 말을 들을 만한지(성과·경력 등, 스크립트 근거)" },
  "knowhow": [
    { "category": "콘텐츠제작|계정성장|수익화|플랫폼전략|운영·루틴|마인드셋 중 하나",
      "title": "노하우 제목", "detail": "구체적으로 무엇을 하라는 것인지 2~3문장",
      "why": "왜 효과가 있는지 한 문장" }
  ],
  "playbook": [
    { "step": 1, "name": "단계 이름", "action": "이 단계에서 실제로 하는 일",
      "automatable": "높음|중간|낮음|불가",
      "tools": ["이 단계 자동화에 쓸 실제 도구 1~3개"],
      "howToAutomate": "이 단계를 어떻게 자동화/반자동화하는지 구체적으로 1~2문장" }
  ],
  "automationBlueprint": {
    "overview": "이 영상의 프로세스를 하나의 자동화 파이프라인으로 묶으면 어떤 모습인지 3~4문장",
    "stack": [ { "layer": "아이디어|제작|배포|분석|수익화 중 하나", "tool": "도구 이름", "role": "그 도구가 하는 역할 한 문장" } ],
    "cronIdeas": ["정기적으로 자동 실행하면 좋은 작업 3~5개"]
  },
  "actionPlan": {
    "day1": ["오늘 당장 할 일 3~5개(체크리스트 문장)"],
    "week1": ["첫 주에 할 일 3~5개"]
  },
  "risks": ["주의사항·리스크·윤리/정책 이슈 2~4개 (예: 과장·사기 소지, 플랫폼 정책 위반, 지속가능성 등)"],
  "quotes": [ { "text": "인상적인 인용구(스크립트에서 발췌)", "at": "타임스탬프 있으면(없으면 '')" } ]
}`;

function parseJson(text) {
  let t = String(text).replace(/```json/gi, '').replace(/```/g, '').trim();
  const s = t.indexOf('{'), e = t.lastIndexOf('}');
  if (s === -1 || e === -1) throw new Error('JSON을 찾지 못했어요');
  return JSON.parse(t.slice(s, e + 1));
}

// 앱과 같은 기본 모델(Sonnet)로 분석. 필터링용 Haiku보다 비싸므로 호출부에서 건수를 제한한다.
export async function analyzeSource({ key, model, title, channel, url, transcript }) {
  const meta = [];
  if (title) meta.push(`제목: ${title}`);
  if (channel) meta.push(`출처/채널: ${channel}`);
  if (url) meta.push(`URL: ${url}`);
  const userText = `${meta.join('\n')}\n\n아래는 소스 텍스트입니다. 이 내용을 근거로 핵심 노하우·인사이트를 정리하고,` +
    ` 그 프로세스를 가능한 한 자동화·콘텐츠화할 수 있도록 분석하세요. 반드시 아래 JSON 스키마로만 응답하세요.\n\n` +
    `[소스 시작]\n${String(transcript).slice(0, 48000)}\n[소스 끝]\n\n${JSON_SCHEMA}`;

  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
    body: JSON.stringify({
      model: model || 'claude-sonnet-5',
      // 앱(16000)보다 낮게 잡는다 — 서버리스 60초 제한 안에서 끝나야 하고,
      // 발췌가 5,500자로 제한돼 있어 이 스키마 출력에는 충분하다
      max_tokens: 8000,
      system: SYSTEM_PROMPT,
      messages: [{ role: 'user', content: [{ type: 'text', text: userText }] }],
    }),
  });
  if (!r.ok) {
    let m = 'Claude HTTP ' + r.status;
    try { const j = await r.json(); if (j.error && j.error.message) m += ': ' + j.error.message; } catch {}
    throw new Error(m);
  }
  const j = await r.json();
  if (j.stop_reason === 'max_tokens') throw new Error('응답이 잘렸어요(소스가 너무 김)');
  const texts = (j.content || []).filter(c => c.type === 'text').map(c => c.text || '');
  return parseJson(texts.join('\n'));
}
