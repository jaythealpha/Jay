# 🎨 블록 블라스트 — 에셋 생성 키트

> **왜 이 파일이 있나요?**
> Higgsfield 무제한/무료 생성은 **Claude Code(클라우드) 세션에서는 차단**되어 있습니다.
> 백엔드 안내: *"무제한 생성은 Claude chat, Claude Cowork, ChatGPT에서 이용 가능"*.
> 그래서 **지원 환경에서 아래 프롬프트를 복붙 → 생성 → PNG 저장 → `assets/blockblast/`에 커밋**하면 됩니다.
> 게임 코드(`blockblast.html`)는 **파일이 존재하는 순간 이모지를 스프라이트로 자동 교체**합니다. 코드 수정 불필요.

---

## ✅ 공통 설정 (모든 몬스터 동일)

| 항목 | 값 |
|---|---|
| 모델 | **GPT Image 2.6** (`gpt_image_2_6`) 또는 Nano Banana Pro |
| 비율 | **1:1 (정사각형)** |
| 배경 | **투명 (transparent)** |
| 포맷 | **PNG** |
| 품질 | medium 이상, 1k |
| 🔑 **스타일 레퍼런스** | **`assets/blockblast/mon_jiji.png` 또는 `mon_bangul.png`를 레퍼런스 이미지로 첨부** → 15종과 톤·외곽선·픽셀 질감이 일치함 |

**공통 스타일 문구 (모든 프롬프트 앞에 자동 포함되는 개념):**
> Cute chunky chibi **pixel-art** video game monster sprite, thick dark outline, vibrant retro 16-bit pixel shading, bold clean pixels, big sparkly eyes, rosy cheeks, friendly happy smile, full body, centered, facing forward, single character, **transparent background**, square kawaii game icon. Match the art style of the attached reference sprite.

---

## 🧊 몬스터 9종 — 프롬프트 & 저장 파일명

### 1. 서리곰 (얼음) → `mon_seorigom.png`
```
A round fluffy frost BEAR made of pale icy-blue crystal fur, tiny stubby limbs,
little ice shards on its back, soft frosty cheeks. Pale blue + white palette.
[공통 스타일 문구 적용]
```

### 2. 눈송이 (얼음) → `mon_nunsongi.png`
```
A tiny living SNOWFLAKE sprite, six-point crystalline white-and-cyan body,
a cute round face in the center, glittering frost sparkles. Icy white + cyan palette.
[공통 스타일 문구 적용]
```

### 3. 빙하펭 (얼음) → `mon_binghapeng.png`
```
A chubby baby PENGUIN standing on a small ice floe, blue-white feathers,
orange tiny beak and feet, a little frost crown of ice. Glacier blue palette.
[공통 스타일 문구 적용]
```

### 4. 바위돌이 (바위) → `mon_bawidori.png`
```
A chunky rock GOLEM, grey boulder body with blocky stone arms,
a patch of green moss on top, friendly pebble eyes. Grey + mossy green palette.
[공통 스타일 문구 적용]
```

### 5. 모래여우 (바위) → `mon_moraeyeou.png`
```
A desert sand FOX, tan and sandy-gold fur, big pointy ears, fluffy tail,
small sand swirls around its paws. Warm sand-tan + ochre palette.
[공통 스타일 문구 적용]
```

### 6. 수정사슴 (바위) → `mon_sujeong.png`
```
A small CRYSTAL DEER fawn, soft lavender body, translucent gemstone antlers
that sparkle, gentle shiny eyes. Amethyst purple + crystal pink palette.
[공통 스타일 문구 적용]
```

### 7. 번개토끼 (전기) → `mon_beongaetokki.png`
```
A yellow lightning RABBIT, chubby body, long zigzag lightning-bolt shaped ears,
tiny spark cheeks, electric energy crackle. Bright yellow + electric blue palette.
[공통 스타일 문구 적용]
```

### 8. 화산아기 (불) → `mon_hwasanagi.png`
```
A chubby VOLCANO BABY creature, orange-red molten body, a little volcano-cone
hat with tiny lava bubbles and smoke puff, warm glowing cheeks. Lava orange + red palette.
[공통 스타일 문구 적용]
```

