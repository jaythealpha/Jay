# 포스터 프리셋 이미지 30장 생성 프롬프트

포스터 탭의 예시 이미지를 GPT(ChatGPT 이미지 생성 또는 OpenAI 이미지 API)로 만들 때 쓰는 프롬프트입니다.
두 가지 방법이 있습니다.

- **방법 A — ChatGPT 대화창**: 아래 "마스터 프롬프트"를 붙여 넣으면 30장을 순서대로 만들어 줍니다. 한 번에 다 나오지 않으면 `계속`이라고 입력하세요.
- **방법 B — API 일괄 생성**: 아래 스크립트로 30장을 한 번에 자동 생성합니다. API 키는 본인 컴퓨터의 환경변수로만 넣으세요(채팅·파일에 붙여 넣지 마세요).

완성된 이미지를 올려 주시면 WebP로 변환해 `assets/poster/poster-01.webp …` 로 넣고, 포스터 예시(제목·부제·안내 문구 4개 언어)를 붙이겠습니다.

## 공통 규칙 (모든 이미지에 적용)

| 항목 | 규칙 | 이유 |
|---|---|---|
| 크기 | 세로 1024×1536 (2:3) | 4:5 피드와 9:16 스토리로 모두 잘라 쓰기 좋음 |
| 구도 | 주제는 위쪽 60% 안, 아래쪽 35%는 단순하고 어두운 여백(바닥·하늘·그림자) | 아래에 제목·문구·QR 카드가 들어감 |
| 금지 | 글자, 숫자, 로고, 워터마크, 서명, QR 코드, 실존 브랜드·유명 캐릭터·유명 작품 | 사용자 문구와 겹침, 상표·저작권 문제 |
| 인물 | 있어도 되지만 실존 인물처럼 보이지 않게, 정면 클로즈업 피하기 | 초상권·용도 범용성 |
| 품질 | 잡지·광고 수준, 선명한 초점, 자연스러운 조명 | 포스터 배경으로 바로 사용 |

## 방법 A — ChatGPT 마스터 프롬프트 (그대로 복사)

