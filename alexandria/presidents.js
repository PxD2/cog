// Hall of Presidents — every president on a stage, every inaugural address word for word (from the COG packs),
// a roll call, speeches read aloud with each sentence lighting up, and games for young readers.
import * as C from "./core.js";
import * as CF from "./comfort.js";

const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ord = n => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th");
const years = p => `${p.from}–${p.to ?? "today"}`;
const initials = name => name.replace(/\b(Jr|Sr)\.?/g, "").split(/\s+/).filter(w => /^[A-Z]/.test(w)).map(w => w[0]).join("").slice(0, 3);
export const ERAS = [
  [1, 6, "A New Nation", "#c9a227"], [7, 15, "Growing West", "#c0794a"], [16, 19, "Civil War & Rebuilding", "#b5523b"],
  [20, 25, "Railroads & Industry", "#8a6a3a"], [26, 29, "Progress & World War I", "#3aa37c"], [30, 33, "Depression & World War II", "#4f80c9"],
  [34, 41, "Cold War & Space Age", "#7a62c2"], [42, 47, "A New Century", "#2f9cb6"],
];
export const eraOf = n => ERAS.find(([a, b]) => n >= a && n <= b);
const medal = (p, big) => { const e = eraOf(p.n); return `<span class="medal${big ? " big" : ""}" style="--era:${e[3]}"><b>${p.n}</b><i>${esc(initials(p.name))}</i></span>`; };

// ------------------------------------------------------------------ voices: each president gets his own (synthetic) voice
let voices = [];
const loadVoices = () => { voices = (speechSynthesis.getVoices() || []).filter(v => /^en(-|_|$)/i.test(v.lang)); };
if ("speechSynthesis" in window) { loadVoices(); speechSynthesis.onvoiceschanged = loadVoices; }
function voiceFor(n) {
  const male = voices.filter(v => /male|david|mark|guy|george|daniel|fred|alex|james|aaron|ryan|christopher|eric/i.test(v.name) && !/female/i.test(v.name));
  const pool = male.length ? male : voices;
  return { voice: pool.length ? pool[n % pool.length] : null, pitch: 0.82 + (n % 5) * 0.06, rate: 0.95 };
}
let job = null;
export function hush() { if (job) { job.stop = true; job = null; } if ("speechSynthesis" in window) speechSynthesis.cancel(); document.querySelectorAll(".s.speak").forEach(x => x.classList.remove("speak")); }
function say(text, n, onend) {
  if (!("speechSynthesis" in window)) { onend && setTimeout(onend, 1500); return; }
  const u = new SpeechSynthesisUtterance(text), v = voiceFor(n);
  if (v.voice) u.voice = v.voice;
  u.pitch = v.pitch; u.rate = v.rate * CF.get().rate;
  u.onend = () => onend && onend(); u.onerror = () => onend && onend();
  speechSynthesis.speak(u);
}
function readSpans(spans, n, btn, from = 0) {
  if (job) { hush(); if (btn) btn.textContent = "▶ Stand and deliver"; return; }
  const me = job = { stop: false };
  if (btn) btn.textContent = "■ Stop";
  let i = from;
  const next = () => {
    document.querySelectorAll(".s.speak").forEach(x => x.classList.remove("speak"));
    if (me.stop || i >= spans.length) { if (job === me) job = null; if (btn) btn.textContent = "▶ Stand and deliver"; return; }
    const el = spans[i++];
    el.classList.add("speak");
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    say(el.textContent, n, next);
  };
  next();
}

// ------------------------------------------------------------------ pages
export async function render(view, path, params, ctx) {
  hush();
  const [ros, sps] = await Promise.all([C.roster(), C.speeches()]);
  if (!ros.length) { view.innerHTML = `<div class="empty">The Hall of Presidents has not been published yet. On base1 run <code>publish_presidents.py</code>.</div>`; return; }
  const [a, b, c] = path;
  if (a === "president") return president(view, ros, sps, +b, ctx);
  if (a === "speech") return speechPage(view, ros, +b, +c, params.get("s"), ctx);
  if (b === "roll") return rollCall(view, ros, sps);
  if (b === "who") return whoSaidIt(view, ros, sps);
  if (b === "order") return orderUp(view, ros);
  if (b === "lengths") return lengths(view, ros, sps);
  return hallMain(view, ros, sps);
}

