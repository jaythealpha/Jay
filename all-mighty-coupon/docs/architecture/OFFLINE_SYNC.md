# Offline & Sync

원칙: **Offline First for Redemption** — 매장에서 통신이 나빠도 최근 동기화된
쿠폰과 바코드를 열 수 있어야 한다.

## 구현됨 (Milestone 0)

- `CouponCache` 인터페이스 + `SharedPrefsCouponCache` 구현
  (`apps/mobile/lib/core/storage/coupon_cache.dart`):
  마지막 성공 응답의 JSON 스냅샷 + 동기화 시각 저장.
- `CouponRepository`: 네트워크 우선 → 실패 시 캐시 폴백.
  캐시 응답은 `fromCache: true`로 표시되고 UI가 오프라인 배너를 띄운다
  — 캐시 데이터가 실시간 데이터처럼 보이지 않게 한다.
- 캐시도 비어 있으면 사용자용 오류 + 다시 시도.
- 단위 테스트: 캐시 라운드트립, 폴백, 캐시 미스 rethrow.

## 설계됨 · 미구현

- **Drift 구조화 로컬 DB** (M2, ADR-0003): 검색·필터를 오프라인에서 수행하려면
  키-밸류 스냅샷으로는 부족하다. 스냅샷 캐시는 그때 Drift로 대체.
- **오프라인 사용 완료 임시 처리** (M2): 로컬에 REDEEMED 마킹 → 네트워크 복구
  시 서버 반영. 충돌 규칙: 서버가 이미 EXPIRED/REDEEMED면 사용자에게 고지 후
  서버 상태 우선, 단 사용자의 명시적 동작(사용 완료)은 유실하지 않고 이벤트로
  기록.
- **바코드 오프라인 표시** (M2): 바코드 페이로드를 기기 보안 저장소
  (flutter_secure_storage)에 캐시, 앱 활성 상태에서만 표시.
