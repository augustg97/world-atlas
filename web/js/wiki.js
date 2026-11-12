// The live description. A location card names its English Wikipedia article (data/wiki.json, made and checked at
// build time by build/wiki_titles.py) and, when the card opens, the page asks en.wikipedia.org for that article's
// lead and shows it with its credit. No Wikipedia text is stored in the atlas.
//
// What the request carries: the article's title and nothing else. It is anonymous (no cookies, no custom headers,
// no referrer) and goes to one host, en.wikipedia.org. It tells that host which place's card was opened, as
// following a link to the article would.
//
// What comes back is UNTRUSTED text written by other people. It is only ever put on the page with textContent,
// never as HTML, and no image is taken (their licences vary). It is the LIVE tier: fetched now, credited, and not
// the atlas's own words. If the host cannot be reached the card says so in one line and is otherwise as it was.

import { getJSON } from './gl.js';
import { TIERS } from './catalog.js';

export const WIKI_API = 'https://en.wikipedia.org/w/api.php';
export const LEAD_CAP = 1500;          // characters of the lead shown; the cut is at the end of a sentence
export const TIMEOUT_MS = 8000;
const RETRY_MS = 60000;                // after a failure the host is not asked again for this long

const n3 = (v) => { const s = Number(v).toFixed(3); return s === '-0.000' ? '0.000' : s; };
/** The key a card is filed under in data/wiki.json. The same rule as card_key() in build/wiki_titles.py. */
export function wikiKey(kind, c) {
  if (kind === 'city' || kind === 'volcano') return `${c[0]}|${n3(c[1])}|${n3(c[2])}`;
  if (kind === 'country') return c.a3;
  if (kind === 'dispute') return `${c.name}|${c.note}`;
  if (kind === 'feature') return `${c.name}|${c.kind}|${n3(c.lon)}|${n3(c.lat)}`;
  if (kind === 'peak') return `${c.name}|${n3(c.lon)}|${n3(c.lat)}`;
  if (kind === 'river') return c.lines && c.lines[0] && c.lines[0].length > 1 ? `${c.name}|${c.lines[0][0]}|${c.lines[0][1]}` : '';
  return '';
}

let table = null, tableP = null;
/** The title table. Asked for once; a failure leaves every card without an article and says so in the console. */
export function loadTitles() {
  tableP ||= getJSON('data/wiki.json').then((j) => { table = j; return j; }).catch((e) => { console.error('wiki.json not loaded:', e.message); table = {}; return table; });
  return tableP;
}
/** { title, qid } for a card, null if the card has no article, undefined while the table is still on its way. */
export function articleFor(kind, key, t = table) {
  if (!t) return undefined;
  const v = t[kind] && Object.prototype.hasOwnProperty.call(t[kind], key) ? t[kind][key] : null;
  return v ? { title: v[0], qid: v[1] } : null;
}

/** The one request: the lead of one article as plain text, with its canonical address. */
export const leadUrl = (title) => `${WIKI_API}?action=query&prop=extracts|info&exintro=1&explaintext=1&redirects=1&inprop=url&format=json&formatversion=2&origin=*&titles=${encodeURIComponent(title)}`;
export const articleUrl = (title) => `https://en.wikipedia.org/wiki/${encodeURIComponent(String(title).replace(/ /g, '_'))}`;

