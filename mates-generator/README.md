# Yogibo Mates 이미지 프롬프트 생성기

[`yogibo.jp/collections/mates`](https://yogibo.jp/collections/mates) 페이지의 모든 메이트
캐릭터를 다양한 화풍(수채화, 유화, 애니메이션, 3D 등)으로 그릴 수 있는
**상세 이미지 생성 프롬프트**를 자동으로 만들어 주는 정적 웹 도구입니다.

## 📊 캐릭터 데이터 현황 (2026-07-31 전면 교체)

이전 `characters.json` 은 "일반적으로 알려진 캐릭터" 24종을 추정해 만든 시드 데이터였습니다.
실제 라인업과 대조해 보니 **24종 중 9종만 실존**했고, 캐릭터 이름이 전부 "강아지 메이트"처럼
종 이름으로 되어 있었으며(실제 메이트는 방울이·미호·릴리처럼 고유 이름을 가진 캐릭터입니다),
색상값(`#F1D7B0` 등)도 근거 없이 만들어진 값이었습니다. 그래서 데이터를 전부 새로 만들었습니다.

| 항목 | 상태 |
|---|---|
| 캐릭터 수 | **33종** (Mate 31 + Roll Mate 엘리게이터 + Plant Mate 사니) |
| 캐릭터 이름 | 🟢 실제 이름 — 일본어(アーネスト)·영문(Ernest)·한국어(옐리) |
| 종 · 성격 | 🟢 공식 제품 페이지 소개 문구 기준 |
| 실루엣 · 특징 | 🟡 종 + 메이트 공통 디자인에서 도출한 일반 서술 (실물 대조 전) |
| **색상(palette)** | 🔴 **미검증 — 전부 비어 있음** (아래 참고) |
| 한국 판매 여부 | 🟢 사내 제품 레지스트리 기준 16종 표시 + 실물 제품컷 링크 |

### 색상을 비워 둔 이유

색을 지어내 넣으면 실제 제품과 다른 색으로 그려지므로, 확인되지 않은 색은 **아예 넣지 않습니다.**
대신 프롬프트에 `colours: match the official product photo exactly` 를 넣고, 결과 화면에
**실물 제품컷 링크**를 띄웁니다. 그 사진을 이미지 생성 도구에 함께 넣으면 실제 색으로 나옵니다.

실물을 보고 색을 확정했다면 해당 캐릭터의 `palette` 를 채우고 `palette_status` 를
`"verified"` 로 바꾸세요. 그때부터 프롬프트에 색상 문구가 직접 들어갑니다.

> ⚠️ 로스터 출처 — 이 작업 환경에서는 `yogibo.jp` 직접 접근이 차단(403)되어,
> 공식 제품 페이지의 **제목·소개 문구 검색 결과**와 **사내 제품 레지스트리**를 근거로 구성했습니다.
> 접근 가능한 환경이라면 아래 `라이브 사이트와의 동기화` 로 한 번 더 대조해 주세요.

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
#    - images[0].src -> reference_360 / 색상 확인용
#    silhouette / features 는 이미지를 보고 보완, palette 는 실물 색을 확인해 채운다
```

추가/수정한 캐릭터는 그대로 `characters.json` 에 넣으면 UI가 자동으로 반영합니다.

`silhouette` · `features` · `personality` · `signature_pose` 는 **프롬프트에 그대로 들어가므로
영문으로** 작성하세요 (이미지 생성 도구가 영문 프롬프트에 맞춰져 있습니다).
UI에 보이는 이름(`name_ko` · `name_ja`)만 현지어를 유지합니다.

## 라이선스 / 권리 고지

Yogibo Mates 캐릭터 IP는 ㈜Yogibo의 자산입니다. 본 도구는 **개인 학습 · 팬아트 ·
프롬프트 작성 보조** 목적이며, 생성된 이미지를 상업적으로 활용하기 전에는
권리자에게 별도 허가를 받으세요.
