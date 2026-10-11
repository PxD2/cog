// Alexandria tutor — answers only from the library. Every sentence it quotes carries its COG address,
// so a reader can always open the exact source. Optional: a local model on base1 (Ollama) writes the reply,
// still fed only the passages found here.
import * as C from "./core.js";

const cfgKey = "alexandria.tutor";
export function config() {
  try { return Object.assign({ url: "http://localhost:11434", model: "", useModel: false }, JSON.parse(localStorage.getItem(cfgKey) || "{}")); }
  catch (e) { return { url: "http://localhost:11434", model: "", useModel: false }; }
}
export function saveConfig(c) { try { localStorage.setItem(cfgKey, JSON.stringify(c)); } catch (e) {} }

export async function models(url) {
  const r = await fetch(url.replace(/\/$/, "") + "/api/tags", { signal: AbortSignal.timeout(3000) });
  return ((await r.json()).models || []).map(m => m.name).filter(n => !n.includes("embed"));
}

function pick(sents, level, n) {
  const seen = new Set(), out = [];
  const pref = sents.filter(s => !level || s.level === level).concat(sents);
  for (const s of pref) { if (seen.has(s.t)) continue; seen.add(s.t); out.push(s); if (out.length >= n) break; }
  return out;
}

export async function answer(q, ctx = {}) {
  const text = q.trim();
  const low = text.toLowerCase();
  const level = ctx.level || "deeper";
  const arts = await C.articles();
  const here = ctx.slug ? arts.find(a => a.slug === ctx.slug) : null;
  const vague = /^(summari[sz]e|explain( this| it)?|what is this( about)?|tell me (more|about this)|tl;?dr)\??$/.test(low);
  // which article is the question about?
  const r = await C.search(vague && here ? here.t : text, 40);
  let focus = r.articles[0] || here;
  if (here && (vague || /\b(this|it|here)\b/.test(low))) focus = here;

  if (/quiz|test me|question me/.test(low)) {
    const a = focus || arts[Math.floor(Math.random() * arts.length)];
    return { kind: "quiz", slug: a.slug, text: `Quiz on ${a.t} — here you go.`, cites: [], actions: [{ label: "Open " + a.t, href: "#/a/" + a.slug }] };
  }
  if (focus && /^when\b|what year|which year|\bdate\b/.test(low) && focus.y != null) {
    const y = focus.y < 0 ? `${-focus.y} BC` : focus.y;
    return { kind: "fact", text: `${focus.t}: ${y}. ${focus.sum || ""}`.trim(), cites: [],
      actions: [{ label: "See it on the timeline", href: "#/timeline?y=" + focus.y }, { label: "Read " + focus.t, href: "#/a/" + focus.slug }] };
  }
  if (focus && /^where\b|which (place|state|country)|map/.test(low) && focus.p) {
    return { kind: "fact", text: `${focus.t} is placed at ${focus.p[0].toFixed(2)}, ${focus.p[1].toFixed(2)} on the atlas. ${focus.sum || ""}`.trim(), cites: [],
      actions: [{ label: "Show on the atlas", href: "#/atlas?a=" + focus.slug }, { label: "Read " + focus.t, href: "#/a/" + focus.slug }] };
  }
  const simple = /simpl|kid|easy|young|like i'?m|eli5/.test(low);
  let sents = r.sentences;
  if (focus) {
    // stay on the article the question is about; other articles only when they match the question strongly
    const qw = C.words(text).filter(w => !["explain", "simply", "simple", "tell", "about", "kid", "kids", "easy", "what", "summarize"].includes(w));
    const strong = s => qw.length > 1 && qw.filter(w => s.w.has(w)).length >= Math.ceil(qw.length * 0.75);
    let own = sents.filter(s => s.slug === focus.slug);
    if (own.length < 2 || vague || simple) {
      const all = (await C.sentenceIndex()).filter(s => s.slug === focus.slug);
      own = own.concat(all.filter(s => !own.includes(s)));
    }
    sents = own.concat(sents.filter(s => s.slug !== focus.slug && strong(s)));
  }
  const cites = pick(sents, simple ? "young" : level, simple ? 3 : 4);
  if (!cites.length && !focus) {
    return { kind: "none", text: "The library doesn't have anything on that yet. Try other words, or add it: the Library Desk on base1 can find it on loc.gov and absorb it.",
      cites: [], actions: [] };
  }
  const lead = focus ? `${focus.t} — ${focus.sum || ""}`.trim() : "Here is what the library says:";
  const res = { kind: "answer", text: lead, cites, actions: [] };
  if (focus) res.actions.push({ label: "Read the full article", href: "#/a/" + focus.slug });
  for (const s of r.sources.slice(0, 2)) res.actions.push({ label: "Primary source: " + (s.t || "").slice(0, 60), href: "#/src/" + encodeURIComponent(s.section.id) + "/" + s.f + "/" + s.i });
  if (focus && focus.y != null) res.actions.push({ label: "Timeline", href: "#/timeline?y=" + focus.y });

  const cfg = config();
  if (cfg.useModel && cfg.model) {
    try {
      const passages = cites.concat(pick(sents, null, 10)).slice(0, 10).map(s => `[${s.a}] (${s.title}) ${s.t}`).join("\n");
      const sys = `You are the Alexandria tutor for students (K-12). Answer ONLY from the passages below. Quote addresses like [1042.3] after facts you use. If the passages do not answer it, say the library does not cover that yet. ${simple ? "Use very simple words for a young reader." : "Be clear and short."}\n\nPassages:\n${passages}`;
      const r2 = await fetch(cfg.url.replace(/\/$/, "") + "/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: cfg.model, stream: false, options: { temperature: 0.2 }, messages: [{ role: "system", content: sys }, { role: "user", content: text }] }),
        signal: AbortSignal.timeout(120000) });
      const m = (await r2.json()).message;
      if (m && m.content) { res.text = m.content.trim(); res.model = cfg.model; }
    } catch (e) { res.note = "Local model not reachable — answered from the library directly."; }
  }
  return res;
}
