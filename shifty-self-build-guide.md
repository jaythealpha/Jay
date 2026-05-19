# 시프티 대체 — 자체 개발(인하우스 + 바이브 코딩) 구현 가이드

> 작성일: 2026-05-19
> 전제(사용자 확정): **법인사업자 · GPS 출퇴근 필수 · 30명 · 사내 개발자 보유 · 바이브 코딩 방식**
> 목표: 출퇴근 기록(GPS) 단일 기능을 자체 구축해 시프티(연 57.6만 원)를 대체

---

## 0. 먼저: 자체 개발이 이 케이스에서 성립하는 이유
- 외주(200만~500만)는 ROI 불성립이었으나, **사내 인력 + 바이브 코딩이면 MVP 공수가 3~5일 수준**으로 축소 → 현금 지출 ≈ 0, 회수 즉시.
- 단, **반드시 인지할 한계**: 순수 웹(PWA)은 OS 단의 위치 위조(모의 위치 앱) 탐지·WiFi BSSID 읽기가 **불가**. 시프티·알밤이 비콘/네이티브 SDK를 쓰는 이유가 이것. 부정출근 방지를 강하게 하려면 **네이티브 래퍼(Capacitor)**가 필요(§6).

---

## 1. 기능 범위

### MVP (1차, 必)
- 직원 로그인(사번+PIN 또는 매직링크)
- 출근/퇴근 버튼 → 브라우저 Geolocation으로 좌표 수집
- **서버측 지오펜스 검증**: 사업장 좌표 반경 내에서만 인정
- 출퇴근 기록 저장(서버 시각 기준), 본인 당일 기록 조회
- 관리자: 전직원 기록 조회 + **엑셀(CSV) 내보내기**

### 2차 (확장, 선택)
- 다중 사업장, 근무 스케줄 대비 지각/조퇴 표시
- 셀카 촬영 첨부(대리출근 억제)
- 월별 근로시간 집계 리포트, 알림(미출근 푸시)

### 비범위 (의도적 제외)
- 급여·주휴수당 계산, 연차관리, 전자결재 → 필요 시 시프티/알밤 잔류가 더 쌈. **확장하지 말 것**(분석 1차 결론과 동일: 풀스위트 자체구현은 비효율).

---

## 2. 권장 스택 (바이브 코딩 적합성 기준)

| 레이어 | 선택 | 이유 |
|---|---|---|
| 프론트 | **Next.js(App Router) PWA** | 바이브 코딩 친화, 모바일 설치형, HTTPS 기본 |
| 인증 | **Supabase Auth** (사번 매핑 + 매직링크/OTP) | 무료 티어 5만 MAU, 코드량 적음 |
| DB/백엔드 | **Supabase (Postgres + RLS + Edge Function)** | SQL → 엑셀 내보내기·감사 용이, 지오펜스 검증을 Edge Function에 서버측 구현 |
| 호스팅 | **Vercel 무료 / Supabase 무료** | 30명 트래픽은 무료 한도 내 |
| (선택) 네이티브 | **Capacitor**로 PWA 래핑 | 모의위치 탐지·디바이스 바인딩 강화 시 |

운영비: 서버 ≈ 0원(무료 티어), **도메인 약 1.5만~2만 원/년만 발생**.

---

## 3. 데이터 모델 (Supabase / Postgres)

```sql
-- 직원
create table employees (
  id uuid primary key default gen_random_uuid(),
  emp_code text unique not null,
  name text not null,
  device_id text,                 -- 1인 1단말 바인딩(선택)
  active boolean default true
);

-- 사업장(지오펜스 기준점)
create table worksites (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  lat double precision not null,
  lng double precision not null,
  radius_m int not null default 200   -- GPS 드리프트 감안 150~250m
);

-- 출퇴근 기록 (근로기준법상 3년 보존 — 삭제 금지, soft 처리)
create table attendance (
  id uuid primary key default gen_random_uuid(),
  employee_id uuid references employees(id),
  worksite_id uuid references worksites(id),
  type text check (type in ('IN','OUT')),
  server_ts timestamptz not null default now(),  -- 권위 시각(클라 시각 신뢰 금지)
  client_lat double precision,
  client_lng double precision,
  accuracy_m double precision,        -- 정확도. 임계 초과 시 거부
  distance_m double precision,        -- 사업장과의 거리(서버 계산)
  status text,                        -- OK / OUT_OF_RANGE / LOW_ACCURACY
  ip text,
  photo_url text                      -- 셀카(선택)
);
```
- RLS: 직원은 본인 행만 select/insert, 관리자 롤만 전체 조회.
- 보존: `attendance`는 **물리 삭제 금지**, 비활성 직원도 기록 유지(3년+).

---

## 4. 핵심 로직 — 출퇴근 + 지오펜스 (반드시 서버측)

클라이언트는 좌표만 보내고, **검증·시각은 전부 Edge Function이 수행**한다.

```
[클라] navigator.geolocation.getCurrentPosition({enableHighAccuracy:true})
   → {lat, lng, accuracy} 를 Edge Function에 전송
[서버 Edge Function]
   1) accuracy > 100m  → status=LOW_ACCURACY, 거부
   2) Haversine(거리, 사업장)  > worksite.radius_m → status=OUT_OF_RANGE, 거부
   3) 직전 기록과 동일 type 연속/단시간 중복 → 거부(중복 클릭·이상행동)
   4) (선택) device_id != 등록 단말 → 경고/거부
   5) 통과 → server_ts=now()로 INSERT, status=OK
```

