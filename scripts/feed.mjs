// Feeds RSS 2.0 curados para Facebook (vía IFTTT). Se corre después de actualizar.mjs.
//   feed.xml          — titulares top de fútbol boliviano / la Verde: máx. 2 nuevos por pasada y 8 por día.
//   feed-ligero.xml   — el mismo material, máx. 1 cada 12 h (≈2 por día), para planes de IFTTT con pocos créditos.
//   Ritmo: máx. 2 por pasada, máx. 2 cada 3 h, máx. 8 cada 24 h y nada entre las 0:00 y las 7:00 (hora de Bolivia).
// Las elecciones se guardan en data/feed-estado.json (publicado junto a la web) para que nunca cambien:
// GUID estable por noticia ⇒ IFTTT no vuelve a publicar nada.
// Uso: node scripts/feed.mjs <noticias.json> <carpeta del sitio>
import { readFileSync, writeFileSync } from 'node:fs';
import { R, normal } from './reglas.mjs';

const [ENTRADA = 'data/noticias.json', SITIO = '.'] = process.argv.slice(2);
const BASE = 'https://ghatugames.github.io/deportes/';
const ESTADO_URL = process.env.FEED_ESTADO_URL || BASE + 'data/feed-estado.json';
const UA = 'Mozilla/5.0 (compatible; GhatuDeportes/1.0; +' + BASE + ')';
const CFG = { porPasada: 2, porVentana: 2, ventanaH: 3, porDia: 8, edadMaxH: 8, silencio: [0, 7], ligeroCadaH: 12, guardarDias: 10, enFeed: 15 };
const ahora = process.env.FEED_AHORA ? Date.parse(process.env.FEED_AHORA) : Date.now(), H = 36e5;   // FEED_AHORA: solo para pruebas

/* ---------- estado anterior (si no se puede leer, NO se publica: evita repetir) ---------- */
let estado = { version: 1, elegidas: [] };
{
  let leido = false;
  for (let i = 1; i <= 3 && !leido; i++) {
    try {
      const r = await fetch(ESTADO_URL + '?t=' + ahora, { headers: { 'User-Agent': UA }, signal: AbortSignal.timeout(15000) });
      if (r.status === 404) { console.log('Feed: primera vez (no hay estado anterior).'); leido = true; break; }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const j = await r.json(); if (!Array.isArray(j.elegidas)) throw new Error('estado inválido');
      estado = j; leido = true;
    } catch (e) { console.log('Feed: no se pudo leer el estado (' + e.message + '), intento ' + i); await new Promise(z => setTimeout(z, 3000 * i)); }
  }
  if (!leido) { console.error('Feed: sin estado anterior confiable; se cancela para no repetir publicaciones.'); process.exit(2); }
}
estado.elegidas = estado.elegidas.filter(e => Date.parse(e.elegida) > ahora - CFG.guardarDias * 864e5);
const yaGuid = new Set(estado.elegidas.map(e => e.guid));

/* ---------- candidatas ---------- */
const datos = JSON.parse(readFileSync(ENTRADA, 'utf8'));
const clubes = t => { const x = ' ' + normal(t) + ' ', s = new Set(); for (const m of x.matchAll(new RegExp(R.clubesBO.source, 'g'))) s.add(m[1].replace(/^club /, '')); return s; };
const palabras = t => new Set(normal(t).replace(/[^a-z0-9 ]+/g, ' ').split(' ').filter(w => w.length > 3));
const parecido = (a, b) => { const A = palabras(a), B = palabras(b); let k = 0; A.forEach(w => { if (B.has(w)) k++; }); return k / Math.max(1, Math.min(A.size, B.size)); };
function mismaHistoria(n, e) {
  if (parecido(n.t, e.t) >= 0.5) return true;
  const a = clubes(n.t), b = clubes(e.t);
  if (a.size >= 2 && b.size >= 2 && [...a].filter(x => b.has(x)).length >= 2) return true;   // mismo partido
  return false;
}
const esBolivia = n => { const x = ' ' + normal(n.t + ' ' + (n.s || '')) + ' '; return R.clubesBO.test(x) || (R.verde.test(x) && (n.pais === 'BO' || /bolivi/.test(x))) || (n.pais === 'BO' && R.ambiguosBO.test(x) && R.futbol.test(x)); };
const esVerde = n => (n.c || []).includes('seleccion');
const directa = n => /^https:\/\//.test(n.u) && !/(^|\.)news\.google\.com\//.test(n.u.replace(/^https:\/\//, ''));
const candidatas = (datos.noticias || []).filter(n => directa(n) && esBolivia(n))
  .filter(n => !/\b(en vivo|minuto a minuto|ver en vivo|donde ver|dónde ver|a que hora|a qué hora|hora y donde)\b/i.test(n.t))
  .filter(n => Date.parse(n.d) > ahora - CFG.edadMaxH * H && Date.parse(n.d) <= ahora + 10 * 60e3)
  .filter(n => !yaGuid.has('ghatu-deportes-' + n.id));
