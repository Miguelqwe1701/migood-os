// Migood Home: draws the home screen and moves around it with a controller,
// the keyboard or the mouse. System things go through the bridge to
// migood-home (Python): ask("apps"), ask("launch", {id}), ...
"use strict";

// ---------- bridge ----------
const pending = new Map();
let nextId = 1;
window.migood = window.migood || {};
window.migood._reply = (id, result) => {
  const done = pending.get(id);
  if (done) { pending.delete(id); done(result); }
};
function ask(cmd, args = {}) {
  return new Promise((resolve) => {
    const id = nextId++;
    pending.set(id, resolve);
    const handler = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.migood;
    if (handler) handler.postMessage(JSON.stringify({ id, cmd, args }));
    else if (window.migoodMock) window.migoodMock(cmd, args).then((r) => window.migood._reply(id, r));
    else resolve({ error: "no bridge" });
  });
}

const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const fileUrl = (p) => (p ? "file://" + encodeURI(p) : "");

function toast(text) {
  const t = $("#toast");
  t.textContent = text; t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 2600);
}

// ---------- tiles ----------
let APPS = [];
const byId = (id) => APPS.find((a) => a.id === id);

function appTile(app) {
  const b = el("button", "tile");
  b.dataset.nav = ""; b.dataset.app = app.id;
  if (app.icon) { const i = el("img"); i.src = fileUrl(app.icon); i.alt = ""; b.append(i); }
  else b.append(el("div", null, "🎮"));
  b.append(el("span", null, app.name));
  return b;
}

function quickTile(icon, label, run) {
  const b = el("button", "tile");
  b.dataset.nav = "";
  b.append(el("div", null, icon), el("span", null, label));
  b.addEventListener("click", run);
  return b;
}

async function launch(id) {
  if (!byId(id)) { toast("That app isn't installed"); return; }
  const r = await ask("launch", { id });
  toast(r && r.ok ? `Opening ${byId(id).name}…` : (r && r.error) || "Couldn't open it");
  setTimeout(refreshRecent, 1500);
}

function fill(container, items) {
  container.replaceChildren(...items);
}

async function refreshRecent() {
  const rec = (await ask("recent", { limit: 10 })) || [];
  const apps = rec.map((r) => byId(r.id)).filter(Boolean);
  if (apps.length) fill($("#recent"), apps.map(appTile));
  // Hero: the last thing played, else Migood Games.
  const hero = apps.find((a) => a.game) || byId("migood-games.desktop") || apps[0];
  if (hero) {
    $("#hero").dataset.app = hero.id;
    $("#hero-title").textContent = hero.name;
    $("#hero-eyebrow").textContent = rec.length ? "Jump back in" : "Start here";
    $("#hero-sub").textContent = hero.comment || "Play, chat and Remote Play with your friends.";
    $("#hero-art").style.backgroundImage = hero.icon ? `url("${fileUrl(hero.icon)}")` : "";
  }
}

async function loadApps() {
  APPS = (await ask("apps")) || [];
  if (!Array.isArray(APPS)) APPS = [];
  const games = APPS.filter((a) => a.game);
  fill($("#games-grid"), games.map(appTile));
  fill($("#apps-grid"), APPS.map(appTile));
  fill($("#home-games"), games.slice(0, 12).map(appTile));
  const has = (id) => !!byId(id);
  const q = [];
  if (has("migood-games.desktop")) {
    q.push(quickTile("🛒", "Store", () => launch("migood-games.desktop")));
    q.push(quickTile("👥", "Friends", () => launch("migood-games.desktop")));
    q.push(quickTile("📡", "Remote Play", () => launch("migood-games.desktop")));
  }
  if (has("migood-ai.desktop")) q.push(quickTile("✨", "Migood AI", () => launch("migood-ai.desktop")));
  if (has("org.chromium.Chromium.desktop")) q.push(quickTile("🌐", "Browser", () => launch("org.chromium.Chromium.desktop")));
  if (has("migood-install.desktop")) q.push(quickTile("💾", "Install Migood OS", () => launch("migood-install.desktop")));
  q.push(quickTile("🖥", "Desktop mode", desktopMode));
  fill($("#quick"), q);
  await refreshRecent();
}

// ---------- status bar ----------
function clock() {
  $("#clock").textContent = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}
