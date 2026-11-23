/* Ghatu Deportes — muestra data/noticias.json (lo genera cada hora scripts/actualizar.mjs en GitHub Actions). */
(function () {
  'use strict';
  var $ = function (s) { return document.querySelector(s); };
  var CATS = [['', 'Todas'], ['bolivia', 'Bolivia'], ['seleccion', 'La Verde'], ['copas', 'Copas'], ['mundial', 'Mundial y selecciones'], ['futbol', 'Fútbol mundial'], ['otros', 'Otros deportes']];
  var NOMBRE_CAT = { bolivia: 'Bolivia', seleccion: 'La Verde', copas: 'Copas', mundial: 'Selecciones', futbol: 'Fútbol', otros: 'Otros deportes' };
  var TANDA = 24, VIEJO_H = 4;
  var datos = null, cat = '', q = '', cuantas = TANDA, cargando = false, ultimaCarga = 0;
  var lista = $('#lista'), estado = $('#estado'), resumen = $('#resumen'), mas = $('#mas'), buscar = $('#buscar'), limpiar = $('#limpiar');

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function normal(s) { return String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }
  function urlSegura(u) { return /^https?:\/\//i.test(u || '') ? u : ''; }
  function hace(ms) {
    var m = Math.max(0, Math.round((Date.now() - ms) / 60000));
    if (m < 1) return 'hace instantes'; if (m < 60) return 'hace ' + m + ' min';
    var h = Math.round(m / 60); if (h < 24) return 'hace ' + h + ' h';
    var d = Math.round(h / 24); return d === 1 ? 'ayer' : 'hace ' + d + ' días';
  }
  var FMT = null; try { FMT = new Intl.DateTimeFormat('es-BO', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }); } catch (e) {}
  function cuando(iso) { var t = Date.parse(iso); if (isNaN(t)) return ''; return (Date.now() - t < 864e5) ? hace(t) : (FMT ? FMT.format(new Date(t)) : new Date(t).toLocaleString()); }
  function resaltar(texto) {
    var t = esc(texto); if (!q) return t;
    var palabras = q.split(' ').filter(function (w) { return w.length > 1; }); if (!palabras.length) return t;
    // marca coincidencias ignorando tildes: se busca sobre la versión normalizada, posición a posición
    var n = normal(t), marcas = [];
    palabras.forEach(function (w) { var i = 0, k; while ((k = n.indexOf(w, i)) > -1) { marcas.push([k, k + w.length]); i = k + w.length; } });
    if (!marcas.length || n.length !== t.length) return t;
    marcas.sort(function (a, b) { return a[0] - b[0]; });
    var out = '', pos = 0;
    marcas.forEach(function (m) { if (m[0] < pos) return; var seg = t.slice(m[0], m[1]); if (/[&;]/.test(seg)) return; out += t.slice(pos, m[0]) + '<mark>' + seg + '</mark>'; pos = m[1]; });
    return out + t.slice(pos);
  }

  /* pestañas */
  function pintarPestanas() {
    var cuenta = {}; (datos ? datos.noticias : []).forEach(function (n) { (n.c || []).forEach(function (c) { cuenta[c] = (cuenta[c] || 0) + 1; }); });
    $('#pestanas').innerHTML = CATS.map(function (c) {
      var n = c[0] ? (cuenta[c[0]] || 0) : (datos ? datos.noticias.length : 0);
      return '<button type="button" data-c="' + c[0] + '" aria-pressed="' + (c[0] === cat) + '">' + c[1] + (datos ? ' <small>' + n + '</small>' : '') + '</button>';
    }).join('');
  }
  $('#pestanas').addEventListener('click', function (e) {
    var b = e.target.closest('button[data-c]'); if (!b) return;
    cat = b.getAttribute('data-c'); cuantas = TANDA;
    try { history.replaceState(null, '', cat ? '#' + cat : location.pathname + location.search); } catch (er) {}
    pintarPestanas(); pintar();
    var nb = $('#pestanas button[aria-pressed=true]'); if (nb && nb.scrollIntoView) nb.scrollIntoView({ block: 'nearest', inline: 'center' });
  });

  /* tarjetas */
  function tarjeta(n, portada) {
    var u = urlSegura(n.u); if (!u) return '';
    var img = urlSegura(n.img);
    var cats = (n.c || []).filter(function (c) { return c !== 'futbol' || (n.c || []).length === 1; }).slice(0, 2);
    return '<a class="nota' + (portada ? ' portada' : '') + (img ? '' : ' sin-img') + '" href="' + esc(u) + '" target="_blank" rel="noopener noreferrer nofollow">' +
      (img ? '<div class="img"><img src="' + esc(img) + '" alt="" loading="' + (portada ? 'eager' : 'lazy') + '" decoding="async" referrerpolicy="no-referrer"' + (portada ? ' fetchpriority="high"' : '') + '></div>' : '') +
      '<div class="txt"><div class="meta"><span class="medio">' + esc(n.f) + '</span><span>·</span><time datetime="' + esc(n.d) + '">' + cuando(n.d) + '</time>' +
      cats.map(function (c) { return '<span class="cat ' + esc(c) + '">' + esc(NOMBRE_CAT[c] || c) + '</span>'; }).join('') + '</div>' +
      '<h2>' + resaltar(n.t) + '</h2>' + (n.s ? '<p>' + resaltar(n.s) + '</p>' : '') +
      '<span class="ir">Leer en ' + esc(n.f) + '</span></div></a>';
  }
  function filtradas() {
    var palabras = q ? q.split(' ').filter(Boolean) : [];
    return datos.noticias.filter(function (n) {
      if (cat && (n.c || []).indexOf(cat) < 0) return false;
      if (!palabras.length) return true;
      var h = n._h || (n._h = normal(n.t + ' ' + (n.s || '') + ' ' + n.f));
      return palabras.every(function (w) { return h.indexOf(w) > -1; });
    });
  }
  function pintarTira() {
    var t = $('#tira'), bo = (!cat && !q && datos) ? datos.noticias.filter(function (n) { return (n.c || []).indexOf('bolivia') > -1 && urlSegura(n.u); }).slice(0, 6) : [];
    t.hidden = bo.length < 3; if (t.hidden) return;
    $('#tira-lista').innerHTML = bo.map(function (n) { return '<a class="mini" href="' + esc(n.u) + '" target="_blank" rel="noopener noreferrer nofollow"><b>' + esc(n.t) + '</b><small><strong>' + esc(n.f) + '</strong> · <time datetime="' + esc(n.d) + '">' + cuando(n.d) + '</time></small></a>'; }).join('');
  }
  $('#tira').addEventListener('click', function (e) { var b = e.target.closest('[data-ir]'); if (b) { var x = $('#pestanas button[data-c="' + b.getAttribute('data-ir') + '"]'); if (x) x.click(); } });
  function pintar() {
    if (!datos) return;
    pintarTira();
    var sel = filtradas(), vis = sel.slice(0, cuantas);
    lista.setAttribute('aria-busy', 'false');
    if (!sel.length) {
      lista.innerHTML = '<div class="aviso"><b>' + (q ? 'Sin resultados para «' + esc(buscar.value.trim()) + '»' : 'Por ahora no hay noticias en esta sección') + '</b>' + (q || cat ? 'Prueba con otra palabra o mira todas las noticias.' : 'Vuelve en un rato.') +
        ((q || cat) ? '<br><button type="button" class="boton primario" id="ver-todas">Ver todas las noticias</button>' : '') + '</div>';
      mas.hidden = true; resumen.textContent = ''; return;
    }
    var portada = !q && !!urlSegura(vis[0].img);       // la más nueva sale grande si trae foto (el orden no cambia)
    lista.innerHTML = vis.map(function (n, i) { return tarjeta(n, portada && i === 0); }).join('');
    mas.hidden = sel.length <= cuantas;
    mas.textContent = 'Ver más noticias (' + (sel.length - vis.length) + ')';
    resumen.textContent = (q ? sel.length + (sel.length === 1 ? ' resultado' : ' resultados') : sel.length + ' noticias') + (cat ? ' en ' + CATS.filter(function (c) { return c[0] === cat; })[0][1] : '') + ' · de la más nueva a la más antigua';
  }
  lista.addEventListener('click', function (e) { if (e.target && e.target.id === 'ver-todas') { cat = ''; q = ''; buscar.value = ''; limpiar.hidden = true; cuantas = TANDA; pintarPestanas(); pintar(); } });
  // imagen rota: se quita sin mover el resto
  lista.addEventListener('error', function (e) {
    var im = e.target; if (!im || im.tagName !== 'IMG') return;
    var a = im.closest('.nota'), box = im.parentNode; if (box) box.remove(); if (a) { a.classList.add('sin-img'); }
  }, true);
  mas.addEventListener('click', function () { cuantas += TANDA; pintar(); });

  /* búsqueda */
  var tBus;
  buscar.addEventListener('input', function () {
    limpiar.hidden = !buscar.value; clearTimeout(tBus);
    tBus = setTimeout(function () { q = normal(buscar.value.trim()).replace(/\s+/g, ' '); cuantas = TANDA; pintar(); }, 160);
  });
  buscar.addEventListener('keydown', function (e) { if (e.key === 'Enter') { buscar.blur(); } });
  limpiar.addEventListener('click', function () { buscar.value = ''; limpiar.hidden = true; q = ''; cuantas = TANDA; pintar(); buscar.focus(); });

  /* estado "actualizado hace X" */
  function pintarEstado() {
    if (!datos) return;
    var g = Date.parse(datos.generado), viejo = Date.now() - g > VIEJO_H * 36e5;
    estado.className = 'estado ' + (viejo ? 'viejo' : 'ok');
    estado.querySelector('span').innerHTML = '<span class="largo">Actualizado </span>' + esc(hace(g));
    estado.title = (viejo ? 'Las noticias pueden estar desactualizadas. ' : '') + 'Última actualización: ' + (FMT ? FMT.format(new Date(g)) : new Date(g).toLocaleString()) + ' · ' + datos.fuentesOk + ' de ' + datos.fuentesTotal + ' medios respondieron';
    [].forEach.call(document.querySelectorAll('#lista time, #tira time'), function (t) { t.textContent = cuando(t.getAttribute('datetime')); });
  }
  function pintarFuentes() {
    var vistos = {}, items = [];
    (datos.fuentes || []).forEach(function (f) {
      var k = f.nombre === 'Google Noticias' ? 'Google Noticias (búsquedas)' : f.nombre;
      if (!vistos[k]) { vistos[k] = { n: k, ok: false, items: 0 }; items.push(vistos[k]); }
      vistos[k].ok = vistos[k].ok || f.ok; vistos[k].items += f.items;
    });
    $('#fuentes').innerHTML = items.map(function (f) { return '<li class="' + (f.ok ? '' : 'mal') + '"><i></i>' + esc(f.n) + '<small>' + (f.ok ? f.items + ' titulares' : 'sin respuesta') + '</small></li>'; }).join('');
  }

  /* carga */
  function cargar(silencioso) {
    if (cargando) return; cargando = true;
    var ctl = window.AbortController ? new AbortController() : null, t = setTimeout(function () { if (ctl) ctl.abort(); }, 15000);
    fetch('data/noticias.json', { cache: silencioso ? 'no-cache' : 'default', signal: ctl ? ctl.signal : undefined })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (j) {
        if (!j || !Array.isArray(j.noticias)) throw new Error('datos');
        var nuevo = !datos || j.generado !== datos.generado;
        datos = j; ultimaCarga = Date.now();
        if (nuevo) { pintarPestanas(); pintar(); pintarFuentes(); }
        pintarEstado();
      })
      .catch(function () {
        if (datos) { pintarEstado(); return; }          // ya hay noticias en pantalla: se dejan
        estado.className = 'estado error'; estado.querySelector('span').textContent = 'Sin conexión';
        lista.setAttribute('aria-busy', 'false');
        lista.innerHTML = '<div class="aviso"><b>No pudimos cargar las noticias</b>Revisa tu conexión a internet e inténtalo de nuevo.<br><button type="button" class="boton primario" id="reintentar">Reintentar</button></div>';
        var b = $('#reintentar'); if (b) b.addEventListener('click', function () { lista.innerHTML = '<div class="esqueleto"></div><div class="esqueleto"></div>'; cargar(false); });
      })
      .then(function () { clearTimeout(t); cargando = false; });
  }
  var h = (location.hash || '').slice(1); if (CATS.some(function (c) { return c[0] && c[0] === h; })) cat = h;
  pintarPestanas(); cargar(false);
  setInterval(pintarEstado, 60000);
  // al volver a la pestaña (o cada 15 min con la página abierta) se buscan noticias nuevas
  document.addEventListener('visibilitychange', function () { if (!document.hidden && Date.now() - ultimaCarga > 10 * 60000) cargar(true); });
  setInterval(function () { if (!document.hidden) cargar(true); }, 15 * 60000);

  /* tema claro / oscuro */
  var raiz = document.documentElement, bt = $('#tema');
  function esClaro() { var t = raiz.getAttribute('data-tema'); return t ? t === 'claro' : !!(window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches); }
  function etiquetaTema() { bt.setAttribute('aria-label', esClaro() ? 'Cambiar a modo oscuro' : 'Cambiar a modo claro'); }
  bt.addEventListener('click', function () { var t = esClaro() ? 'oscuro' : 'claro'; raiz.setAttribute('data-tema', t); try { localStorage.setItem('gd_tema', t); } catch (e) {} etiquetaTema(); });
  etiquetaTema();
})();