const puntaje = n => (esVerde(n) ? 3 : 0) + (n.img ? 2 : 0) + (n.s ? 1 : 0) + (n.pais === 'BO' ? 1 : 0) - (ahora - Date.parse(n.d)) / (4 * H);

/* ---------- elección de esta pasada ---------- */
const horaBO = (new Date(ahora - 4 * H)).getUTCHours();      // Bolivia: UTC-4 todo el año
const enSilencio = !process.env.FEED_IGNORAR_SILENCIO && horaBO >= CFG.silencio[0] && horaBO < CFG.silencio[1];
const ult24 = estado.elegidas.filter(e => Date.parse(e.elegida) > ahora - 24 * H);
const enVentana = estado.elegidas.filter(e => Date.parse(e.elegida) > ahora - CFG.ventanaH * H).length;
let cupo = enSilencio ? 0 : Math.max(0, Math.min(CFG.porPasada, CFG.porVentana - enVentana, CFG.porDia - ult24.length));
const nuevas = [];
for (const n of candidatas.sort((a, b) => puntaje(b) - puntaje(a))) {
  if (cupo <= 0) break;
  if ([...ult24, ...nuevas].some(e => mismaHistoria(n, e))) continue;
  if (nuevas.some(e => e.f === n.f)) continue;                 // variedad de medios en la misma pasada
  nuevas.push(n); cupo--;
}

/* ---------- imagen: tamaño y tipo reales para <enclosure> ---------- */
async function infoImagen(url) {
  if (!url) return null;
  // HEAD → GET de 1 byte → GET completo (algunas CDN redimensionan al vuelo y no informan el tamaño)
  for (const metodo of ['HEAD', 'RANGO', 'GET']) {
    try {
      const r = await fetch(url, { method: metodo === 'HEAD' ? 'HEAD' : 'GET', headers: { 'User-Agent': UA, ...(metodo === 'RANGO' ? { Range: 'bytes=0-0' } : {}) }, signal: AbortSignal.timeout(15000), redirect: 'follow' });
      if (!r.ok) continue;
      const tipo = (r.headers.get('content-type') || '').split(';')[0].trim();
      if (!/^image\/(jpeg|png|webp|gif)$/.test(tipo)) { try { await r.body?.cancel(); } catch {} return null; }
      let largo = 0;
      if (metodo === 'GET') { const b = await r.arrayBuffer(); largo = b.byteLength; }
      else { largo = metodo === 'HEAD' ? +r.headers.get('content-length') : +(/\/(\d+)$/.exec(r.headers.get('content-range') || '')?.[1] || 0); try { await r.body?.cancel(); } catch {} }
      if (largo > 0) return { url, tipo, largo };
    } catch { /* probar el siguiente método */ }
  }
  return null;
}
const ultimaLigera = estado.elegidas.filter(e => e.ligero).map(e => Date.parse(e.elegida)).sort((a, b) => b - a)[0] || 0;
let ligeroLibre = ahora - ultimaLigera >= CFG.ligeroCadaH * H;
for (const n of nuevas.sort((a, b) => puntaje(b) - puntaje(a))) {
  const img = await infoImagen(n.img);
  estado.elegidas.push({ guid: 'ghatu-deportes-' + n.id, id: n.id, t: n.t, u: n.u, f: n.f, d: n.d, s: n.s || '', img: img || null, verde: esVerde(n), ligero: ligeroLibre, elegida: new Date(ahora).toISOString() });
  ligeroLibre = false;
}