function hallMain(view, ros, sps) {
  const said = new Set(sps.map(s => s.pr));
  view.innerHTML = `
    <section class="pres-hero">
      <div class="curtain"></div>
      <p class="kicker">Alexandria presents</p>
      <h1>The Hall of Presidents</h1>
      <p class="lead">Every president of the United States, from George Washington to today. Hear each one's inaugural address, word for word, with every sentence lighting up as it is spoken. Then test yourself.</p>
      <div class="pres-actions">
        <a class="pill gold" href="#/presidents/roll">▶ Roll call</a>
        <a class="pill" href="#/presidents/who">Who said it?</a>
        <a class="pill" href="#/presidents/order">Order up!</a>
        <a class="pill" href="#/presidents/lengths">Longest &amp; shortest speeches</a>
      </div>
      <p class="fine">${ros.length} presidencies · ${sps.length} speeches · voices are read by your device, not recordings</p>
    </section>
    ${ERAS.map(([lo, hi, name, col]) => `<section class="era-row" style="--era:${col}"><h2><span>${esc(name)}</span><small>${ros.find(p => p.n === lo).from}–${(ros.find(p => p.n === hi) || {}).to ?? "today"}</small></h2>
      <div class="medals">${ros.filter(p => p.n >= lo && p.n <= hi).map(p => `<a class="pcard" href="#/president/${p.n}">${medal(p)}<span><b>${esc(p.name)}</b><small>${years(p)} · ${esc(p.party)}</small>${said.has(p.n) ? `<em>♪ speech</em>` : ""}</span></a>`).join("")}</div></section>`).join("")}`;
}

async function president(view, ros, sps, n, ctx) {
  const p = ros.find(x => x.n === n);
  if (!p) { view.innerHTML = `<div class="empty">No president number ${n}.</div>`; return; }
  const mine = sps.filter(s => s.pr === n).sort((a, b) => (a.y || 0) - (b.y || 0));
  const same = ros.filter(x => x.name === p.name && x.n !== n);
  const prev = ros.find(x => x.n === n - 1), next = ros.find(x => x.n === n + 1);
  const e = eraOf(n);
  view.innerHTML = `
    <div class="crumbs"><a href="#/presidents">Hall of Presidents</a> › ${esc(e[2])}</div>
    <section class="spot" style="--era:${e[3]}">
      ${medal(p, true)}
      <div><p class="kicker" style="color:${e[3]}">${ord(n)} President of the United States</p><h1>${esc(p.name)}</h1>
        <div class="facts"><span class="chip s">⏱ ${years(p)}</span><span class="chip">${esc(p.party)}</span><span class="chip">⌂ ${esc(p.state)}</span>
          ${same.length ? `<span class="chip">also the ${same.map(x => ord(x.n)).join(" and ")}</span>` : ""}</div>
        <p class="lead">${esc(p.note)}</p></div>
    </section>
    <h2 style="margin-top:28px">Speeches</h2>
    ${mine.length ? `<div class="grid">${mine.map(s => `<a class="card" href="#/speech/${s.f}/${s.i}" style="--accent:${e[3]}"><span class="meta">${esc(s.d || s.y || "")}${s.w ? " · " + s.w.toLocaleString() + " words" : ""}${s.mv ? " · ▶ recording" : ""}</span><h3>${esc(s.oc || s.t)}</h3><p>${s.w ? `about ${Math.max(1, Math.round(s.w / 130))} minutes to read aloud` : ""}</p></a>`).join("")}</div>`
      : `<div class="empty">${esc(p.no_inaugural || "No speeches in the library yet.")} The Library Desk on base1 can find his speeches and recordings at the Library of Congress or the Internet Archive.</div>`}
    <div class="pres-nav">${prev ? `<a class="pill" href="#/president/${prev.n}">← ${esc(prev.name)}</a>` : "<span></span>"}
      <button class="pill" id="askP">Ask the tutor about ${esc(p.short)}</button>
      ${next ? `<a class="pill" href="#/president/${next.n}">${esc(next.name)} →</a>` : "<span></span>"}</div>`;
  view.querySelector("#askP").onclick = () => ctx.ask(`Tell me about ${p.name}`);
}

