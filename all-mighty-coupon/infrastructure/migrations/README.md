# Migrations

데이터베이스 마이그레이션은 Prisma가 관리하며 실제 파일은
`apps/api/prisma/migrations/`에 있다.

- 로컬 적용/생성: `npm run db:migrate` (prisma migrate dev)
- CI/배포 적용: `npm run db:migrate:deploy -w @amc/api` (prisma migrate deploy)

이 디렉터리는 Prisma 외의 인프라 수준 마이그레이션(예: 확장 설치 스크립트)이
필요해질 때 사용한다.
