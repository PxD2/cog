// Alexandria service worker: installable, and readable offline.
// App shell: cache first. Library data (packs, sets): network first, cached copy when offline.
// "Save the library for offline" asks this worker to fetch every pack listed in the catalog.
const VERSION = "alexandria-v1";
const SHELL = ["./", "index.html", "app.css", "app.js", "core.js", "tutor.js", "presidents.js", "civics.js", "comfort.js", "vr.js",
  "manifest.webmanifest", "img/icon-192.png", "img/icon-512.png", "img/rotunda.jpg", "img/theater.jpg"];
self.addEventListener("install", e => e.waitUntil(
  caches.open(VERSION).then(c => c.addAll(SHELL.map(u => new Request(u, { cache: "reload" })))).catch(() => {}).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION && k.startsWith("alexandria-") && k !== "alexandria-data").map(k => caches.delete(k)))).then(() => self.clients.claim())));
const isData = url => /\/(books|sections|loc|sets)\//.test(url.pathname);
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (isData(url) || url.origin !== location.origin) {           // data + CDN libraries: network first, cache fallback
    e.respondWith(fetch(req).then(r => { if (r.ok || r.type === "opaque") { const copy = r.clone(); caches.open("alexandria-data").then(c => c.put(req, copy)); } return r; })
      .catch(() => caches.match(req, { ignoreSearch: true })));
    return;
  }
  e.respondWith(caches.match(req, { ignoreSearch: true }).then(hit => hit || fetch(req).then(r => { const copy = r.clone(); caches.open(VERSION).then(c => c.put(req, copy)); return r; })));
});
self.addEventListener("message", async e => {
  if (!e.data || e.data.type !== "cacheAll") return;
  const port = e.ports && e.ports[0];
  try {
    const base = new URL("../", self.registration.scope);
    const cat = await (await fetch(new URL("books/catalog.json", base))).json();
    const files = new Set(["books/catalog.json", "loc/state.json", "sections/presidents/roster.json", "sections/civics/congresses.json",
      "sections/civics/threads/index.json", "sections/civics/threads/covenant-republic.json", "sets/great_hall.glb", "sets/presidents_hall.glb",
      "sets/reading_room.glb", "sets/archive_stair.glb"]);
    (cat.books || []).forEach(b => files.add(b.file));
    (cat.sections || []).forEach(s => { if (!s.base) { (s.files || []).forEach(f => files.add(f)); } (s.index || []).forEach(f => files.add(f)); });
    const c = await caches.open("alexandria-data");
    let done = 0;
    for (const f of files) {
      try { const r = await fetch(new URL(f, base)); if (r.ok) await c.put(new URL(f, base).href, r); } catch (err) {}
      done++; if (port) port.postMessage({ done, total: files.size });
    }
    if (port) port.postMessage({ done: files.size, total: files.size, finished: true });
  } catch (err) { if (port) port.postMessage({ error: String(err) }); }
});