```
You are generating 30 background images for poster templates. Create them ONE BY ONE in order (1 → 30),
each as a separate image, and label each reply with its number and short name. If you cannot finish
in one reply, stop and continue from the next number when I say "계속" (continue).

Rules for EVERY image:
- Portrait 1024x1536 (2:3).
- Composition: the main subject sits in the upper 60% of the frame. The bottom 35% must be calm,
  simple and darker (floor, table, sky, shadow, water, bokeh) with no important details,
  because a headline and a white QR card will be placed there later.
- Absolutely NO text, letters, numbers, signage words, logos, watermarks, signatures or QR codes.
- No real brands, no famous characters, no famous artworks, no real-person likeness.
  People may appear but not as front-facing close-ups.
- Premium editorial / advertising quality, sharp focus, rich but natural lighting, cohesive colour palette.

The 30 images:
1. Specialty café grand opening — sunlit coffee bar, latte art cup and pastries on marble, warm morning light.
2. Artisan bakery — rustic sourdough loaves and croissants on a wooden counter, flour dust, cosy glow.
3. Modern Korean restaurant — elegant set of banchan dishes on a dark stone table, steam, moody top light.
4. Cocktail bar night — amber cocktail with ice on a dark bar, neon reflections, deep teal and copper tones.
5. Wine tasting evening — glasses of red wine, grapes and candles on a long table in a vineyard at dusk.
6. Flower shop — overflowing bouquets of peonies and ranunculus in a bright shop window, pastel palette.
7. Beauty / skincare launch — glass serum bottles (unbranded) on water ripples with soft pink light.
8. Hair salon — stylish minimalist salon chair, mirrors, warm wood and plants, soft daylight.
9. Fitness studio — dramatic gym with kettlebells and ropes, rim light, energetic red and black tones.
10. Yoga & wellness retreat — mat on a wooden deck facing misty mountains at sunrise, calm greens.
11. Real-estate open house — bright modern living room with large windows and city view, airy whites.
12. Wedding — floral arch with white roses and soft draped fabric in a garden, golden hour.
13. Birthday party — pastel balloons, confetti and a tiered cake on a table, playful but elegant.
14. Kids' art class — colourful paint pots, brushes and paper on a sunny classroom table, cheerful.
15. Live concert — stage lights and haze over a cheering crowd silhouette, purple and blue beams.
16. Jazz night — saxophone on a stool under a warm spotlight in a dim lounge, smoky bokeh.
17. DJ / club party — turntables with glowing neon lines, laser beams, magenta and cyan.
18. Art exhibition — white gallery with abstract colourful paintings (original, not famous works), spotlights.
19. Book fair — stacks of vintage books and reading lamps in a cosy library, warm browns.
20. Outdoor film night — vintage projector beam toward a screen in a park at night, string lights.
21. Fashion sale — clothing rack with seasonal outfits and shopping bags (no logos), clean studio backdrop.
22. Electronics / tech launch — sleek unbranded gadget floating with light trails, dark blue gradient.
23. Hotel & travel — infinity pool overlooking a tropical sea at sunset, palm silhouettes.
24. Camping & outdoor — tent glowing under the Milky Way beside a lake, campfire sparks.
25. Pet shop — happy golden retriever and cat with toys on a soft pastel set, bright and friendly.
26. Startup demo day / conference — modern auditorium with stage, screens glowing (no text), audience from behind.
27. Christmas market — wooden stalls with fairy lights and snow, mulled-wine steam, red and gold.
28. Korean traditional holiday (Chuseok / Seollal) — hanok courtyard with lanterns, songpyeon and persimmons.
29. Summer beach festival — bright beach with umbrellas, surfboards and turquoise waves, high summer sun.
30. Autumn harvest market — pumpkins, apples and baskets on a farm stand with falling maple leaves.
```

## 방법 B — OpenAI API로 30장 한 번에 생성

1. 컴퓨터에 Node.js 18 이상 설치
2. 터미널에서 API 키를 환경변수로 설정 (키는 이 문서나 채팅에 적지 마세요)
   - macOS/Linux: `export OPENAI_API_KEY=...`
   - Windows PowerShell: `$env:OPENAI_API_KEY="..."`
3. 아래 내용을 `gen-posters.mjs` 로 저장하고 `node gen-posters.mjs` 실행 → `poster-images/poster-01.png …` 생성

