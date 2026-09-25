/* UserScope dashboard client. */
"use strict";

const POLL_MS = 1200;

const state = {
  tab: "all",
  q: "",
  seen: new Set(),
  last: null,
};

const $ = (id) => document.getElementById(id);
const esc = (s) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));

const STATUS_META = {
  claimed: { label: "Claimed", cls: "claimed" },
  available: { label: "Available", cls: "available" },
  unknown: { label: "Error", cls: "unknown" },
  waf: { label: "Blocked", cls: "waf" },
  illegal: { label: "Illegal", cls: "illegal" },
};

/* ---------- toast ---------- */
let toastTimer;
function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 4200);
}

/* ---------- polling core ---------- */
async function pollStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error("API " + res.status);
    const s = await res.json();
    render(s);
  } catch (err) {
    toast("Dashboard API unreachable — is the server running?");
  }
}

/* ---------- render ---------- */
function render(s) {
  state.last = s;
  renderPill(s);
  renderProgress(s);
  renderStats(s);
  renderTabs(s);
  renderTable(s);
  renderFeed(s);
  renderExport(s);
  $("ver").textContent = "v" + esc(s.engine_version || "?");
}

function renderPill(s) {
  const pill = $("pill");
  const txt = $("pillText");
  pill.className = "pill";
  if (s.state === "running") {
    pill.classList.add("searching");
    txt.textContent = s.checked + "/" + s.total + " scanning";
  } else if (s.state === "idle") {
    txt.textContent = "Idle";
  } else if (s.error) {
    pill.classList.add("error");
    txt.textContent = "Error";
  } else {
    pill.classList.add("finished");
    txt.textContent = "Finished";
  }
}

function renderProgress(s) {
  const wrap = $("progressWrap");
  if (s.state !== "running") {
    wrap.hidden = true;
    return;
  }
  wrap.hidden = false;
  const pct = s.total ? Math.round((s.checked / s.total) * 100) : 0;
  $("progressFill").style.width = Math.min(100, pct) + "%";
  $("progressPct").textContent = pct + "%";
  const user = esc(s.username || "");
  $("progressLabel").textContent = "Scanning @" + user + " — " + s.checked + " of " + s.total + " sites";
}

function renderStats(s) {
  const c = s.counts || {};
  const toalChecked = s.checked || 0;
  const total = s.total || 0;
  const cards = [
    { cls: "progress", k: "Checked", v: toalChecked + " / " + total, d: s.state === "running" ? s.elapsed + "s elapsed" : "done in " + (s.elapsed || 0) + "s" },
    { cls: "claimed", k: "Claimed", v: c.claimed || 0, d: "accounts found" },
    { cls: "available", k: "Available", v: c.available || 0, d: "username free" },
    { cls: "unknown", k: "Error", v: c.unknown || 0, d: "could not check" },
    { cls: "waf", k: "Blocked", v: c.waf || 0, d: "bot detection" },
    { cls: "illegal", k: "Illegal", v: c.illegal || 0, d: "bad format" },
  ];
  $("stats").innerHTML = cards.map((x) =>
    `<div class="stat ${x.cls}"><div class="k">${x.k}</div><div class="v">${x.v}</div><div class="d">${x.d}</div></div>`
  ).join("");
}

function renderTabs(s) {
  const counts = s.counts || {};
  const problems = (counts.unknown || 0) + (counts.waf || 0) + (counts.illegal || 0);
  const tabs = [
    { id: "all", label: "All" },
    { id: "claimed", label: "Claimed" },
    { id: "available", label: "Available" },
    { id: "problems", label: "Problems" },
  ];
  const badges = { all: s.total, claimed: counts.claimed || 0, available: counts.available || 0, problems: problems };
  $("tabs").innerHTML = tabs.map((t) =>
    `<button data-tab="${t.id}" class="${state.tab === t.id ? "active" : ""}">${t.label} <em>${badges[t.id]}</em></button>`
  ).join("");
  $("tabs").querySelectorAll("button").forEach((b) => {
    b.onclick = () => { state.tab = b.dataset.tab; pollStatus(); };
  });
  renderStatusLabel(s);
}

function filteredResults(s) {
  const res = s.results || {};
  let list = Object.entries(res);
  if (state.tab === "claimed") list = list.filter(([, m]) => m.status === "claimed");
  else if (state.tab === "available") list = list.filter(([, m]) => m.status === "available");
  else if (state.tab === "problems") list = list.filter(([, m]) => ["unknown", "waf", "illegal"].includes(m.status));
  const q = state.q.trim().toLowerCase();
  if (q) {
    list = list.filter(([name, m]) => {
      const meta = STATUS_META[m.status] || STATUS_META.unknown;
      const hay = [name, m.url_user || "", m.url_main || "", meta.label, m.http_status, m.context].join(" ").toLowerCase();
      return q.split(/\s+/).every((part) => hay.includes(part));
    });
  }
  const order = { claimed: 0, illegal: 1, unknown: 2, waf: 3, available: 4 };
  list.sort((a, b) => (order[a[1].status] ?? 5) - (order[b[1].status] ?? 5) || a[0].localeCompare(b[0]));
  return list;
}

