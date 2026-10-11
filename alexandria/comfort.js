// Comfort — anti eye-fatigue and anti-nausea settings, kept per viewer and used by every page and by the 3D/VR Hall.
// Reading: paper / sepia / night / warm-night (less blue light), text size, line spacing, an easy-read font, a column
// width cap, reduced motion, and a 20-20-20 break reminder. VR: teleport only (no gliding), snap turning,
// a comfort vignette, a seated height option and a lighter scene for steadier frame rates.
const KEY = "alexandria.comfort";
const DEFAULTS = { theme: "auto", size: 100, leading: 1.75, font: "serif", motion: "auto", breaks: true, breakMin: 20, rate: 1.0,
  vrTurn: "snap30", vrVignette: true, vrTeleportOnly: true, vrSeated: false, vrLight: false };
let S = load();
const listeners = new Set();
function load() { try { return Object.assign({}, DEFAULTS, JSON.parse(localStorage.getItem(KEY) || "{}")); } catch (e) { return { ...DEFAULTS }; } }
function save() { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} listeners.forEach(f => f(S)); }
export const get = () => S;
export const onChange = f => listeners.add(f);
export const reducedMotion = () => S.motion === "reduce" || (S.motion === "auto" && matchMedia("(prefers-reduced-motion: reduce)").matches);
export const scrollBehavior = () => (reducedMotion() ? "auto" : "smooth");

export function apply() {
  const r = document.documentElement;
  const theme = S.theme === "auto" ? (r.dataset.userTheme || "") : S.theme;
  r.dataset.reading = ["sepia", "night", "warm"].includes(theme) ? theme : "";
  if (theme === "light" || theme === "dark") r.dataset.theme = theme;
  else if (theme === "sepia") r.dataset.theme = "light";
  else if (theme === "night" || theme === "warm") r.dataset.theme = "dark";
  r.style.setProperty("--read-scale", S.size / 100);
  r.style.setProperty("--read-leading", S.leading);
  r.dataset.font = S.font;
  r.dataset.motion = reducedMotion() ? "reduce" : "";
  scheduleBreak();
}

// ---- 20-20-20: every 20 minutes of reading, look at something 20 feet away for 20 seconds
let breakTimer = null, lastActive = Date.now(), activeMs = 0;
["scroll", "keydown", "pointerdown"].forEach(ev => addEventListener(ev, () => { const now = Date.now(); if (now - lastActive < 60000) activeMs += now - lastActive; lastActive = now; }, { passive: true }));
function scheduleBreak() {
  clearInterval(breakTimer);
  if (!S.breaks) return;
  breakTimer = setInterval(() => {
    if (document.hidden || activeMs < S.breakMin * 60000) return;
    activeMs = 0;
    showBreak();
  }, 30000);
}
function showBreak() {
  if (document.querySelector(".eye-break")) return;
  const d = document.createElement("div");
  d.className = "eye-break";
  d.innerHTML = `<div><b>Rest your eyes</b><p>Look at something far away — about 20 feet — for 20 seconds. Blink slowly.</p><div class="eb-bar"><i></i></div><button class="pill">I'm back</button></div>`;
  document.body.appendChild(d);
  d.querySelector("button").onclick = () => d.remove();
  setTimeout(() => d.remove(), 21000);
}

// ---- the settings panel
export function panel() {
  let p = document.getElementById("comfortPanel");
  if (p) { p.hidden = !p.hidden; return; }
  p = document.createElement("aside");
  p.id = "comfortPanel";
  p.className = "comfort";
  const opt = (name, val, label) => `<button data-k="${name}" data-v="${val}" class="${String(S[name]) === String(val) ? "on" : ""}">${label}</button>`;
  p.innerHTML = `
    <div class="tutor-head"><div><b>Comfort</b><small>easy on the eyes, steady in VR</small></div><button class="icon" data-close>✕</button></div>
    <div class="cf-body">
      <h5>Page</h5><div class="cf-seg">${opt("theme", "auto", "Auto")}${opt("theme", "light", "Paper")}${opt("theme", "sepia", "Sepia")}${opt("theme", "night", "Night")}${opt("theme", "warm", "Warm night")}</div>
      <p class="fine">Warm night cuts blue light for evening reading.</p>
      <h5>Text size <span id="cfSize">${S.size}%</span></h5><input type="range" min="85" max="160" step="5" value="${S.size}" data-r="size">
      <h5>Line spacing <span id="cfLead">${S.leading}</span></h5><input type="range" min="1.4" max="2.2" step="0.05" value="${S.leading}" data-r="leading">
      <h5>Font</h5><div class="cf-seg">${opt("font", "serif", "Book")}${opt("font", "sans", "Clean")}${opt("font", "easy", "Easy-read")}</div>
      <h5>Motion</h5><div class="cf-seg">${opt("motion", "auto", "Follow device")}${opt("motion", "reduce", "Reduce")}${opt("motion", "full", "Full")}</div>
      <h5>Eye breaks</h5><div class="cf-seg">${opt("breaks", true, "Remind me")}${opt("breaks", false, "Off")}</div>
      <p class="fine">Every ${S.breakMin} minutes of reading: look far away for 20 seconds.</p>
      <h5>Read-aloud speed <span id="cfRate">${S.rate.toFixed(2)}×</span></h5><input type="range" min="0.7" max="1.4" step="0.05" value="${S.rate}" data-r="rate">
      <h5>VR · moving</h5><div class="cf-seg">${opt("vrTeleportOnly", true, "Teleport only")}${opt("vrTeleportOnly", false, "Allow gliding")}</div>
      <h5>VR · turning</h5><div class="cf-seg">${opt("vrTurn", "snap30", "Snap 30°")}${opt("vrTurn", "snap45", "Snap 45°")}${opt("vrTurn", "smooth", "Smooth")}</div>
      <h5>VR · comfort</h5><div class="cf-seg">${opt("vrVignette", true, "Vignette on")}${opt("vrVignette", false, "Off")}</div>
      <div class="cf-seg">${opt("vrSeated", false, "Standing")}${opt("vrSeated", true, "Seated")}</div>
      <div class="cf-seg">${opt("vrLight", false, "Full scene")}${opt("vrLight", true, "Lighter scene (steadier)")}</div>
      <button class="pill" data-reset style="margin-top:14px">Reset to defaults</button>
    </div>`;
  document.body.appendChild(p);
  p.addEventListener("click", ev => {
    if (ev.target.closest("[data-close]")) { p.hidden = true; return; }
    if (ev.target.closest("[data-reset]")) { S = { ...DEFAULTS }; save(); apply(); p.remove(); panel(); return; }
    const b = ev.target.closest("[data-k]"); if (!b) return;
    let v = b.dataset.v; v = v === "true" ? true : v === "false" ? false : v;
    S[b.dataset.k] = v; save(); apply();
    b.parentElement.querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b));
  });
  p.addEventListener("input", ev => {
    const r = ev.target.dataset.r; if (!r) return;
    S[r] = +ev.target.value; save(); apply();
    p.querySelector("#cfSize").textContent = S.size + "%"; p.querySelector("#cfLead").textContent = S.leading; p.querySelector("#cfRate").textContent = S.rate.toFixed(2) + "×";
  });
}