async function speechPage(view, ros, f, i, hi, ctx) {
  const d = await C.speech(f, i);
  const p = ros.find(x => x.n === d.pres) || { n: 0, name: "", from: "", to: "" };
  const e = eraOf(p.n || 1);
  const paras = await C.decode(d.seq);
  const total = paras.reduce((t, x) => t + x.length, 0);
  view.innerHTML = `
    <div class="crumbs"><a href="#/presidents">Hall of Presidents</a> › ${p.n ? `<a href="#/president/${p.n}">${esc(p.name)}</a>` : ""}</div>
    <section class="spot podium" style="--era:${e[3]}">
      ${p.n ? medal(p, true) : ""}
      <div><p class="kicker" style="color:${e[3]}">${esc(d.occasion || "Speech")} · ${esc(d.date || "")}</p><h1>${esc(p.name || d.title)}</h1>
        <div class="facts"><span class="chip">${(d.words || 0).toLocaleString()} words</span><span class="chip">${total} sentences</span>
        <span class="chip">≈ ${Math.max(1, Math.round((d.words || 0) / 130))} min aloud</span></div>
        <div class="art-actions"><button class="pill gold" id="deliver">▶ Stand and deliver</button>
          ${d.key ? `<button class="pill" id="famous">★ The famous line</button>` : ""}
          <button class="pill" id="askS">Ask the tutor</button></div>
        ${d.key_text ? `<blockquote class="famous">“${esc(d.key_text)}”</blockquote>` : ""}
      </div>
    </section>
    ${playerFor(d)}
    <div class="doc speech" id="text">${ctx.prose(paras, false)}</div>
    <p class="fine">${esc(d.source || "")}. Public domain. Stored as COG addresses; turn on # to see them.</p>`;
  const spans = [...view.querySelectorAll("#text .s")];
  if (d.key) view.querySelectorAll(`#text .s[data-a="${CSS.escape(d.key)}"]`).forEach(x => x.classList.add("key"));
  view.querySelector("#deliver").onclick = ev => readSpans(spans, p.n, ev.currentTarget);
  const fam = view.querySelector("#famous");
  if (fam) fam.onclick = () => { const k = spans.findIndex(x => x.dataset.a === d.key); hush(); spans[k].scrollIntoView({ block: "center" }); spans[k].classList.add("speak"); say(spans[k].textContent, p.n, () => spans[k].classList.remove("speak")); };
  view.querySelector("#askS").onclick = () => ctx.ask(`What did ${p.name} say in his ${d.occasion || "speech"}?`);
  view.querySelector("#text").onclick = ev => { const s = ev.target.closest(".s"); if (s && ctx.state.nums) location.hash = "#/m/" + s.dataset.a; };
  if (hi) { const el = spans.find(x => x.dataset.a === hi); if (el) { el.classList.add("speak"); el.scrollIntoView({ block: "center" }); setTimeout(() => el.classList.remove("speak"), 2500); } }
}
function playerFor(d) {
  const m = d.media || [];
  const v = m.find(x => x.type === "video"), a = m.find(x => x.type === "audio");
  if (v) return `<div class="media-box"><video class="player" controls preload="metadata" src="${esc(v.url)}"></video><p class="fine">The real recording, streamed from ${esc(d.archive || "the archive")}.</p></div>`;
  if (a) return `<div class="media-box"><audio class="player" controls preload="metadata" src="${esc(a.url)}"></audio><p class="fine">The real recording, streamed from ${esc(d.archive || "the archive")}.</p></div>`;
  return "";
}

