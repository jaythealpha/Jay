# 요기보 B2B 파이프라인 추적 시트 가이드

`pipeline_template.csv`를 Google Sheets로 임포트해서 사용하세요.
(파일 → 가져오기 → 쉼표 구분 / 인코딩 UTF-8)

---

## 1. 컬럼 정의

### 기본 정보 (수집 단계)
| 컬럼 | 설명 | 예시 |
|---|---|---|
| `id` | 고유 ID (자동증가) | 1, 2, 3… |
| `target_name` | 기관명 | 서울OO고등학교 |
| `target_type` | school / library / gov | school |
| `sub_type` | 초/중/고/공공도서관/시청 등 | 고등학교 |
| `region` | 시도 | 서울특별시 |
| `contact_person` | 담당자 성함·직책 | 홍길동 행정실장 |
| `contact_dept` | 부서명 | 행정실 |
| `contact_email` | 이메일 | admin@... |
| `phone` | 연락처 | 02-000-0000 |
| `homepage` | 홈페이지 | http://... |
| `est_budget_tier` | S(>3,000만) / A(1,000~3,000만) / B(<1,000만) | A |
| `segment_priority` | P1(이번주) / P2(이번달) / P3(분기) | P1 |

### 발송 단계
| 컬럼 | 설명 |
|---|---|
| `first_send_date` | 1차 메일 발송일 (YYYY-MM-DD) |
| `template_used` | A-1 / A-2 / B-1 / C-1 등 |
| `subject_line` | 실제 사용한 제목 (A/B 추적) |
| `opened_at` | 메일 오픈 시각 (가능 시) |
| `replied_at` | 회신 시각 |
| `response_label` | COLD / WARM / HOT / DEAD |
| `follow_up_date` | 2차 팔로업 예정일 |

### 협상·계약 단계
| 컬럼 | 설명 |
|---|---|
| `sample_sent` | TRUE / FALSE |
| `proposal_sent` | TRUE / FALSE |
| `quote_amount_krw` | 견적 금액 |
| `procurement_channel` | 나라장터 / S2B / 수의계약 / 입찰 |
| `expected_close_date` | 예상 클로징일 |
| `stage` | Prospect → Contacted → Qualified → Proposal → Negotiation → Won/Lost |
| `probability_pct` | 단계별 가중치 (아래 표) |
| `weighted_revenue_krw` | = quote × probability/100 (예측 매출) |
| `actual_revenue_krw` | 실 매출 (계약 완료 시 입력) |
| `won_lost_date` | 종결일 |
| `lost_reason` | 예산부족 / 경쟁사 / 일정연기 / 기타 |
| `next_action` | 다음 액션 (자연어) |
| `owner` | 담당자 (요기보 내부) |
| `notes` | 자유 메모 |

---

## 2. 스테이지 가중치 (수식 자동화용)

| Stage | Probability |
|---|---|
| Prospect | 10% |
| Contacted (회신 받음) | 25% |
| Qualified (예산·시기 확인) | 40% |
| Proposal (제안서 송부) | 55% |
| Negotiation (견적 검토 중) | 75% |
| Verbal Commit (구두 확정) | 90% |
| Won | 100% |
| Lost | 0% |

Google Sheets 수식 예 (M열에 stage가 있다고 가정):

```
=IFS(M2="Prospect",10, M2="Contacted",25, M2="Qualified",40,
     M2="Proposal",55, M2="Negotiation",75, M2="Verbal Commit",90,
     M2="Won",100, M2="Lost",0)
```

가중 매출 (`weighted_revenue_krw`) 자동 계산:

```
=IF(AND(ISNUMBER(quote_amount_krw), ISNUMBER(probability_pct)),
    quote_amount_krw * probability_pct / 100, 0)
```

---

## 3. 목표 매출 1억 원 역산 — 대시보드 권장 KPI

상단 요약 시트에 아래 6개 셀만 두면 충분합니다.

| KPI | 수식 (개념) | 목표치 |
|---|---|---|
| 총 타겟 수 | COUNTA(`target_name`) | 800~1,200 |
| 발송 완료 | COUNTA(`first_send_date`) | 800+ |
| 회신율 | 회신 / 발송 | ≥ 3% |
| Proposal 진입 수 | COUNTIF(`stage`, ">=Proposal") | 30+ |
| 가중 파이프라인 합 | SUM(`weighted_revenue_krw`) | 1.5억+ |
| 실 매출 합 | SUM(`actual_revenue_krw`) | **100,000,000** |

> 1억 매출을 90% 확률로 달성하려면 **가중 파이프라인이 1.5억** 쌓여 있어야 안전합니다.

---

## 4. 운영 리듬 (주간 워크플로)

| 요일 | 작업 |
|---|---|
| 월 | 신규 타겟 100건 추가 (수집 스크립트 실행) |
| 화 | 1차 메일 발송 (50건) |
| 수 | 1차 메일 발송 (50건) + 전주 회신 처리 |
| 목 | 7일 경과 미응답 건 2차 팔로업 (단문) |
| 금 | 파이프라인 리뷰 — `stage` 업데이트, `next_action` 갱신 |

월 1회: 가중 매출 vs 목표 비교 → 채널/세그먼트 비중 조정

---

## 5. 데이터 위생 규칙

1. **수신거부(DEAD)** 라벨이 붙은 행은 발송 리스트에서 영구 제외 — 절대 재발송 금지 (정보통신망법)
2. **개인정보**(담당자명·이메일)는 별도 시트에서 ID로만 참조 — 마스터 시트에는 기관 단위만
3. **백업**: 매주 금요일 CSV export → Google Drive `b2b-pipeline-archive/` 폴더
4. 메일 발송 도구는 **개인정보 처리위탁 계약**이 체결된 곳만 사용 (Stibee, 메일침프 한국 리셀러 등)
