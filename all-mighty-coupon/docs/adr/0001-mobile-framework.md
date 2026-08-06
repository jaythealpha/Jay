# ADR-0001: 모바일 프레임워크 — Flutter

- 상태: 채택됨 (Milestone 0에서 구현)
- 날짜: 2026-08-06

## 결정

Flutter(+Dart) 단일 코드베이스로 iOS/Android를 커버한다.
상태 관리는 Riverpod, 라우팅은 GoRouter, 네트워크는 Dio.

## 근거

- 개인 쿠폰 지갑은 카메라·공유 시트·푸시·바코드 렌더링 등 플랫폼 기능이
  필요하지만, 대부분 성숙한 Flutter 플러그인(ML Kit 포함)이 존재한다.
- 단일 팀이 두 플랫폼을 동시에 출시해야 하므로 코드베이스 이원화 비용이 크다.
- Google ML Kit Barcode Scanning의 Flutter 지원이 검증되어 있어
  Three-Second Capture 요구를 충족할 수 있다.

## 대안

- 네이티브 2벌(Swift/Kotlin): 품질 최상이나 리소스 2배 — 기각.
- React Native: 가능하나 바코드/카메라 파이프라인 성숙도와 렌더링 일관성에서
  Flutter 우위 판단.

## 결과

- M0에서 불변 모델은 수동 작성(코드젠 없음). 모델 수가 늘면 Freezed 도입 검토.
- 웹 지원은 비목표.
