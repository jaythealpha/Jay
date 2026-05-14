# Claude 작업 대시보드

이 세션에서 Claude 가 생성한 모든 산출물(전략 문서, 웹 도구 등)을 **한 화면에서
보고 즉시 실행**할 수 있는 정적 대시보드입니다.

## 실행

```bash
# 리포지토리 루트에서
python3 -m http.server 8000
# 브라우저: http://localhost:8000/dashboard/
```

> 대시보드는 같은 리포지토리 안의 상대 경로(`../yogibo-korea-10x-strategy.md`,
> `../mates-generator/index.html`)를 참조합니다. 반드시 **리포지토리 루트에서**
> 정적 서버를 띄워주세요. `dashboard/` 안에서 서버를 띄우면 상대 경로가 깨집니다.

## 화면 구성

1. **요약 통계** — 전체 작업 수, 완료/진행 중 개수, 분류 수
2. **검색창 + 분류 칩 + 상태 토글** — 빠른 필터링
3. **카드 그리드** — 모든 작업을 한 눈에. 카드 클릭 시 상세 모달
4. **상세 모달**
   - `markdown` 타입: 본문을 [marked.js](https://marked.js.org/) 로 렌더링해 인라인 표시
   - `webapp` 타입: iframe 으로 임베드, "새 탭에서 실행" 버튼 제공
   - 직접 링크: `https://…/dashboard/#project=<id>` 로 특정 작업 바로 열기

## 등록된 작업

| 작업 | 분류 | 타입 | 경로 |
| --- | --- | --- | --- |
| Yogibo 한국 시장 10배 확대 전략안 | 전략 / 사업기획 | markdown | `../yogibo-korea-10x-strategy.md` |
| Yogibo Mates 이미지 프롬프트 생성기 | 도구 / 크리에이티브 | webapp | `../mates-generator/index.html` |

## 새 작업 추가하기

`dashboard/projects.json` 의 `projects` 배열에 아래 스키마로 항목을 추가하면
새로고침만으로 카드가 자동 생성됩니다.

```json
{
  "id": "unique-slug",
  "title": "작업 제목",
  "category": "분류 라벨",
  "status": "완료 | 진행 중 | 초안",
  "type": "markdown | webapp | data | link",
  "path": "../상대경로",
  "icon": "📈",
  "tags": ["키워드", "..."],
  "summary": "한 줄 요약",
  "description": "상세 설명",
  "actions": [{ "label": "원문", "href": "../path" }],
  "created": "2026-05-14",
  "commit": "abcdefg"
}
```

### 타입 가이드

- **markdown** — `.md` 파일. 본문이 모달 안에 렌더링됨
- **webapp** — `.html` 파일. iframe 임베드 + 새 탭 실행 액션 자동 추가
- **data** — JSON/텍스트 파일. 본문을 코드 블록으로 표시
- **link** — 외부 URL 등 미리보기 없는 경우 `description` 만 표시

## 디렉터리

```
dashboard/
├── index.html      # 마크업
├── style.css       # 스타일
├── app.js          # 카드 렌더링 + 상세 모달 + 마크다운/임베드
├── projects.json   # 작업 레지스트리 (편집해서 작업 추가)
└── README.md
```

## 의존성

- 외부: [marked.js](https://cdn.jsdelivr.net/npm/marked) (CDN, 마크다운 렌더링용)
- 그 외 빌드/번들러 불필요. 순수 정적 페이지.
