// Laws, Amendments & the Court — every presidency broken into its Congresses, with the landmark laws, amendments and
// Supreme Court cases of each; and guided threads (the first: The Covenant Republic). All text comes from the COG packs.
import * as C from "./core.js";

const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const yearOf = d => +(String(d).slice(0, 4));
const fmtDate = d => { const [y, m, dd] = String(d).split("-"); if (!m) return y; return new Date(+y, +m - 1, +(dd || 1)).toLocaleDateString(undefined, { year: "numeric", month: "short", ...(dd ? { day: "numeric" } : {}) }); };
const kindChip = k => { const v = C.KINDS[k] || ["•", k, "#888"]; return `<span class="kchip" style="--k:${v[2]}">${v[0]} ${esc(v[1])}</span>`; };
const lmCard = e => { const v = C.KINDS[e.lk] || ["•", "", "#888"]; return `<button class="lm" data-t="${esc(e.t)}" style="--k:${v[2]}"><span>${v[0]}</span><b>${esc(e.t)}</b><small>${fmtDate(e.d)}${e.cg ? " · " + C.ordinal(e.cg) + " Congress" : ""}</small></button>`; };

async function lmDetail(e, box, ctx) {
  const d = await C.landmark(e);
  box.innerHTML = `<div class="lm-detail" style="--k:${(C.KINDS[e.lk] || [0, 0, "#888"])[2]}">${kindChip(e.lk)}<h3>${esc(d.title)}</h3>
    <p class="fine">${fmtDate(d.date)}${d.congress ? ` · ${C.ordinal(d.congress)} Congress` : ""}${d.pres ? ` · in the presidency of <a href="#/president/${d.pres}">${esc(ctx.ros.find(p => p.n === d.pres)?.name || "")}</a>` : ""}</p>
    <p class="lm-text">${esc(d.text)} ${ctx.state.nums ? `<sup class="addr" style="display:inline">${d.addrs.join(" ")}</sup>` : ""}</p>
    <div class="art-actions"><button class="pill" data-say>▶ Read to me</button><a class="pill" href="${esc(d.url)}" target="_blank" rel="noopener" style="text-decoration:none;color:inherit">Primary source at loc.gov ↗</a>
    <button class="pill" data-ask>Ask the tutor</button></div></div>`;
  box.querySelector("[data-say]").onclick = () => { speechSynthesis.cancel(); speechSynthesis.speak(Object.assign(new SpeechSynthesisUtterance(`${d.title}. ${d.text}`), { rate: ctx.rate() })); };
  box.querySelector("[data-ask]").onclick = () => ctx.ask(`Explain ${d.title}`);
  box.scrollIntoView({ block: "nearest", behavior: ctx.motion() });
}

