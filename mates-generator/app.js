// Yogibo Mates 이미지 프롬프트 생성기
// 캐릭터 데이터(characters.json)와 스타일 프리셋(styles.json)을 결합해
// 다양한 이미지 생성 도구용 상세 프롬프트를 출력한다.

const EMOJI_MAP = {
  dog: "🐶", cat: "🐱", bear: "🐻", "polar-bear": "🐻‍❄️",
  rabbit: "🐰", pig: "🐷", frog: "🐸", sheep: "🐑",
  penguin: "🐧", whale: "🐳", shark: "🦈", turtle: "🐢",
  elephant: "🐘", lion: "🦁", tiger: "🐯", octopus: "🐙",
  unicorn: "🦄", cow: "🐮", dinosaur: "🦖", monkey: "🐵",
  fox: "🦊", panda: "🐼", hippo: "🦛", duck: "🦆",
};

const state = {
  characters: [],
  styles: [],
  selectedCharacterId: null,
};

// ────────────────────────────────────────────────────────────────────────────
// 데이터 로딩
// ────────────────────────────────────────────────────────────────────────────
async function loadData() {
  const [charactersRes, stylesRes] = await Promise.all([
    fetch("characters.json"),
    fetch("styles.json"),
  ]);
  const charactersData = await charactersRes.json();
  const stylesData = await stylesRes.json();
  state.characters = charactersData.characters;
  state.styles = stylesData.styles;
}

// ────────────────────────────────────────────────────────────────────────────
// 렌더링
// ────────────────────────────────────────────────────────────────────────────
function renderCharacterGrid(filter = "") {
  const grid = document.getElementById("character-grid");
  const q = filter.trim().toLowerCase();
  grid.innerHTML = "";
  state.characters
    .filter((c) => {
      if (!q) return true;
      return [c.name_ja, c.name_ko, c.name_en, c.species, ...(c.tags || [])]
        .join(" ")
        .toLowerCase()
        .includes(q);
    })
    .forEach((c) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "char-card" + (c.id === state.selectedCharacterId ? " selected" : "");
      card.dataset.id = c.id;
      card.setAttribute("role", "option");
      card.setAttribute("aria-selected", c.id === state.selectedCharacterId ? "true" : "false");
      card.innerHTML = `
        <div class="char-emoji" aria-hidden="true">${EMOJI_MAP[c.id] || "✨"}</div>
        <div class="char-name">${c.name_ko}</div>
        <div class="char-name-en">${c.name_en}</div>
      `;
      card.addEventListener("click", () => {
        state.selectedCharacterId = c.id;
        renderCharacterGrid(filter);
      });
      grid.appendChild(card);
    });
}

function renderStyleSelect() {
  const sel = document.getElementById("style-select");
  sel.innerHTML = state.styles
    .map((s) => `<option value="${s.id}">${s.name_ko} · ${s.name_en}</option>`)
    .join("");
}

// ────────────────────────────────────────────────────────────────────────────
// 프롬프트 빌더
// ────────────────────────────────────────────────────────────────────────────
function buildBaseDescription(character) {
  // 캐릭터 정체를 명확히 묘사하는 코어 문장
  return [
    `Yogibo Mate plush character "${character.name_en}" (${character.species})`,
    `silhouette: ${character.silhouette}`,
    `color palette: ${character.palette}`,
    `signature features: ${character.features}`,
    `personality: ${character.personality}`,
  ].join(", ");
}

function buildExtras({ pose, scene, mood, lighting, camera }, character) {
  const parts = [];
  parts.push(`pose: ${pose && pose.trim() ? pose.trim() : character.signature_pose}`);
  if (scene && scene.trim()) parts.push(`setting: ${scene.trim()}`);
  if (mood && mood.trim()) parts.push(`mood: ${mood.trim()}`);
  if (lighting) parts.push(`lighting: ${lighting}`);
  if (camera) parts.push(`composition: ${camera}`);
  return parts.join(", ");
}

function composePrompt({ character, style, options, target }) {
  const base = buildBaseDescription(character);
  const extras = buildExtras(options, character);
  const styleClause = style.prompt;

  // 도구별 포맷 분기
  const aspect = options.aspect || "1:1";

  if (target === "midjourney") {
    return {
      prompt:
        `${base}, ${extras}, ${styleClause}, highly detailed, cohesive character design ` +
        `--ar ${aspect} --style raw --v 6`,
      negative: null,
      label: "Midjourney",
    };
  }
  if (target === "stable-diffusion") {
    return {
      prompt:
        `masterpiece, best quality, ${base}, ${extras}, ${styleClause}, detailed character design, coherent anatomy`,
      negative:
        (style.negative ? style.negative + ", " : "") +
        "lowres, bad anatomy, deformed, extra limbs, watermark, text, jpeg artifacts, blurry",
      label: "Stable Diffusion",
    };
  }
  if (target === "dalle") {
    return {
      prompt:
        `Create an image of the Yogibo Mate plush character "${character.name_en}". ` +
        `${capitalize(base)}. ${capitalize(extras)}. Render it in this style: ${styleClause}. ` +
        `Aspect ratio ${aspect}. Keep the character recognizable and on-model.`,
      negative: null,
      label: "DALL·E / GPT Image",
    };
  }
  // universal
  return {
    prompt: `${base}. ${capitalize(extras)}. Style: ${styleClause}. Aspect ratio ${aspect}.`,
    negative: style.negative || null,
    label: "Universal",
  };
}

