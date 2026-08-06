# Docker

개발용 Docker Compose 파일은 모노레포 루트(`all-mighty-coupon/docker-compose.yml`)에
있다 — `docker compose up -d` 한 번으로 PostgreSQL 16 + Redis 7이 뜬다.

프로덕션 컨테이너 이미지(Dockerfile)는 배포 준비 단계(M2 이후)에서 이 디렉터리에
추가한다.