```js
// gen-posters.mjs — generates 30 portrait poster backgrounds with the OpenAI Images API
import fs from "fs";
const RULES = "Portrait 1024x1536. Main subject in the upper 60%; bottom 35% calm, simple and darker for a headline and a white QR card. " +
  "NO text, letters, numbers, logos, watermarks, signatures or QR codes. No real brands, famous characters, famous artworks or real-person likeness; " +
  "people only from behind or at a distance. Premium editorial advertising quality, sharp focus, natural rich lighting.";
const SCENES = [
  "Specialty café grand opening — sunlit coffee bar, latte art cup and pastries on marble, warm morning light.",
  "Artisan bakery — rustic sourdough loaves and croissants on a wooden counter, flour dust, cosy glow.",
  "Modern Korean restaurant — elegant set of banchan dishes on a dark stone table, steam, moody top light.",
  "Cocktail bar night — amber cocktail with ice on a dark bar, neon reflections, deep teal and copper tones.",
  "Wine tasting evening — glasses of red wine, grapes and candles on a long table in a vineyard at dusk.",
  "Flower shop — overflowing bouquets of peonies and ranunculus in a bright shop window, pastel palette.",
  "Beauty / skincare launch — unbranded glass serum bottles on water ripples with soft pink light.",
  "Hair salon — stylish minimalist salon chair, mirrors, warm wood and plants, soft daylight.",
  "Fitness studio — dramatic gym with kettlebells and ropes, rim light, energetic red and black tones.",
  "Yoga & wellness retreat — mat on a wooden deck facing misty mountains at sunrise, calm greens.",
  "Real-estate open house — bright modern living room with large windows and city view, airy whites.",
  "Wedding — floral arch with white roses and soft draped fabric in a garden, golden hour.",
  "Birthday party — pastel balloons, confetti and a tiered cake on a table, playful but elegant.",
  "Kids' art class — colourful paint pots, brushes and paper on a sunny classroom table, cheerful.",
  "Live concert — stage lights and haze over a cheering crowd silhouette, purple and blue beams.",
  "Jazz night — saxophone on a stool under a warm spotlight in a dim lounge, smoky bokeh.",
  "DJ / club party — turntables with glowing neon lines, laser beams, magenta and cyan.",
  "Art exhibition — white gallery with original abstract colourful paintings, gallery spotlights.",
  "Book fair — stacks of vintage books and reading lamps in a cosy library, warm browns.",
  "Outdoor film night — vintage projector beam toward a screen in a park at night, string lights.",
  "Fashion sale — clothing rack with seasonal outfits and plain shopping bags, clean studio backdrop.",
  "Electronics / tech launch — sleek unbranded gadget floating with light trails, dark blue gradient.",
  "Hotel & travel — infinity pool overlooking a tropical sea at sunset, palm silhouettes.",
  "Camping & outdoor — tent glowing under the Milky Way beside a lake, campfire sparks.",
  "Pet shop — happy golden retriever and cat with toys on a soft pastel set, bright and friendly.",
  "Startup demo day — modern auditorium stage with glowing blank screens, audience seen from behind.",
  "Christmas market — wooden stalls with fairy lights and snow, mulled-wine steam, red and gold.",
  "Korean traditional holiday — hanok courtyard with lanterns, songpyeon rice cakes and persimmons.",
  "Summer beach festival — bright beach with umbrellas, surfboards and turquoise waves, high summer sun.",
  "Autumn harvest market — pumpkins, apples and baskets on a farm stand with falling maple leaves."
];
const KEY = process.env.OPENAI_API_KEY;
if (!KEY) { console.error("Set OPENAI_API_KEY first."); process.exit(1); }
fs.mkdirSync("poster-images", { recursive: true });
for (let i = 0; i < SCENES.length; i++) {
  const n = String(i + 1).padStart(2, "0"), out = `poster-images/poster-${n}.png`;
  if (fs.existsSync(out)) { console.log("skip", out); continue; }          // re-run safely after errors
  const r = await fetch("https://api.openai.com/v1/images/generations", {
    method: "POST",
    headers: { Authorization: "Bearer " + KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ model: "gpt-image-1", prompt: SCENES[i] + " " + RULES, size: "1024x1536", quality: "high", n: 1 })
  });
  const d = await r.json();
  if (!r.ok) { console.error(n, d.error && d.error.message); continue; }
  fs.writeFileSync(out, Buffer.from(d.data[0].b64_json, "base64"));
  console.log("saved", out);
}
```

- 실패한 번호는 다시 실행하면 이미 만든 파일은 건너뛰고 나머지만 만듭니다.
- 모델 이름(`gpt-image-1`)이나 가격은 OpenAI 쪽에서 바뀔 수 있으니 실행 전 OpenAI 문서에서 확인하세요.

## 받은 뒤 할 일 (제가 처리)

1. 30장을 1080×1620 WebP(약 200~300KB)와 작은 미리보기로 변환
2. 이미지마다 제목·부제·안내 문구를 한국어·영어·일본어·중국어로 작성해 포스터 예시에 추가
3. 글자가 섞여 나왔거나 아래 여백이 복잡한 이미지는 다시 생성할 번호를 알려 드림