function capitalize(s) {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// ────────────────────────────────────────────────────────────────────────────
// UI 핸들러
// ────────────────────────────────────────────────────────────────────────────
function getCurrentOptions() {
  return {
    pose: document.getElementById("pose").value,
    scene: document.getElementById("scene").value,
    mood: document.getElementById("mood").value,
    lighting: document.getElementById("lighting").value,
    camera: document.getElementById("camera").value,
    aspect: document.getElementById("aspect").value,
  };
}

function getCurrentTarget() {
  const el = document.querySelector('input[name="target"]:checked');
  return el ? el.value : "universal";
}

function getSelectedCharacter() {
  return state.characters.find((c) => c.id === state.selectedCharacterId);
}

function getSelectedStyle() {
  const id = document.getElementById("style-select").value;
  return state.styles.find((s) => s.id === id);
}

function renderResults(blocks) {
  const out = document.getElementById("output");
  out.innerHTML = "";
  blocks.forEach((b) => {
    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <h3>${escapeHtml(b.title)}</h3>
      <pre>${escapeHtml(b.prompt)}</pre>
      ${b.negative ? `<h3>Negative prompt</h3><pre>${escapeHtml(b.negative)}</pre>` : ""}
      ${b.meta ? `<p class="meta">${escapeHtml(b.meta)}</p>` : ""}
    `;
    out.appendChild(wrap);
  });
  document.getElementById("copy").disabled = blocks.length === 0;
  // 마지막에 모든 결과를 합친 텍스트를 클립보드 후보로 저장
  out.dataset.copyText = blocks
    .map((b) =>
      `# ${b.title}\n${b.prompt}` + (b.negative ? `\n\n[Negative]\n${b.negative}` : "")
    )
    .join("\n\n---\n\n");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (m) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[m]));
}

function handleGenerate() {
  const character = getSelectedCharacter();
  if (!character) {
    alert("먼저 캐릭터를 선택하세요.");
    return;
  }
  const style = getSelectedStyle();
  const options = getCurrentOptions();
  const target = getCurrentTarget();
  const result = composePrompt({ character, style, options, target });

  renderResults([
    {
      title: `${character.name_ko} · ${style.name_ko} · ${result.label}`,
      prompt: result.prompt,
      negative: result.negative,
      meta: `aspect ${options.aspect} · target: ${target}`,
    },
  ]);
}

function handleGenerateAllStyles() {
  const character = getSelectedCharacter();
  if (!character) {
    alert("먼저 캐릭터를 선택하세요.");
    return;
  }
  const options = getCurrentOptions();
  const target = getCurrentTarget();
  const blocks = state.styles.map((style) => {
    const r = composePrompt({ character, style, options, target });
    return {
      title: `${character.name_ko} · ${style.name_ko}`,
      prompt: r.prompt,
      negative: r.negative,
    };
  });
  renderResults(blocks);
}

async function handleCopy() {
  const text = document.getElementById("output").dataset.copyText || "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    const btn = document.getElementById("copy");
    const original = btn.textContent;
    btn.textContent = "복사됨 ✓";
    setTimeout(() => (btn.textContent = original), 1400);
  } catch {
    alert("클립보드 복사에 실패했어요. 결과 영역에서 직접 선택해 복사해주세요.");
  }
}

// ────────────────────────────────────────────────────────────────────────────
// 부트스트랩
// ────────────────────────────────────────────────────────────────────────────
(async function init() {
  try {
    await loadData();
  } catch (err) {
    document.getElementById("output").innerHTML =
      `<p class="placeholder">데이터를 불러오지 못했습니다: ${escapeHtml(String(err))}<br/>` +
      `로컬 파일 시스템에서 직접 열면 fetch가 막힐 수 있습니다. ` +
      `<code>python3 -m http.server</code> 등으로 정적 서버를 띄워 접속해주세요.</p>`;
    return;
  }
  renderCharacterGrid();
  renderStyleSelect();
  document.getElementById("search").addEventListener("input", (e) =>
    renderCharacterGrid(e.target.value)
  );
  document.getElementById("generate").addEventListener("click", handleGenerate);
  document.getElementById("generate-all-styles").addEventListener("click", handleGenerateAllStyles);
  document.getElementById("copy").addEventListener("click", handleCopy);
})();