// ------------------------------------------------------------------ roll call
function rollCall(view, ros, sps) {
  const keyBy = {};
  sps.filter(s => s.pr).forEach(s => { (keyBy[s.pr] = keyBy[s.pr] || []).push(s); });
  view.innerHTML = `
    <div class="roll">
      <div class="roll-stage"><div class="beam"></div><div id="rollMedal"></div><h1 id="rollName">The Hall of Presidents</h1><p id="rollLine" class="lead">Press start. Each president is called, in order.</p></div>
      <div class="roll-row" id="rollRow">${ros.map(p => `<span data-n="${p.n}" title="${esc(p.name)}">${p.n}</span>`).join("")}</div>
      <div class="art-actions" style="justify-content:center"><button class="pill gold" id="rollGo">▶ Start the roll call</button><button class="pill" id="rollSkip">Next ›</button>
        <label class="fine"><input type="checkbox" id="rollLines" checked> famous lines too</label><a class="pill" href="#/presidents">Back to the Hall</a></div>
    </div>`;
  let i = 0, running = false;
  const famous = async n => { const s = (keyBy[n] || []).find(x => x); if (!s) return null; const d = await C.speech(s.f, s.i); return d.key_text || null; };
  const alive = () => !!document.getElementById("rollMedal");
  const show = async () => {
    if (!alive()) { running = false; hush(); return; }
    if (!running || i >= ros.length) { running = false; view.querySelector("#rollGo").textContent = i >= ros.length ? "↺ Again" : "▶ Continue"; if (i >= ros.length) i = 0; return; }
    const p = ros[i];
    view.querySelector("#rollMedal").innerHTML = medal(p, true);
    view.querySelector("#rollMedal").firstElementChild.classList.add("rise");
    view.querySelector("#rollName").textContent = p.name;
    view.querySelector("#rollRow").querySelectorAll("span").forEach(s => s.classList.toggle("on", +s.dataset.n === p.n));
    view.querySelector(`#rollRow span[data-n="${p.n}"]`).scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
    const line = view.querySelector("#rollLines").checked ? await famous(p.n) : null;
    if (!alive()) { running = false; return; }
    view.querySelector("#rollLine").textContent = `${ord(p.n)} President · ${years(p)}` + (line ? ` — “${line}”` : "");
    const me = p.n;
    say(`${p.name}. ${ord(p.n)} President of the United States, ${p.from} to ${p.to ?? "today"}.`, 0, () => {
      if (!running || ros[i] !== p) return;
      if (line) say(line, me, () => { if (running && ros[i] === p) { i++; setTimeout(show, 350); } });
      else { i++; setTimeout(show, 350); }
    });
  };
  view.querySelector("#rollGo").onclick = () => { if (running) { running = false; hush(); view.querySelector("#rollGo").textContent = "▶ Continue"; return; } running = true; view.querySelector("#rollGo").textContent = "❚❚ Pause"; show(); };
  view.querySelector("#rollSkip").onclick = () => { hush(); i = Math.min(i + 1, ros.length - 1); if (!running) { running = true; view.querySelector("#rollGo").textContent = "❚❚ Pause"; } show(); };
}