Haversine 거리(서버):
```
R=6371000; dLat,dLng=라디안 차;
a=sin(dLat/2)^2 + cos(lat1)cos(lat2)sin(dLng/2)^2;
distance = 2R*atan2(√a,√(1-a))
```

---

## 5. 부정출근(대리/위조) 방지 — 현실적 강도

| 기법 | 웹 PWA 가능? | 효과 |
|---|---|---|
| 서버 시각 권위화 | ✅ | 시각 조작 차단 |
| 정확도 임계(>100m 거부) | ✅ | 저품질·우회 일부 차단 |
| 지오펜스 반경 검증 | ✅ | 원격 출근 차단 |
| 중복/이상행동 탐지(짧은 간격, 불가능 이동거리) | ✅ | 패턴 부정 탐지 |
| 1인 1단말 바인딩(device_id) | ✅(쿠키/스토리지, 약함) | 대리출근 억제 |
| 셀카 촬영 첨부 | ✅ | 대리출근 강력 억제 |
| **모의 위치(Mock GPS) 앱 탐지** | ❌ 웹 불가 | **Capacitor 네이티브 필요** |
| **WiFi BSSID/비콘 확인** | ❌ 웹 불가 | **네이티브 필요** |

**결론**: 강한 위·변조 방지가 필요하면 §2의 Capacitor 래핑으로 모의위치 탐지 플러그인을 추가. 그렇지 않다면 "셀카 + 지오펜스 + 이상탐지 + 관리자 검수"로 실무 수준은 확보 가능(단, 시프티 대비 방지력은 약함을 의사결정자에게 명시).

---

## 6. 보안·법적 요건 (법인 필수 체크)
- **개인정보**: 위치·셀카 수집 → 수집·이용 동의 화면, 보유기간·목적 고지. 최소수집(좌표만, 상시 추적 금지 — 출퇴근 순간만).
- **근로기준법**: 근로시간 기록 **3년 보존**. `attendance` 삭제 금지 + 정기 백업(Supabase 백업/주기적 CSV 내보내기).
- **HTTPS 필수**(Geolocation API 요건) — Vercel 기본 충족.
- 관리자 계정 2FA, RLS로 타인 기록 접근 차단.

---

## 7. 바이브 코딩 진행법 (이 프로젝트에 맞춘 방식)
1. **스펙 먼저**: 본 문서의 §3 스키마·§4 로직을 그대로 AI에 컨텍스트로 제공(자연어 'vibe'만으로 시작 금지 — 지오펜스/보존은 정확성이 중요).
2. **수직 슬라이스 순서로 프롬프트**: ①Supabase 스키마+RLS → ②로그인 → ③출근 Edge Function(검증 포함) → ④직원 화면 → ⑤관리자 조회/CSV.
3. **검증 루프 필수**: 각 슬라이스마다 (a) 반경 밖 좌표 거부 (b) 저정확도 거부 (c) 중복 클릭 거부 (d) 본인 외 기록 조회 차단 — 4개 테스트를 실제로 돌려 통과 확인 후 다음 단계. "돌아간다"는 AI 주장만 신뢰 금지.
4. **민감 로직은 사람이 리뷰**: 거리 계산식, 시각 권위화, RLS 정책은 머지 전 직접 점검.
5. 시드 데이터(사업장 좌표 1곳, 더미 직원 3명)로 현장 모바일 실측 후 `radius_m` 보정.

---

## 8. 로드맵 (사내 인력 기준)

| 단계 | 산출물 | 소요(가이드) |
|---|---|---|
| D1 | Supabase 프로젝트·스키마·RLS, 로그인 | 0.5~1일 |
| D2 | 출/퇴근 Edge Function + 지오펜스·정확도·중복 검증 | 1~1.5일 |
| D3 | 직원 PWA 화면(출근/퇴근/내 기록), 동의 화면 | 1일 |
| D4 | 관리자 조회·CSV 내보내기, 시드·현장 실측 보정 | 1일 |
| D5 | (선택) 셀카 첨부 / Capacitor 모의위치 방지 | 1~2일 |
| 전환 | 시프티 1주 병행 → 검증 후 해지 | 1주 |

---

## 9. 자체개발 vs 시프티 잔류 — 최종 판단 기준
- **자체개발 권고 조건(모두 충족 시)**: 사내 인력 유휴분 존재 + 부정출근 방지 강도를 "셀카+지오펜스" 수준으로 합의 가능 + 유지보수 담당자 1명 지정.
- **시프티 잔류가 나은 경우**: 부정출근 방지력이 분쟁 리스크상 중요(노무 이슈 잦음) + 유지보수 인력 회수 불확실 → 단가 다운그레이드(옵션 A)가 안전.
- 핵심: 절감액 연 ~57만 원은 작다. 자체개발의 진짜 비용은 **개발이 아니라 향후 유지보수·법적 책임의 내재화**. 이걸 감당할 담당자가 없으면 만들지 말 것.

---

## 부록. 한 줄 요약
> **"바이브 코딩으로 MVP는 며칠이면 가능하지만, 순수 웹으로는 시프티만큼의 부정출근 방지가 안 된다."**
> 만들 수 있고 비용도 거의 0이지만, 결정은 '개발 가능성'이 아니라 '방지 강도 타협 + 유지보수·법적 책임을 누가 질 것인가'로 내려야 한다.
