// Alexandria data core — everything comes from the COG packs on GitHub. No text is stored anywhere else:
// articles and sources are lines of (meaning-id, variant-index) addresses, rebuilt here from the meaning packs.
// After a pack is loaded, every expansion is a Map lookup (no parsing on the hot path).
export const TRUST = "The Library of Congress is a taxpayer trust: held in trust for the people who paid for it, not a government organization or entity.";
const BASE = new URL("../", import.meta.url).href;      // the cog repo root on GitHub Pages
const files = new Map();
export function getFile(path, base = "") {
  const url = (base || BASE) + path;
  if (!files.has(url)) files.set(url, fetch(url).then(r => { if (!r.ok) throw new Error(path + " " + r.status); return r.json(); }));
  return files.get(url);
}

let catalog = null;
export async function getCatalog() {
  if (!catalog) catalog = getFile("books/catalog.json").catch(() => ({ books: [], sections: [], totals: {} }));
  return catalog;
}

// ---------------------------------------------------------------- meanings: id -> rows, loaded pack by pack
const rows = new Map();               // m -> [{start, vs, keys}]
const loadedPacks = new Set();
function absorbPack(p) {
  for (const r of p.s || []) {
    const list = rows.get(r[0]) || [];
    list.push({ start: r[2][0], vs: r[3], keys: r[1] });
    list.sort((a, b) => a.start - b.start);
    rows.set(r[0], list);
  }
}
async function loadPack(file) {
  if (loadedPacks.has(file)) return;
  loadedPacks.add(file);
  absorbPack(await getFile(file));
}
function packsFor(cat, m) {
  return cat.books.filter(b => b.kind === "meanings" && (b.room !== "core" ||
    (b.from != null && m >= b.from && m <= b.to) || (b.cont || []).includes(m))).map(b => b.file);
}
export async function ensureMeanings(ids) {
  const cat = await getCatalog();
  const need = new Set();
  for (const m of ids) if (!rows.has(m)) packsFor(cat, m).forEach(f => need.add(f));
  await Promise.all([...need].map(loadPack));
}
export function variant(m, v) {
  const list = rows.get(m);
  if (!list) return null;
  for (const r of list) if (v >= r.start && v < r.start + r.vs.length) return r.vs[v - r.start];
  return null;
}
export async function meaning(m) {
  await ensureMeanings([m]);
  const list = rows.get(m) || [];
  const keys = (list.find(r => r.keys && r.keys.length) || { keys: [] }).keys;
  return { m, keys, variants: list.flatMap(r => r.vs.map((t, i) => ({ v: r.start + i, t }))) };
}

// a line of addresses -> paragraphs of {a, t}
export async function decode(seq) {
  const toks = (seq || "").split(" ").filter(Boolean);
  await ensureMeanings(new Set(toks.filter(t => t !== "|").map(t => +t.split(".")[0])));
  const paras = [[]];
  for (const t of toks) {
    if (t === "|") { paras.push([]); continue; }
    const [m, v] = t.split(".").map(Number);
    paras[paras.length - 1].push({ a: t, t: variant(m, v) ?? `[${t}]` });
  }
  return paras.filter(p => p.length);
}

// ---------------------------------------------------------------- sections, articles, sources
export async function sections() { return (await getCatalog()).sections || []; }

async function indexOf(sec) {
  const parts = await Promise.all((sec.index || []).map(f => getFile(f).catch(() => ({ e: [] }))));
  return parts.flatMap(p => p.e || []);
}

let articlesP = null;
export function articles() {
  if (!articlesP) articlesP = (async () => {
    const sec = (await sections()).find(s => s.id === "encyclopedia");
    if (!sec) return [];
    const latest = new Map();
    for (const e of await indexOf(sec)) latest.set(e.id, e);          // later entries are newer versions
    return [...latest.values()].map(e => ({ ...e, slug: e.id.replace(/^article:/, ""), section: sec }));
  })();
  return articlesP;
}
export async function article(slug) {
  const e = (await articles()).find(a => a.slug === slug);
  if (!e) return null;
  const pack = await getFile(e.section.files[e.f - 1], e.section.base);
  return { ...e, ...pack.docs[e.i] };
}

let sourcesP = null;
export function sources() {         // primary-source documents in every other section
  if (!sourcesP) sourcesP = (async () => {
    const out = [];
    for (const s of await sections()) {
      if (s.id === "encyclopedia" || s.id === "civics") continue;
      for (const e of await indexOf(s)) out.push({ ...e, section: s });
    }
    return out;
  })();
  return sourcesP;
}
export async function sourceDoc(e) {
  const pack = await getFile(e.section.files[e.f - 1], e.section.base);
  return pack.docs[e.i];
}

// ---------------------------------------------------------------- search: titles, summaries, and every sentence of the articles
const STOP = new Set("a an the and or but nor of to in on at by for with from as into onto upon over under about above below between is are was were be been being it its this that these those there here which who whom whose what when where why how shall will may might must can could would should do does did done has have had having not no so such than then i me my you your we our they them their he she his her".split(" "));
export const words = s => (s.toLowerCase().match(/[a-z0-9]+/g) || []).filter(w => !STOP.has(w) && w.length > 1);

