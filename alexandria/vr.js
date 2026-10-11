// The Great Hall and the Hall of Presidents — Alexandria in 3D on a screen and in VR (WebXR, e.g. a Quest browser).
// The architecture is built in Blender and baked in Cycles (sets/*.glb); this file brings it to life: books on the
// shelves, a tutor orb, a screening wall, 47 presidents on their pedestals, speeches delivered at the lectern.
// Live content sits on anchors named in Blender (NICHE_k, ORB, SPAWN, P01..P47, LECTERN, SCREEN).
import * as THREE from "three";
import { VRButton } from "three/addons/webxr/VRButton.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import * as C from "./core.js";
import * as T from "./tutor.js";
import { ERAS, eraOf } from "./presidents.js";

const SETS = new URL("../sets/", import.meta.url).href;
const PRES_OFFSET = new THREE.Vector3(0, 0, -120);       // the theater is built away from the rotunda
let R = null;

// ------------------------------------------------------------------ helpers
function canvasTex(w, h, draw) {
  const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
  draw(cv.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}
function wrap(ctx, text, max) {
  const out = []; let line = "";
  for (const w of String(text).split(/\s+/)) { const t = line ? line + " " + w : w; if (ctx.measureText(t).width > max && line) { out.push(line); line = w; } else line = t; }
  if (line) out.push(line); return out;
}
function rr(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
function label(text, w, h, opts = {}) {
  const px = opts.px || 54, col = opts.color || "#d4ad3b";
  const tex = canvasTex(1024, Math.round(1024 * h / w), (ctx, W, H) => {
    ctx.fillStyle = opts.button ? "rgba(24,30,40,.92)" : "rgba(10,12,16,.78)"; rr(ctx, 0, 0, W, H, H * 0.28); ctx.fill();
    ctx.strokeStyle = col; ctx.lineWidth = 6; rr(ctx, 3, 3, W - 6, H - 6, H * 0.28); ctx.stroke();
    ctx.fillStyle = "#f6ecd2"; ctx.font = `600 ${Math.round(px * H / 140)}px Inter, sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(text, W / 2, H / 2 + 2);
  });
  return new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }));
}
function spineTex(title, col) {
  return canvasTex(256, 380, (ctx) => {
    const g = ctx.createLinearGradient(0, 0, 256, 0);
    g.addColorStop(0, "#" + col.clone().multiplyScalar(0.35).getHexString()); g.addColorStop(0.5, "#" + col.clone().multiplyScalar(0.7).getHexString()); g.addColorStop(1, "#" + col.clone().multiplyScalar(0.35).getHexString());
    ctx.fillStyle = g; ctx.fillRect(0, 0, 256, 380);
    ctx.strokeStyle = "#e3c06a"; ctx.lineWidth = 5; ctx.strokeRect(16, 16, 224, 348); ctx.strokeRect(26, 26, 204, 328);
    ctx.fillStyle = "#f8efd8"; ctx.font = "650 30px Fraunces, Georgia, serif"; ctx.textAlign = "center";
    const lines = wrap(ctx, title, 190).slice(0, 5); let y = 190 - (lines.length - 1) * 19;
    for (const l of lines) { ctx.fillText(l, 128, y); y += 38; }
  });
}
function medalTex(p) {
  const e = eraOf(p.n);
  return canvasTex(512, 640, (ctx, W, H) => {
    const g = ctx.createRadialGradient(W * 0.4, H * 0.34, 20, W / 2, H * 0.4, W * 0.5);
    g.addColorStop(0, "#ffffff"); g.addColorStop(0.18, e[3]); g.addColorStop(1, "#140d07");
    ctx.fillStyle = "rgba(0,0,0,0)"; ctx.fillRect(0, 0, W, H);
    ctx.beginPath(); ctx.arc(W / 2, H * 0.4, W * 0.42, 0, Math.PI * 2); ctx.fillStyle = g; ctx.fill();
    ctx.lineWidth = 14; ctx.strokeStyle = "#e9c55a"; ctx.stroke();
    ctx.fillStyle = "#fff6dd"; ctx.textAlign = "center"; ctx.font = "650 140px Fraunces, Georgia, serif";
    ctx.fillText(p.name.split(/\s+/).filter(w => /^[A-Z]/.test(w)).map(w => w[0]).join("").slice(0, 3), W / 2, H * 0.47);
    ctx.font = "600 44px Inter, sans-serif"; ctx.fillStyle = "#e9c55a"; ctx.fillText(String(p.n), W / 2, H * 0.2);
    rr(ctx, 30, H * 0.82, W - 60, 92, 30); ctx.fillStyle = "rgba(12,10,8,.85)"; ctx.fill(); ctx.strokeStyle = "#e9c55a"; ctx.lineWidth = 4; ctx.stroke();
    ctx.fillStyle = "#f6ecd2"; ctx.font = "600 40px Inter, sans-serif"; ctx.fillText(p.name, W / 2, H * 0.82 + 58, W - 80);
  });
}
function beamMesh(height, radius, color) {
  const geo = new THREE.ConeGeometry(radius, height, 48, 1, true); geo.translate(0, -height / 2, 0);
  const tex = canvasTex(4, 256, (ctx) => { const g = ctx.createLinearGradient(0, 0, 0, 256); g.addColorStop(0, "rgba(255,240,200,0.0)"); g.addColorStop(0.15, "rgba(255,232,180,0.35)"); g.addColorStop(1, "rgba(255,225,160,0.02)"); ctx.fillStyle = g; ctx.fillRect(0, 0, 4, 256); });
  return new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ map: tex, color, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
}
function dust(count, radius, height, center) {
  const pos = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) { const a = Math.random() * Math.PI * 2, r = Math.sqrt(Math.random()) * radius; pos.set([center.x + Math.cos(a) * r, Math.random() * height, center.z + Math.sin(a) * r], i * 3); }
  const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const sprite = canvasTex(64, 64, (ctx) => { const gr = ctx.createRadialGradient(32, 32, 0, 32, 32, 32); gr.addColorStop(0, "rgba(255,240,210,1)"); gr.addColorStop(1, "rgba(255,240,210,0)"); ctx.fillStyle = gr; ctx.fillRect(0, 0, 64, 64); });
  return new THREE.Points(g, new THREE.PointsMaterial({ size: 0.05, map: sprite, transparent: true, opacity: 0.55, depthWrite: false, blending: THREE.AdditiveBlending }));
}
async function loadSet(name) {
  const gltf = await new GLTFLoader().loadAsync(SETS + name);
  const anchors = {};
  gltf.scene.traverse(o => {
    if (o.isMesh) {
      const src = o.material;
      if (o.userData.baked && src.map) { o.material = new THREE.MeshBasicMaterial({ map: src.map, side: THREE.DoubleSide }); o.material.map.colorSpace = THREE.SRGBColorSpace; }
      else if (o.userData.emissive) o.material = new THREE.MeshBasicMaterial({ color: src.color.clone().multiplyScalar(2.2) });
      o.userData.surface = true;
    } else if (/^(NICHE_\d|ORB|SPAWN|P\d\d|LECTERN|SCREEN)$/.test(o.name)) anchors[o.name] = o;
  });
  return { root: gltf.scene, anchors };
}
// Blender's niche anchors point their front away from the centre; turn them half round so -z is "into the niche"
const at = (anchor, x, y, z) => anchor.localToWorld(new THREE.Vector3(-x, y, -z));
const HALF = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.PI);
const faceQ = anchor => anchor.getWorldQuaternion(new THREE.Quaternion()).multiply(HALF);

// ------------------------------------------------------------------ the hall
export async function enter(host, opts = {}) {
  if (R) return;
  const hint = t => { const h = host.querySelector("#hallHint"); if (h) h.textContent = t; };
  hint("Opening the Great Hall…");
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  renderer.xr.enabled = true;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  host.appendChild(renderer.domElement);
  let vrb = null;
  const xr = navigator.xr && await navigator.xr.isSessionSupported("immersive-vr").catch(() => false);
  if (xr) { vrb = VRButton.createButton(renderer); host.appendChild(vrb); }
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x05060a);
  scene.fog = new THREE.FogExp2(0x05060a, 0.012);
  const rig = new THREE.Group(); scene.add(rig);
  const camera = new THREE.PerspectiveCamera(68, innerWidth / innerHeight, 0.05, 400);
  camera.position.set(0, 1.6, 0); rig.add(camera);
  scene.add(new THREE.HemisphereLight(0xfff1d6, 0x10131a, 1.2));     // only lights the live (unbaked) objects

  // post-processing on screens (not in the headset): bloom makes gold, glow and the oculus shine
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.5, 0.55, 0.99);   // only light sources bloom
  composer.addPass(bloom); composer.addPass(new OutputPass());

  const pickables = [];
  const floors = [];
  let hall, pres;
  try { hall = await loadSet("great_hall.glb"); }
  catch (e) { hall = null; }
  const arts = await C.articles();
  const subs = Object.keys(C.SUBJECTS).filter(s => arts.some(a => a.s === s));

  // ---- Great Hall
  const hallGroup = new THREE.Group(); scene.add(hallGroup);
  let anchors = {};
  if (hall) {
    hallGroup.add(hall.root); anchors = hall.anchors;
    hall.root.traverse(o => { if (o.isMesh && /floor/i.test(o.name)) { o.userData.floor = "hall"; floors.push(o); } });
  } else {                                                          // fallback architecture if the set is missing
    const f = new THREE.Mesh(new THREE.CircleGeometry(15, 96), new THREE.MeshStandardMaterial({ color: 0x1a1d24, roughness: 0.5 }));
    f.rotation.x = -Math.PI / 2; f.userData.floor = "hall"; hallGroup.add(f); floors.push(f);
    for (let k = 0; k < 10; k++) { const a = k / 10 * Math.PI * 2, e = new THREE.Object3D(); e.position.set(Math.sin(a) * 15, 0, -Math.cos(a) * 15); e.lookAt(0, 0, 0); hallGroup.add(e); anchors["NICHE_" + k] = e; }
    const o = new THREE.Object3D(); o.position.set(0, 1.55, 0); anchors.ORB = o; const s = new THREE.Object3D(); s.position.set(0, 0, 6.5); anchors.SPAWN = s;
  }
  hallGroup.updateMatrixWorld(true);
  rig.position.copy(anchors.SPAWN.getWorldPosition(new THREE.Vector3()));
  // light shaft from the oculus + floating dust
  const shaft = beamMesh(24, 3.0, 0x8a7a5a); shaft.position.set(0, 23, 0); hallGroup.add(shaft);
  const motes = dust(900, 6, 18, new THREE.Vector3()); hallGroup.add(motes);
  // tutor orb
  const orbPos = anchors.ORB.getWorldPosition(new THREE.Vector3());
  const orb = new THREE.Mesh(new THREE.IcosahedronGeometry(0.4, 4), new THREE.MeshStandardMaterial({ color: 0xffd36a, emissive: 0xc8901a, emissiveIntensity: 1.6, roughness: 0.25, metalness: 0.5 }));
  orb.position.copy(orbPos); orb.userData.orb = true; hallGroup.add(orb); pickables.push(orb);
  const orbLabel = label("Ask the tutor", 1.5, 0.26, { px: 56 }); orbLabel.position.copy(orbPos).add(new THREE.Vector3(0, 0.75, 0)); hallGroup.add(orbLabel);
  // subject niches with books
  subs.forEach((s, k) => {
    const an = anchors["NICHE_" + (k + 1)]; if (!an) return;
    const col = new THREE.Color(C.subj(s).c);
    const lab = label(`${C.subj(s).i}  ${s}`, 3.0, 0.4, { color: C.subj(s).c, px: 60 });
    lab.position.copy(at(an, 0, 4.75, -0.25)); lab.quaternion.copy(faceQ(an)); hallGroup.add(lab);
    const glow = new THREE.PointLight(col, 6, 5, 2); glow.position.copy(at(an, 0, 3, 0.6)); hallGroup.add(glow);
    const list = arts.filter(a => a.s === s).sort((a, b) => a.t.localeCompare(b.t));
    list.forEach((a, i) => {
      const row = Math.floor(i / 7), c = i % 7;
      const book = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.58, 0.3), [
        new THREE.MeshStandardMaterial({ color: col.clone().multiplyScalar(0.5), roughness: 0.6 }), new THREE.MeshStandardMaterial({ color: col.clone().multiplyScalar(0.5), roughness: 0.6 }),
        new THREE.MeshStandardMaterial({ color: 0xe9e0c8 }), new THREE.MeshStandardMaterial({ color: 0xe9e0c8 }),
        new THREE.MeshStandardMaterial({ map: spineTex(a.t, col), roughness: 0.55 }), new THREE.MeshStandardMaterial({ color: col.clone().multiplyScalar(0.45) })]);
      book.position.copy(at(an, -1.45 + c * 0.48, 2.93 - row * 1.0, -1.3));
      book.quaternion.copy(faceQ(an));
      book.userData.slug = a.slug; hallGroup.add(book); pickables.push(book);
    });
  });
  // door to the Hall of Presidents (niche 0)
  const doorA = anchors.NICHE_0;
  const door = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 4.6), new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }));
  door.position.copy(at(doorA, 0, 2.4, -1.2)); door.quaternion.copy(faceQ(doorA)); door.userData.door = "presidents";
  hallGroup.add(door); pickables.push(door);
  const doorLab = label("★  The Hall of Presidents  ★", 3.4, 0.46, { px: 58 }); doorLab.position.copy(at(doorA, 0, 5.75, 0.6)); doorLab.quaternion.copy(door.quaternion); hallGroup.add(doorLab);
  // screening wall (niche 9)
  const screen = buildScreen(anchors.NICHE_9);

  // ---- reading panel (shared by both halls)
  const panel = makePanel();
  scene.add(panel.group); panel.group.visible = false; pickables.push(...panel.buttons);

  // ---- input
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  let yaw = 0, pitch = 0, drag = null, moved = 0, target = null;
  const el = renderer.domElement;
  el.addEventListener("pointerdown", e => { drag = [e.clientX, e.clientY]; moved = 0; el.setPointerCapture(e.pointerId); });
  el.addEventListener("pointermove", e => { if (!drag) return; const dx = e.clientX - drag[0], dy = e.clientY - drag[1]; moved += Math.abs(dx) + Math.abs(dy);
    yaw -= dx * 0.0042; pitch = Math.max(-1.1, Math.min(1.1, pitch - dy * 0.0042)); drag = [e.clientX, e.clientY]; });
  el.addEventListener("pointerup", e => { drag = null; if (moved < 6) { ndc.set(e.clientX / innerWidth * 2 - 1, -(e.clientY / innerHeight) * 2 + 1); ray.setFromCamera(ndc, camera); select(ray); } });
  el.addEventListener("wheel", e => { camera.fov = Math.max(38, Math.min(85, camera.fov + e.deltaY * 0.02)); camera.updateProjectionMatrix(); }, { passive: true });
  const keys = new Set(); const kd = e => keys.add(e.key.toLowerCase()), ku = e => keys.delete(e.key.toLowerCase());
  addEventListener("keydown", kd); addEventListener("keyup", ku);
  [0, 1].forEach(i => {
    const c = renderer.xr.getController(i);
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(0, 0, -1)]), new THREE.LineBasicMaterial({ color: 0xe9c55a }));
    line.scale.z = 10; c.add(line);
    c.addEventListener("selectstart", () => { const m = new THREE.Matrix4().extractRotation(c.matrixWorld); ray.ray.origin.setFromMatrixPosition(c.matrixWorld); ray.ray.direction.set(0, 0, -1).applyMatrix4(m); select(ray); });
    rig.add(c);
  });
  function select(rc) {
    const hit = rc.intersectObjects(pickables.concat(floors), false)[0];
    if (!hit) return;
    const o = hit.object;
    if (o.userData.btn) return panel.press(o.userData.btn);
    if (o.userData.slug) return panel.open(o.userData.slug);
    if (o.userData.orb) return panel.tutor();
    if (o.userData.media && screen) return screen.show(o.userData.media);
    if (o.userData.door === "presidents") return goPresidents();
    if (o.userData.door === "hall") return goHall();
    if (o.userData.pres) return pres && pres.spot(o.userData.pres);
    if (o.userData.roll) return pres && pres.roll();
    if (o.userData.floor) { target = hit.point.clone(); target.y = 0; }
  }
  function placePanel(near) {
    const dir = new THREE.Vector3(); camera.getWorldDirection(dir); dir.y = 0; dir.normalize();
    const pos = new THREE.Vector3(); camera.getWorldPosition(pos);
    panel.group.position.copy(pos).addScaledVector(dir, near ? 1.4 : 1.75); panel.group.position.y = renderer.xr.isPresenting ? pos.y - 0.1 : pos.y - 0.05;
    panel.group.lookAt(pos.x, panel.group.position.y, pos.z); panel.group.visible = true;
  }

  // ---- screening wall
  function buildScreen(an) {
    if (!an) return null;
    const q = faceQ(an);
    const scrMat = new THREE.MeshBasicMaterial({ color: 0x0b0d12 });
    const scr = new THREE.Mesh(new THREE.PlaneGeometry(3.85, 2.2), scrMat); scr.position.copy(at(an, 0, 2.7, -1.38)); scr.quaternion.copy(q); hallGroup.add(scr);
    const lab = label("▶  Film, Sound & Pictures", 3.0, 0.4, { px: 58 }); lab.position.copy(at(an, 0, 4.75, -0.25)); lab.quaternion.copy(q); hallGroup.add(lab);
    const loader = new THREE.TextureLoader(); loader.setCrossOrigin("anonymous");
    let video = null, audio = null;
    C.sources().then(srcs => {
      const media = srcs.filter(e => ["video", "audio", "image", "map"].includes(e.fm) && (e.th || e.mv)).slice(-12);
      media.forEach((e, i) => {
        const m = new THREE.MeshBasicMaterial({ color: 0x2a3140 });
        const tile = new THREE.Mesh(new THREE.PlaneGeometry(0.56, 0.36), m);
        tile.position.copy(at(an, -1.5 + (i % 6) * 0.6, 1.25 - Math.floor(i / 6) * 0.42, -1.2)); tile.quaternion.copy(q);
        tile.userData.media = e;
        if (e.th) loader.load(e.th, t => { t.colorSpace = THREE.SRGBColorSpace; m.map = t; m.color.set(0xffffff); m.needsUpdate = true; }, undefined, () => {});
        hallGroup.add(tile); pickables.push(tile);
      });
    }).catch(() => {});
    function stop() { if (video) { video.pause(); video.removeAttribute("src"); video.load(); video = null; } if (audio) { audio.pause(); audio = null; } }
    async function show(e) {
      stop();
      const d = (await C.getFile(e.section.files[e.f - 1], e.section.base)).docs[e.i];
      const m = d.media || [], v = m.find(x => x.type === "video"), a = m.find(x => x.type === "audio"), img = m.find(x => x.type === "image");
      const still = url => loader.load(url, t => { t.colorSpace = THREE.SRGBColorSpace; scrMat.map = t; scrMat.color.set(0xffffff); scrMat.needsUpdate = true; }, undefined, () => hint(d.title + " — open it on the page"));
      hint(d.title + (d.date ? ` (${d.date})` : ""));
      if (v) {
        video = Object.assign(document.createElement("video"), { crossOrigin: "anonymous", playsInline: true, src: v.url });
        video.addEventListener("error", () => { scrMat.map = null; scrMat.color.set(0x0b0d12); scrMat.needsUpdate = true; hint(d.title + " — plays on the page, not on the 3D screen"); }, { once: true });
        const vt = new THREE.VideoTexture(video); vt.colorSpace = THREE.SRGBColorSpace;
        video.addEventListener("loadeddata", () => { scrMat.map = vt; scrMat.color.set(0xffffff); scrMat.needsUpdate = true; }, { once: true });
        video.play().catch(() => {});
      } else if (a) { audio = new Audio(a.url); audio.play().catch(() => {}); if (img || d.thumb) still((img || {}).url || d.thumb); }
      else if (img || d.thumb) still((img || {}).url || d.thumb);
    }
    return { show, stop };
  }

  // ---- the Hall of Presidents (built on first visit)
  async function buildPresidents() {
    const g = new THREE.Group(); g.position.copy(PRES_OFFSET); scene.add(g);
    let set = null;
    try { set = await loadSet("presidents_hall.glb"); } catch (e) { set = null; }
    let A = {};
    if (set) {
      g.add(set.root); A = set.anchors;
      set.root.traverse(o => { if (o.isMesh && /floor|stage/i.test(o.name)) { o.userData.floor = "pres"; floors.push(o); } });
    } else {
      const f = new THREE.Mesh(new THREE.CircleGeometry(24, 96), new THREE.MeshStandardMaterial({ color: 0x14161c })); f.rotation.x = -Math.PI / 2; f.userData.floor = "pres"; g.add(f); floors.push(f);
      let n = 1; [[5, 13], [7, 16], [9, 18]].forEach(([r, c], t) => { for (let i = 0; i < c; i++) { const a = (18 + 144 * i / (c - 1)) * Math.PI / 180, e = new THREE.Object3D(); e.position.set(Math.cos(a) * r, 1.4 + t * 0.4, -Math.sin(a) * r); g.add(e); A["P" + String(n++).padStart(2, "0")] = e; } });
      const l = new THREE.Object3D(); l.position.set(0, 2.25, -2); g.add(l); A.LECTERN = l; const s = new THREE.Object3D(); s.position.set(0, 0, 11); g.add(s); A.SPAWN = s;
    }
    g.updateMatrixWorld(true);
    const ros = await C.roster(), sps = await C.speeches();
    const figures = {};
    const centre = A.LECTERN.getWorldPosition(new THREE.Vector3());
    const seat = n => {                    // read left to right on every tier (Blender numbers them right to left)
      for (const [lo, hi] of [[1, 13], [14, 29], [30, 47]]) if (n >= lo && n <= hi) return lo + (hi - n);
      return n;
    };
    ros.forEach(p => {
      const an = A["P" + String(seat(p.n)).padStart(2, "0")]; if (!an) return;
      const pos = an.getWorldPosition(new THREE.Vector3());
      const m = new THREE.Mesh(new THREE.PlaneGeometry(0.85, 1.07), new THREE.MeshBasicMaterial({ map: medalTex(p), transparent: true, depthWrite: false }));
      m.position.copy(pos).add(new THREE.Vector3(0, 0.6, 0)); m.lookAt(centre.x, m.position.y, centre.z + 14); m.userData.pres = p.n;
      scene.add(m); g.attach(m); pickables.push(m); figures[p.n] = m;
    });
    const beam = beamMesh(9, 1.1, 0xffe8b0); beam.visible = false; g.add(beam);
    const motes2 = dust(700, 10, 12, new THREE.Vector3(PRES_OFFSET.x, 0, PRES_OFFSET.z - 4)); scene.add(motes2);
    const spawn = A.SPAWN.getWorldPosition(new THREE.Vector3());
    const back = label("◀  Back to the Great Hall", 2.6, 0.38, { button: true, px: 56 }); back.position.copy(spawn).add(new THREE.Vector3(-1.8, 1.6, 1.2)); back.lookAt(spawn.x, 1.6, spawn.z - 10);
    back.userData.door = "hall"; g.attach(back); pickables.push(back);
    const rollB = label("▶  Roll call", 1.8, 0.38, { button: true, px: 56, color: "#e9c55a" }); rollB.position.copy(spawn).add(new THREE.Vector3(1.6, 1.6, 1.2)); rollB.lookAt(spawn.x, 1.6, spawn.z - 10);
    rollB.userData.roll = true; g.attach(rollB); pickables.push(rollB);
    const title = label("THE HALL OF PRESIDENTS", 9, 0.9, { px: 64 }); title.position.copy(centre).add(new THREE.Vector3(0, 6.2, -9.5)); g.attach(title);
    let current = null, rolling = false;
    function light(n) {
      const f = figures[n]; if (!f) return;
      beam.visible = true; beam.position.copy(f.position).add(new THREE.Vector3(0, 8.4, 0));
      Object.values(figures).forEach(x => x.scale.setScalar(1)); f.scale.setScalar(1.35); current = n;
    }
    async function spot(n) {
      rolling = false; light(n);
      const p = ros.find(x => x.n === n), mine = sps.filter(s => s.pr === n).sort((a, b) => (a.y || 0) - (b.y || 0));
      if (!mine.length) return panel.show(`${p.name}`, `${ordinal(n)} President · ${p.from}–${p.to ?? "today"}\n\n${p.note}\n\n${p.no_inaugural || ""}`, n);
      const d = await C.speech(mine[0].f, mine[0].i);
      return panel.speech(p, d, mine);
    }
    async function roll() {
      if (rolling) { rolling = false; speechSynthesis.cancel(); return; }
      rolling = true; panel.group.visible = false;
      for (const p of ros) {
        if (!rolling) break;
        light(p.n); hint(`${p.name} · ${ordinal(p.n)} President · ${p.from}–${p.to ?? "today"}`);
        await new Promise(res => { const u = new SpeechSynthesisUtterance(`${p.name}.`); u.onend = res; u.onerror = res; speechSynthesis.speak(u); setTimeout(res, 4000); });
        await new Promise(res => setTimeout(res, 250));
      }
      rolling = false;
    }
    return { group: g, spawn, spot, roll, figures, get current() { return current; } };
  }
  async function goPresidents() {
    hint("Opening the Hall of Presidents…");
    if (!pres) pres = await buildPresidents();
    rig.position.copy(pres.spawn); yaw = 0; pitch = 0.05; target = null; panel.group.visible = false;
    const bar = host.querySelector(".hall-bar b"); if (bar) bar.textContent = "The Hall of Presidents";
    hint("The Hall of Presidents · select a president to hear him speak · Roll call to meet them all");
  }
  function goHall() { const bar = host.querySelector(".hall-bar b"); if (bar) bar.textContent = "The Great Hall"; rig.position.copy(anchors.SPAWN.getWorldPosition(new THREE.Vector3())); yaw = 0; pitch = 0; target = null; panel.group.visible = false; speechSynthesis.cancel(); hint(defaultHint); }

  // ---- reading panel
  function makePanel() {
    const W = 1024, H = 1240;
    const cv = document.createElement("canvas"); cv.width = W; cv.height = H;
    const ctx = cv.getContext("2d");
    const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
    const group = new THREE.Group();
    group.add(new THREE.Mesh(new THREE.PlaneGeometry(1.1, 1.33), new THREE.MeshBasicMaterial({ map: tex, transparent: true })));
    const mk = (txt, x) => { const b = label(txt, 0.2, 0.09, { button: true, px: 40 }); b.position.set(x, -0.74, 0.01); b.userData.btn = txt; return b; };
    const buttons = [mk("◀ Prev", -0.44), mk("Next ▶", -0.22), mk("Level", 0), mk("Listen", 0.22), mk("✕", 0.44)];
    buttons.forEach(b => group.add(b));
    const S = { slug: null, title: "", kicker: "", pages: [], page: 0, level: opts.level || "deeper", mode: "read", sents: [], n: 0, hi: -1 };
    function draw() {
      const grd = ctx.createLinearGradient(0, 0, 0, H); grd.addColorStop(0, "#f8f0dc"); grd.addColorStop(1, "#efe2c2");
      ctx.fillStyle = grd; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = "#c9a227"; ctx.fillRect(0, 0, W, 12); ctx.fillRect(0, H - 6, W, 6);
      ctx.fillStyle = "#6a5a35"; ctx.font = "600 27px Inter, sans-serif"; ctx.fillText(S.kicker, 60, 68);
      ctx.fillStyle = "#1d1a14"; ctx.font = "650 56px Fraunces, Georgia, serif";
      let y = 146; for (const l of wrap(ctx, S.title, W - 120)) { ctx.fillText(l, 60, y); y += 64; }
      y += 14; ctx.font = "400 35px Fraunces, Georgia, serif";
      for (const l of S.pages[S.page] || []) {
        if (l.hi) { ctx.fillStyle = "rgba(201,162,39,.28)"; ctx.fillRect(52, y - 34, W - 104, 46); }
        ctx.fillStyle = "#2a251c"; ctx.fillText(l.t, 60, y); y += 48;
      }
      ctx.fillStyle = "#8a7d62"; ctx.font = "500 24px JetBrains Mono, monospace";
      ctx.fillText(S.pages.length > 1 ? `page ${S.page + 1} of ${S.pages.length}` : "", 60, H - 36);
      tex.needsUpdate = true;
    }
    function layout(sents, titleLines, hi = -1) {     // sentences -> wrapped lines (remembering which sentence each line is from)
      ctx.font = "400 35px Fraunces, Georgia, serif";
      const lines = [];
      sents.forEach((s, k) => { if (s === "\n") { lines.push({ t: "", k: -1 }); return; } wrap(ctx, s, W - 120).forEach(t => lines.push({ t, k, hi: k === hi })); });
      const per = Math.floor((H - 250 - titleLines * 64) / 48), pages = [];
      for (let i = 0; i < lines.length; i += per) pages.push(lines.slice(i, i + per));
      return pages.length ? pages : [[]];
    }
    function setText(kicker, title, sents, near) {
      ctx.font = "650 56px Fraunces, Georgia, serif";
      Object.assign(S, { kicker, title, sents, page: 0, hi: -1, tl: wrap(ctx, title, W - 120).length });
      S.pages = layout(sents, S.tl); draw(); placePanel(near);
    }
    function highlight(k) {
      S.hi = k; S.pages = layout(S.sents, S.tl, k);
      const pg = S.pages.findIndex(p => p.some(l => l.k === k)); if (pg >= 0) S.page = pg; draw();
    }
    async function open(slug) {
      const a = await C.article(slug);
      const lv = a.levels[S.level] ? S.level : Object.keys(a.levels)[0];
      const paras = await C.decode(a.levels[lv]);
      S.mode = "read"; S.slug = slug; S.level = lv; S.n = 0;
      setText(lv === "young" ? "YOUNG READERS · K–5" : "EXPLORE DEEPER · 6–12", a.title, paras.flatMap((p, i) => (i ? ["\n"] : []).concat(p.map(x => x.t))));
    }
    async function speech(p, d, all) {
      const paras = await C.decode(d.seq);
      S.mode = "speech"; S.n = p.n; S.key = d.key_text || null;
      setText(`${ordinal(p.n).toUpperCase()} PRESIDENT · ${(d.occasion || "SPEECH").toUpperCase()} · ${d.date || ""}`, p.name,
        (d.key_text ? [`★ “${d.key_text}”`, "\n"] : []).concat(paras.flatMap((q, i) => (i ? ["\n"] : []).concat(q.map(x => x.t)))), true);
    }
    function show(title, text, n) { S.mode = "info"; S.n = n || 0; setText("THE HALL OF PRESIDENTS", title, text.split("\n").map(x => x || "\n"), true); }
    async function tutor(q) {
      const day = Math.floor(Date.now() / 864e5);
      const focus = S.slug || (arts[day % arts.length] || {}).slug;
      const question = q || `Summarize ${(arts.find(a => a.slug === focus) || {}).t || "the library"}`;
      const r = await T.answer(question, { slug: focus, level: S.level });
      S.mode = "tutor";
      setText("TUTOR · ANSWERS ONLY FROM THE LIBRARY", question, [r.text, "\n", ...(r.cites || []).flatMap(c => [`“${c.t}”  [${c.a} · ${c.title}]`, "\n"])], true);
    }
    let reading = null;
    function listen() {
      speechSynthesis.cancel();
      if (reading) { reading.stop = true; reading = null; return; }
      const me = reading = { stop: false };
      const order = S.sents.map((s, k) => [s, k]).filter(([s]) => s !== "\n");
      const startAt = order.findIndex(([, k]) => S.pages[S.page].some(l => l.k === k));
      let i = Math.max(0, startAt);
      const next = () => {
        if (me.stop || i >= order.length) { reading = null; highlight(-1); return; }
        const [s, k] = order[i++]; highlight(k);
        const u = new SpeechSynthesisUtterance(s.replace(/^★ /, "")); u.pitch = S.n ? 0.82 + (S.n % 5) * 0.06 : 1; u.rate = 0.96;
        u.onend = next; u.onerror = next; speechSynthesis.speak(u);
      };
      next();
    }
    function press(b) {
      if (b.startsWith("◀")) S.page = Math.max(0, S.page - 1);
      else if (b.startsWith("Next")) S.page = Math.min(S.pages.length - 1, S.page + 1);
      else if (b === "Level" && S.mode === "read") { S.level = S.level === "young" ? "deeper" : "young"; return open(S.slug); }
      else if (b === "Listen") return listen();
      else if (b === "✕") { group.visible = false; speechSynthesis.cancel(); if (reading) reading.stop = true; reading = null; return; }
      draw();
    }
    return { group, buttons, open, speech, show, tutor, press };
  }

  // ---- loop
  const defaultHint = xr ? "Press ENTER VR · trigger a book to read · the gold doorway leads to the Hall of Presidents" : "Drag to look · WASD to walk · click a book to read · the gold doorway leads to the Hall of Presidents";
  hint(defaultHint);
  const clock = new THREE.Clock();
  function onResize() { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); composer.setSize(innerWidth, innerHeight); }
  addEventListener("resize", onResize);
  renderer.setAnimationLoop(() => {
    const dt = Math.min(clock.getDelta(), 0.05), t = clock.elapsedTime;
    orb.rotation.y += dt * 0.5; orb.position.y = orbPos.y + Math.sin(t * 1.4) * 0.06;
    motes.rotation.y += dt * 0.01; motes.position.y = Math.sin(t * 0.2) * 0.3;
    shaft.material.opacity = 0.55 + Math.sin(t * 0.7) * 0.12;
    if (pres && pres.current) { const f = pres.figures[pres.current]; if (f) f.position.y += Math.sin(t * 2) * 0.0008; }
    if (!renderer.xr.isPresenting) {
      camera.rotation.set(pitch, yaw, 0, "YXZ");
      const f = new THREE.Vector3(-Math.sin(yaw), 0, -Math.cos(yaw)), r = new THREE.Vector3(Math.cos(yaw), 0, -Math.sin(yaw)), sp = 3.2 * dt;
      if (keys.has("w") || keys.has("arrowup")) rig.position.addScaledVector(f, sp);
      if (keys.has("s") || keys.has("arrowdown")) rig.position.addScaledVector(f, -sp);
      if (keys.has("a") || keys.has("arrowleft")) rig.position.addScaledVector(r, -sp);
      if (keys.has("d") || keys.has("arrowright")) rig.position.addScaledVector(r, sp);
    }
    if (target) { rig.position.lerp(target, Math.min(1, dt * 4)); if (rig.position.distanceTo(target) < 0.02) target = null; }
    if (renderer.xr.isPresenting) renderer.render(scene, camera); else composer.render();
  });
  R = { renderer, host, vrb, onExit: opts.onExit, cleanup: () => { if (screen) screen.stop(); removeEventListener("resize", onResize); removeEventListener("keydown", kd); removeEventListener("keyup", ku); } };
  window.__hall = { scene, camera, panel, rig, screen, goPresidents, goHall, get pres() { return pres; }, setView: (y, p) => { yaw = y; pitch = p; } };
}
const ordinal = n => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th");

export function exit() {
  if (!R) return;
  const s = R.renderer.xr.getSession(); if (s) s.end();
  R.renderer.setAnimationLoop(null);
  R.renderer.domElement.remove(); if (R.vrb) R.vrb.remove();
  R.renderer.dispose(); R.cleanup(); speechSynthesis.cancel();
  const cb = R.onExit; R = null; if (cb) cb();
}
