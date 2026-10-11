// Alexandria — the app. Reads only COG packs from GitHub (see core.js). Progressive disclosure: clean reading by default,
// the numbers appear only when "#" is on. Nothing heavy loads until it is needed (map, 3D/VR hall).
import * as C from "./core.js";
import * as T from "./tutor.js";
import * as P from "./presidents.js";

const $ = (s, el = document) => el.querySelector(s);
const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const view = $("#view");
const store = { get(k, d) { try { return localStorage.getItem("alexandria." + k) ?? d; } catch (e) { return d; } },
                set(k, v) { try { localStorage.setItem("alexandria." + k, v); } catch (e) {} } };
const state = { level: store.get("level", "deeper"), nums: store.get("nums", "0") === "1", slug: null };
const FMT = { video: ["▶", "Video"], audio: ["♪", "Audio"], image: ["▣", "Photo"], map: ["⌖", "Map"], manuscript: ["✎", "Manuscript"],
  newspaper: ["▤", "Newspaper"], book: ["❏", "Book"], text: ["¶", "Text"] };
const fmtTag = f => FMT[f] ? `${FMT[f][0]} ${FMT[f][1]}` : "";
const thumbHtml = e => e.th ? `<div class="thumb" style="background-image:url('${esc(e.th)}')">${e.fm === "video" || e.fm === "audio" ? `<b>${FMT[e.fm][0]}</b>` : ""}</div>` : "";
const srcCard = e => `<a class="card${e.th ? " has-thumb" : ""}" href="${srcHref(e)}">${thumbHtml(e)}<span class="meta">${esc([fmtTag(e.fm), e.d || yearTxt(e.y)].filter(Boolean).join(" · "))}</span><h3>${esc(e.t)}</h3><p>${esc(e.section.title)}${e.ar && e.ar !== "loc.gov" ? " · " + esc(e.ar) : ""}${e.n ? " · " + e.n.toLocaleString() + " sentences" : ""}</p></a>`;
const yearTxt = y => y == null ? "" : y < 0 ? `${-y} BC` : String(y);

// ------------------------------------------------------------------ chrome: level, numbers, theme
function syncChrome() {
  document.querySelectorAll("[data-level]").forEach(b => b.classList.toggle("on", b.dataset.level === state.level));
  $("#nums").setAttribute("aria-pressed", state.nums);
  document.body.classList.toggle("nums", state.nums);
}
document.querySelectorAll("[data-level]").forEach(b => b.onclick = () => { state.level = b.dataset.level; store.set("level", state.level); syncChrome(); route(); });
$("#nums").onclick = () => { state.nums = !state.nums; store.set("nums", state.nums ? "1" : "0"); syncChrome(); };
const theme = store.get("theme", "");
if (theme) document.documentElement.dataset.theme = theme;
$("#theme").onclick = () => {
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  const cur = document.documentElement.dataset.theme || (dark ? "dark" : "light");
  document.documentElement.dataset.theme = cur === "dark" ? "light" : "dark";
  store.set("theme", document.documentElement.dataset.theme);
  if (map) setTiles();
};
$("#trust").textContent = C.TRUST;

// ------------------------------------------------------------------ search box (instant)
const q = $("#q"), sugg = $("#sugg");
let st;
q.addEventListener("input", () => { clearTimeout(st); st = setTimeout(suggest, 120); });
q.addEventListener("keydown", e => {
  if (e.key === "Enter") { location.hash = "#/search?q=" + encodeURIComponent(q.value); sugg.hidden = true; q.blur(); }
  if (e.key === "Escape") { sugg.hidden = true; q.blur(); }
});
document.addEventListener("click", e => { if (!e.target.closest(".search")) sugg.hidden = true; });
document.addEventListener("keydown", e => {
  if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) { e.preventDefault(); q.focus(); }
});
async function suggest() {
  const v = q.value.trim();
  if (!v) { sugg.hidden = true; return; }
  const m = v.match(/^(\d+)(?:\.(\d+))?$/);
  const r = await C.search(v, 5);
  let h = "";
  if (m) h += `<h6>Address</h6><a href="#/m/${m[1]}${m[2] ? "." + m[2] : ""}">Meaning ${esc(v)}<small>open every exact sentence with this meaning</small></a>`;
  if (r.articles.length) h += "<h6>Articles</h6>" + r.articles.slice(0, 5).map(a => `<a href="#/a/${a.slug}">${esc(a.t)}<small>${esc(a.sum)}</small></a>`).join("");
  if (r.sentences.length) h += "<h6>Sentences</h6>" + r.sentences.slice(0, 4).map(s => `<a href="${sentHref(s)}">${esc(s.t)}<small>${esc(s.title)} · ${s.a}</small></a>`).join("");
  if (r.sources.length) h += "<h6>Primary sources</h6>" + r.sources.slice(0, 3).map(srcLink).join("");
  h += `<a href="#/search?q=${encodeURIComponent(v)}"><small>All results for “${esc(v)}” · Enter</small></a>`;
  sugg.innerHTML = h;
  sugg.hidden = false;
}
const sentHref = s => s.kind === "speech" ? `#/${s.slug}?s=${s.a}` : `#/a/${s.slug}?s=${s.a}`;
const srcHref = e => `#/src/${encodeURIComponent(e.section.id)}/${e.f}/${e.i}`;
const srcLink = e => `<a href="${srcHref(e)}">${esc(e.t)}<small>${esc(e.section.title)} · ${esc(e.d || yearTxt(e.y))}</small></a>`;
sugg.addEventListener("click", () => { sugg.hidden = true; q.value = ""; });

