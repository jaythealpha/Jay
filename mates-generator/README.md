# Yogibo Mates 이미지 프롬프트 생성기

[`yogibo.jp/collections/mates`](https://yogibo.jp/collections/mates) 페이지의 모든 메이트
캐릭터를 다양한 화풍(수채화, 유화, 애니메이션, 3D 등)으로 그릴 수 있는
**상세 이미지 생성 프롬프트**를 자동으로 만들어 주는 정적 웹 도구입니다.

> ⚠️ 주의 — 본 작업 환경에서는 `yogibo.jp` 도메인으로의 외부 요청이 차단되어
> 자동 스크래핑이 불가능했습니다. 따라서 `characters.json` 의 라인업은
> 일반적으로 알려진 Yogibo Mates 캐릭터를 기반으로 작성한 시드 데이터입니다.
> 실제 페이지와 차이가 있을 수 있으니 `라이브 사이트와의 동기화` 섹션을 참고해 갱신하세요.

## 사용 방법

### 1) 정적 서버로 띄우기

`fetch()` 가 `file://` 에서 막히기 때문에 간단한 HTTP 서버가 필요합니다.

```bash
cd mates-generator
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000 접속
```

### 2) UI 흐름

1. **캐릭터 선택** — 좌측 그리드에서 메이트 한 마리를 클릭합니다. 검색창으로
   한국어/영어/일본어 이름과 태그를 모두 검색할 수 있어요.
2. **화풍 선택** — 수채화, 유화, 연필 스케치, 일본 애니, 지브리풍, Pixar 3D,
   클레이메이션, 펠트 공예, 픽셀 아트, 우키요에 등 20여 종의 프리셋 중 하나를 고릅니다.
3. **세부 옵션 (선택)** — 포즈, 배경, 분위기, 조명, 카메라 구도, 화면 비율을
   취향에 맞게 조정합니다.
4. **대상 도구** — 범용 / Midjourney / Stable Diffusion / DALL·E 중 출력 포맷을 고릅니다.
   - Midjourney: `--ar`, `--v` 등 파라미터 자동 추가
   - Stable Diffusion: positive/negative 프롬프트 분리 출력
   - DALL·E: 자연어 지시문 형태
5. **프롬프트 생성** — 결과를 결과 영역에 표시하고 한 번에 복사할 수 있습니다.
6. **선택 캐릭터 × 모든 화풍** — 같은 캐릭터를 모든 스타일로 일괄 생성합니다.

## 파일 구조

```
mates-generator/
├── index.html        # UI
├── style.css         # 디자인
├── app.js            # 프롬프트 빌더 로직
├── characters.json   # 캐릭터 DB (편집 가능)
├── styles.json       # 화풍 프리셋 DB (편집 가능)
└── README.md
```

## 캐릭터 데이터 스키마

`characters.json > characters[]`

| 필드 | 설명 |
| --- | --- |
| `id` | 고유 슬러그 (URL-safe) |
| `name_ja / name_ko / name_en` | 다국어 이름 |
| `species` | 동물 종류(영문, 프롬프트에 직접 사용) |
| `silhouette` | 전체 형태/비율 — 프롬프트에서 가장 결정적인 정보 |
| `palette` | 컬러 팔레트(HEX/색명, 영문) |
| `features` | 무늬·표정·부속물 등 디테일 |
| `personality` | 성격 키워드(영문) — 무드 생성에 활용 |
| `signature_pose` | 사용자가 포즈를 비워뒀을 때의 기본 포즈 |
| `tags` | 검색·필터용 키워드 |

## 화풍 데이터 스키마

`styles.json > styles[]`

| 필드 | 설명 |
| --- | --- |
| `id` | 고유 슬러그 |
| `name_ko / name_en` | 표시 이름 |
| `prompt` | 캐릭터 묘사 뒤에 붙는 스타일 절(영문) |
| `negative` | (선택) Stable Diffusion용 negative prompt 보조 |

## 프롬프트가 만들어지는 방식

```
[base]   Yogibo Mate plush character "{name_en}" ({species}),
         silhouette: {silhouette},
         color palette: {palette},
         signature features: {features},
         personality: {personality}

[extras] pose: {pose | signature_pose},
         setting: {scene}, mood: {mood},
         lighting: {lighting}, composition: {camera}

[style]  {style.prompt}

[tail]   aspect ratio / 도구별 파라미터
```

도구별로 위 조립 결과가 자연어 / `--ar` 플래그 / negative 분리 형태로 변환됩니다.

## 라이브 사이트와의 동기화

`yogibo.jp` 가 접근 가능한 환경에서 실제 라인업을 가져오려면:

```bash
# 1) Shopify 표준 엔드포인트(공개) 호출
curl -A "Mozilla/5.0" \
  "https://yogibo.jp/collections/mates/products.json?limit=250" \
  > products.json

# 2) products.json 의 각 product 를 characters.json 의 스키마로 매핑
#    - title       -> name_ja
#    - handle      -> id
#    - product_type / tags -> species, tags
#    - images[0].src -> 참고용
#    silhouette / palette / features 등은 이미지를 보고 사람이 작성/보완
```

추가/수정한 캐릭터는 그대로 `characters.json` 에 넣으면 UI가 자동으로 반영합니다.

## 라이선스 / 권리 고지

Yogibo Mates 캐릭터 IP는 ㈜Yogibo의 자산입니다. 본 도구는 **개인 학습 · 팬아트 ·
프롬프트 작성 보조** 목적이며, 생성된 이미지를 상업적으로 활용하기 전에는
권리자에게 별도 허가를 받으세요.
