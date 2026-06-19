/* Bambu Auto front-end.
 * Vanilla JS, no build step. Composed of small helpers (toast, modal, form,
 * jobs render). State: TRACK, MODE, UP (uploaded paths), SEL (selected ids).
 */

(() => {
  "use strict";

  // ───────────── state ─────────────
  let TRACK = "3d";
  let MODE = "batch";
  const UP = { up3d: [], upFn: [] };
  const SEL = new Set();
  let LAST_BAL = null;
  let CFG = {};
  let REFRESH_TIMER = null;

  // ───────────── tiny helpers ─────────────
  const $ = (id) => document.getElementById(id);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const esc = (s) =>
    String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  function keyHdr() {
    const k = ($("key").value || "").trim();
    return k ? { "X-Meshy-Key": k } : {};
  }

  // ───────────── toast ─────────────
  function toast(msg, kind = "info", ttl = 3500) {
    const root = $("toasts");
    const el = document.createElement("div");
    el.className = "toast " + kind;
    el.innerHTML =
      '<span>' + esc(msg) + '</span><button class="x" aria-label="닫기">×</button>';
    el.querySelector(".x").onclick = () => el.remove();
    root.appendChild(el);
    if (ttl) setTimeout(() => el.remove(), ttl);
  }
  window.toast = toast;

  // ───────────── modal ─────────────
  window.openKeyModal = () => $("keyModalBg").classList.add("open");
  window.closeKeyModal = () => $("keyModalBg").classList.remove("open");

  // ───────────── theme ─────────────
  function applyTheme(mode) {
    const root = document.documentElement;
    if (mode === "light" || mode === "dark") root.setAttribute("data-theme", mode);
    else root.removeAttribute("data-theme");
    try { localStorage.setItem("theme", mode); } catch (e) {}
  }
  window.toggleTheme = () => {
    const cur = document.documentElement.getAttribute("data-theme");
    const next = cur === "dark" ? "light" : cur === "light" ? "auto" : "dark";
    applyTheme(next);
    toast("테마: " + (next === "auto" ? "시스템 따라감" : next), "info", 1600);
  };
  try { applyTheme(localStorage.getItem("theme") || "auto"); } catch (e) {}

  // ───────────── tracks / modes ─────────────
  window.setTrack = (t) => {
    TRACK = t;
    $$(".track-btn").forEach((b) => b.classList.toggle("on", b.dataset.track === t));
    $("form3d").classList.toggle("hidden", t !== "3d");
    $("formFunc").classList.toggle("hidden", t !== "func");
    $("formCad").classList.toggle("hidden", t !== "cad");
    refresh();
  };

  window.setMode = (m) => {
    MODE = m;
    ["mBatch", "mView", "mText"].forEach((id) =>
      $(id).classList.toggle(
        "on",
        (id === "mBatch" && m === "batch") ||
          (id === "mView" && m === "multiview") ||
          (id === "mText" && m === "text"),
      ),
    );
    const hints = {
      batch: "한 줄에 이미지 URL 1개 = 물체 1개.",
      multiview: "같은 물체 2~4장 → 정밀 3D 1개.",
      text: "한 줄에 설명 1개. 예: 요기보 캐릭터 피규어",
    };
    $("hint").textContent = hints[m];
    $("src").placeholder = m === "text" ? "요기보 캐릭터 피규어" : "https://.../productA.jpg";
  };

  window.onBrandChange = () => {
    const t = $("brandType").value;
    $("brandText").classList.toggle("hidden", t !== "text");
    $("brandIcon").classList.toggle("hidden", t !== "icon");
  };

  window.onProductChange = () => {
    $("fmagWrap").style.display = $("product").value === "magnet" ? "block" : "none";
  };

  // ───────────── key / credits ─────────────
  window.saveKey = () => {
    try { localStorage.setItem("meshy_key", ($("key").value || "").trim()); } catch (e) {}
  };
  window.checkBal = async () => {
    $("keyMsg").textContent = "조회 중…";
    try {
      const c = await (await fetch("/api/credits", { headers: keyHdr() })).json();
      if (c.meshy_balance == null) {
        $("keyMsg").textContent = "잔액 조회 실패 — 키를 확인하세요.";
        toast("키 확인 실패", "err");
      } else {
        $("keyMsg").textContent = "현재 잔액: " + c.meshy_balance.toLocaleString();
        LAST_BAL = c.meshy_balance;
        renderCredits(c);
      }
    } catch (e) {
      $("keyMsg").textContent = "오류: " + e;
    }
  };

  // ───────────── file upload ─────────────
  window.upFiles = async (input, store, msgId) => {
    const fs = input.files;
    if (!fs.length) return;
    $(msgId).textContent = "업로드 중…";
    const fd = new FormData();
    for (const f of fs) fd.append("files", f);
    try {
      const r = await fetch("/api/upload", { method: "POST", body: fd });
      const j = await r.json();
      if (!r.ok) {
        $(msgId).textContent = "업로드 실패: " + (j.detail || r.status);
        toast("업로드 실패", "err");
        return;
      }
      UP[store] = (UP[store] || []).concat(j.paths || []);
      $(msgId).textContent = UP[store].length + "개 첨부됨";
    } catch (e) {
      $(msgId).textContent = "업로드 실패: " + e;
      toast("업로드 실패: " + e, "err");
    }
  };

  // ───────────── form validation ─────────────
  function setFieldErr(inputId, msg) {
    const el = $(inputId).closest(".field");
    if (!el) return;
    el.classList.toggle("is-invalid", !!msg);
    const e = el.querySelector(".err");
    if (e && msg) e.textContent = msg;
  }

  function srcs(id) {
    return $(id)
      .value.split(/\n/)
      .map((s) => s.trim())
      .filter(Boolean);
  }

  // ───────────── submit ─────────────
  async function post(body, btnId) {
    const btn = $(btnId);
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> 제출 중…';
    try {
      const r = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      if (!r.ok) {
        toast("오류: " + (j.detail || r.status), "err");
      } else {
        toast(j.count + "개 작업 대기열 등록", "ok");
      }
    } catch (e) {
      toast("네트워크 오류: " + e, "err");
    } finally {
      btn.disabled = false;
      btn.innerHTML = orig;
      refresh();
    }
  }

  window.submit3d = async () => {
    const s = srcs("src").concat(UP.up3d);
    if (!s.length) { setFieldErr("src", "최소 하나는 입력하세요."); return; }
    setFieldErr("src", null);
    if (MODE === "multiview" && s.length > 4) { toast("멀티뷰는 최대 4장", "err"); return; }
    if (s.length > 20) { toast("최대 20개", "err"); return; }
    await post(
      {
        track: "3d", sources: s, mode: MODE,
        material: $("mat").value, printer: $("prn").value,
        addon: $("addon").value,
        texture: $("tex").checked, remesh: $("rem").checked,
        precision: $("prec").value, remove_bg: $("bg").checked,
        brand_type: $("brandType").value,
        brand_text: $("brandText").value,
        brand_icon: $("brandIcon").value,
        meshy_key: ($("key").value || "").trim(),
      },
      "go3d",
    );
    UP.up3d = [];
    $("up3dMsg").textContent = "";
  };

  window.submitFunc = async () => {
    const s = srcs("fsrc").concat(UP.upFn);
    if (!s.length) { setFieldErr("fsrc", "이미지 URL 또는 파일 첨부."); return; }
    setFieldErr("fsrc", null);
    if (s.length > 20) { toast("최대 20개", "err"); return; }
    await post(
      {
        track: "func", sources: s, mode: "batch",
        product: $("product").value,
        magnet_size: $("fmagsize").value,
        flat_size_mm: parseFloat($("fsize").value) || 50,
        flat_thickness_mm: parseFloat($("fth").value) || 3.5,
        material: $("fmat").value, printer: $("fprn").value,
        remove_bg: $("fbg").checked,
      },
      "goFn",
    );
    UP.upFn = [];
    $("upFnMsg").textContent = "";
  };

  window.submitCad = async () => {
    const spec = ($("cadPrompt").value || "").trim();
    if (!spec) { setFieldErr("cadPrompt", "CAD 스펙을 입력하세요."); return; }
    setFieldErr("cadPrompt", null);
    const params = {};
    for (const ln of ($("cadParams").value || "").split(/\n/)) {
      const s = ln.trim();
      if (!s || !s.includes("=")) continue;
      const idx = s.indexOf("=");
      const k = s.slice(0, idx).trim();
      const v = s.slice(idx + 1).trim();
      const n = parseFloat(v);
      params[k] = Number.isNaN(n) || !/^-?[\d.]+$/.test(v) ? v : n;
    }
    await post(
      {
        track: "cad", sources: [],
        cad_prompt: spec, cad_params: params,
        cad_model: $("cadModel").value,
        cad_max_attempts: parseInt($("cadAttempts").value) || 3,
        material: $("cadMat").value, printer: $("cadPrn").value,
      },
      "goCad",
    );
  };

  // ───────────── job operations ─────────────
  window.retry = async (id) => {
    await fetch("/api/jobs/" + id + "/retry", { method: "POST" });
    toast("재시도 등록", "info");
    refresh();
  };
  window.share = (id) => {
    const u = location.origin + "/share/" + id;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(u).then(
        () => toast("공유 링크 복사됨", "ok"),
        () => prompt("공유 링크:", u),
      );
    } else { prompt("공유 링크:", u); }
  };
  window.retexture = async (id) => {
    const p = prompt("텍스처 설명 (예: 광택 파스텔, 만화풍):");
    if (!p) return;
    const h = Object.assign({ "Content-Type": "application/json" }, keyHdr());
    const r = await fetch("/api/jobs/" + id + "/retexture", {
      method: "POST", headers: h, body: JSON.stringify({ prompt: p }),
    });
    const j = await r.json();
    if (!r.ok) toast("오류: " + (j.detail || r.status), "err");
    else toast("재텍스처 등록", "ok");
    refresh();
  };
  window.del = async (id) => {
    if (!confirm("이 작업을 삭제할까요?")) return;
    await fetch("/api/jobs/" + id, { method: "DELETE" });
    SEL.delete(id);
    refresh();
  };
  window.bulkDelete = async () => {
    const ids = Array.from(SEL);
    if (!ids.length) return;
    if (!confirm(ids.length + "개를 삭제할까요?")) return;
    await fetch("/api/jobs/bulk-delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    SEL.clear();
    refresh();
  };

  // ───────────── select state ─────────────
  function onSel(cb) {
    if (cb.checked) SEL.add(cb.dataset.id);
    else SEL.delete(cb.dataset.id);
    syncBulk();
    cb.closest(".jcard").classList.toggle("selected", cb.checked);
  }
  function syncBulk() {
    const n = SEL.size;
    const b = $("bulk");
    b.disabled = !n;
    b.textContent = n ? "선택 삭제 (" + n + ")" : "선택 삭제";
  }

  // ───────────── jobs render ─────────────
  function badge(state) {
    const ko = state === "sliced" ? "완료" : state === "new" ? "대기" : state;
    let kind = "";
    if (state === "sliced" || state === "done") kind = "ok";
    else if (state.startsWith("failed")) kind = "no";
    else if (state !== "new") kind = "go";
    return '<span class="bdg ' + kind + '">' + esc(ko) + "</span>";
  }

  function renderCredits(c) {
    const bal = c.meshy_balance == null ? "키 입력 후 확인" : c.meshy_balance.toLocaleString();
    const used = c.monthly_used != null ? c.monthly_used : "?";
    const cap = c.monthly_cap != null ? c.monthly_cap : "?";
    $("cred").innerHTML =
      "<b>Meshy 잔액 " + esc(bal) + "</b> · 월 견적 " + esc(used) + "/" + esc(cap);
    $("cred-mini").textContent = c.meshy_balance == null ? "" : "🪙 " + bal;
  }

  function dlLinks(x) {
    const links = [];
    if (x.bambu3mf) {
      links.push(
        '<a class="primary" href="/api/bambu3mf/' + x.id +
        '" title="Bambu/Orca에서 열면 색마다 익스트루더 배정">🎨 멀티컬러 3MF</a>',
      );
    }
    if (x.color3mf) {
      links.push(
        '<a class="secondary" href="/api/color3mf/' + x.id +
        '" title="미리보기용 컬러 3MF">컬러 3MF</a>',
      );
    }
    if (x.has_gcode) links.push('<a href="/api/download/' + x.id + '">3MF</a>');
    for (const f of x.model_formats || [])
      links.push('<a href="/api/model/' + x.id + "/" + f + '">' + esc(f) + "</a>");
    for (let i = 1; i <= (x.color_parts || 0); i++)
      links.push(
        '<a href="/api/colorpart/' + x.id + "/" + i + '" title="색상 파트 ' + i + '">C' + i + "</a>",
      );
    return links.length ? links.join("") : '<span class="hint">아직 결과 없음</span>';
  }

  function palette(x) {
    if (!(x.palette || []).length) return "";
    return (
      '<div>' +
      x.palette
        .map((c) => '<span class="swatch" style="background:' + esc(c) + '"></span>')
        .join("") +
      "</div>"
    );
  }

  function jobCard(x) {
    const sel = SEL.has(x.id);
    const cr = x.credits > 0
      ? '<span class="bdg coin" title="' + (x.credits_actual ? "실측" : "견적") +
        '">🪙' + x.credits + (x.credits_actual ? "" : "~") + "</span>"
      : "";
    const opts = cr + (x.options || []).map((s) => '<span class="bdg">' + esc(s) + "</span>").join("");
    const ck = sel ? " checked" : "";
    const thumb = x.has_thumb
      ? '<img src="/api/thumb/' + x.id + '" class="jthumb" alt="" onerror="this.style.display=\'none\'">'
      : '<div class="jthumb empty">◽</div>';
    const acts =
      (TRACK === "3d" && x.state === "sliced"
        ? '<button class="btn btn-icon" title="텍스처 입히기" onclick="retexture(\'' + x.id + '\')">🎨</button>'
        : "") +
      (x.can_retry
        ? '<button class="btn btn-icon" title="재시도" onclick="retry(\'' + x.id + '\')">↻</button>'
        : "") +
      (x.has_gcode
        ? '<button class="btn btn-icon" title="공유" onclick="share(\'' + x.id + '\')">🔗</button>'
        : "") +
      '<button class="btn btn-icon" title="삭제" onclick="del(\'' + x.id + '\')">🗑</button>';

    const msg = esc(x.message || "");
    const created = (x.created || "").slice(5, 16).replace("T", " ");
    return (
      '<div class="jcard' + (sel ? " selected" : "") + '" data-id="' + x.id + '">' +
        '<input type="checkbox" class="jsel" data-id="' + x.id + '"' + ck + ' aria-label="선택">' +
        '<div class="jcard-head">' + thumb +
          '<div class="jhead-text">' +
            '<div class="jid"><span class="mono">' + esc(x.id.slice(0, 8)) + "</span>" + badge(x.state) + "</div>" +
            '<div class="jmeta">' + esc(x.material) + " · " + esc(x.printer || "auto") + " · " + esc(created) + "</div>" +
          "</div>" +
        "</div>" +
        '<div class="jmsg" title="' + msg + '">' + msg + "</div>" +
        '<div class="jopts">' + (opts || '<span class="hint">옵션 없음</span>') + "</div>" +
        '<div class="jdl">' + dlLinks(x) + "</div>" +
        palette(x) +
        '<div class="jacts">' +
          '<div class="spacer"></div>' + acts +
        "</div>" +
      "</div>"
    );
  }

  async function refresh() {
    try {
      const j = await (await fetch("/api/jobs")).json();
      const root = $("jobs");
      const rows = (j.jobs || []).filter((x) => (x.track || "3d") === TRACK);
      $("empty").classList.toggle("hidden", rows.length > 0);
      root.classList.toggle("hidden", rows.length === 0);
      root.innerHTML = rows.map(jobCard).join("");
      $$(".jsel", root).forEach((cb) => (cb.onclick = () => onSel(cb)));
      syncBulk();

      const c = await (await fetch("/api/credits", { headers: keyHdr() })).json();
      renderCredits(c);
    } catch (e) {
      console.error("refresh failed", e);
    }
  }
  window.refresh = refresh;

  // ───────────── boot ─────────────
  async function loadPrinters() {
    try {
      const p = await (await fetch("/api/printers")).json();
      for (const id of ["prn", "fprn", "cadPrn"]) {
        const s = $(id);
        if (!s) continue;
        for (const n of p.printers) {
          const o = document.createElement("option");
          o.value = n; o.textContent = n.toUpperCase();
          s.appendChild(o);
        }
        if (Array.from(s.options).some((o) => o.value === "a1")) s.value = "a1";
      }
    } catch (e) {}
  }

  async function loadVersion() {
    try {
      const v = await (await fetch("/api/version")).json();
      $("ver").textContent = "build " + (v.version || "?");
    } catch (e) {}
  }

  async function loadConfig() {
    try {
      CFG = await (await fetch("/api/config")).json();
      if (CFG.byo_required) {
        $("keyMsg").textContent = "⚠ 본인 Meshy 키 입력 필수";
      }
    } catch (e) {}
  }

  function restoreKey() {
    try {
      $("key").value = localStorage.getItem("meshy_key") || "";
    } catch (e) {}
  }

  // addon select keycap → auto-enable texture
  document.addEventListener("DOMContentLoaded", () => {
    const a = $("addon");
    if (a) {
      a.addEventListener("change", function () {
        const kc = this.value === "keycap";
        $("addonHint").classList.toggle("hidden", !kc);
        if (kc) $("tex").checked = true;
      });
    }
    restoreKey();
    loadConfig();
    loadVersion();
    loadPrinters();
    onProductChange();
    refresh();
    REFRESH_TIMER = setInterval(refresh, 3000);
  });

  // pause refresh when tab hidden (less server load)
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (REFRESH_TIMER) { clearInterval(REFRESH_TIMER); REFRESH_TIMER = null; }
    } else if (!REFRESH_TIMER) {
      refresh();
      REFRESH_TIMER = setInterval(refresh, 3000);
    }
  });
})();
