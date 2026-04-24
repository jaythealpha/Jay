# Memory App — POC

> 핵심 가설 검증: **"아이 그림 사진 → 살아 움직이는 캐릭터"** 파이프라인이 실제로 동작하는가?

## 무엇을 증명하려는가

Memory App의 심장은 "그림이 움직인다"는 마법이다. 이 마법이 기술적으로 성립하지 않으면 나머지(집, 나라, 친구)는 의미가 없다. 이 POC는 **사람 형태 그림을 자동으로 리깅하고 프리셋 모션으로 움직이게 만드는** 최단 경로를 검증한다.

비목표 (POC 범위 밖):
- 동물·사물 애니메이션 (v2)
- 실시간 처리 (배치/비동기로 충분)
- UI/UX (CLI로 충분)
- 음성 (별도 POC)
- 집/월드 렌더링 (별도 POC)

## 두 가지 트랙

| 트랙 | 도구 | 비용 | 통제 가능성 | POC 우선순위 |
|---|---|---|---|---|
| **A. 결정론적 리깅** | Meta Animated Drawings | 무료(자체 호스팅) | 높음(프리셋 BVH) | **★ 메인** |
| B. 생성형 영상 | Kling/Veo via fal.ai | 유료(초당 $0.05~) | 낮음(프롬프트 의존) | 비교군 |

**트랙 A를 메인으로 잡는 이유**: 앱은 "캐릭터가 집에서 항상 살아있다"는 컨셉이라 *반복 가능한 루프 모션*이 필요하다. 생성형은 매번 다른 결과가 나와서 "우리집의 그 캐릭터" 일관성을 깨뜨린다. 생성형은 "오늘 처음 깨어나는 순간" 같은 특수 모먼트에만 쓰는 게 맞다.

## 구조

```
poc/
├── README.md                    # 이 문서
├── docker-compose.yml           # Animated Drawings TorchServe 기동
├── docker/
│   └── Dockerfile               # Meta repo + 우리 wrapper 설치
├── src/
│   ├── pipeline.py              # CLI 엔트리포인트 (image → GIF)
│   └── tracks/
│       ├── animated_drawings.py # 트랙 A
│       └── generative_api.py    # 트랙 B (fal.ai)
├── scripts/
│   ├── setup.sh                 # 일괄 셋업
│   └── smoke_test.py            # 무거운 모델 없이 환경 검증
├── samples/                     # 테스트용 아이 그림 (.gitkeep)
└── docs/
    ├── success_criteria.md      # 합격/불합격 기준
    └── decision_log.md          # 결정 이력
```

## 실행 방법

### 1. 트랙 A (Animated Drawings, 로컬)

전제: Docker, 8GB+ RAM. GPU 없어도 동작 (CPU 추론, 느림).

```bash
# 1) 빌드 (5~10분, 모델 다운로드 포함)
docker compose up -d --build

# 2) 헬스체크
curl http://localhost:8080/ping
# → {"status":"Healthy"} 가 나와야 함

# 3) 그림 한 장 애니메이션
python3 src/pipeline.py samples/my_kid_drawing.jpg out/
# → out/video.gif 생성됨

# 종료
docker compose down
```

### 2. 트랙 B (Kling, 클라우드)

전제: `FAL_KEY` 환경변수.

```bash
export FAL_KEY="..."
python3 src/pipeline.py --track b samples/my_kid_drawing.jpg out/
```

## 합격 기준

상세는 `docs/success_criteria.md` 참고. 요약:

| 지표 | 목표 | 비고 |
|---|---|---|
| 사람 그림 인식 성공률 | ≥ 70% | 10장 중 7장 이상에서 캐릭터 추출 성공 |
| 자동 리깅 품질 | ≥ 50% 무수정 가능 | 나머지는 수동 보조 UI로 보완 가능해야 함 |
| 처리 시간(CPU) | ≤ 60초/장 | 사용자에겐 비동기로 보여줌 |
| 모션 자연스러움 | 5점 만점 3점 이상 | 부모 5명 블라인드 평가 |

## 결과 (실행 후 채울 것)

- [ ] 도커 빌드 성공
- [ ] 샘플 5장 애니메이션 생성
- [ ] 인식 성공률 측정
- [ ] 모션 품질 평가
- [ ] 처리 시간 기록

> **참고**: 이 POC는 사용자 로컬 머신(Docker 데몬 + 8GB RAM)에서 실행하도록 설계됨. 코드 작성 환경(샌드박스)에서는 `python3 scripts/smoke_test.py`로 레이아웃·문법 검증까지만 수행. 실제 모델 추론은 `bash scripts/setup.sh`로 시작.

## 다음 단계

POC 통과 시:
1. 동물·사물 확장 검증 (트랙 B 비교)
2. 수동 보조 리깅 UI 프로토타입
3. 음성 녹음/합성 POC
4. 2.5D 집 렌더링 POC

POC 실패 시:
- 어느 단계가 실패했는지 분석 → 수동 보조 비중 늘리거나 컨셉 재조정
