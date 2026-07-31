# 🦄 키캡 리사이저 — 3MF → 1u + Cherry MX 스템

3D 키캡 파일(`.3mf` / `.glb`)을 브라우저에 끌어다 놓으면 **표준 1u 크기(약 18mm)로 리사이즈**하고
**정확한 Cherry MX 십자 스템**을 넣어 바로 인쇄 가능한 파일로 만들어 줍니다.

> 이 프로젝트는 저장소의 게임·렌즈 시리즈와 별개인 **독립 앱**입니다. `keycap/` 폴더만으로 완전히 동작합니다.

라이브: https://jaythealpha.github.io/Jay/keycap/

## ✨ 무엇을 해 주나요

- 📐 **1u 리사이즈** — 목표 바닥 크기를 지정하면 비율을 유지한 채 스케일 조정
- 🔩 **Cherry MX 스템 생성** — 십자 슬롯 폭·길이(span)·칼라 지름·스템 높이·삽입 깊이를 직접 조절
- 🎨 **GLB 텍스처 → AMS 색상** — GLB의 텍스처 색을 Bambu AMS 필라멘트 수(기본 4색)로 양자화해
  `paint_color`가 들어간 멀티컬러 3MF로 출력
- 🖼️ **레퍼런스 이미지 투영 / 팔레트 적용** — 이미지의 색을 모델에 입히거나, 색상만 뽑아 팔레트로 사용
- 📊 **높이·깊이 컬러 모드** — 텍스처가 지저분할 때 높이 기준으로 깔끔한 색 밴드를 만듭니다
- 👀 **3D 미리보기** — 변환 결과를 돌려 보고 원본/결과 치수를 비교

## 🚀 실행하기

```bash
# 저장소 루트에서
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000/keycap/ 접속
```

ES 모듈(importmap)을 쓰기 때문에 `file://` 로 직접 열면 동작하지 않습니다. 로컬 서버나 HTTPS로 여세요.

## 🔒 파일은 어디로도 가지 않습니다

모든 처리는 **브라우저 안에서만** 실행됩니다. 서버 업로드도, 외부 API 호출도 없습니다.
필요한 라이브러리(JSZip 3.10.1, three.js 0.160.0)는 CDN 대신 **`vendor/` 에 내장**되어 있어
사내망·오프라인에서도 그대로 동작하고, 페이지가 외부로 요청을 보내지 않습니다.

라이브러리를 올릴 때는 `vendor/` 의 파일을 교체하세요 (three.js는 `three.module.js` +
`addons/controls/OrbitControls.js` · `addons/loaders/GLTFLoader.js` · `addons/utils/BufferGeometryUtils.js`).

## 📁 구성

```
keycap/
├─ index.html                     ← 앱 본체 (단일 파일, 빌드 없음)
├─ vendor/                        ← 내장 라이브러리 (JSZip · three.js)
├─ samples/Unicorn_keycap_1u.3mf  ← 변환 결과 샘플 (유니콘 키캡 1u)
└─ bambu-color-guide.md           ← Bambu Studio 색상 처리·수동 페인팅 가이드
```

## 🖨️ 출력 후 Bambu Studio에서

멀티컬러 3MF의 색이 의도대로 안 나오거나 단색으로 열릴 때는
[bambu-color-guide.md](bambu-color-guide.md) 를 참고하세요.