// ------------------------------------------------------------------ router
window.addEventListener("hashchange", route);
async function route() {
  stopSpeaking();
  const h = location.hash.slice(1) || "/";
  const [path, qs] = h.split("?");
  const p = new URLSearchParams(qs || "");
  const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
  const navKey = ["president", "speech"].includes(parts[0]) ? "presidents" : (parts[0] || "");
  document.querySelectorAll("[data-nav]").forEach(a => a.classList.toggle("on", a.dataset.nav === navKey));
  document.body.dataset.page = { a: "article", m: "meaning", src: "media", section: "sources" }[parts[0]] || navKey || "home";
  state.slug = null;
  try {
    if (!parts.length) await home();
    else if (parts[0] === "explore") await explore();
    else if (parts[0] === "subject") await explore(parts[1]);
    else if (parts[0] === "a") await showArticle(parts[1], p.get("s"));
    else if (parts[0] === "m") await showMeaning(parts[1]);
    else if (parts[0] === "timeline") await timeline(p.get("y"));
    else if (parts[0] === "atlas") await atlas(p.get("a"));
    else if (parts[0] === "sources") await showSources();
    else if (parts[0] === "media") await mediaPage(p.get("f") || "");
    else if (parts[0] === "presidents" || parts[0] === "president" || parts[0] === "speech") await P.render(view, parts, p, { prose, state, ask: q => { openTutor(); ask(q); } });
    else if (parts[0] === "section") await showSources(parts[1]);
    else if (parts[0] === "src") await showSource(parts[1], +parts[2], +parts[3]);
    else if (parts[0] === "quiz") await quizPage(p.get("a"), p.get("s"));
    else if (parts[0] === "search") await searchPage(p.get("q") || "");
    else await home();
  } catch (e) {
    view.innerHTML = `<div class="empty">Could not load that from GitHub (${esc(e.message)}). Check the connection and try again.</div>`;
  }
  view.focus({ preventScroll: true });
  if (!p.get("s") && !p.get("y")) scrollTo({ top: 0 });
}

// ------------------------------------------------------------------ home
async function home() {
  const [arts, cat, srcs] = await Promise.all([C.articles(), C.getCatalog(), C.sources()]);
  const t = cat.totals || {};
  const counts = {};
  arts.forEach(a => counts[a.s] = (counts[a.s] || 0) + 1);
  const day = Math.floor(Date.now() / 864e5);
  const f = arts.length ? arts[day % arts.length] : null;
  const fs = f ? C.subj(f.s) : null;
  const dated = arts.filter(a => a.y != null && a.y !== 0).sort((a, b) => a.y - b.y);
  view.innerHTML = `
    <div class="hero-wrap"><section class="hero">
      <div>
        <p class="kicker">The People's Trust</p>
        <h1>Everything here is held in trust for the people.</h1>
        <p class="lead">An encyclopedia built from public sources and stored as numbered meanings on GitHub. Read at your level, walk it in VR, and ask the tutor anything. Every answer comes from the library itself.</p>
        <form class="big-search" onsubmit="location.hash='#/search?q='+encodeURIComponent(this.q.value);return false"><input name="q" placeholder="What do you want to learn?" aria-label="Search the library"><button>Search</button></form>
        <div class="stats">
          <div><b>${arts.length}</b><span>articles</span></div>
          <div><b>${srcs.length.toLocaleString()}</b><span>primary sources</span></div>
          <div><b>${(t.meanings || 0).toLocaleString()}</b><span>meanings</span></div>
          <div><b>${(t.sentences || 0).toLocaleString()}</b><span>sentences</span></div>
        </div>
      </div>
      ${f ? `<a class="feature card" href="#/a/${f.slug}" style="--accent:${fs.c}">
        <p class="kicker">Today's article · ${esc(f.s)}</p><h2>${esc(f.t)}</h2><p>${esc(f.sum)}</p>
        <span class="chip s">${fs.i} ${esc(yearTxt(f.y) || f.s)}</span></a>` : ""}
    </section></div>
    <a class="hall-banner" href="#/presidents"><span class="medal big" style="--era:#c9a227"><b>47</b><i>★</i></span>
      <span><p class="kicker">New · The Hall of Presidents</p><b>Every president. Every inaugural address, word for word.</b><small>Roll call · speeches that light up as they're spoken · Who said it? · Order up!</small></span><span class="pill gold">Enter →</span></a>
    <section class="section"><div class="row-head"><h2>Subjects</h2><a href="#/explore">All articles →</a></div>
      <div class="subjects">${Object.entries(C.SUBJECTS).filter(([n]) => counts[n]).map(([n, v]) =>
        `<a class="subject" href="#/subject/${encodeURIComponent(n)}" style="--accent:${v.c}"><i>${v.i}</i><span><b>${esc(n)}</b><small>${counts[n]} articles</small></span></a>`).join("")}</div></section>
    <section class="section"><div class="row-head"><h2>Through time</h2><a href="#/timeline">Open the timeline →</a></div>
      <div class="strip">${dated.map(a => `<a href="#/a/${a.slug}" style="--accent:${C.subj(a.s).c}"><b>${yearTxt(a.y)}</b><span>${esc(a.t)}</span></a>`).join("")}</div></section>
    <section class="section"><div class="row-head"><h2>From the Library of Congress</h2><a href="#/sources">All sources →</a></div>
      ${srcs.length ? `<div class="grid">${srcs.slice(-6).reverse().map(srcCard).join("")}</div>`
        : `<div class="empty">No primary sources absorbed yet. On base1, open the COG Absorber and press ABSORB NOW. They appear here on their own.</div>`}</section>`;
}

