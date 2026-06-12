#!/usr/bin/env bash
# itch.io 업로드용 zip 패키지 빌드
# 사용: bash tools/build_itch.sh  →  dist/office-runner-itch.zip
#
# itch.io HTML 게임은 zip 루트에 index.html이 있어야 하므로
# v2(러너)를 index.html로 삼고, v1(텍스트)을 text.html로 동봉한다.
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf dist
mkdir -p dist/pkg

# v2 러너 → index.html (내부 링크 보정: 텍스트 버전 → text.html)
sed 's|href="./index.html">📖 텍스트 버전(v1)</a>|href="./text.html">📖 텍스트 버전(v1)</a>|' v2.html > dist/pkg/index.html

# v1 텍스트 → text.html (v2 링크 보정)
sed 's|href="./v2.html"|href="./index.html"|' index.html > dist/pkg/text.html

# 영어판 (한국어 링크 보정: v2 → index.html)
sed 's|href="./v2.html">🇰🇷 한국어</a>|href="./index.html">🇰🇷 한국어</a>|' en.html > dist/pkg/en.html

(cd dist/pkg && zip -q -r ../office-runner-itch.zip .)
rm -rf dist/pkg
echo "✅ dist/office-runner-itch.zip"
unzip -l dist/office-runner-itch.zip
