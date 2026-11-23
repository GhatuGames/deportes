// Ghatu Deportes — junta titulares de fuentes RSS públicas y escribe data/noticias.json.
// Solo guarda: titular, medio, fecha, resumen corto (si el feed lo trae), miniatura (si el feed la trae) y el enlace original.
// Sin dependencias (Node 20+). Uso: node scripts/actualizar.mjs [salida.json]
import { writeFileSync, readFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { FUENTES, BLOQUEADOS } from './fuentes.mjs';
import { R } from './reglas.mjs';

const SALIDA = process.argv[2] || 'data/noticias.json';
const PREVIO = process.env.PREVIO_URL || 'https://ghatugames.github.io/deportes/data/noticias.json';
const UA = 'Mozilla/5.0 (compatible; GhatuDeportes/1.0; +https://ghatugames.github.io/deportes/)';
const DIAS = 5, MAX_POR_FUENTE = 45, MAX_TOTAL = 600, LARGO_RESUMEN = 190;
const ahora = Date.now();

/* ---------- utilidades de texto ---------- */
const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', iexcl: '¡', iquest: '¿', laquo: '«', raquo: '»', ldquo: '“', rdquo: '”', lsquo: '‘', rsquo: '’', ndash: '–', mdash: '—', hellip: '…', middot: '·', deg: '°',
  aacute: 'á', eacute: 'é', iacute: 'í', oacute: 'ó', uacute: 'ú', Aacute: 'Á', Eacute: 'É', Iacute: 'Í', Oacute: 'Ó', Uacute: 'Ú', ntilde: 'ñ', Ntilde: 'Ñ', uuml: 'ü', Uuml: 'Ü', ccedil: 'ç', ordm: 'º', ordf: 'ª', euro: '€' };
function decodificar(s) {
  return String(s || '').replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e) => {
    if (e[0] === '#') { const n = e[1].toLowerCase() === 'x' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10); try { return String.fromCodePoint(n); } catch { return ''; } }
    return ENT[e] ?? m;
  });
}
function sinCdata(s) {
  return String(s || '')
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/<!--\[CDATA\[([\s\S]*?)\]\]-->/g, '$1')              // feeds "pasados por un navegador" (El Deber)
    .replace(/&lt;!\[CDATA\[([\s\S]*?)\]\]&gt;?/g, '$1');
}
const limpiar = s => decodificar(decodificar(sinCdata(s)).replace(/<[^>]*>/g, ' ')).replace(/\s+/g, ' ').trim();
function etiqueta(xml, nombres) {
  for (const n of nombres) {
    const r = new RegExp('<' + n + '(?:\\s[^>]*)?>([\\s\\S]*?)</' + n + '>', 'i').exec(xml);
    if (r) return r[1];
  }
  return '';
}
function recortar(s, n) {
  if (s.length <= n) return s;
  const c = s.slice(0, n), i = c.lastIndexOf(' ');
  return (i > n * 0.6 ? c.slice(0, i) : c).replace(/[\s,.;:–—-]+$/, '') + '…';
}
const normal = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

