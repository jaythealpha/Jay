# 🏆 글로벌 랭킹 설정 (5분)

블록 블라스트는 **서버리스 글로벌 랭킹**을 지원합니다. 백엔드로 [Supabase](https://supabase.com)(무료 티어)를 사용하며, 별도 서버를 운영할 필요 없이 클라이언트에서 직접 점수를 제출·조회합니다.

> 설정하지 않아도 게임은 **이 기기 안의 로컬 Top-10 랭킹**으로 정상 작동합니다. 아래 설정을 완료하면 자동으로 전 세계 랭킹으로 전환됩니다.

## 1. Supabase 프로젝트 만들기
1. [supabase.com](https://supabase.com) 가입 → **New project** 생성 (리전은 아무거나)
2. 프로젝트가 준비되면 **Project Settings → API** 로 이동
3. 다음 두 값을 복사:
   - **Project URL** (예: `https://abcd1234.supabase.co`)
   - **공개 키** — 프로젝트 생성 시점에 따라 형식이 다릅니다. 둘 다 지원합니다.
     - 신형: **Publishable key** (`sb_publishable_...`) ← 최근 만든 프로젝트는 이쪽
     - 레거시: **anon public** key (`eyJ...` JWT)

> ⚠️ 최근 Supabase 프로젝트는 레거시 JWT `anon` 키가 **비활성 상태일 수 있습니다.**
> 그 키로 호출하면 `{"message":"Invalid API key"}` 가 돌아옵니다. 이때는 Publishable
> 키를 쓰세요. 게임 코드가 키 형식을 보고 헤더를 알아서 맞춥니다 — JWT면
> `apikey` + `Authorization: Bearer`, publishable 키면 JWT가 아니라 Bearer 로 보내면
> 401이 날 수 있으므로 `apikey` 만 보냅니다.

## 2. 랭킹 테이블 만들기
Supabase 대시보드 → **SQL Editor** 에서 아래를 실행:

```sql
create table if not exists public.leaderboard (
  id         bigint generated always as identity primary key,
  name       text not null check (char_length(name) <= 10),
  score      integer not null check (score >= 0 and score < 100000000),
  dex        integer default 0,
  created_at timestamptz default now()
);

-- 점수 내림차순 조회 최적화
create index if not exists leaderboard_score_idx on public.leaderboard (score desc);

-- 행 수준 보안: 누구나 읽고, 점수 제출(insert)만 가능. 수정·삭제는 불가.
alter table public.leaderboard enable row level security;

create policy "read_all"   on public.leaderboard for select using (true);
create policy "insert_any" on public.leaderboard for insert with check (true);
```

## 3. 게임에 키 연결

> ✅ **연결·확인 완료 (2026-07-31)** — 프로젝트 `hsgzhaswfzikzdpaawdi` 의 URL과
> **publishable 키**가 `blockblast.html` 의 `LB_CONFIG` 에 들어가 있고, 테이블 조회가
> `[]` 로 정상 응답하는 것까지 확인했습니다. 글로벌 랭킹이 실제로 동작합니다.
>
> 이 프로젝트는 레거시 anon(JWT) 키가 비활성이라(`Invalid API key`) publishable 키를 씁니다.

`blockblast.html` 상단의 `LB_CONFIG` 를 채웁니다:

```js
const LB_CONFIG={
  url:   "https://abcd1234.supabase.co",   // ← Project URL
  key:   "sb_publishable_...",              // ← publishable 키 (또는 레거시 anon JWT)
  table: "leaderboard",
};
```

저장하고 새로고침하면 랭킹 화면 상단이 **🌍 글로벌 랭킹**으로 바뀝니다. 끝!

## 동작 방식
- **점수 제출**: 게임 오버 시 이름 입력 후 `랭킹 등록` → `POST /rest/v1/leaderboard`
- **랭킹 조회**: `GET .../leaderboard?order=score.desc&limit=20`
- **내 순위**: `score=gt.<내점수>` 카운트 + 1 — 응답의 `Content-Range` 헤더에서 총건수를 읽습니다.
  브라우저는 CORS 규칙상 `Content-Range` 를 기본으로 읽지 못하는데, Supabase(PostgREST)가
  `Access-Control-Expose-Headers` 로 노출해 주기 때문에 동작합니다. 혹시 순위 숫자가
  이상하면 이 헤더부터 확인하세요(읽지 못하면 로컬 계산으로 조용히 폴백합니다).
- 네트워크 오류 시 자동으로 로컬 랭킹으로 폴백

## 연결 확인 방법

게임을 열어 **🏆 랭킹 보기** 를 눌렀을 때 상단이 `🌍 글로벌 랭킹` 이면 키가 인식된 것입니다.
다만 이 표시는 **키 존재 여부만** 보므로, 테이블이 없거나 SQL을 안 돌렸으면 조회가 실패해
조용히 로컬 랭킹으로 떨어집니다. 서버까지 확실히 확인하려면:

브라우저 주소창에 아래를 넣는 방법이 가장 간단합니다(셸 따옴표 문제가 없음).
`YOUR_KEY` 자리에 **실제 키를 붙여넣어야** 합니다 — 자리표시자를 그대로 두면
`Invalid API key` 가 나옵니다.

```
https://hsgzhaswfzikzdpaawdi.supabase.co/rest/v1/leaderboard?select=*&limit=1&apikey=YOUR_KEY
```

| 응답 | 뜻 |
|---|---|
| `[]` 또는 기록 배열 | 정상 — 키·테이블 모두 OK |
| `relation "public.leaderboard" does not exist` | 키는 OK, 2번 SQL 미실행 |
| `Invalid API key` | 키가 거부됨 — 자리표시자를 안 바꿨거나, 레거시 JWT 키가 비활성 (위 1번 경고 참고) |

## 보안 참고
- `anon` 키는 클라이언트 공개용으로 설계된 키라 노출되어도 됩니다.
- RLS 정책으로 **읽기 + 점수 추가만** 허용되고 타인 기록 수정/삭제는 막혀 있습니다.
- 어뷰징(가짜 고득점)이 걱정되면, 나중에 Supabase Edge Function으로 서버 검증을 추가하거나 rate-limit 정책을 걸 수 있습니다.
