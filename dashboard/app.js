// Claude 작업 대시보드
// projects.json 에 등록된 모든 산출물을 카드로 표시하고, 클릭 시
// - markdown 타입: 본문을 marked.js 로 렌더링해 모달에 표시
// - webapp 타입: 모달 안 iframe 으로 임베드 + 새 탭 열기 액션 제공

const STATE = {
  projects: [],
  filter: { q: "", category: "all", status: new Set(["완료", "진행 중", "초안"]) },
};

const STATUS_CLASS = {
  "완료": "done",
  "진행 중": "progress",
  "초안": "draft",
};

// ─────────────────────────────────────────────────────────
async function init() {
  try {
    const r = await fetch("projects.json", { cache: "no-store" });
    const data = await r.json();
    STATE.projects = data.projects;
  } catch (err) {
    document.getElementById("card-grid").innerHTML =
      `<p class="empty">projects.json 을 불러오지 못했습니다.<br/>` +
      `<code>python3 -m http.server</code> 등 정적 서버로 실행 후 ` +
      `<code>/dashboard/</code> 경로로 접속해주세요.<br/>` +
      `(${escapeHtml(String(err))})</p>`;
    return;
  }
  renderStats();
  renderCategoryChips();
  renderCards();
  bindControls();
  bindDetail();
  // URL hash로 직접 진입 (#project=mates-generator)
  if (location.hash.startsWith("#project=")) {
    const id = decodeURIComponent(location.hash.slice("#project=".length));
    const p = STATE.projects.find((x) => x.id === id);
    if (p) openDetail(p);
  }
}

// ─────────────────────────────────────────────────────────
function renderStats() {
  const total = STATE.projects.length;
  const byStatus = STATE.projects.reduce((acc, p) => {
    acc[p.status] = (acc[p.status] || 0) + 1;
    return acc;
  }, {});
  const categories = new Set(STATE.projects.map((p) => p.category)).size;

  const stats = [
    { num: total, label: "전체 작업" },
    { num: byStatus["완료"] || 0, label: "완료" },
    { num: byStatus["진행 중"] || 0, label: "진행 중" },
    { num: categories, label: "분류" },
  ];
  document.getElementById("stats").innerHTML = stats
    .map((s) => `<div class="stat"><div class="stat-num">${s.num}</div><div class="stat-label">${escapeHtml(s.label)}</div></div>`)
    .join("");
}

function renderCategoryChips() {
  const cats = ["all", ...new Set(STATE.projects.map((p) => p.category))];
  document.getElementById("category-chips").innerHTML = cats
    .map(
      (c) =>
        `<button class="chip${STATE.filter.category === c ? " active" : ""}" data-cat="${escapeHtml(c)}">${c === "all" ? "전체" : escapeHtml(c)}</button>`
    )
    .join("");
  document.querySelectorAll(".chip").forEach((btn) =>
    btn.addEventListener("click", () => {
      STATE.filter.category = btn.dataset.cat;
      renderCategoryChips();
      renderCards();
    })
  );
}

function renderCards() {
  const grid = document.getElementById("card-grid");
  const q = STATE.filter.q.trim().toLowerCase();
  const items = STATE.projects.filter((p) => {
    if (STATE.filter.category !== "all" && p.category !== STATE.filter.category) return false;
    if (!STATE.filter.status.has(p.status)) return false;
    if (!q) return true;
    return [p.title, p.summary, p.category, ...(p.tags || [])].join(" ").toLowerCase().includes(q);
  });

  if (items.length === 0) {
    grid.innerHTML = `<p class="empty">조건에 맞는 작업이 없습니다.</p>`;
    return;
  }

  grid.innerHTML = items
    .map(
      (p) => `
    <article class="card" data-id="${escapeHtml(p.id)}" role="button" tabindex="0" aria-label="${escapeHtml(p.title)} 상세 열기">
      <div class="card-top">
        <div class="card-icon" aria-hidden="true">${escapeHtml(p.icon || "📄")}</div>
        <div class="card-status ${STATUS_CLASS[p.status] || ""}">${escapeHtml(p.status)}</div>
      </div>
      <div class="card-category">${escapeHtml(p.category)}</div>
      <h3 class="card-title">${escapeHtml(p.title)}</h3>
      <p class="card-summary">${escapeHtml(p.summary || "")}</p>
      <div class="card-tags">${(p.tags || []).slice(0, 5).map((t) => `<span class="card-tag">${escapeHtml(t)}</span>`).join("")}</div>
    </article>`
    )
    .join("");

  grid.querySelectorAll(".card").forEach((el) => {
    const id = el.dataset.id;
    const p = STATE.projects.find((x) => x.id === id);
    el.addEventListener("click", () => openDetail(p));
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openDetail(p);
      }
    });
  });
}