async function refreshStatus() {
  const s = (await ask("status")) || {};
  $("#net").textContent = s.online ? "● Online" : "○ Offline";
  $("#vol").textContent = s.volume == null ? "" : (s.muted ? "🔇" : "🔊 " + s.volume + "%");
  $("#bat").textContent = s.battery ? (s.battery.charging ? "⚡" : "🔋") + " " + s.battery.percent + "%" : "";
  if (s.volume != null) { $("#volume").value = s.volume; $("#volume-num").textContent = s.volume + "%"; }
}
async function loadAccount() {
  const a = (await ask("account")) || {};
  $("#myname").textContent = a.name || "Player";
  if (a.avatar) $("#avatar").src = fileUrl(a.avatar);
  else $("#avatar").src = "logo.png";
}

// ---------- settings ----------
async function loadWifi() {
  const nets = (await ask("wifi")) || [];
  if (!Array.isArray(nets) || !nets.length) { fill($("#wifi-list"), [el("p", "empty", "No Wi-Fi networks found.")]); return; }
  fill($("#wifi-list"), nets.slice(0, 12).map((n) => {
    const b = el("button", "net" + (n.connected ? " on" : ""));
    b.dataset.nav = "";
    b.append(el("span", null, (n.secure ? "🔒 " : "") + n.ssid),
             el("span", "sig", n.connected ? "Connected" : n.signal + "%"));
    b.addEventListener("click", () => connectWifi(n));
    return b;
  }));
}
async function connectWifi(n) {
  if (n.connected) return;
  let password = "";
  if (n.secure) {
    password = await askPassword(`Password for ${n.ssid}`);
    if (password == null) return;
  }
  toast(`Connecting to ${n.ssid}…`);
  const r = await ask("wifi_connect", { ssid: n.ssid, password });
  toast(r.ok ? `Connected to ${n.ssid}` : r.error || "Couldn't connect");
  loadWifi(); refreshStatus();
}
function askPassword(title) {
  return new Promise((resolve) => {
    $("#ask-title").textContent = title;
    const input = $("#ask-input"); input.value = "";
    openOverlay("#ask", input);
    const done = (v) => { closeOverlay(); $("#ask-ok").onclick = $("#ask-cancel").onclick = null; resolve(v); };
    $("#ask-ok").onclick = () => done(input.value);
    $("#ask-cancel").onclick = () => done(null);
    input.onkeydown = (e) => { if (e.key === "Enter") { e.stopPropagation(); done(input.value); } };
  });
}
$("#volume").addEventListener("input", (e) => {
  $("#volume-num").textContent = e.target.value + "%";
  ask("volume", { percent: +e.target.value });
});

function desktopMode() {
  toast("Switching to Desktop mode…");
  ask("desktop_mode");
}
const actions = {
  settings: () => launch("migood-settings.desktop"),
  updates: () => launch("migood-updates.desktop"),
  desktop: desktopMode,
  power: () => openOverlay("#power"),
};

// ---------- overlays ----------
let overlay = null;
function openOverlay(sel, focusEl) {
  overlay = $(sel); overlay.hidden = false;
  focus(focusEl || overlay.querySelector("[data-nav]"));
}
function closeOverlay() {
  if (!overlay) return;
  overlay.hidden = true; overlay = null;
  focus(document.querySelector(".page.active [data-nav]") || document.querySelector(".tab.active"));
}

// ---------- tabs ----------
const TABS = ["home", "games", "apps", "settings"];
function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".page").forEach((p) => p.classList.toggle("active", p.id === name));
  if (name === "settings") loadWifi();
}
function stepTab(d) {
  const cur = TABS.indexOf(document.querySelector(".tab.active").dataset.tab);
  const next = TABS[(cur + d + TABS.length) % TABS.length];
  showTab(next);
  focus(document.querySelector(`.tab[data-tab="${next}"]`));
}

