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

## Milestone 2에서 추가 구현됨

- **오프라인 검색·필터·정렬**: 캐시는 항상 전체 목록 스냅샷을 저장하고,
  오프라인에서는 서버와 동일한 필터/정렬 규칙을 로컬로 적용
  (`wallet_query.dart` `applyQueryLocally`, 단위 테스트 포함).
- **오프라인 사용 완료 임시 처리**: redeem이 네트워크 오류로 실패하면
  `PendingActionQueue`(중복 제거)에 저장하고 사용자에게 안내. 다음 지갑
  조회/새로고침 시 `SyncService`가 재생 — 네트워크 오류면 유지, 서버 거부
  (이미 사용됨 등)면 서버 상태 우선으로 큐에서 제거. 이벤트 로그는 서버에
  보존.
- **바코드 오프라인 표시**: 열람 성공 시 기기 보안 저장소(BarcodeVault,
  flutter_secure_storage)에 캐시. 오프라인이면 배너와 함께 캐시 표시,
  캐시도 없으면 오류 + 재시도.
- 세션 만료는 오프라인 폴백에서 제외 — 인증 문제를 캐시 데이터로 가리지
  않는다.

## 설계됨 · 미구현

- **Drift 구조화 로컬 DB** (ADR-0003 갱신): 스냅샷 캐시가 M2의 오프라인
  요구(목록·검색·필터·바코드)를 충족했다. Drift는 양방향 필드 동기화·부분
  갱신이 필요해지는 시점(M3+)에 도입한다.
- 필드 수정의 오프라인 큐잉·충돌 해소(현재는 redeem만 큐잉).