function bindControls() {
  document.getElementById("search").addEventListener("input", (e) => {
    STATE.filter.q = e.target.value;
    renderCards();
  });
  const map = { "show-done": "완료", "show-progress": "진행 중", "show-draft": "초안" };
  Object.entries(map).forEach(([id, status]) => {
    document.getElementById(id).addEventListener("change", (e) => {
      if (e.target.checked) STATE.filter.status.add(status);
      else STATE.filter.status.delete(status);
      renderCards();
    });
  });
}

// ─────────────────────────────────────────────────────────
function bindDetail() {
  document.querySelectorAll("[data-close]").forEach((el) =>
    el.addEventListener("click", closeDetail)
  );
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDetail();
  });
}

async function openDetail(p) {
  if (!p) return;
  const dlg = document.getElementById("detail");
  dlg.hidden = false;
  dlg.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  history.replaceState(null, "", "#project=" + encodeURIComponent(p.id));

  document.getElementById("detail-category").textContent = p.category;
  document.getElementById("detail-title").textContent = p.title;
  document.getElementById("detail-summary").textContent = p.summary || "";

  // 메타
  const meta = [
    p.status ? `상태 · ${p.status}` : null,
    p.created ? `생성일 · ${p.created}` : null,
    p.commit ? `commit · ${p.commit}` : null,
    p.type ? `타입 · ${p.type}` : null,
    p.path ? `경로 · ${p.path}` : null,
  ].filter(Boolean);
  document.getElementById("detail-meta").innerHTML = meta
    .map((m) => `<span>${escapeHtml(m)}</span>`)
    .join("");

  // 액션 버튼
  const actions = [];
  if (p.type === "webapp") {
    actions.push({ label: "🚀 새 탭에서 실행", href: p.path, target: "_blank", primary: true });
  }
  if (p.type === "markdown") {
    actions.push({ label: "📄 원문 파일 열기", href: p.path, target: "_blank", primary: true });
  }
  (p.actions || []).forEach((a) => actions.push(a));

  document.getElementById("detail-actions").innerHTML = actions
    .map(
      (a) =>
        `<a href="${escapeHtml(a.href)}" ${a.target ? `target="${escapeHtml(a.target)}" rel="noopener"` : ""} class="${a.primary ? "primary" : ""}">${escapeHtml(a.label)}</a>`
    )
    .join("");

  // 본문
  const body = document.getElementById("detail-body");
  body.innerHTML = `<p style="color:var(--muted)">로딩 중…</p>`;

  if (p.type === "markdown") {
    try {
      const r = await fetch(p.path, { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const text = await r.text();
      const html = window.marked ? window.marked.parse(text) : escapeHtml(text);
      body.innerHTML =
        (p.description ? `<p style="color:var(--ink-soft);margin-top:0">${escapeHtml(p.description)}</p>` : "") +
        `<div class="md">${html}</div>`;
    } catch (err) {
      body.innerHTML = `<p style="color:var(--muted)">마크다운을 불러오지 못했습니다: ${escapeHtml(String(err))}</p>`;
    }
  } else if (p.type === "webapp") {
    body.innerHTML =
      (p.description ? `<p style="color:var(--ink-soft);margin-top:0">${escapeHtml(p.description)}</p>` : "") +
      `<iframe src="${escapeHtml(p.path)}" loading="lazy" title="${escapeHtml(p.title)}"></iframe>`;
  } else if (p.type === "data") {
    try {
      const r = await fetch(p.path, { cache: "no-store" });
      const text = await r.text();
      body.innerHTML = `<pre class="md"><code>${escapeHtml(text)}</code></pre>`;
    } catch (err) {
      body.innerHTML = `<p style="color:var(--muted)">${escapeHtml(String(err))}</p>`;
    }
  } else {
    body.innerHTML = p.description
      ? `<p>${escapeHtml(p.description)}</p>`
      : `<p style="color:var(--muted)">미리보기를 지원하지 않는 타입입니다.</p>`;
  }
}

function closeDetail() {
  const dlg = document.getElementById("detail");
  dlg.hidden = true;
  dlg.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
  document.getElementById("detail-body").innerHTML = "";
  if (location.hash.startsWith("#project=")) {
    history.replaceState(null, "", location.pathname + location.search);
  }
}

// ─────────────────────────────────────────────────────────
function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (m) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[m]));
}

window.addEventListener("DOMContentLoaded", init);
