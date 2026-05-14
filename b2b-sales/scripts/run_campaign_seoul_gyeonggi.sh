#!/usr/bin/env bash
#
# 1차 캠페인 데이터 수집 — 서울 + 경기
# 실행 위치: 프로젝트 루트 (b2b-sales의 부모 디렉토리)
# 소요 시간: 약 5~8분 (NEIS 페이지 수가 많음)
#
# 선행조건: .env 또는 ~/.bashrc 에 세 키가 모두 설정되어 있을 것
#
set -euo pipefail

cd "$(dirname "$0")/.."   # b2b-sales/

mkdir -p data logs

echo "[1/6] 키 검증..."
python scripts/verify_keys.py | tee logs/verify.log
if ! grep -q "✅ NEIS" logs/verify.log; then
    echo "NEIS 키 검증 실패. 중단합니다." >&2
    exit 1
fi

echo "[2/6] 서울 학교 수집..."
python scripts/collect_targets.py --type school   --region 서울특별시 2>&1 | tee logs/seoul_school.log

echo "[3/6] 경기 학교 수집..."
python scripts/collect_targets.py --type school   --region 경기도       2>&1 | tee logs/gyeonggi_school.log

echo "[4/6] 서울 도서관 수집..."
python scripts/collect_targets.py --type library  --region 서울특별시 2>&1 | tee logs/seoul_library.log

echo "[5/6] 경기 도서관 수집..."
python scripts/collect_targets.py --type library  --region 경기도       2>&1 | tee logs/gyeonggi_library.log

echo "[6/6] 서울/경기 관공서 수집..."
python scripts/collect_targets.py --type gov      --region 서울특별시 2>&1 | tee logs/seoul_gov.log
python scripts/collect_targets.py --type gov      --region 경기도       2>&1 | tee logs/gyeonggi_gov.log

echo
echo "=== 수집 완료. data/ 폴더 확인 ==="
ls -lh data/

echo
echo "다음 단계: python scripts/prioritize.py 실행 → 상위 200건 추출"