// ------------------------------------------------------------------ the civics timeline: presidency → Congresses → landmarks
export async function civicsPage(view, params, ctx) {
  const [{ congresses, landmarks }, ros] = await Promise.all([C.civics(), C.roster()]);
  ctx.ros = ros;
  if (!congresses.length) { view.innerHTML = `<div class="empty">The civics layer has not been published yet (publish_civics.py).</div>`; return; }
  const filter = params.get("k") || "";
  const shown = landmarks.filter(e => !filter || e.lk === filter);
  const founding = shown.filter(e => !e.cg);
  const byCong = {};
  shown.filter(e => e.cg).forEach(e => (byCong[e.cg] = byCong[e.cg] || []).push(e));
  const counts = {};
  landmarks.forEach(e => counts[e.lk] = (counts[e.lk] || 0) + 1);
  const blocks = ros.map(p => {
    const cgs = congresses.filter(c => c.presidents.includes(p.n));
    const items = cgs.map(c => ({ c, items: (byCong[c.n] || []).filter(e => e.pr === p.n || (!e.pr && c.presidents[0] === p.n)) }));
    const total = items.reduce((t, x) => t + x.items.length, 0);
    return `<section class="pres-block${total ? "" : " quiet"}" id="p${p.n}">
      <header><a href="#/president/${p.n}" class="pb-name"><b>${p.n}</b> ${esc(p.name)}</a><small>${p.from}–${p.to ?? "today"} · ${esc(p.party)}</small></header>
      <div class="cg-row">${items.map(({ c, items }) => `<div class="cg"><div class="cg-h">${C.ordinal(c.n)} Congress <small>${c.from}–${c.to}</small></div>
        ${items.length ? `<div class="lms">${items.map(lmCard).join("")}</div>` : `<div class="cg-empty">—</div>`}</div>`).join("")}</div></section>`;
  }).join("");
  view.innerHTML = `
    <section class="civ-hero"><p class="kicker">Laws, Amendments &amp; the Court</p><h1>How the law grew, Congress by Congress</h1>
      <p class="lead">Every presidency, split into the Congresses that served with it: ${congresses.length} Congresses, from the 1st in 1789 to the ${C.ordinal(congresses.length)} today. Under each are the landmark laws, amendments and Supreme Court cases. Tap any one for what it did and its primary source.</p>
      <div class="tl-controls">${["", ...Object.keys(C.KINDS)].map(k => `<button class="${k === filter ? "on" : ""}" onclick="location.hash='#/civics${k ? "?k=" + k : ""}'">${k ? C.KINDS[k][0] + " " + C.KINDS[k][1] + " · " + (counts[k] || 0) : "Everything · " + landmarks.length}</button>`).join("")}
        <a class="pill" href="#/threads" style="text-decoration:none;color:inherit">Guided threads →</a></div>
      <div class="jump">Jump to a president: <select id="jumpP">${ros.map(p => `<option value="${p.n}">${p.n}. ${esc(p.name)} (${p.from})</option>`).join("")}</select></div>
    </section>
    <div id="lmDetail"></div>
    ${founding.length ? `<section class="pres-block founding"><header><span class="pb-name">Before the presidency</span><small>1775–1789</small></header><div class="lms">${founding.map(lmCard).join("")}</div></section>` : ""}
    ${blocks}`;
  const det = view.querySelector("#lmDetail");
  view.addEventListener("click", ev => { const b = ev.target.closest(".lm"); if (!b) return; const e = landmarks.find(x => x.t === b.dataset.t); if (e) { b.closest(".pres-block").after(det); lmDetail(e, det, ctx); } });
  view.querySelector("#jumpP").onchange = ev => view.querySelector("#p" + ev.target.value).scrollIntoView({ behavior: ctx.motion(), block: "start" });
  if (params.get("p")) { const el = view.querySelector("#p" + params.get("p")); if (el) { el.scrollIntoView({ block: "start" }); el.classList.add("flash"); } }
}

// for a president's page: his Congresses and their landmarks
export async function presidentCivics(n, ctx) {
  const [{ congresses, landmarks }, ros] = await Promise.all([C.civics(), C.roster()]);
  ctx.ros = ros;
  const cgs = congresses.filter(c => c.presidents.includes(n));
  if (!cgs.length) return "";
  const html = cgs.map(c => {
    const items = landmarks.filter(e => e.cg === c.n && e.pr === n);
    return `<div class="cg"><div class="cg-h">${C.ordinal(c.n)} Congress <small>${c.from}–${c.to}</small></div>${items.length ? `<div class="lms">${items.map(lmCard).join("")}</div>` : `<div class="cg-empty">No landmark in the library yet</div>`}</div>`;
  }).join("");
  return `<h2 style="margin-top:28px">Congresses &amp; the law</h2><div class="cg-row" id="presCiv">${html}</div><div id="lmDetail"></div>
    <p class="fine"><a href="#/civics?p=${n}">See him in the full Laws &amp; the Court timeline →</a></p>`;
}
export function wirePresidentCivics(view, ctx) {
  view.querySelectorAll("#presCiv .lm").forEach(b => b.onclick = async () => {
    const { landmarks } = await C.civics(); const e = landmarks.find(x => x.t === b.dataset.t); if (e) lmDetail(e, view.querySelector("#lmDetail"), ctx);
  });
}

