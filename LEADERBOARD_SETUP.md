# 🏆 글로벌 랭킹 설정 (5분)

블록 블라스트는 **서버리스 글로벌 랭킹**을 지원합니다. 백엔드로 [Supabase](https://supabase.com)(무료 티어)를 사용하며, 별도 서버를 운영할 필요 없이 클라이언트에서 직접 점수를 제출·조회합니다.

> 설정하지 않아도 게임은 **이 기기 안의 로컬 Top-10 랭킹**으로 정상 작동합니다. 아래 설정을 완료하면 자동으로 전 세계 랭킹으로 전환됩니다.

## 1. Supabase 프로젝트 만들기
1. [supabase.com](https://supabase.com) 가입 → **New project** 생성 (리전은 아무거나)
2. 프로젝트가 준비되면 **Project Settings → API** 로 이동
3. 다음 두 값을 복사:
   - **Project URL** (예: `https://abcd1234.supabase.co`)
   - **anon public** key (공개용 키 — 클라이언트에 노출되어도 안전)

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
`blockblast.html` 상단의 `LB_CONFIG` 를 채웁니다:

```js
const LB_CONFIG={
  url:   "https://abcd1234.supabase.co",   // ← Project URL
  key:   "eyJhbGciOi...",                    // ← anon public key
  table: "leaderboard",
};
```

저장하고 새로고침하면 랭킹 화면 상단이 **🌍 글로벌 랭킹**으로 바뀝니다. 끝!

## 동작 방식
- **점수 제출**: 게임 오버 시 이름 입력 후 `랭킹 등록` → `POST /rest/v1/leaderboard`
- **랭킹 조회**: `GET .../leaderboard?order=score.desc&limit=20`
- **내 순위**: `score=gt.<내점수>` 카운트 + 1
- 네트워크 오류 시 자동으로 로컬 랭킹으로 폴백

## 보안 참고
- `anon` 키는 클라이언트 공개용으로 설계된 키라 노출되어도 됩니다.
- RLS 정책으로 **읽기 + 점수 추가만** 허용되고 타인 기록 수정/삭제는 막혀 있습니다.
- 어뷰징(가짜 고득점)이 걱정되면, 나중에 Supabase Edge Function으로 서버 검증을 추가하거나 rate-limit 정책을 걸 수 있습니다.