// ------------------------------------------------------------------ games
const shuffle = a => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
async function whoSaidIt(view, ros, sps) {
  const withKey = [];
  for (const s of sps.filter(x => x.pr)) { const d = await C.speech(s.f, s.i); if (d.key_text) withKey.push({ s, d, p: ros.find(x => x.n === d.pres) }); }
  const rounds = shuffle(withKey).slice(0, 8);
  let r = 0, score = 0;
  if (location.hash.indexOf("/who") < 0) return;
  view.innerHTML = `<div class="crumbs"><a href="#/presidents">Hall of Presidents</a></div><p class="kicker">Game</p><h1>Who said it?</h1><p class="lead">Each line is real, word for word, from an inaugural address. Pick who said it.</p><div class="game" id="game"></div>`;
  const g = view.querySelector("#game");
  const round = () => {
    if (r >= rounds.length) { g.innerHTML = `<h2>${score} of ${rounds.length}!</h2><p class="lead">${score === rounds.length ? "Perfect — a true historian." : "Hear the speeches in the Hall, then try again."}</p><button class="pill gold" id="again">Play again</button>`; g.querySelector("#again").onclick = () => whoSaidIt(view, ros, sps); return; }
    const q = rounds[r];
    const names = [...new Set(ros.map(p => p.name))].filter(nm => nm !== q.p.name);
    const opts = shuffle([q.p.name, ...shuffle(names).slice(0, 3)]);
    g.innerHTML = `<p class="fine">Question ${r + 1} of ${rounds.length} · score ${score}</p><blockquote class="famous big">“${esc(q.d.key_text)}”</blockquote>
      <div class="opts">${opts.map(o => `<button>${esc(o)}</button>`).join("")}</div><div id="after"></div>`;
    g.querySelectorAll(".opts button").forEach(b => b.onclick = () => {
      const right = b.textContent === q.p.name;
      if (right) score++;
      g.querySelectorAll(".opts button").forEach(x => { x.disabled = true; if (x.textContent === q.p.name) x.classList.add("right"); });
      if (!right) b.classList.add("wrong");
      g.querySelector("#after").innerHTML = `<p>${right ? "Yes!" : "Not quite."} ${esc(q.p.name)}, ${esc(q.d.occasion)}, ${esc(q.d.date)}. <a href="#/speech/${q.s.f}/${q.s.i}?s=${q.d.key}">Hear it in the speech →</a></p><button class="pill gold">Next</button>`;
      say(q.d.key_text, q.p.n);
      g.querySelector("#after button").onclick = () => { hush(); r++; round(); };
    });
  };
  if (!rounds.length) g.innerHTML = `<div class="empty">No famous lines yet.</div>`; else round();
}
function orderUp(view, ros) {
  const people = [...new Map(ros.map(p => [p.name, p])).values()];
  const pick = shuffle(people).slice(0, 5);
  const answer = pick.slice().sort((a, b) => a.n - b.n);
  let chosen = [];
  view.innerHTML = `<div class="crumbs"><a href="#/presidents">Hall of Presidents</a></div><p class="kicker">Game</p><h1>Order up!</h1>
    <p class="lead">Tap these five presidents in the order they served, first to last.</p>
    <div class="order" id="pool">${shuffle(pick).map(p => `<button data-n="${p.n}">${medal(p)}<b>${esc(p.name)}</b></button>`).join("")}</div>
    <div class="order picked" id="picked"></div><div id="res"></div>`;
  view.querySelectorAll("#pool button").forEach(b => b.onclick = () => {
    if (b.disabled) return;
    b.disabled = true; chosen.push(+b.dataset.n);
    view.querySelector("#picked").insertAdjacentHTML("beforeend", `<span>${chosen.length}. ${esc(ros.find(p => p.n === +b.dataset.n).name)}</span>`);
    if (chosen.length === 5) {
      const ok = chosen.every((n, k) => n === answer[k].n);
      view.querySelector("#res").innerHTML = `<h2>${ok ? "Perfect order!" : "Close!"}</h2><p>${answer.map(p => `<a href="#/president/${p.n}">${esc(p.name)}</a> (${years(p)})`).join(" → ")}</p><button class="pill gold" id="again">New five</button>`;
      view.querySelector("#again").onclick = () => orderUp(view, ros);
    }
  });
}
async function lengths(view, ros, sps) {
  const list = sps.filter(s => s.k === "speech" && s.w).sort((a, b) => a.y - b.y);
  const max = Math.max(...list.map(s => s.w));
  const longest = list.reduce((a, b) => (b.w > a.w ? b : a)), shortest = list.reduce((a, b) => (b.w < a.w ? b : a));
  const name = s => (ros.find(p => p.n === s.pr) || {}).name || "";
  view.innerHTML = `<div class="crumbs"><a href="#/presidents">Hall of Presidents</a></div><p class="kicker">Game</p><h1>Longest &amp; shortest speeches</h1>
    <p class="lead">Guess first: which inaugural address was the <b>longest</b>?</p>
    <div class="opts" id="guess">${shuffle([longest, ...shuffle(list.filter(s => s !== longest)).slice(0, 3)]).map(s => `<button data-id="${esc(s.id)}">${esc(name(s))} · ${s.y}</button>`).join("")}</div>
    <div id="reveal" hidden>
      <p class="lead" style="margin-top:18px">Longest: <b>${esc(name(longest))}</b>, ${longest.y} — ${longest.w.toLocaleString()} words. Shortest: <b>${esc(name(shortest))}</b>, ${shortest.y} — just ${shortest.w.toLocaleString()} words.</p>
      <div class="bars" role="list">${list.map(s => `<a role="listitem" href="#/speech/${s.f}/${s.i}" title="${esc(name(s))} ${s.y}: ${s.w.toLocaleString()} words" style="--h:${(s.w / max * 100).toFixed(1)}%;--era:${eraOf(s.pr || 1)[3]}" class="${s === longest || s === shortest ? "mark" : ""}"><i></i><small>${s.y}</small></a>`).join("")}</div>
      <p class="fine">Each bar is one inaugural address, by year. Tap a bar to read it.</p></div>`;
  view.querySelectorAll("#guess button").forEach(b => b.onclick = () => {
    view.querySelectorAll("#guess button").forEach(x => { x.disabled = true; if (x.dataset.id === longest.id) x.classList.add("right"); });
    if (b.dataset.id !== longest.id) b.classList.add("wrong");
    view.querySelector("#reveal").hidden = false;
  });
}