/* ---------- lectura tolerante de RSS / Atom ---------- */
function enlaceDe(it) {
  let l = /<link[^>]*href="([^"]+)"/i.exec(it)?.[1];               // Atom
  if (!l) l = /<link(?:\s[^>]*)?>\s*(?:<!\[CDATA\[)?\s*(https?:\/\/[^\s<\]]+)/i.exec(it)?.[1];   // RSS (también <link> sin cerrar)
  if (!l) { const g = limpiar(etiqueta(it, ['guid', 'id'])); if (/^https?:\/\//.test(g)) l = g; }
  return l ? decodificar(l.trim()) : '';
}
function imagenDe(it, desc) {
  const cands = [];
  for (const m of it.matchAll(/<(media:content|media:thumbnail|enclosure)\b([^>]*)>/gi)) {
    const a = m[2], url = /url="([^"]+)"/i.exec(a)?.[1], tipo = /type="([^"]+)"/i.exec(a)?.[1] || '', medio = /medium="([^"]+)"/i.exec(a)?.[1] || '';
    if (url && (/^image\//i.test(tipo) || medio === 'image' || m[1].toLowerCase() === 'media:thumbnail' || (!tipo && !medio && /\.(jpe?g|png|webp)(\?|$)/i.test(url)))) cands.push(url);
  }
  const enDesc = /<img[^>]+src=["']([^"']+)["']/i.exec(decodificar(sinCdata(desc)))?.[1];
  if (enDesc) cands.push(enDesc);
  const u = cands.map(decodificar).find(x => /^https:\/\//i.test(x));
  return u || '';
}
function fechaDe(it) {
  const t = limpiar(etiqueta(it, ['pubDate', 'pubdate', 'dc:date', 'published', 'updated']));
  const d = Date.parse(t);
  return isNaN(d) ? null : d;
}
function leerFeed(xml, f) {
  const bloques = xml.match(/<item[\s>][\s\S]*?<\/item>/gi) || xml.match(/<entry[\s>][\s\S]*?<\/entry>/gi) || [];
  const out = [];
  for (const it of bloques) {
    let titulo = limpiar(etiqueta(it, ['title']));
    const url = enlaceDe(it), d = fechaDe(it);
    if (!titulo || !/^https?:\/\//.test(url) || !d) continue;
    let medio = f.nombre;
    if (f.tipo === 'gnews') {
      const src = limpiar(etiqueta(it, ['source']));
      if (!src || BLOQUEADOS.test(src) || /[\u3040-\u9fff\uac00-\ud7af\u0400-\u04ff\u0600-\u06ff]/.test(src)) continue;   // solo medios en alfabeto latino
      medio = src;
      const suf = ' - ' + src; if (titulo.endsWith(suf)) titulo = titulo.slice(0, -suf.length).trim();
    }
    const desc = etiqueta(it, ['description', 'summary']);
    let resumen = f.tipo === 'gnews' ? '' : limpiar(desc);
    if (normal(resumen).startsWith(normal(titulo).slice(0, 40))) resumen = resumen.slice(titulo.length).trim();
    if (resumen.length < 25) resumen = '';
    medio = medio.split(/\s+[|–—-]\s+/)[0].replace(/[\s|·:–—-]+$/, '').trim().slice(0, 40) || f.nombre;
    out.push({ t: recortar(titulo, 180), u: url, f: medio, fid: f.id, pais: f.pais, gn: f.tipo === 'gnews' ? 1 : 0, d, s: recortar(resumen, LARGO_RESUMEN), img: f.tipo === 'gnews' ? '' : imagenDe(it, desc), base: f.base || [] });
  }
  return out;
}

/* ---------- categorías por palabras clave ---------- */

function categorias(n) {
  const x = ' ' + normal(n.t + ' ' + n.s) + ' ', c = new Set(n.base);
  const bo = n.pais === 'BO';
  const tagBO = R.clubesBO.test(x) || (bo && R.ambiguosBO.test(x));
  const verde = R.verde.test(x) && (bo || /bolivi/.test(x));
  const otros = R.otros.test(x), fut = R.futbol.test(x) || tagBO || verde || c.has('futbol') || c.has('copas');
  if (bo || tagBO || verde) c.add('bolivia');
  if (verde) c.add('seleccion');
  if (R.copas.test(x)) c.add('copas');
  if (R.mundial.test(x) && !R.noMundial.test(x)) c.add('mundial');
  if (otros && !(R.futbol.test(x) && !/\b(futsal|futbol de salon|talla baja)\b/.test(x) && !/\b(tenis|nba|f1|formula 1|boxeo|ufc|nfl|mlb|ciclismo)\b/.test(x))) { c.add('otros'); c.delete('futbol'); }
  else if (fut && !(tagBO && !R.copas.test(x) && !c.has('mundial'))) c.add('futbol');
  if (!c.has('futbol') && !c.has('otros') && !tagBO && !verde) c.add(fut ? 'futbol' : 'otros');
  if (c.has('otros')) { c.delete('futbol'); c.delete('copas'); c.delete('mundial'); }
  return [...c];
}

/* ---------- deduplicación ---------- */
function claveUrl(u) {
  try {
    const x = new URL(u); x.hash = '';
    [...x.searchParams.keys()].forEach(k => { if (/^(utm_|fbclid|gclid|ref$|oc$|cmp|outputType|output)/i.test(k)) x.searchParams.delete(k); });
    return (x.hostname.replace(/^www\./, '') + x.pathname.replace(/\/+$/, '') + (x.search || '')).toLowerCase();
  } catch { return u; }
}
const claveTitulo = t => normal(t).replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 90);
const puntaje = n => (n.gn ? 0 : 4) + (n.img ? 2 : 0) + (n.s ? 1 : 0);

/* ---------- descarga ---------- */
async function bajar(url, intentos = 3) {
  for (let i = 1; i <= intentos; i++) {
    const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), 20000);
    try {
      const r = await fetch(url, { headers: { 'User-Agent': UA, Accept: 'application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.9, */*;q=0.5' }, signal: ctl.signal, redirect: 'follow' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const txt = await r.text();
      if (!/<(item|entry)[\s>]/i.test(txt)) throw new Error('sin noticias en el feed (' + r.status + ' ' + (r.headers.get('content-type') || '?').split(';')[0] + ' ' + txt.length + 'B: ' + txt.slice(0, 60).replace(/\s+/g, ' ') + ')');
      return txt;
    } catch (e) { if (i === intentos) throw e; await new Promise(z => setTimeout(z, 4000 * i)); }
    finally { clearTimeout(t); }
  }
}

const estado = [], nuevas = [];
// Google Noticias limita pedidos seguidos: esas fuentes van una tras otra; los medios, en paralelo.
const enCola = FUENTES.filter(f => f.tipo === 'gnews'), enParalelo = FUENTES.filter(f => f.tipo !== 'gnews');
async function procesar(f) {
  try {
    const items = leerFeed(await bajar(f.url), f)
      .filter(n => n.d > ahora - DIAS * 864e5 && n.d < ahora + 2 * 36e5)
      .sort((a, b) => b.d - a.d).slice(0, MAX_POR_FUENTE);
    items.forEach(n => nuevas.push(n));
    estado.push({ id: f.id, nombre: f.nombre, ok: items.length > 0, items: items.length, ...(items.length ? {} : { error: 'sin noticias recientes' }) });
  } catch (e) { estado.push({ id: f.id, nombre: f.nombre, ok: false, items: 0, error: String(e.message || e).slice(0, 80) }); }
}
await Promise.all([Promise.all(enParalelo.map(procesar)), (async () => { for (const f of enCola) { await procesar(f); await new Promise(z => setTimeout(z, 2500)); } })()]);

// Noticias anteriores (de la web publicada): así no se pierde nada si un medio falla en esta pasada
let previas = [];
try {
  const r = await fetch(PREVIO + '?t=' + ahora, { headers: { 'User-Agent': UA }, signal: AbortSignal.timeout(15000) });
  if (r.ok) previas = ((await r.json()).noticias || []).map(n => ({ ...n, d: Date.parse(n.d), base: [], pais: n.pais || 'INT' }));
} catch { /* primera vez o sin conexión */ }
if (!previas.length && existsSync(SALIDA)) { try { previas = (JSON.parse(readFileSync(SALIDA, 'utf8')).noticias || []).map(n => ({ ...n, d: Date.parse(n.d), base: [] })); } catch {} }

const porUrl = new Map(), porTitulo = new Map();
for (const n of [...nuevas, ...previas.map(p => ({ ...p, _prev: 1 }))]) {
  if (!n.t || !n.u || !(n.d > ahora - DIAS * 864e5)) continue;
  const ku = claveUrl(n.u), kt = claveTitulo(n.t);
  const otro = porUrl.get(ku) || porTitulo.get(kt);
  if (otro) {
    if (!otro._prev && n._prev) continue;                // lo nuevo manda
    if (puntaje(n) <= puntaje(otro)) continue;
    porUrl.delete(claveUrl(otro.u)); porTitulo.delete(claveTitulo(otro.t));
  }
  porUrl.set(ku, n); porTitulo.set(kt, n);
}
const lista = [...new Set(porUrl.values())].sort((a, b) => b.d - a.d).slice(0, MAX_TOTAL).map(n => ({
  id: createHash('sha1').update(claveUrl(n.u)).digest('hex').slice(0, 10),
  t: n.t, u: n.u, f: n.f, fid: n.fid, pais: n.pais, d: new Date(n.d).toISOString(),
  ...(n.s ? { s: n.s } : {}), ...(n.img ? { img: n.img } : {}),
  c: n._prev && n.c ? n.c : categorias(n)
}));

const okFuentes = estado.filter(e => e.ok).length;
if (!nuevas.length && !previas.length) { console.error('Ninguna fuente respondió y no hay datos anteriores: no se publica.'); process.exit(1); }
estado.sort((a, b) => FUENTES.findIndex(f => f.id === a.id) - FUENTES.findIndex(f => f.id === b.id));
writeFileSync(SALIDA, JSON.stringify({ generado: new Date(ahora).toISOString(), fuentesOk: okFuentes, fuentesTotal: FUENTES.length, fuentes: estado, noticias: lista }));
console.log(`${lista.length} noticias (${nuevas.length} leídas ahora, ${previas.length} anteriores) · fuentes OK ${okFuentes}/${FUENTES.length}`);
for (const e of estado) console.log((e.ok ? '  OK   ' : '  FALLA') + ' ' + e.id.padEnd(12) + ' ' + String(e.items).padStart(3) + (e.error ? '  ' + e.error : ''));
const cnt = {}; lista.forEach(n => n.c.forEach(c => cnt[c] = (cnt[c] || 0) + 1)); console.log('  categorías:', JSON.stringify(cnt));