const ABBR = /(?:^|[\s(])(?:[A-Z]|St|Mt|Dr|Mr|Mrs|Ms|Jr|Sr|Ft|Gen|Col|Lt|No|vs|ca|c|cf|approx|est|e\.g|i\.e|U\.S|U\.K)$/;
/** Where sentences end in a paragraph: the index just past each full stop that closes one. */
export function sentenceEnds(p) {
  const out = [], re = /[.!?]["”’)\]]*(?=\s+["“‘(]?[A-Z0-9À-Þ]|\s*$)/g;
  let m;
  while ((m = re.exec(p))) { if (p[m.index] !== '.' || !ABBR.test(p.slice(Math.max(0, m.index - 8), m.index))) out.push(m.index + m[0].length); }
  return out;
}
/**
 * A lead as paragraphs, no longer than `cap` characters in all, cut at the end of a sentence. Whole paragraphs
 * are kept while they fit; the one that does not is cut at its last sentence that does. `cut` says text was left out.
 */
export function trimLead(text, cap = LEAD_CAP) {
  const paras = String(text ?? '').split(/\n+/).map((p) => p.replace(/\(\s*[;,]\s*/g, '(').replace(/\(\s+/g, '(').replace(/\s*\(\s*\)/g, '').replace(/\s+/g, ' ').trim()).filter(Boolean);
  const out = []; let used = 0;
  for (const p of paras) {
    if (used + p.length <= cap) { out.push(p); used += p.length; continue; }
    const end = sentenceEnds(p).filter((i) => used + i <= cap).pop();
    if (end) out.push(p.slice(0, end));
    else if (!out.length) { const sp = p.lastIndexOf(' ', cap); out.push(p.slice(0, sp > 0 ? sp : cap) + ' …'); }
    return { paras: out, cut: true };
  }
  return { paras: out, cut: false };
}

/** The API's answer as { title, url, paras, cut }, or a thrown Error that says what was wrong with it. */
export function parseLead(j, cap = LEAD_CAP) {
  const pg = j && j.query && Array.isArray(j.query.pages) ? j.query.pages[0] : null;
  if (!pg || pg.missing || pg.invalid || typeof pg.title !== 'string') throw new Error('no such article');
  const url = typeof pg.fullurl === 'string' && pg.fullurl.startsWith('https://en.wikipedia.org/wiki/') ? pg.fullurl : articleUrl(pg.title);
  return { title: pg.title, url, ...trimLead(pg.extract || '', cap) };
}

const leads = new Map();               // title -> { ok: true, lead, at } | { ok: false, at }: this session's memory
let flight = null;                      // the one request in the air: { title, ctrl, timer }

function land(title) { if (flight && flight.title === title) { clearTimeout(flight.timer); flight = null; } }
/** Stop the request in the air, if it is not for `keep`. Called when the card closes or shows another place. */
export function cancelLead(keep = null) {
  if (flight && flight.title !== keep) { clearTimeout(flight.timer); flight.ctrl.abort(); flight = null; }
}
/** The lead of an article: from this session's memory, or by one anonymous request with a timeout. */
export function fetchLead(title, now = Date.now()) {
  const had = leads.get(title);
  if (had && (had.ok || now - had.at < RETRY_MS)) return Promise.resolve(had);
  if (flight && flight.title === title) return flight.done;
  cancelLead();
  const ctrl = new AbortController();
  const mine = { title, ctrl, timedOut: false };
  mine.timer = setTimeout(() => { mine.timedOut = true; ctrl.abort(); }, TIMEOUT_MS);
  mine.done = fetch(leadUrl(title), { credentials: 'omit', referrerPolicy: 'no-referrer', signal: ctrl.signal })
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then((j) => { const v = { ok: true, lead: parseLead(j), at: Date.now() }; leads.set(title, v); land(title); return v; })
    .catch((e) => {
      const closed = e && e.name === 'AbortError' && !mine.timedOut;       // the card went away: not a failure, and not remembered
      land(title);
      if (closed) return null;
      const v = { ok: false, at: Date.now() }; leads.set(title, v); return v;
    });
  flight = mine;
  return mine.done;
}

// ------------------------------------------------------------------------------------------- on the card
const node = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
const link = (href, text, cls) => { const a = node('a', cls, text); a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a; };

function paint(box, art, v) {
  const head = box.querySelector('.sec-h');
  box.replaceChildren(head);
  if (!head.querySelector('.tier')) { const b = node('span', 'tier tier-live', `${TIERS.live.label} · Wikipedia`); b.title = TIERS.live.title; head.append(' ', b); }
  if (!v) { box.append(node('p', 'wiki-state', 'Asking Wikipedia…')); return; }
  if (!v.ok) {
    box.append(node('p', 'wiki-state', 'Wikipedia could not be reached, so no description is shown.'));
    box.append(link(articleUrl(art.title), 'The article on Wikipedia →', 'wiki-more'));
    return;
  }
  const L = v.lead;
  for (const p of L.paras) box.append(node('p', 'prose', p));
  if (!L.paras.length) box.append(node('p', 'wiki-state', 'The article has no introduction to show.'));
  box.append(link(L.url, L.cut ? 'Read the rest of the article on Wikipedia →' : 'Read the article on Wikipedia →', 'wiki-more'));
  const c = node('p', 'wiki-credit');
  c.append('Text from “', link(L.url, L.title), '” by Wikipedia contributors, ', link('https://creativecommons.org/licenses/by-sa/4.0/', 'CC BY-SA 4.0'),
    `. Fetched live from en.wikipedia.org at ${new Date(v.at).toISOString().slice(11, 16)} UTC; it is not the atlas’s own text and the atlas has not checked it.`);
  box.append(c);
  if (box.dataset.caution) box.append(node('div', 'note contested', box.dataset.caution));
}

/**
 * Fill the card's description. `host` holds at most one `.wiki[data-wkey="kind:key"]` placeholder (cards.js);
 * with no host, or none in it, whatever was in the air is stopped. Safe to call on every re-render of a card:
 * a lead already fetched is painted at once, and one on its way is not asked for twice.
 */
export function mountDescription(host) {
  const box = host ? host.querySelector('.wiki[data-wkey]') : null;
  if (!box) { cancelLead(); return; }
  const wkey = box.dataset.wkey, cut = wkey.indexOf(':'), art = articleFor(wkey.slice(0, cut), wkey.slice(cut + 1));
  const still = () => box.isConnected && box.dataset.wkey === wkey;
  if (art === undefined) { cancelLead(); loadTitles().then(() => { if (still()) mountDescription(host); }); return; }
  if (art === null) {
    cancelLead();
    box.querySelector('.wiki-state').textContent = 'No Wikipedia article is matched to this card, so none is shown.';
    return;
  }
  cancelLead(art.title);
  const had = leads.get(art.title);
  paint(box, art, had && (had.ok || Date.now() - had.at < RETRY_MS) ? had : null);
  if (had && (had.ok || Date.now() - had.at < RETRY_MS)) return;
  fetchLead(art.title).then((v) => {
    if (!v) return;
    // the card may have been re-rendered while the request was in the air: paint whichever placeholder is there now
    const cur = host.querySelector('.wiki[data-wkey]');
    if (cur && cur.dataset.wkey === wkey) paint(cur, art, v);
  });
}
