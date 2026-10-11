// The Great Hall — Alexandria in 3D on a screen and in VR (WebXR, e.g. a Quest browser). Same packs, same tutor.
// Subjects are alcoves around the hall, articles are books on their shelves. Select a book to read it on a panel;
// select the floor to walk there; the orb in the centre is the tutor.
import * as THREE from "three";
import { VRButton } from "three/addons/webxr/VRButton.js";
import * as C from "./core.js";
import * as T from "./tutor.js";

let R = null;     // running hall

export async function enter(host, opts = {}) {
  if (R) return;
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  renderer.xr.enabled = true;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  host.appendChild(renderer.domElement);
  let vrb = null;
  if (navigator.xr && await navigator.xr.isSessionSupported("immersive-vr").catch(() => false)) {
    vrb = VRButton.createButton(renderer);
    host.appendChild(vrb);
    host.querySelector("#hallHint").textContent = "Press ENTER VR · trigger on a book to read · trigger on the floor to walk";
  }
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x07090d);
  scene.fog = new THREE.Fog(0x07090d, 14, 34);
  const rig = new THREE.Group();
  scene.add(rig);
  const camera = new THREE.PerspectiveCamera(70, innerWidth / innerHeight, 0.05, 100);
  camera.position.set(0, 1.6, 0);
  rig.add(camera);
  rig.position.set(0, 0, 5.5);

  // ---- light & architecture
  scene.add(new THREE.HemisphereLight(0xfff1d6, 0x10131a, 0.85));
  const key = new THREE.PointLight(0xffd58a, 40, 30, 1.6); key.position.set(0, 8, 0); scene.add(key);
  const RAD = 11;
  const floor = new THREE.Mesh(new THREE.CircleGeometry(RAD + 2, 96), new THREE.MeshStandardMaterial({ color: 0x1a1d24, roughness: 0.55, metalness: 0.15 }));
  floor.rotation.x = -Math.PI / 2; floor.userData.floor = true; scene.add(floor);
  const inlay = new THREE.Mesh(new THREE.RingGeometry(2.2, 2.32, 96), new THREE.MeshBasicMaterial({ color: 0xd4ad3b }));
  inlay.rotation.x = -Math.PI / 2; inlay.position.y = 0.005; scene.add(inlay);
  const inlay2 = inlay.clone(); inlay2.geometry = new THREE.RingGeometry(RAD - 3.2, RAD - 3.1, 128); scene.add(inlay2);
  const colMat = new THREE.MeshStandardMaterial({ color: 0xcfc6b2, roughness: 0.7 });
  for (let i = 0; i < 24; i++) {
    const a = i / 24 * Math.PI * 2;
    const c = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.26, 7, 20), colMat);
    c.position.set(Math.cos(a) * (RAD + 1), 3.5, Math.sin(a) * (RAD + 1)); scene.add(c);
  }
  const ring = new THREE.Mesh(new THREE.TorusGeometry(RAD + 1, 0.25, 12, 96), new THREE.MeshStandardMaterial({ color: 0xb59a5a, metalness: 0.6, roughness: 0.4 }));
  ring.rotation.x = Math.PI / 2; ring.position.y = 7; scene.add(ring);
  const stars = new THREE.Points(new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(
    Array.from({ length: 1800 }, () => { const u = Math.random() * Math.PI * 2, v = Math.random() * 0.45 * Math.PI, r = 30; return [r * Math.cos(u) * Math.cos(v), 8 + r * Math.sin(v), r * Math.sin(u) * Math.cos(v)]; }).flat(), 3)),
    new THREE.PointsMaterial({ color: 0xfff3d0, size: 0.08 }));
  scene.add(stars);

  // ---- tutor orb
  const orb = new THREE.Mesh(new THREE.IcosahedronGeometry(0.42, 3), new THREE.MeshStandardMaterial({ color: 0xd4ad3b, emissive: 0x8a6510, emissiveIntensity: 1.1, roughness: 0.3, metalness: 0.4 }));
  orb.position.set(0, 1.5, 0); orb.userData.orb = true; scene.add(orb);
  const ped = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.7, 1, 32), colMat); ped.position.y = 0.5; scene.add(ped);
  scene.add(label("Ask the tutor", 1.6, 0.28, 0, 2.25, 0, null, 54));

  // ---- subject alcoves with books
  const arts = await C.articles();
  const bySub = {};
  arts.forEach(a => (bySub[a.s] = bySub[a.s] || []).push(a));
  const subs = Object.keys(C.SUBJECTS).filter(s => bySub[s]);
  const pickables = [floor, orb];
  subs.forEach((s, k) => {
    const ang = k / subs.length * Math.PI * 2;
    const g = new THREE.Group();
    g.position.set(Math.cos(ang) * (RAD - 1.6), 0, Math.sin(ang) * (RAD - 1.6));
    g.lookAt(0, 0, 0);
    scene.add(g);
    const col = new THREE.Color(C.subj(s).c);
    const shelf = new THREE.Mesh(new THREE.BoxGeometry(3.2, 2.4, 0.5), new THREE.MeshStandardMaterial({ color: 0x4a3a26, roughness: 0.75 }));
    shelf.position.set(0, 1.2, -0.25); g.add(shelf);
    const glow = new THREE.PointLight(col, 14, 6, 2); glow.position.set(0, 2.6, 1.2); g.add(glow);
    g.add(label(`${C.subj(s).i}  ${s}`, 3.2, 0.42, 0, 2.75, 0.05, col, 60));
    const list = bySub[s].sort((a, b) => a.t.localeCompare(b.t));
    list.forEach((a, i) => {
      const row = Math.floor(i / 6), cIdx = i % 6;
      const book = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.62, 0.32), [
        new THREE.MeshStandardMaterial({ color: col.clone().multiplyScalar(0.6) }), new THREE.MeshStandardMaterial({ color: col.clone().multiplyScalar(0.6) }),
        new THREE.MeshStandardMaterial({ color: 0xe9e0c8 }), new THREE.MeshStandardMaterial({ color: 0xe9e0c8 }),
        new THREE.MeshStandardMaterial({ map: spine(a.t, col), roughness: 0.6 }), new THREE.MeshStandardMaterial({ color: col.clone().multiplyScalar(0.5) })]);
      book.position.set(-1.25 + cIdx * 0.5, 1.95 - row * 0.8, 0.12);
      book.userData.slug = a.slug;
      g.add(book); pickables.push(book);
    });
  });

  // ---- reading panel
  const panel = makePanel();
  scene.add(panel.group);
  panel.group.visible = false;
  pickables.push(...panel.buttons);

  // ---- input: mouse/touch on a screen, controllers in VR
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let yaw = 0, pitch = 0, drag = null, moved = 0;
  const el = renderer.domElement;
  el.addEventListener("pointerdown", e => { drag = [e.clientX, e.clientY]; moved = 0; el.setPointerCapture(e.pointerId); });
  el.addEventListener("pointermove", e => { if (!drag) return; const dx = e.clientX - drag[0], dy = e.clientY - drag[1]; moved += Math.abs(dx) + Math.abs(dy);
    yaw -= dx * 0.004; pitch = Math.max(-1.1, Math.min(1.1, pitch - dy * 0.004)); drag = [e.clientX, e.clientY]; });
  el.addEventListener("pointerup", e => { drag = null; if (moved < 6) { ndc.set(e.clientX / innerWidth * 2 - 1, -(e.clientY / innerHeight) * 2 + 1); ray.setFromCamera(ndc, camera); select(ray); } });
  el.addEventListener("wheel", e => { camera.fov = Math.max(40, Math.min(85, camera.fov + e.deltaY * 0.02)); camera.updateProjectionMatrix(); }, { passive: true });
  const keys = new Set();
  const kd = e => keys.add(e.key.toLowerCase()), ku = e => keys.delete(e.key.toLowerCase());
  addEventListener("keydown", kd); addEventListener("keyup", ku);
  const ctrls = [0, 1].map(i => {
    const c = renderer.xr.getController(i);
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(0, 0, -1)]), new THREE.LineBasicMaterial({ color: 0xd4ad3b }));
    line.scale.z = 8; c.add(line);
    c.addEventListener("selectstart", () => { const m = new THREE.Matrix4().extractRotation(c.matrixWorld); ray.ray.origin.setFromMatrixPosition(c.matrixWorld); ray.ray.direction.set(0, 0, -1).applyMatrix4(m); select(ray); });
    rig.add(c); return c;
  });

  let target = null;
  function select(rc) {
    const hit = rc.intersectObjects(pickables, false)[0];
    if (!hit) return;
    const o = hit.object;
    if (o.userData.btn) return panel.press(o.userData.btn);
    if (o.userData.slug) return panel.open(o.userData.slug, o);
    if (o.userData.orb) return panel.tutor();
    if (o.userData.floor) { const p = hit.point; const r = Math.hypot(p.x, p.z); const k = Math.min(1, (RAD - 2.6) / r); target = new THREE.Vector3(p.x * k, 0, p.z * k); }
  }

  // panel placement: in front of where you look
  function placePanel(near) {
    const dir = new THREE.Vector3(); camera.getWorldDirection(dir); dir.y = 0; dir.normalize();
    const pos = new THREE.Vector3(); camera.getWorldPosition(pos);
    panel.group.position.copy(pos).addScaledVector(dir, near ? 1.4 : 1.7); panel.group.position.y = renderer.xr.isPresenting ? pos.y - 0.1 : 1.55;
    panel.group.lookAt(pos.x, panel.group.position.y, pos.z);
    panel.group.visible = true;
  }

  function makePanel() {
    const W = 1024, H = 1200;
    const cv = document.createElement("canvas"); cv.width = W; cv.height = H;
    const ctx = cv.getContext("2d");
    const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
    const group = new THREE.Group();
    const board = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 1.29), new THREE.MeshBasicMaterial({ map: tex, transparent: true }));
    group.add(board);
    const mk = (txt, x) => { const b = label(txt, 0.2, 0.09, x, -0.72, 0.01, null, 40, true); b.userData.btn = txt; return b; };
    const buttons = [mk("◀ Prev", -0.44), mk("Next ▶", -0.22), mk("Level", 0), mk("Listen", 0.22), mk("✕", 0.44)];
    buttons.forEach(b => group.add(b));
    const S = { slug: null, title: "", pages: [], page: 0, level: opts.level || "deeper", mode: "read" };
    function draw() {
      ctx.fillStyle = "#f4ecd8"; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = "#d4ad3b"; ctx.fillRect(0, 0, W, 14);
      ctx.fillStyle = "#6a5a35"; ctx.font = "600 28px Inter, sans-serif";
      ctx.fillText(S.mode === "tutor" ? "TUTOR · answers only from the library" : (S.level === "young" ? "YOUNG READERS · K–5" : "EXPLORE DEEPER · 6–12"), 60, 70);
      ctx.fillStyle = "#1d1a14"; ctx.font = "650 58px Fraunces, Georgia, serif";
      let y = 150; for (const l of wrap(ctx, S.title, W - 120)) { ctx.fillText(l, 60, y); y += 66; }
      y += 16; ctx.font = "400 36px Fraunces, Georgia, serif"; ctx.fillStyle = "#2a251c";
      for (const l of S.pages[S.page] || []) { ctx.fillText(l, 60, y); y += 50; }
      ctx.fillStyle = "#8a7d62"; ctx.font = "500 24px JetBrains Mono, monospace";
      ctx.fillText(S.pages.length > 1 ? `page ${S.page + 1} of ${S.pages.length}` : "", 60, H - 40);
      tex.needsUpdate = true;
    }
    function paginate(text, titleLines) {
      ctx.font = "400 36px Fraunces, Georgia, serif";
      const lines = text.split("\n").flatMap(p => p ? wrap(ctx, p, W - 120).concat([""]) : [""]);
      const per = Math.floor((H - 260 - titleLines * 66) / 50);
      const pages = []; for (let i = 0; i < lines.length; i += per) pages.push(lines.slice(i, i + per));
      return pages.length ? pages : [[]];
    }
    async function open(slug) {
      const a = await C.article(slug);
      const lv = a.levels[S.level] ? S.level : Object.keys(a.levels)[0];
      const paras = await C.decode(a.levels[lv]);
      ctx.font = "650 58px Fraunces, Georgia, serif";
      Object.assign(S, { slug, mode: "read", level: lv, title: a.title, page: 0, text: paras.map(p => p.map(x => x.t).join(" ")).join("\n") });
      S.pages = paginate(S.text, wrap(ctx, a.title, W - 120).length);
      draw(); placePanel();
    }
    async function tutor(q) {
      const day = Math.floor(Date.now() / 864e5);
      const focus = S.slug || (arts[day % arts.length] || {}).slug;
      const question = q || `Summarize ${(arts.find(a => a.slug === focus) || {}).t || "the library"}`;
      const r = await T.answer(question, { slug: focus, level: S.level });
      const body = [r.text, ...(r.cites || []).map(c => `“${c.t}”  [${c.a} · ${c.title}]`)].join("\n");
      ctx.font = "650 58px Fraunces, Georgia, serif";
      Object.assign(S, { mode: "tutor", title: question, page: 0, text: body });
      S.pages = paginate(body, wrap(ctx, question, W - 120).length);
      draw(); placePanel(true);
    }
    function press(b) {
      if (b.startsWith("◀")) S.page = Math.max(0, S.page - 1);
      else if (b.startsWith("Next")) S.page = Math.min(S.pages.length - 1, S.page + 1);
      else if (b === "Level" && S.mode === "read") { S.level = S.level === "young" ? "deeper" : "young"; return open(S.slug); }
      else if (b === "Level") return;
      else if (b === "Listen") { speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance((S.pages[S.page] || []).join(" ")); speechSynthesis.speak(u); return; }
      else if (b === "✕") { group.visible = false; speechSynthesis.cancel(); return; }
      draw();
    }
    return { group, buttons, open, tutor, press };
  }

  // ---- loop
  const clock = new THREE.Clock();
  function onResize() { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); }
  addEventListener("resize", onResize);
  renderer.setAnimationLoop(() => {
    const dt = Math.min(clock.getDelta(), 0.05), t = clock.elapsedTime;
    orb.rotation.y += dt * 0.5; orb.position.y = 1.5 + Math.sin(t * 1.4) * 0.06;
    stars.rotation.y += dt * 0.004;
    if (!renderer.xr.isPresenting) {
      camera.rotation.set(pitch, yaw, 0, "YXZ");
      const f = new THREE.Vector3(-Math.sin(yaw), 0, -Math.cos(yaw)), r = new THREE.Vector3(Math.cos(yaw), 0, -Math.sin(yaw));
      const sp = 3 * dt;
      if (keys.has("w") || keys.has("arrowup")) rig.position.addScaledVector(f, sp);
      if (keys.has("s") || keys.has("arrowdown")) rig.position.addScaledVector(f, -sp);
      if (keys.has("a") || keys.has("arrowleft")) rig.position.addScaledVector(r, -sp);
      if (keys.has("d") || keys.has("arrowright")) rig.position.addScaledVector(r, sp);
      const rr = Math.hypot(rig.position.x, rig.position.z); if (rr > RAD - 2.6) rig.position.multiplyScalar((RAD - 2.6) / rr);
    }
    if (target) { rig.position.lerp(target, Math.min(1, dt * 4)); if (rig.position.distanceTo(target) < 0.02) target = null; }
    renderer.render(scene, camera);
  });
  R = { renderer, host, vrb, onExit: opts.onExit, cleanup: () => { removeEventListener("resize", onResize); removeEventListener("keydown", kd); removeEventListener("keyup", ku); } };
  window.__hall = { scene, camera, panel, rig };   // for testing
}