// ------------------------------------------------------------------ explore
async function explore(subject) {
  const arts = (await C.articles()).filter(a => !subject || a.s === subject).sort((a, b) => a.t.localeCompare(b.t));
  const s = subject ? C.subj(subject) : null;
  view.innerHTML = `<p class="kicker">${subject ? "Subject" : "Explore"}</p><h1 style="margin-bottom:8px">${subject ? `<span style="color:${s.c}">${s.i}</span> ${esc(subject)}` : "All articles"}</h1>
    <div class="tl-controls">${["", ...Object.keys(C.SUBJECTS)].map(n => `<button class="${(n || undefined) === subject ? "on" : ""}" onclick="location.hash='${n ? "#/subject/" + encodeURIComponent(n) : "#/explore"}'">${n || "All"}</button>`).join("")}</div>
    <div class="grid">${arts.map(articleCard).join("")}</div>`;
}
const articleCard = a => { const s = C.subj(a.s); return `<a class="card" href="#/a/${a.slug}" style="--accent:${s.c}"><span class="meta">${s.i} ${esc(a.s)}${a.y ? " · " + yearTxt(a.y) : ""}</span><h3>${esc(a.t)}</h3><p>${esc(a.sum)}</p></a>`; };

// ------------------------------------------------------------------ article
const prose = (paras, young) => `<div class="prose ${young ? "young" : ""}">${paras.map(p => "<p>" + p.map(x =>
  `<span class="s" data-a="${x.a}">${esc(x.t)}</span><sup class="addr">${x.a}</sup>`).join(" ") + "</p>").join("")}</div>`;

async function showArticle(slug, hi) {
  const a = await C.article(slug);
  if (!a) { view.innerHTML = `<div class="empty">No article called ${esc(slug)}.</div>`; return; }
  state.slug = slug;
  const levels = Object.keys(a.levels || {});
  const lvl = levels.includes(state.level) ? state.level : levels[0];
  const paras = await C.decode(a.levels[lvl]);
  const s = C.subj(a.subject);
  const arts = await C.articles();
  const rel = (a.related || []).map(r => arts.find(x => x.t.toLowerCase() === r.toLowerCase())).filter(Boolean);
  const srcHits = (await C.search(a.title + " " + (a.related || []).join(" "), 5)).sources.slice(0, 5);
  document.body.style.setProperty("--page-accent", s.c);
  view.innerHTML = `
    <div class="crumbs"><a href="#/explore">Articles</a> › <a href="#/subject/${encodeURIComponent(a.subject)}">${esc(a.subject)}</a></div>
    <div class="article" style="--accent:${s.c}">
      <article>
        <div class="art-head"><p class="kicker" style="color:${s.c}">${s.i} ${esc(a.subject)}</p><h1>${esc(a.title)}</h1></div>
        <p class="lead">${esc(a.summary)}</p>
        <div class="facts">${a.year != null ? `<a class="chip s" href="#/timeline?y=${a.year}">⏱ ${yearTxt(a.year)}</a>` : ""}${a.place ? `<a class="chip s" href="#/atlas?a=${slug}">⌖ on the atlas</a>` : ""}<span class="chip">${a.n} sentences</span></div>
        <div class="levels">${levels.map(l => `<button data-l="${l}" class="${l === lvl ? "on" : ""}">${l === "young" ? "Young readers · K–5" : "Explore deeper · 6–12"}</button>`).join("")}</div>
        <div class="art-actions">
          <button class="pill" id="read">▶ Read to me</button>
          <button class="pill" id="askT">Ask the tutor about this</button>
          ${(a.quiz || []).length ? `<a class="pill" href="#quizbox" style="text-decoration:none;color:inherit">Quiz</a>` : ""}
        </div>
        <div id="text">${prose(paras, lvl === "young")}</div>
        ${(a.quiz || []).length ? `<div class="quiz" id="quizbox"></div>` : ""}
      </article>
      <aside class="side">
        ${a.place ? `<div><h4>Where</h4><div class="mini-map" id="mini"></div></div>` : ""}
        ${rel.length ? `<div><h4>Related</h4><ul>${rel.map(r => `<li><a href="#/a/${r.slug}">${esc(r.t)}</a></li>`).join("")}</ul></div>` : ""}
        <div><h4>Primary sources</h4>${srcHits.length ? `<ul>${srcHits.map(e => `<li><a href="${srcHref(e)}">${esc(e.t)}</a></li>`).join("")}</ul>`
          : `<p class="fine" style="margin:0">None absorbed for this topic yet.</p>`}</div>
        <div><h4>How this page is stored</h4><p class="fine" style="margin:0">This article is not stored as text. It's ${a.n} COG addresses, rebuilt in your browser from the shared meaning packs. Turn on <b>#</b> to see each sentence's address. Click one to see every wording of that meaning.</p></div>
      </aside>
    </div>`;
  view.querySelectorAll("[data-l]").forEach(b => b.onclick = () => { state.level = b.dataset.l; store.set("level", state.level); syncChrome(); showArticle(slug); });
  $("#text").onclick = e => { const s = e.target.closest(".s"); if (s && state.nums) location.hash = "#/m/" + s.dataset.a; };
  $("#read").onclick = () => speak($("#text"), $("#read"));
  $("#askT").onclick = () => { openTutor(); ask(`Summarize ${a.title}`); };
  if (a.quiz && a.quiz.length) renderQuiz($("#quizbox"), [{ a, items: a.quiz.filter(x => x.level === lvl).concat(a.quiz.filter(x => x.level !== lvl)) }], a.title);
  if (a.place) leaflet().then(L => { const m = L.map("mini", { zoomControl: false, attributionControl: false }).setView(a.place, 4); tiles(L).addTo(m);
    L.circleMarker(a.place, { radius: 8, color: s.c, fillColor: s.c, fillOpacity: .8 }).addTo(m); });
  if (hi) { const el = view.querySelector(`.s[data-a="${CSS.escape(hi)}"]`); if (el) { el.classList.add("speak"); el.scrollIntoView({ block: "center" }); setTimeout(() => el.classList.remove("speak"), 2500); } }
}

// ------------------------------------------------------------------ read aloud with sentence highlight
let speaking = null;
function stopSpeaking() { P.hush(); if (speaking) { speaking.stop = true; speechSynthesis.cancel(); document.querySelectorAll(".s.speak").forEach(x => x.classList.remove("speak")); speaking = null; } }
function speak(root, btn) {
  if (!("speechSynthesis" in window)) { btn.textContent = "No voice on this device"; return; }
  if (speaking) { stopSpeaking(); btn.textContent = "▶ Read to me"; return; }
  const ss = [...root.querySelectorAll(".s")];
  const job = speaking = { stop: false };
  btn.textContent = "■ Stop";
  let i = 0;
  const next = () => {
    document.querySelectorAll(".s.speak").forEach(x => x.classList.remove("speak"));
    if (job.stop || i >= ss.length) { if (speaking === job) speaking = null; btn.textContent = "▶ Read to me"; return; }
    const el = ss[i++];
    el.classList.add("speak");
    el.scrollIntoView({ block: "nearest", behavior: "smooth" });
    const u = new SpeechSynthesisUtterance(el.textContent);
    u.rate = state.level === "young" ? 0.92 : 1;
    u.onend = next; u.onerror = next;
    speechSynthesis.speak(u);
  };
  next();
}

// ------------------------------------------------------------------ quiz
function renderQuiz(box, sets, title) {
  const items = sets.flatMap(s => s.items.map(x => ({ ...x, a: s.a })));
  let right = 0, done = 0;
  box.innerHTML = `<h3>${title ? "Check what you learned" : "Quiz"}</h3><p class="fine">${items.length} questions${title ? "" : " from across the library"}</p>` +
    items.map((x, i) => `<div class="q" data-i="${i}"><p>${i + 1}. ${esc(x.q)}${title ? "" : ` <a class="fine" href="#/a/${x.a.slug}">(${esc(x.a.title || x.a.t)})</a>`}</p>
      <div class="opts">${x.choices.map((c, j) => `<button data-j="${j}">${esc(c)}</button>`).join("")}</div></div>`).join("") + `<div class="score" id="score"></div>`;
  box.querySelectorAll(".q").forEach(qe => qe.querySelectorAll("button").forEach(b => b.onclick = () => {
    const x = items[+qe.dataset.i], j = +b.dataset.j;
    qe.querySelectorAll("button").forEach((o, k) => { o.disabled = true; if (k === x.answer) o.classList.add("right"); });
    if (j === x.answer) right++; else b.classList.add("wrong");
    done++;
    box.querySelector("#score").textContent = `${right} of ${done} right` + (done === items.length ? (right === items.length ? " — perfect!" : " — open the article and try again any time.") : "");
  }));
}
async function quizPage(slug, subject) {
  const arts = await C.articles();
  const pool = arts.filter(a => (!slug || a.slug === slug) && (!subject || a.s === subject));
  const full = await Promise.all(pool.map(a => C.article(a.slug)));
  const sets = full.filter(a => a.quiz && a.quiz.length).map(a => ({ a, items: a.quiz.filter(x => x.level === state.level) })).filter(s => s.items.length);
  for (let i = sets.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [sets[i], sets[j]] = [sets[j], sets[i]]; }
  view.innerHTML = `<p class="kicker">Quiz · ${state.level === "young" ? "K–5" : "6–12"}</p><h1>Test yourself</h1>
    <div class="tl-controls">${["", ...Object.keys(C.SUBJECTS)].map(n => `<button class="${(n || null) === subject ? "on" : ""}" onclick="location.hash='#/quiz${n ? "?s=" + encodeURIComponent(n) : ""}'">${n || "Everything"}</button>`).join("")}</div>
    <div class="quiz" id="qz" style="max-width:none"></div>`;
  const pick = sets.slice(0, 8).map(s => ({ a: s.a, items: [s.items[Math.floor(Math.random() * s.items.length)]] }));
  if (pick.length) renderQuiz($("#qz"), pick, slug ? pick[0].a.title : null); else $("#qz").innerHTML = `<div class="empty">No questions at this level yet.</div>`;
}

// ------------------------------------------------------------------ meaning (power users)
async function showMeaning(addr) {
  const [m, v] = addr.split(".").map(Number);
  const r = await C.meaning(m);
  view.innerHTML = `<p class="kicker">Meaning ${m}</p><h1>${esc(r.keys.join(" · ") || "Meaning " + m)}</h1>
    <p class="lead">Every exact sentence in the library that says this. The address is (meaning-id, variant-index): the same sentence has the same address in every article and every source.</p>
    ${r.variants.length ? `<ul class="variants">${r.variants.map(x => `<li class="${x.v === v ? "hi" : ""}"><b>${m}.${x.v}</b><span>${esc(x.t)}</span></li>`).join("")}</ul>`
      : `<div class="empty">No meaning ${m} yet.</div>`}`;
}

// ------------------------------------------------------------------ timeline
const ERAS = [[-1e9, -500, "Ancient world"], [-500, 500, "Classical age"], [500, 1450, "Middle Ages"], [1450, 1700, "Renaissance & Reformation"],
  [1700, 1800, "Age of Revolution"], [1800, 1900, "The 1800s"], [1900, 2000, "The 1900s"], [2000, 1e9, "Today"]];
async function timeline(y) {
  const [arts, srcs] = await Promise.all([C.articles(), C.sources()]);
  const items = arts.filter(a => a.y != null && a.y !== 0).map(a => ({ y: a.y, t: a.t, sub: a.sum, href: "#/a/" + a.slug, c: C.subj(a.s).c, s: a.s }))
    .concat(srcs.filter(e => e.y).map(e => ({ y: e.y, t: e.t, sub: e.section.title + " · primary source", href: srcHref(e), c: "#8b929a", s: "Sources" })))
    .sort((a, b) => a.y - b.y);
  const filter = store.get("tl", "");
  const show = items.filter(x => !filter || x.s === filter);
  let html = "", era = null;
  for (const x of show) {
    const e = ERAS.find(([a, b]) => x.y >= a && x.y < b);
    if (e !== era) { era = e; html += `<div class="era">${e[2]}</div>`; }
    html += `<a class="tl-item" data-y="${x.y}" href="${x.href}" style="--accent:${x.c}"><b>${yearTxt(x.y)}</b><span>${esc(x.t)}<small>${esc(x.sub)}</small></span></a>`;
  }
  view.innerHTML = `<p class="kicker">Timeline</p><h1>Through time</h1>
    <div class="tl-controls">${["", ...Object.keys(C.SUBJECTS), "Sources"].map(n => `<button data-f="${esc(n)}" class="${n === filter ? "on" : ""}">${n || "Everything"}</button>`).join("")}</div>
    <div class="timeline">${html || `<div class="empty">Nothing here yet.</div>`}</div>`;
  view.querySelectorAll("[data-f]").forEach(b => b.onclick = () => { store.set("tl", b.dataset.f); timeline(); });
  if (y != null) {
    const el = [...view.querySelectorAll(".tl-item")].reduce((best, el) => !best || Math.abs(+el.dataset.y - y) < Math.abs(+best.dataset.y - y) ? el : best, null);
    if (el) { el.scrollIntoView({ block: "center" }); el.classList.add("flash"); }
  }
}

// ------------------------------------------------------------------ atlas (Leaflet, loaded on demand)
let leafletP = null, map = null, tileLayer = null;
function leaflet() {
  if (!leafletP) leafletP = new Promise((res, rej) => {
    const l = document.createElement("link"); l.rel = "stylesheet"; l.href = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"; document.head.appendChild(l);
    const s = document.createElement("script"); s.src = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"; s.onload = () => res(window.L); s.onerror = rej; document.head.appendChild(s);
  });
  return leafletP;
}
const isDark = () => (document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark";
function tiles(L) {
  return L.tileLayer(`https://{s}.basemaps.cartocdn.com/${isDark() ? "dark_all" : "light_all"}/{z}/{x}/{y}{r}.png`,
    { subdomains: "abcd", maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>' });
}
function setTiles() { leaflet().then(L => { if (tileLayer) map.removeLayer(tileLayer); tileLayer = tiles(L).addTo(map); }); }
async function atlas(focus) {
  const arts = (await C.articles()).filter(a => a.p);
  view.innerHTML = `<p class="kicker">Atlas</p><h1 style="margin-bottom:14px">Where it happened</h1><div class="atlas" id="map"></div>`;
  const L = await leaflet();
  map = L.map("map", { worldCopyJump: true }).setView([30, -20], 2);
  tileLayer = tiles(L).addTo(map);
  let fm = null;
  for (const a of arts) {
    const s = C.subj(a.s);
    const mk = L.circleMarker(a.p, { radius: 8, color: s.c, weight: 2, fillColor: s.c, fillOpacity: .75 }).addTo(map)
      .bindPopup(`<a href="#/a/${a.slug}">${esc(a.t)}</a><br><span style="opacity:.75">${esc(yearTxt(a.y))} · ${esc(a.s)}</span>`);
    if (a.slug === focus) fm = [mk, a];
  }
  if (fm) { map.setView(fm[1].p, 5); fm[0].openPopup(); }
}

// ------------------------------------------------------------------ primary sources
async function showSources(secId) {
  const secs = (await C.sections()).filter(s => s.id !== "encyclopedia");
  const srcs = await C.sources();
  if (!secId) {
    view.innerHTML = `<p class="kicker">Primary sources</p><h1>From the archives</h1><p class="lead">Texts, films, recordings, photographs and maps from the Library of Congress and the Internet Archive. <a href="#/media">Browse the media →</a></p><p class="lead">${esc(C.TRUST)}</p>
      <div class="grid section" style="margin-top:20px">${secs.length ? secs.map(s => `<a class="card" href="#/section/${encodeURIComponent(s.id)}"><span class="meta">Section</span><h3>${esc(s.title)}</h3><p>${(s.docs || 0).toLocaleString()} documents · ${(s.sentences || 0).toLocaleString()} sentences</p></a>`).join("")
        : `<div class="empty">Nothing absorbed yet. Use the COG Absorber on base1.</div>`}</div>`;
    return;
  }
  const s = secs.find(x => x.id === secId);
  const list = srcs.filter(e => e.section.id === secId).sort((a, b) => (a.y || 9999) - (b.y || 9999));
  view.innerHTML = `<div class="crumbs"><a href="#/sources">Sources</a> › ${esc(s ? s.title : secId)}</div><h1 style="margin-bottom:18px">${esc(s ? s.title : secId)}</h1>
    <div class="grid">${list.map(srcCard).join("") || `<div class="empty">No documents yet.</div>`}</div>`;
}
// ------------------------------------------------------------------ media: films, recordings, photographs, maps
async function mediaPage(f) {
  const all = (await C.sources()).filter(e => e.fm && e.fm !== "text" && e.fm !== "book" && (e.th || e.mv));
  const counts = {};
  all.forEach(e => counts[e.fm] = (counts[e.fm] || 0) + 1);
  const list = all.filter(e => !f || e.fm === f).sort((a, b) => (a.y || 9999) - (b.y || 9999));
  view.innerHTML = `<p class="kicker">Media</p><h1>Film, sound and pictures</h1>
    <p class="lead">Recordings and images play straight from the archive that holds them. The library keeps their catalogue text, captions and transcripts as COG, so the tutor and search can use them.</p>
    <div class="tl-controls">${["", ...Object.keys(FMT).filter(k => counts[k])].map(k => `<button class="${k === f ? "on" : ""}" onclick="location.hash='#/media${k ? "?f=" + k : ""}'">${k ? fmtTag(k) + " · " + counts[k] : "Everything · " + all.length}</button>`).join("")}</div>
    <div class="grid media-grid">${list.map(srcCard).join("") || `<div class="empty">No media absorbed yet. In the COG Absorber, pick a format (Video, Audio, Photos, Maps) when you add a source.</div>`}</div>`;
}
function player(d) {
  const m = d.media || [];
  const vids = m.filter(x => x.type === "video"), auds = m.filter(x => x.type === "audio"), imgs = m.filter(x => x.type === "image");
  const caps = m.filter(x => x.type === "caption" && /\.vtt(\?|$)/i.test(x.url));
  const track = caps.map((c, i) => `<track kind="captions" src="${esc(c.url)}" srclang="en" label="Captions"${i ? "" : " default"}>`).join("");
  let h = "";
  if (vids.length) h += `<video class="player" controls preload="metadata" playsinline ${imgs[0] || d.thumb ? `poster="${esc((imgs[0] || {}).url || d.thumb)}"` : ""}>${vids.map(v => `<source src="${esc(v.url)}"${v.mime ? ` type="${esc(v.mime)}"` : ""}>`).join("")}${track}</video>`;
  else if (auds.length) h += `<div class="audio-wrap">${d.thumb ? `<img src="${esc(d.thumb)}" alt="">` : ""}<audio class="player" controls preload="metadata">${auds.map(a => `<source src="${esc(a.url)}"${a.mime ? ` type="${esc(a.mime)}"` : ""}>`).join("")}</audio></div>`;
  else if (imgs.length) h += `<figure class="gallery"><a href="${esc(imgs[0].url)}" target="_blank" rel="noopener"><img id="bigimg" src="${esc(imgs[0].url)}" alt="${esc(d.title)}"></a>
    ${imgs.length > 1 ? `<div class="thumbs">${imgs.map(x => `<img src="${esc(x.url)}" alt="" data-src="${esc(x.url)}">`).join("")}</div>` : ""}</figure>`;
  const pdf = m.find(x => x.type === "pdf");
  if (pdf) h += `<p class="fine"><a href="${esc(pdf.url)}" target="_blank" rel="noopener">Open the scanned pages (PDF) ↗</a></p>`;
  return h ? `<div class="media-box">${h}</div>` : "";
}
async function showSource(secId, f, i) {
  const sec = (await C.sections()).find(s => s.id === secId);
  const pack = await C.getFile(sec.files[f - 1], sec.base);
  const d = pack.docs[i];
  const paras = await C.decode(d.seq);
  view.innerHTML = `<div class="crumbs"><a href="#/sources">Sources</a> › <a href="#/section/${encodeURIComponent(secId)}">${esc(sec.title)}</a></div>
    <p class="kicker">${esc([fmtTag(d.format) || "Primary source", d.date, d.archive && d.archive !== "loc.gov" ? d.archive : ""].filter(Boolean).join(" · "))}</p><h1>${esc(d.title)}</h1>
    ${player(d)}
    <div class="art-actions" style="margin-top:14px"><button class="pill" id="read">▶ Read to me</button><a class="pill" href="${esc(d.url)}" target="_blank" rel="noopener" style="text-decoration:none;color:inherit">Original at ${esc(d.archive || "loc.gov")} ↗</a></div>
    ${d.text_from && d.text_from !== "fulltext" ? `<p class="fine">${d.text_from === "captions" ? "Transcript from the recording's captions" : "Catalogue record (no transcript online yet)"} · stored as COG addresses</p>` : ""}
    <div class="doc" id="text">${prose(paras, false)}</div>`;
  view.querySelectorAll(".thumbs img").forEach(t => t.onclick = () => { $("#bigimg").src = t.dataset.src; $("#bigimg").parentElement.href = t.dataset.src; });
  $("#text").onclick = e => { const s = e.target.closest(".s"); if (s && state.nums) location.hash = "#/m/" + s.dataset.a; };
  $("#read").onclick = () => speak($("#text"), $("#read"));
}

// ------------------------------------------------------------------ search page
async function searchPage(qv) {
  const r = await C.search(qv, 40);
  view.innerHTML = `<p class="kicker">Search</p><h1>“${esc(qv)}”</h1>
    ${r.articles.length ? `<section class="section"><h2>Articles</h2><div class="grid">${r.articles.map(articleCard).join("")}</div></section>` : ""}
    ${r.sentences.length ? `<section class="section"><h2>Sentences</h2><ul class="variants">${r.sentences.slice(0, 25).map(s => `<li><b><a href="#/m/${s.a}">${s.a}</a></b><span>${esc(s.t)} <a class="fine" href="${sentHref(s)}">— ${esc(s.title)}</a></span></li>`).join("")}</ul></section>` : ""}
    ${r.sources.length ? `<section class="section"><h2>Primary sources</h2><div class="grid">${r.sources.map(e => `<a class="card" href="${srcHref(e)}"><span class="meta">${esc(e.section.title)}</span><h3>${esc(e.t)}</h3></a>`).join("")}</div></section>` : ""}
    ${!r.articles.length && !r.sentences.length && !r.sources.length ? `<div class="empty section">Nothing yet. Ask the tutor, or have the Library Desk on base1 find it on loc.gov.</div>` : ""}`;
}

// ------------------------------------------------------------------ tutor drawer
const tutor = $("#tutor"), chat = $("#chat");
function openTutor() { tutor.hidden = false; setChips(); $("#askIn").focus(); }
$("#tutorBtn").onclick = () => tutor.hidden ? openTutor() : (tutor.hidden = true);
$("#tutorClose").onclick = () => tutor.hidden = true;
$("#tutorSet").onclick = () => { const c = $("#tutorCfg"); c.hidden = !c.hidden; };
function setChips() {
  const here = state.slug;
  const chips = here ? ["Summarize this", "Explain it simply", "Quiz me", "When did it happen?"] : ["What is the Bill of Rights?", "Explain photosynthesis simply", "Quiz me on the Constitution", "When was the printing press?"];
  $("#chips").innerHTML = chips.map(c => `<button>${esc(c)}</button>`).join("");
  $("#chips").querySelectorAll("button").forEach(b => b.onclick = () => ask(b.textContent));
}
function msg(cls, html) { const d = document.createElement("div"); d.className = "msg " + cls; d.innerHTML = html; chat.appendChild(d); chat.scrollTop = chat.scrollHeight; return d; }
async function ask(text) {
  if (!text.trim()) return;
  if (/president|inaugur|speech|address|said|washington|lincoln|roosevelt|kennedy|jefferson|reagan|obama|adams|madison|monroe|jackson|grant|wilson|truman|eisenhower|nixon|carter|clinton|bush|trump|biden|harrison|cleveland|mckinley|taft|harding|coolidge|hoover|johnson|polk|taylor|pierce|buchanan|hayes|garfield|arthur|tyler|fillmore|ford|van buren/i.test(text) && !C.speechesLoaded()) {
    const w = msg("ai", "Opening the Hall of Presidents speeches…"); await C.speechIndex().catch(() => {}); w.remove();
  }
  msg("me", esc(text));
  const wait = msg("ai", "…");
  try {
    const r = await T.answer(text, { slug: state.slug, level: state.level });
    if (r.kind === "quiz") { wait.innerHTML = esc(r.text); location.hash = "#/quiz?a=" + r.slug; return; }
    wait.innerHTML = esc(r.text).replace(/\[(\d+\.\d+)\]/g, '<a href="#/m/$1">[$1]</a>').replace(/\n/g, "<br>") +
      (r.cites || []).map(c => `<blockquote>${esc(c.t)}${c.who ? ` <span class="fine">— ${esc(c.who)}</span>` : ""}<a href="${sentHref(c)}" title="${esc(c.title)}">${c.a}</a></blockquote>`).join("") +
      ((r.actions || []).length ? `<div class="acts">${r.actions.map(a => `<a href="${a.href}">${esc(a.label)}</a>`).join("")}</div>` : "") +
      (r.model ? `<small>written by ${esc(r.model)} on base1 from the passages above</small>` : r.note ? `<small>${esc(r.note)}</small>` : "");
  } catch (e) { wait.textContent = "Couldn't reach the library just now."; }
}
$("#ask").onsubmit = e => { e.preventDefault(); const v = $("#askIn").value; $("#askIn").value = ""; ask(v); };
// settings
const cfg = T.config();
$("#useModel").checked = cfg.useModel; $("#ollamaUrl").value = cfg.url;
if (cfg.model) $("#ollamaModel").innerHTML = `<option>${esc(cfg.model)}</option>`;
const saveCfg = () => { T.saveConfig({ url: $("#ollamaUrl").value || "http://localhost:11434", model: $("#ollamaModel").value, useModel: $("#useModel").checked });
  $("#tutorMode").textContent = $("#useModel").checked && $("#ollamaModel").value ? `library + ${$("#ollamaModel").value}` : "answers only from the library"; };
$("#useModel").onchange = saveCfg; $("#ollamaModel").onchange = saveCfg;
$("#ollamaTest").onclick = async () => {
  try { const ms = await T.models($("#ollamaUrl").value || "http://localhost:11434");
    $("#ollamaModel").innerHTML = ms.map(m => `<option>${esc(m)}</option>`).join(""); $("#useModel").checked = true; saveCfg(); msg("ai", `Connected to base1: ${ms.length} models.`); }
  catch (e) { msg("ai", "Couldn't reach Ollama. On base1, run it with OLLAMA_ORIGINS=https://pxd2.github.io (and open this page on base1)."); }
};
saveCfg();
msg("ai", "Ask me anything. I only answer from the library, and every line I quote shows its address, so you can check it.");

// ------------------------------------------------------------------ the Hall (3D on screen, VR in a headset) — loaded only when entered
$("#vrBtn").onclick = async () => {
  const hall = $("#hall");
  hall.hidden = false;
  const mod = await import("./vr.js");
  mod.enter(hall, { level: state.level, onExit: () => { hall.hidden = true; } });
};
$("#hallExit").onclick = async () => { (await import("./vr.js")).exit(); };

syncChrome();
route();