// ---------- focus + spatial navigation (controller / arrows) ----------
let focused = null;
function focus(e) {
  if (!e) return;
  if (focused) focused.classList.remove("focus");
  focused = e; e.classList.add("focus");
  e.focus({ preventScroll: true });
  e.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
}
function candidates() {
  const root = overlay || document;
  return [...root.querySelectorAll("[data-nav]")].filter((e) => {
    if (!overlay && e.closest(".overlay")) return false;
    const page = e.closest(".page");
    return (!page || page.classList.contains("active")) && e.offsetParent !== null;
  });
}
function move(dx, dy) {
  const all = candidates();
  if (!focused || !all.includes(focused)) return focus(all[0]);
  const a = focused.getBoundingClientRect();
  const ax = a.left + a.width / 2, ay = a.top + a.height / 2;
  let best = null, bestScore = Infinity;
  for (const e of all) {
    if (e === focused) continue;
    const b = e.getBoundingClientRect();
    const bx = b.left + b.width / 2, by = b.top + b.height / 2;
    const ddx = bx - ax, ddy = by - ay;
    if (dx && Math.sign(ddx) !== dx) continue;
    if (dy && Math.sign(ddy) !== dy) continue;
    // Prefer things straight ahead; sideways distance costs more.
    const along = dx ? Math.abs(ddx) : Math.abs(ddy);
    const across = dx ? Math.abs(ddy) : Math.abs(ddx);
    const score = along + across * 2.5;
    if (score < bestScore) { bestScore = score; best = e; }
  }
  if (best) focus(best);
}
function activate(e) {
  if (!e) return;
  if (e.dataset.tab) return showTab(e.dataset.tab);
  if (e.dataset.app) return launch(e.dataset.app);
  if (e.dataset.power) { closeOverlay(); toast("Okay…"); return ask("power", { action: e.dataset.power }); }
  if (e.dataset.action && actions[e.dataset.action]) { if (overlay) closeOverlay(); return actions[e.dataset.action](); }
  e.click();
}
function back() {
  if (overlay) return closeOverlay();
  if (document.querySelector(".tab.active").dataset.tab !== "home") { showTab("home"); focus($(".tab")); }
}

document.addEventListener("keydown", (e) => {
  const typing = e.target.tagName === "INPUT" && e.target.type !== "range";
  const k = e.key;
  if (k === "ArrowLeft" && !typing) { move(-1, 0); e.preventDefault(); }
  else if (k === "ArrowRight" && !typing) { move(1, 0); e.preventDefault(); }
  else if (k === "ArrowUp") { move(0, -1); e.preventDefault(); }
  else if (k === "ArrowDown") { move(0, 1); e.preventDefault(); }
  else if (k === "Enter" && !typing) { activate(focused); e.preventDefault(); }
  else if (k === "Escape" || k === "BrowserBack") { back(); e.preventDefault(); }
  else if (k === "PageUp" || (k === "Tab" && e.shiftKey)) { stepTab(-1); e.preventDefault(); }
  else if (k === "PageDown" || k === "Tab") { stepTab(1); e.preventDefault(); }
  else if (k === "Meta" || k === "ContextMenu") { overlay ? closeOverlay() : openOverlay("#power"); }
});
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-nav]");
  if (!t || t.id === "ask-ok" || t.id === "ask-cancel" || t.type === "range") return;
  e.preventDefault(); focus(t); activate(t);
});
$("#me").dataset.action = "power";

// Gamepad: standard mapping (Xbox/PlayStation/Switch Pro controllers).
const BTN = { A: 0, B: 1, LB: 4, RB: 5, START: 9, UP: 12, DOWN: 13, LEFT: 14, RIGHT: 15 };
let held = {}, lastRepeat = 0;
function pollPads(t) {
  for (const pad of navigator.getGamepads ? navigator.getGamepads() : []) {
    if (!pad) continue;
    const ax = pad.axes[0] || 0, ay = pad.axes[1] || 0;
    const dir = {
      UP: pad.buttons[BTN.UP]?.pressed || ay < -0.6, DOWN: pad.buttons[BTN.DOWN]?.pressed || ay > 0.6,
      LEFT: pad.buttons[BTN.LEFT]?.pressed || ax < -0.6, RIGHT: pad.buttons[BTN.RIGHT]?.pressed || ax > 0.6,
    };
    const press = (name, down, fn, repeat) => {
      if (down && (!held[name] || (repeat && t - lastRepeat > 160 && t - held[name] > 350))) {
        if (held[name]) lastRepeat = t; else held[name] = t;
        fn();
      } else if (!down) delete held[name];
    };
    press("UP", dir.UP, () => move(0, -1), true);
    press("DOWN", dir.DOWN, () => move(0, 1), true);
    press("LEFT", dir.LEFT, () => move(-1, 0), true);
    press("RIGHT", dir.RIGHT, () => move(1, 0), true);
    press("A", pad.buttons[BTN.A]?.pressed, () => activate(focused));
    press("B", pad.buttons[BTN.B]?.pressed, back);
    press("LB", pad.buttons[BTN.LB]?.pressed, () => stepTab(-1));
    press("RB", pad.buttons[BTN.RB]?.pressed, () => stepTab(1));
    press("START", pad.buttons[BTN.START]?.pressed, () => (overlay ? closeOverlay() : openOverlay("#power")));
  }
  requestAnimationFrame(pollPads);
}
requestAnimationFrame(pollPads);

// ---------- start ----------
(async function start() {
  clock(); setInterval(clock, 10_000);
  await Promise.all([loadApps(), loadAccount(), refreshStatus()]);
  setInterval(refreshStatus, 15_000);
  focus($("#hero"));
})();