### 9. 황금몽 — 보스 (레전드) → `mon_hwanggeummong.png`
```
A majestic GOLDEN KING monster (BOSS), regal shiny gold body, a jeweled golden
CROWN, a small royal cape, confident grin, radiant sparkles and a subtle aura.
Slightly larger and grander than normal monsters. Luxurious gold + ruby-red palette.
[공통 스타일 문구 적용]
```

---

## 🖼️ (선택) UI·배경 에셋 — 여유 있을 때

게임은 이것들이 없어도 이모지/그라디언트로 정상 동작합니다. 생성 시 아래 파일명으로 저장:

| 파일명 | 프롬프트 요지 | 비율/배경 |
|---|---|---|
| `mon_` 9종 | **(위 최우선)** | 1:1 / 투명 |
| `ui_bomb.png` | 귀여운 픽셀아트 폭탄 아이콘, 빨간 도화선 | 1:1 / 투명 |
| `ui_hammer.png` | 귀여운 픽셀아트 나무+쇠 망치 아이콘 | 1:1 / 투명 |
| `ui_refresh.png` | 귀여운 픽셀아트 초록 순환 화살표 아이콘 | 1:1 / 투명 |
| `ui_logo.png` | "블록 블라스트" 픽셀아트 로고 레터링, 몬스터 테마, 네온 | 3:1 가로 / 투명 |
| `bg_ice.png` | 몽환적 빙하 밤하늘 배경, 별+오로라, 어두운 톤 (게임 가독성 위해 로우 콘트라스트) | 9:16 세로 / 불투명 |
| `bg_volcano.png` | 몽환적 화산 밤하늘 배경, 용암+불씨, 어두운 톤 (로우 콘트라스트) | 9:16 세로 / 불투명 |

> ⚠️ 배경(`bg_*`)은 블록이 위에 올라가므로 **어둡고 대비가 낮아야** 몬스터가 잘 보입니다. "dark, low-contrast, muted, dreamy night" 강조.

---

## 📥 생성 후 적용 방법 (3단계)

1. 생성한 PNG들을 정확한 파일명으로 **`assets/blockblast/`** 에 저장
2. 커밋:
   ```bash
   git add assets/blockblast/mon_*.png
   git commit -m "assets: add remaining 9 monster sprites"
   git push
   ```
3. 게임 새로고침 → 해당 몬스터가 이모지에서 **픽셀 스프라이트로 자동 교체**됨 ✨
   (코드는 `blockblast.html`의 `mon_<id>.png` 자동 로드 로직이 이미 처리)

---

## 🎯 몬스터 id ↔ 파일명 매핑 (참고)

| id | 이름 | 타입 | 파일 | 상태 |
|---|---|---|---|---|
| jiji / bulkkori / hwaryong / mongbul / bangul / padowang / mulyong / saessak / kkotbong / mironyang / kkummong / kulkul / yeoubyeol / pungseon / yuryeong | 15종 | 혼합 | `mon_*.png` | ✅ 완료 |
| seorigom | 서리곰 | ice | `mon_seorigom.png` | ⬜ 생성 필요 |
| nunsongi | 눈송이 | ice | `mon_nunsongi.png` | ⬜ 생성 필요 |
| binghapeng | 빙하펭 | ice | `mon_binghapeng.png` | ⬜ 생성 필요 |
| bawidori | 바위돌이 | rock | `mon_bawidori.png` | ⬜ 생성 필요 |
| moraeyeou | 모래여우 | rock | `mon_moraeyeou.png` | ⬜ 생성 필요 |
| sujeong | 수정사슴 | rock | `mon_sujeong.png` | ⬜ 생성 필요 |
| beongaetokki | 번개토끼 | electric | `mon_beongaetokki.png` | ⬜ 생성 필요 |
| hwasanagi | 화산아기 | fire | `mon_hwasanagi.png` | ⬜ 생성 필요 |
| hwanggeummong | 황금몽 (보스) | legend | `mon_hwanggeummong.png` | ⬜ 생성 필요 |