let sentIdx = null;                  // [{slug, title, level, a, t, w:Set}]
export async function sentenceIndex() {
  if (sentIdx) return sentIdx;
  const list = await articles();
  const full = await Promise.all(list.map(a => article(a.slug)));
  const all = [];
  for (const a of full) for (const [level, seq] of Object.entries(a.levels || {})) {
    for (const p of await decode(seq)) for (const s of p) all.push({ slug: a.slug, title: a.title, level, a: s.a, t: s.t, w: new Set(words(s.t)) });
  }
  sentIdx = all;
  return all;
}
export function score(qw, w, text) {
  let s = 0;
  for (const q of qw) if (w.has(q)) s += 1; else if ([...w].some(x => x.startsWith(q) || q.startsWith(x) && x.length > 3)) s += 0.5;
  return s / Math.sqrt(1 + w.size / 12);
}
export async function search(q, limit = 30) {
  const qw = words(q);
  if (!qw.length) return { articles: [], sentences: [], sources: [] };
  const arts = (await articles()).map(a => ({ a, s: score(qw, new Set(words(`${a.t} ${a.t} ${a.s || ""} ${a.sum || ""}`)), "") }))
    .filter(x => x.s > 0).sort((x, y) => y.s - x.s).slice(0, 12).map(x => x.a);
  const pool = speechIdx ? (await sentenceIndex()).concat(speechIdx) : await sentenceIndex();
  const sents = pool.map(x => ({ x, s: score(qw, x.w) })).filter(x => x.s > 0)
    .sort((a, b) => b.s - a.s).slice(0, limit).map(x => x.x);
  const srcs = (await sources()).map(e => ({ e, s: score(qw, new Set(words(e.t || ""))) })).filter(x => x.s > 0)
    .sort((a, b) => b.s - a.s).slice(0, 12).map(x => x.e);
  return { articles: arts, sentences: sents, sources: srcs };
}

// ---------------------------------------------------------------- civics: Congresses, landmarks, threads
let civP = null;
export function civics() {
  if (!civP) civP = (async () => {
    const sec = (await sections()).find(s => s.id === "civics");
    if (!sec) return { congresses: [], landmarks: [], sec: null };
    const [cg, ix] = await Promise.all([getFile("sections/civics/congresses.json").catch(() => ({ congresses: [] })), indexOf(sec)]);
    const latest = new Map();
    for (const e of ix) latest.set(e.t, { ...e, section: sec });
    const lms = [...latest.values()].sort((a, b) => (a.d || "").localeCompare(b.d || ""));
    return { congresses: cg.congresses || [], landmarks: lms, sec };
  })();
  return civP;
}
export async function landmark(e) {
  const d = (await getFile(e.section.files[e.f - 1], e.section.base)).docs[e.i];
  const paras = await decode(d.seq);
  return { ...d, text: paras.map(p => p.map(x => x.t).join(" ")).join(" "), addrs: paras.flat().map(x => x.a) };
}
export async function threads() { return (await getFile("sections/civics/threads/index.json").catch(() => ({ threads: [] }))).threads; }
export async function thread(id) { return getFile(`sections/civics/threads/${id}.json`); }
export const ordinal = n => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th");
export const KINDS = { founding: ["✒", "Founding", "#c9a227"], amendment: ["Ⅹ", "Amendment", "#b5523b"], law: ["§", "Law", "#3aa37c"],
  case: ["⚖", "Supreme Court", "#4f80c9"], executive: ["★", "President's act", "#9a62c2"] };

// ---------------------------------------------------------------- Hall of Presidents
let rosterP = null, speechesP = null, speechIdx = null;
export function roster() {
  if (!rosterP) rosterP = getFile("sections/presidents/roster.json").then(r => r.presidents || []).catch(() => []);
  return rosterP;
}
export function speeches() {           // every speech in the presidents section, newest version per id
  if (!speechesP) speechesP = (async () => {
    const sec = (await sections()).find(s => s.id === "presidents");
    if (!sec) return [];
    const latest = new Map();
    for (const e of await indexOf(sec)) latest.set(e.id, { ...e, section: sec });
    const ros = await roster();
    return [...latest.values()].map(e => {
      if (!e.pr) {                      // absorbed speeches / recordings: match the president by name in the title
        const hit = ros.slice().sort((a, b) => b.name.length - a.name.length).find(p => (e.t || "").includes(p.name));
        if (hit) e.pr = hit.n;
      }
      return e;
    });
  })();
  return speechesP;
}
export async function speech(f, i) {
  const sec = (await sections()).find(s => s.id === "presidents");
  const d = (await getFile(sec.files[f - 1], sec.base)).docs[i];
  return { ...d, f, i, section: sec };
}
export async function speechIndex() {  // every sentence of every speech (loaded only when asked: the Hall or the tutor)
  if (speechIdx) return speechIdx;
  const list = await speeches(), ros = await roster(), out = [];
  for (const e of list) {
    const d = await speech(e.f, e.i);
    const who = (ros.find(p => p.n === d.pres) || {}).name || "";
    for (const p of await decode(d.seq)) for (const s of p)
      out.push({ slug: `speech/${e.f}/${e.i}`, kind: "speech", title: d.title, who, pres: d.pres, level: "deeper", a: s.a, t: s.t, w: new Set(words(s.t)) });
  }
  speechIdx = out;
  return out;
}
export const speechesLoaded = () => !!speechIdx;

export const SUBJECTS = {
  "Civics & Government": { c: "#c9a227", i: "⚖" },
  "American History": { c: "#c0634a", i: "🏛" },
  "World History": { c: "#a8743f", i: "🗺" },
  "Science": { c: "#3aa37c", i: "🔬" },
  "Mathematics": { c: "#4f80c9", i: "∑" },
  "Geography": { c: "#2f9cb6", i: "🧭" },
  "Language Arts": { c: "#9a62c2", i: "✎" },
  "Technology": { c: "#7a8ca0", i: "⚙" },
};
export const subj = s => SUBJECTS[s] || { c: "#8b929a", i: "◆" };
