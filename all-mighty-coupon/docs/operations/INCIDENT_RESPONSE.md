# Incident Response

Milestone 0은 로컬 개발 단계로 프로덕션 운영이 없다. 아래는 개발 환경
트러블슈팅과 프로덕션 도입 전 준비 사항이다.

## 개발 환경 진단

```bash
docker compose ps                    # postgres/redis 상태 (healthy 여야 함)
curl localhost:3001/health           # {"status":"ok", components...}
docker compose logs postgres redis   # 인프라 로그
```

| 증상                                               | 원인/조치                                                                                    |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| API 부팅 실패: "Invalid environment configuration" | .env 누락/오류 — .env.example 복사 후 값 확인                                                |
| health `database: down`                            | compose 미기동, DATABASE_URL 불일치, 마이그레이션 미적용(`npm run db:migrate`)               |
| health `redis: down`                               | redis 컨테이너 확인, REDIS_URL 확인                                                          |
| e2e 테스트 실패                                    | compose가 떠 있고 마이그레이션이 적용된 상태여야 함                                          |
| 모바일에서 연결 실패                               | Android 에뮬레이터는 `10.0.2.2`, 실기기는 호스트 LAN IP를 `--dart-define=AMC_API_BASE_URL`로 |

## 사고 대응 원칙 (프로덕션 전 확정 필요)

- 로그·오류 추적에 바코드 원문/원본 이미지/OCR 전문이 절대 없어야 한다는
  전제를 사고 조사 시에도 유지한다 (마스킹 우회 금지).
- 사용자 데이터 유출 의심 시: 우선 signed URL 발급 중단 → 토큰 무효화 →
  영향 범위 산정(CouponEvent/Audit 로그) 순서.
- DB 복구는 마이그레이션 이력(`apps/api/prisma/migrations`)과 백업 기준.
- 심각도/에스컬레이션/사후 리뷰 프로세스는 첫 배포 전 이 문서에 확정한다.
