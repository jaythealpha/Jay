# 이 저장소에 설치된 Agent Skills

`.claude/skills/` 에 프로젝트 스코프로 설치되어 있습니다. 이 저장소에서 Claude Code(또는 skills CLI를 지원하는 다른 에이전트)를 열면 자동으로 로드됩니다.

| 스킬 | 출처 | 호출 방식 | 용도 |
|---|---|---|---|
| `find-skills` | [vercel-labs/skills](https://github.com/vercel-labs/skills) | 자동 (모델이 알아서 사용) | "이런 거 해주는 스킬 있어?" 같은 질문에 skills.sh 생태계를 검색·설치 |
| `grill-me` | [mattpocock/skills](https://github.com/mattpocock/skills) | `/grill-me` (수동 전용) | 아이디어·기획을 라운드 단위 질문으로 압박 심문해 결정으로 만들기 |
| `grilling` | [mattpocock/skills](https://github.com/mattpocock/skills) | 자동 / `grill` 트리거 | `grill-me` 가 실제로 실행하는 인터뷰 엔진 (같이 있어야 동작) |
| `frontend-design` | [anthropics/skills](https://github.com/anthropics/skills) | 자동 (UI 만들 때) | 템플릿 같지 않은, 의도가 있는 시각 디자인 방향 잡기 |

## 재설치 / 업데이트

```bash
npx skills@latest add vercel-labs/skills  --skill find-skills      --agent claude-code --copy -y
npx skills@latest add mattpocock/skills   --skill grill-me         --agent claude-code --copy -y
npx skills@latest add mattpocock/skills   --skill grilling         --agent claude-code --copy -y
npx skills@latest add anthropics/skills   --skill frontend-design  --agent claude-code --copy -y

npx skills@latest update   # 전부 최신으로
npx skills@latest list     # 설치된 스킬 확인
```

버전은 `skills-lock.json` 에 고정되어 있습니다.

## 사용 메모

- **grill-me**: 새 대화에서 시작하고 plan mode는 끄세요. 계획을 다 짜둔 상태에서 얹으면 효과가 없습니다. "동의, 동의"만 하면 실패합니다 — 반박하고 범위를 직접 잡으세요. 질문 수가 아니라 **라운드 수**로 진행 상황을 보세요. 한 번에 한 질문씩 받고 싶으면 `CLAUDE.md` 에 `When grilling, ask one question at a time.` 를 추가하세요.
- **frontend-design**: "이 페이지 예쁘게" 대신 대상·독자·페이지의 목적을 한 줄로 주면 결과가 크게 달라집니다. 브리프에 방향(브루탈리즘/맥시멀리즘 등)을 못 박으면 그대로 따릅니다.
- **find-skills**: 뭔가 직접 구현하기 전에 "이거 해주는 스킬 있어?" 라고 물어보면 먼저 검색합니다.