function renderTable(s) {
  const list = filteredResults(s);
  const tbody = $("tbody");
  $("tableWrap").hidden = list.length === 0;
  $("emptyState").style.display = list.length === 0 ? "grid" : "none";
  if (list.length && $("emptyState").querySelector("p")) {
    $("emptyState").querySelector("p").innerHTML = s.state === "idle" && !s.username
      ? "Enter a username and press <b>Search</b> to begin."
      : "No matching sites.";
  }

  tbody.innerHTML = list.map(([name, m]) => {
    const meta = STATUS_META[m.status] || STATUS_META.unknown;
    const ico = (name[0] || "?").toLowerCase();
    const url = m.url_user || m.url_main || "";
    const profile = url
      ? `<a class="profile" href="${esc(url)}" target="_blank" rel="noopener">${esc(url.replace(/^https?:\/\//, "").slice(0, 58))}</a>`
      : `<span class="muted">—</span>`;
    const isNew = !state.seen.has(name);
    return `<tr class="${isNew ? "new" : ""}">
      <td><div class="site-cell"><span class="site-ico">${esc(ico)}</span>
        <div><div class="site-name">${esc(name)}</div>${m.url_main ? `<div class="site-home">${esc(m.url_main.replace(/^https?:\/\//, ""))}</div>` : ""}</div></div></td>
      <td>${profile}</td>
      <td><span class="badge ${meta.cls}">${meta.label}</span></td>
      <td><span class="http">${esc(m.http_status ?? "—")}</span></td>
      <td><span class="time">${m.time_ms != null ? m.time_ms + " ms" : "—"}</span></td>
    </tr>`;
  }).join("");

  list.forEach(([name]) => state.seen.add(name));
  if (s.state === "running" && list.length > state.seen.size) state.seen = new Set(list.map(([n]) => n));
}

function renderFeed(s) {
  const feed = $("feed");
  const items = [...(s.feed || [])].reverse();
  $("feedCount").textContent = items.length ? "last " + items.length : "";
  if (!items.length) {
    feed.innerHTML = `<div class="empty" style="padding:24px"><p>Events will appear here live.</p></div>`;
    return;
  }
  feed.innerHTML = items.map((ev) => {
    const meta = STATUS_META[ev.status] || STATUS_META.unknown;
    return `<div class="feed-row">
      <span class="dot ${ev.status}"></span>
      <span class="fn">${esc(ev.site)} <small>· ${meta.label}</small></span>
      <span class="t">${ev.time_ms != null ? ev.time_ms + "ms" : ""}</span>
    </div>`;
  }).join("");
}

function renderExport(s) {
  const bar = $("exportBar");
  if (s.state === "running") {
    bar.hidden = false;
    $("doneTitle").textContent = "Searching @ " + (s.username || "");
    $("doneMeta").textContent = s.checked + "/" + s.total + " sites · stop will cancel after current batch";
    $("btnCancel").hidden = false;
    bar.className = "card export-bar";
  } else if (s.username) {
    bar.hidden = false;
    $("btnCancel").hidden = true;
    const c = s.counts || {};
    $("doneTitle").textContent = s.error ? "Search finished with errors" : "Search finished";
    $("doneMeta").textContent = (c.claimed || 0) + " found · " + (c.available || 0) + " available · " +
      (c.unknown || 0) + " errors · " + (c.waf || 0) + " blocked · " + (c.illegal || 0) + " illegal";
    bar.className = "card export-bar " + (s.error ? "has-error" : "");
  } else {
    bar.hidden = true;
  }
}

/* ---------- actions ---------- */
function renderFromLast() {
  if (state.last) render(state.last);
}

async function startSearch(e) {
  e.preventDefault();
  const u = $("u").value.trim();
  if (!u) { toast("Enter a username first."); $("u").focus(); return; }
  const nsfw = $("nsfw").checked ? "1" : "0";
  const timeout = $("timeout").value;
  const params = new URLSearchParams({ username: u, nsfw: nsfw, timeout: timeout });
  const btn = $("btnSearch");
  btn.disabled = true;
  btn.querySelector(".spinner").hidden = false;
  btn.querySelector(".btn-txt").textContent = "Searching…";
  $("banner").hidden = true;

  try {
    const res = await fetch("/api/search?" + params.toString(), { method: "POST" });
    const data = await res.json();
    if (!data.ok) { showBanner(data.message, false); }
  } catch (err) {
    showBanner("Could not start search — is the server running?", false);
  } finally {
    btn.disabled = false;
    btn.querySelector(".spinner").hidden = true;
    btn.querySelector(".btn-txt").textContent = "Search";
  }
}

async function cancelSearch() {
  await fetch("/api/cancel", { method: "POST" });
  toast("Stop requested — current batch finishes, then scan stops.");
}

function showBanner(msg, warn) {
  const b = $("banner");
  b.className = "banner" + (warn ? " warn" : "");
  b.textContent = msg;
  b.hidden = false;
}

function renderStatusLabel(s) {
  if (s.scope && s.state !== "idle") {
    $("checkedLabel").textContent = "Platforms: " + s.scope + " · " + (s.state === "running" ? "scanning" : (s.checked || 0) + " of " + s.total + " checked");
    return;
  }
  $("checkedLabel").textContent = "All platforms · " + (s.state === "running" ? "scanning" : (s.checked || 0) + " of " + s.total + " checked");
}

function exportUrl(fmt) {
  return "/api/export?format=" + fmt + "&username=" + encodeURIComponent($("u").value.trim());
}

/* ---------- phone lookup ---------- */
function setMode(mode) {
  const user = mode === "user", phone = mode === "phone";
  $("userPane").hidden = !user;
  $("phonePane").hidden = !phone;
  $("modeUser").classList.toggle("active", user);
  $("modePhone").classList.toggle("active", phone);
  if (phone) {
    loadPhoneHistory();
    $("phoneNum").focus();
    try { history.replaceState(null, "", "#phone"); } catch (err) { /* noop */ }
  } else {
    try { history.replaceState(null, "", window.location.pathname); } catch (err) { /* noop */ }
  }
}

const phoneRow = (d) => [
  ["Country", (d.region_name || "") + (d.region ? " (" + d.region + ")" : "")],
  ["Country code", d.country_code != null ? "+" + d.country_code : "—"],
  ["National number", d.national_number || "—"],
  ["Line type", d.phone_type || "—"],
  ["Carrier", d.carrier || "—"],
  ["Timezone", (d.timezones && d.timezones[0]) || "—"],
  ["Local time", d.local_time || "—"],
  ["Geographic hint", d.geo || "—"],
];

function renderPhone(d) {
  const box = $("phoneResult");
  $("phoneBanner").hidden = true;
  const heroCls = d.valid ? "" : " invalid";
  const heroTxt = d.valid ? "VALID NUMBER" : (d.possible ? "POSSIBLE (not formally valid)" : "INVALID NUMBER");
  const num = d.formats && d.formats.e164 ? d.formats.e164 : (d.query || "");

  let html = `<div class="ph-panel">
    <div class="ph-hero${heroCls}">
      <div class="num">${esc(num)}</div>
      <span class="stat-tag">${heroTxt}</span>
    </div>
    <div class="ph-grid">
      ${phoneRow(d).map(([k, v]) =>
        `<div class="ph-cell"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`
      ).join("")}
    </div>`;

  if (d.formats) {
    html += `<div class="fmt-chips">
      ${Object.entries(d.formats).map(([k, v]) => `<span class="fmt-chip">${esc(k)}: ${esc(v)}</span>`).join("")}
    </div>`;
  }

  if (d.web !== undefined) {
    html += `<div class="ph-web"><h3 style="margin:14px 0 2px;font-size:14px;">Public web visibility</h3>`;
    if (!d.web.length) {
      html += `<span class="muted" style="font-size:12.5px;">No public results found (or the free search was blocked/rate-limited).</span>`;
    } else {
      html += `<ul style="margin:8px 0 0;padding-left:18px;">` + d.web.map((w) =>
        `<li><a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.title)}</a>` +
        (w.snippet ? `<span class="snip">${esc(w.snippet)}</span>` : "") + `</li>`
      ).join("") + `</ul>`;
    }
    html += `</div>`;
  }

  html += `<div class="ph-actions">
      <button class="ghost" id="btnPhCopy" type="button">Copy number</button>
      <button class="ghost" id="btnPhJson" type="button">Export JSON</button>
      <button class="ghost" id="btnPhCsv" type="button">Export CSV</button>
    </div>
  </div>`;
  box.innerHTML = html;
  box.hidden = false;
  state.lastPhone = d;

  $("btnPhCopy").addEventListener("click", () => {
    try { navigator.clipboard.writeText(num); toast("Number copied."); }
    catch (err) { toast("Copy failed — select manually."); }
  });
  $("btnPhJson").addEventListener("click", () => downloadBlob("phone_" + num.replace(/\D+/g, "") + ".json", JSON.stringify(d, null, 2), "application/json"));
  $("btnPhCsv").addEventListener("click", () => {
    const rows = phoneRow(d).map(([k, v]) => '"' + k + '","' + String(v).replace(/"/g, '""') + '"');
    if (d.formats) rows.push("formats," + d.formats.e164);
    downloadBlob("phone_" + num.replace(/\D+/g, "") + ".csv", rows.join("\n"), "text/csv");
  });
}

function downloadBlob(fname, content, type) {
  const blob = new Blob([content], { type: type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = fname;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function analyzePhone() {
  const raw = $("phoneNum").value.trim();
  if (!raw) { toast("Enter a phone number first."); $("phoneNum").focus(); return; }
  const btn = $("btnPhone");
  btn.disabled = true;
  btn.querySelector(".spinner").hidden = false;
  $("phoneBanner").hidden = true;
  try {
    const res = await fetch("/api/phone?num=" + encodeURIComponent(raw) + "&web=" + ($("phoneSearchWeb").checked ? "1" : "0"));
    const data = await res.json();
    if (res.ok) {
      renderPhone(data);
      loadPhoneHistory();
    } else {
      showPhoneBanner(data.error || "Lookup failed.", false);
    }
  } catch (err) {
    showPhoneBanner("Could not reach the server.", false);
  } finally {
    btn.disabled = false;
    btn.querySelector(".spinner").hidden = true;
  }
}

function showPhoneBanner(msg, cls) {
  const b = $("phoneBanner");
  b.className = "banner" + (cls ? " " + cls : "");
  b.textContent = msg;
  b.hidden = false;
}

async function loadPhoneHistory() {
  try {
    const res = await fetch("/api/phone/history");
    const data = await res.json();
    renderPhoneHistory(data.items || []);
  } catch (err) { /* server momentarily down */ }
}

function renderPhoneHistory(items) {
  const list = $("phHist");
  $("phCount").textContent = items.length ? items.length + " saved" : "";
  if (!items.length) {
    list.innerHTML = `<div class="ph-empty">No lookups yet — analyze a number and it appears here.</div>`;
    return;
  }
  list.innerHTML = items.map((it) => {
    const ok = it.valid ? `<span class="ok claimed">valid</span>` : `<span class="ok">invalid</span>`;
    const num = it.formats && it.formats.e164 ? it.formats.e164 : it.query;
    const meta = [it.region, it.carrier].filter(Boolean).join(" · ");
    return `<div class="ph-row" data-num="${esc(num)}">
      <span class="q">${esc(num)}</span>${ok}
      <span class="meta">${esc(meta || "—")} · ${esc(String(it.when || "").slice(0, 16))}</span>
    </div>`;
  }).join("");
  list.querySelectorAll(".ph-row").forEach((row) => {
    row.addEventListener("click", () => {
      $("phoneNum").value = row.dataset.num;
      analyzePhone();
    });
  });
}

async function clearPhoneHistory() {
  try {
    await fetch("/api/phone/history/clear", { method: "POST" });
    loadPhoneHistory();
    toast("History cleared.");
  } catch (err) { toast("Could not clear history."); }
}

/* ---------- wiring ---------- */
document.addEventListener("DOMContentLoaded", () => {
  $("searchForm").addEventListener("submit", startSearch);
  const fRes = $("fRes");
  fRes.addEventListener("input", () => { state.q = fRes.value; renderFromLast(); });
  fRes.addEventListener("keyup", (e) => { if (e.key === "Escape") { fRes.value = ""; state.q = ""; renderFromLast(); } });
  $("btnCancel").addEventListener("click", cancelSearch);
  $("btnReset").addEventListener("click", () => {
    location.reload();
  });
  $("btnJson").addEventListener("click", () => { location.href = exportUrl("json"); });
  $("btnCsv").addEventListener("click", () => { location.href = exportUrl("csv"); });
  $("btnTxt").addEventListener("click", () => { location.href = exportUrl("txt"); });

  $("modeUser").addEventListener("click", () => setMode("user"));
  $("modePhone").addEventListener("click", () => setMode("phone"));
  $("btnPhone").addEventListener("click", analyzePhone);
  $("phoneNum").addEventListener("keydown", (e) => {
    if (e.key === "Enter") analyzePhone();
    else if (e.key === "Escape") { $("phoneNum").value = ""; }
  });
  $("phClear").addEventListener("click", clearPhoneHistory);
  if (window.location.hash === "#phone") setMode("phone");

  window.onerror = (msg, src, line) => toast("JS error: " + msg + " @line " + line);

  pollStatus();
  setInterval(pollStatus, POLL_MS);
});