// ------------------------------------------------------------------ guided threads
export async function threadsPage(view) {
  const list = await C.threads();
  view.innerHTML = `<p class="kicker">Guided threads</p><h1>Walk a story through the library</h1>
    <p class="lead">A thread is a guided tour: one station at a time, each linking to the articles, speeches, laws and cases behind it.</p>
    <div class="grid section">${list.map(t => `<a class="card thread-card" href="#/thread/${esc(t.id)}"><span class="meta">${t.stations} stations · scribes: ${esc(t.scribes)}</span><h3>${esc(t.title)}</h3><p>${esc(t.subtitle)}</p></a>`).join("") || `<div class="empty">No threads yet.</div>`}</div>`;
}
export async function threadPage(view, id, params, ctx) {
  const [th, { landmarks }, ros, arts] = await Promise.all([C.thread(id), C.civics(), C.roster(), C.articles()]);
  ctx.ros = ros;
  let k = Math.max(0, Math.min(th.stations.length - 1, +(params.get("s") || 0)));
  const about = (await C.decode(th.about_seq)).map(p => p.map(x => x.t).join(" ")).join(" ");
  const draw = async () => {
    const st = th.stations[k];
    const paras = await C.decode(st.seq);
    const L = st.links || {};
    const chips = [
      ...(L.presidents || []).map(n => { const p = ros.find(x => x.n === n); return p ? `<a class="chip s" href="#/president/${n}">★ ${esc(p.name)}</a>` : ""; }),
      ...(L.articles || []).map(s => { const a = arts.find(x => x.slug === s); return a ? `<a class="chip s" href="#/a/${s}">❏ ${esc(a.t)}</a>` : ""; }),
      ...(L.landmarks || []).map(t => landmarks.find(x => x.t === t)).filter(Boolean).map(e => `<button class="chip s lmchip" data-t="${esc(e.t)}">${(C.KINDS[e.lk] || ["•"])[0]} ${esc(e.t)}</button>`),
    ].join("");
    view.querySelector("#station").innerHTML = `
      <div class="st-date">${esc(String(st.date).length > 4 ? fmtDate(st.date) : st.date)}</div>
      <h2>${esc(st.title)}</h2>
      <div class="prose st-text">${ctx.prose(paras, false)}</div>
      ${chips ? `<div class="facts">${chips}</div>` : ""}
      <div id="lmDetail"></div>`;
    view.querySelector("#dots").innerHTML = th.stations.map((s, i) => `<button class="${i === k ? "on" : ""}" data-i="${i}" title="${esc(s.title)}"></button>`).join("");
    view.querySelector("#prev").disabled = k === 0;
    view.querySelector("#next").textContent = k === th.stations.length - 1 ? "Back to the start ↺" : "Next station →";
    view.querySelectorAll(".lmchip").forEach(b => b.onclick = () => { const e = landmarks.find(x => x.t === b.dataset.t); if (e) lmDetail(e, view.querySelector("#lmDetail"), ctx); });
    history.replaceState(null, "", `#/thread/${id}?s=${k}`);
  };
  view.innerHTML = `
    <section class="thread-hero"><p class="kicker">Guided thread · scribes: ${esc(th.scribes)}</p><h1>${esc(th.title)}</h1><p class="lead">${esc(th.subtitle)}</p><p class="fine thread-about">${esc(about)}</p></section>
    <div class="thread-nav"><div class="dots" id="dots"></div></div>
    <article class="station" id="station"></article>
    <div class="art-actions station-ctl"><button class="pill" id="prev">← Back</button><button class="pill" id="say">▶ Read to me</button><button class="pill gold" id="next">Next station →</button></div>`;
  view.querySelector("#prev").onclick = () => { if (k > 0) { k--; draw(); } };
  view.querySelector("#next").onclick = () => { k = (k + 1) % th.stations.length; draw(); view.querySelector("#station").scrollIntoView({ block: "start", behavior: ctx.motion() }); };
  view.querySelector("#dots").onclick = ev => { const b = ev.target.closest("button"); if (b) { k = +b.dataset.i; draw(); } };
  view.querySelector("#say").onclick = () => { speechSynthesis.cancel(); const t = view.querySelector("#station"); speechSynthesis.speak(Object.assign(new SpeechSynthesisUtterance(t.querySelector("h2").textContent + ". " + t.querySelector(".st-text").textContent), { rate: ctx.rate() })); };
  await draw();
}
