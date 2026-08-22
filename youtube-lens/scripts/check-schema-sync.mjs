// 앱(index.html)과 서버(api/_analyze.mjs)의 분석 프롬프트·스키마가 갈라지지 않게 검사한다.
//
// 앱이 단일 HTML 파일이라 import를 공유할 수 없어 문자열이 양쪽에 중복돼 있다.
// 실제로 한 번 갈라져서, 자동 분석 결과만 tldr·interviewee·playbook이 빠진 채
// 화면에 렌더돼 섹션 세 개가 통째로 비어 보이는 버그가 있었다.
//
//   node scripts/check-schema-sync.mjs      → 불일치 시 exit 1
import { readFileSync } from 'node:fs';
import { SYSTEM_PROMPT, JSON_SCHEMA } from '../api/_analyze.mjs';
import { SERVER_FORMATS } from '../api/_formats.mjs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

function grab(name) {
  const m = html.match(new RegExp('const ' + name + ' = `([\\s\\S]*?)`;'));
  if (!m) throw new Error(`index.html에서 ${name}을 찾지 못했습니다`);
  return m[1];
}

let failed = false;
for (const [name, serverVal] of [['SYSTEM_PROMPT', SYSTEM_PROMPT], ['JSON_SCHEMA', JSON_SCHEMA]]) {
  const appVal = grab(name);
  if (appVal === serverVal) { console.log(`✅ ${name} 일치`); continue; }
  failed = true;
  console.error(`❌ ${name} 불일치`);
  const a = appVal.split('\n'), b = serverVal.split('\n');
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if (a[i] !== b[i]) {
      console.error(`   첫 차이 ${i + 1}행`);
      console.error(`   app   : ${a[i] ?? '(없음)'}`);
      console.error(`   server: ${b[i] ?? '(없음)'}`);
      break;
    }
  }
}
// 서버가 무인 초안에 쓰는 포맷의 guide/expert/schema가 앱과 같은지도 검사한다.
// 갈라지면 같은 포맷인데 자동 초안만 다른 규칙으로 만들어진다.
for (const [id, fmt] of Object.entries(SERVER_FORMATS)) {
  for (const [field, val] of [['guide', fmt.guide], ['expert', fmt.expert], ['schema', fmt.schema]]) {
    if (html.includes(val)) continue;
    failed = true;
    console.error(`❌ 포맷 ${id}.${field} 이(가) index.html에 없습니다 (문구가 갈라졌습니다)`);
    console.error(`   server: ${String(val).slice(0, 90)}…`);
  }
}
if (!failed) console.log(`✅ 서버 포맷 ${Object.keys(SERVER_FORMATS).length}종 문구 일치`);

if (failed) {
  console.error('\napi/_analyze.mjs · api/_formats.mjs와 index.html의 값을 같게 맞춰주세요.');
  process.exit(1);
}
console.log('스키마 동기화 확인 완료');