export function exit() {
  if (!R) return;
  const s = R.renderer.xr.getSession(); if (s) s.end();
  R.renderer.setAnimationLoop(null);
  R.renderer.domElement.remove(); if (R.vrb) R.vrb.remove();
  R.renderer.dispose(); R.cleanup(); speechSynthesis.cancel();
  const cb = R.onExit; R = null; if (cb) cb();
}

// ---- canvas helpers
function wrap(ctx, text, max) {
  const out = []; let line = "";
  for (const w of String(text).split(/\s+/)) {
    const t = line ? line + " " + w : w;
    if (ctx.measureText(t).width > max && line) { out.push(line); line = w; } else line = t;
  }
  if (line) out.push(line);
  return out;
}
function label(text, w, h, x, y, z, color, px = 48, button = false) {
  const cv = document.createElement("canvas"); cv.width = 1024; cv.height = Math.round(1024 * h / w);
  const ctx = cv.getContext("2d");
  ctx.fillStyle = button ? "#1d2430" : "rgba(10,12,16,0.82)"; roundRect(ctx, 0, 0, cv.width, cv.height, cv.height * 0.3); ctx.fill();
  ctx.strokeStyle = color ? "#" + color.getHexString() : "#d4ad3b"; ctx.lineWidth = 6; roundRect(ctx, 3, 3, cv.width - 6, cv.height - 6, cv.height * 0.3); ctx.stroke();
  ctx.fillStyle = "#f2ead6"; ctx.font = `600 ${Math.round(px * cv.height / 140)}px Inter, sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(text, cv.width / 2, cv.height / 2 + 2);
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex, transparent: true }));
  m.position.set(x, y, z); return m;
}
function spine(title, col) {
  const cv = document.createElement("canvas"); cv.width = 256; cv.height = 380;
  const ctx = cv.getContext("2d");
  ctx.fillStyle = "#" + col.clone().multiplyScalar(0.55).getHexString(); ctx.fillRect(0, 0, 256, 380);
  ctx.strokeStyle = "#d4ad3b"; ctx.lineWidth = 6; ctx.strokeRect(14, 14, 228, 352);
  ctx.fillStyle = "#f6edd6"; ctx.font = "650 30px Fraunces, Georgia, serif"; ctx.textAlign = "center";
  const lines = wrap(ctx, title, 200).slice(0, 5); let y = 190 - (lines.length - 1) * 19;
  for (const l of lines) { ctx.fillText(l, 128, y); y += 38; }
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; return t;
}
function roundRect(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
