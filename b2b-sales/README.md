# 요기보 B2B 영업 실행 키트

> 목표: 학교·도서관·관공서 대상 B2B 매출 **1억 원** 달성
> 작성일: 2026-05-14

## 구조

```
b2b-sales/
├── scripts/
│   ├── collect_targets.py    # 공공데이터 → 타겟 CSV 수집
│   └── enrich_contacts.py    # 홈페이지 크롤링으로 이메일 보강
├── templates/
│   ├── cold_email_templates.md   # 학교/도서관/관공서용 3종
│   └── proposal_template.md      # 공문 형식 제안서 마스터
└── tracking/
    ├── pipeline_template.csv     # Google Sheets 임포트용
    └── README.md                 # 사용 가이드 + KPI
```

## 빠른 실행 순서

```bash
# 1. API 키 발급 후 환경변수 등록
export SCHOOLINFO_KEY=...      # https://open.neis.go.kr
export LIBSEOUL_KEY=...        # https://www.data4library.kr
export DATA_GO_KR_KEY=...      # https://www.data.go.kr

# 2. 타겟 수집 (예: 서울 학교)
python b2b-sales/scripts/collect_targets.py --type school --region 서울특별시

# 3. 이메일 보강
python b2b-sales/scripts/enrich_contacts.py \
    --input b2b-sales/data/targets_school_서울특별시.csv

# 4. 파이프라인 시트 임포트 → Google Sheets

# 5. cold_email_templates.md 를 토대로 발송 (주 100건 페이스)
```

## 1억 매출 도달 시뮬레이션

| 채널 | 타겟 수 | 회신율 | 전환율 | 평균 단가 | 예상 매출 |
|---|---|---|---|---|---|
| 학교 (그린스마트/혁신학교) | 400 | 4% | 35% | 500만 | 2,800만 |
| 공공도서관 (어린이실) | 250 | 5% | 40% | 600만 | 3,000만 |
| 관공서 (청년·민원·복지) | 200 | 3% | 30% | 800만 | 1,440만 |
| 조달청 종합쇼핑몰 인바운드 | — | — | — | — | 2,800만 |
| **합계** | 850 | — | — | — | **약 1억 40만** |

## 주의

- 정보통신망법: 영리 목적 전자우편 발송 시 **제목에 (광고) 표기 의무**가 있으나,
  공공기관·기업 대상 **사업 제안 1:1 메일**은 광고성 정보의 정의에서 제외될 수 있음
  (방통위 가이드 참조). 다만 **수신거부 의사 명시 즉시 발송 중단** 원칙은 지킬 것.
- 개인정보보호법: 공개된 기관 대표 이메일은 합법적 활용 가능하나,
  특정 개인의 사적 정보를 수집·축적하지 말 것.