/* ---------- escribir RSS 2.0 ---------- */
const x = s => String(s ?? '').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffe\uffff]/g, '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const rfc822 = iso => new Date(iso).toUTCString().replace('GMT', '+0000');
const recortar = (s, n) => s.length <= n ? s : s.slice(0, s.lastIndexOf(' ', n) > n * 0.6 ? s.lastIndexOf(' ', n) : n).replace(/[\s,.;:–—-]+$/, '') + '…';
function rss(nombre, titulo, desc, items) {
  const cuerpo = items.map(e => {
    const texto = (e.s ? recortar(e.s, 220) + ' ' : '') + 'Fuente: ' + e.f + '.';
    return `    <item>
      <title>${x(e.t)}</title>
      <link>${x(e.u)}</link>
      <guid isPermaLink="false">${x(e.guid)}</guid>
      <pubDate>${rfc822(e.d)}</pubDate>
      <dc:creator>${x(e.f)}</dc:creator>
      <category>${e.verde ? 'La Verde' : 'Fútbol boliviano'}</category>
      <description>${x(texto)}</description>${e.img ? `
      <enclosure url="${x(e.img.url)}" length="${e.img.largo}" type="${x(e.img.tipo)}"/>` : ''}
    </item>`; }).join('\n');
  const ultima = items[0] ? rfc822(items[0].elegida) : rfc822(new Date(ahora).toISOString());
  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>${x(titulo)}</title>
    <link>${BASE}</link>
    <atom:link href="${BASE}${nombre}" rel="self" type="application/rss+xml"/>
    <description>${x(desc)}</description>
    <language>es-bo</language>
    <lastBuildDate>${ultima}</lastBuildDate>
    <ttl>60</ttl>
    <generator>Ghatu Deportes (scripts/feed.mjs)</generator>
    <image>
      <url>${BASE}assets/icono-144.png</url>
      <title>${x(titulo)}</title>
      <link>${BASE}</link>
      <width>144</width>
      <height>144</height>
    </image>
${cuerpo}
  </channel>
</rss>
`;
}
const orden = (a, b) => Date.parse(b.d) - Date.parse(a.d) || Date.parse(b.elegida) - Date.parse(a.elegida);
const todas = [...estado.elegidas].sort(orden).slice(0, CFG.enFeed);
const ligeras = estado.elegidas.filter(e => e.ligero).sort(orden).slice(0, 10);
writeFileSync(SITIO + '/feed.xml', rss('feed.xml', 'Ghatu Deportes · Fútbol boliviano', 'Lo más importante del fútbol boliviano y la Verde, elegido de medios bolivianos. Cada nota enlaza al medio original.', todas));
writeFileSync(SITIO + '/feed-ligero.xml', rss('feed-ligero.xml', 'Ghatu Deportes · Lo top del día', 'Hasta 2 titulares por día del fútbol boliviano y la Verde, con enlace al medio original.', ligeras));
estado.actualizado = new Date(ahora).toISOString(); estado.reglas = CFG;
writeFileSync(SITIO + '/data/feed-estado.json', JSON.stringify(estado));
console.log(`Feed: ${candidatas.length} candidatas, ${nuevas.length} nuevas${enSilencio ? ' (horario de silencio)' : ''}; 24 h: ${ult24.length + nuevas.length}/${CFG.porDia}; feed.xml ${todas.length} ítems, feed-ligero.xml ${ligeras.length}.`);
nuevas.forEach(n => console.log('  + ' + n.f + ' · ' + n.t));
