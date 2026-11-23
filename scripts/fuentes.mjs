// Fuentes RSS públicas (verificadas con curl). pais: 'BO' = medio boliviano.
// tipo 'gnews' = búsqueda de Google Noticias (el medio real sale en <source>).
// base: etiquetas que se suman siempre (además de las que se detectan por palabras clave).
const GN = q => 'https://news.google.com/rss/search?q=' + encodeURIComponent(q + ' when:3d') + '&hl=es-419&gl=BO&ceid=BO:es-419';
export const FUENTES = [
  // Bolivia (medios bolivianos, secciones de deportes)
  { id: 'eldeber',    nombre: 'El Deber',         pais: 'BO', url: 'https://eldeber.com.bo/rss/deportes' },
  { id: 'opinion',    nombre: 'Opinión',          pais: 'BO', url: 'https://www.opinion.com.bo/rss/deportes' },
  { id: 'reduno',     nombre: 'Red Uno',          pais: 'BO', url: 'https://www.reduno.com.bo/rss/deportes' },
  { id: 'eldiario',   nombre: 'El Diario',        pais: 'BO', url: 'https://www.eldiario.net/portal/category/deportes/feed/' },
  // Bolivia vía Google Noticias (suma Los Tiempos, APG, Unitel, Correo del Sur, etc.)
  { id: 'gn-bo',      nombre: 'Google Noticias',  pais: 'BO', tipo: 'gnews', base: ['bolivia'], url: GN('fútbol boliviano') },
  { id: 'gn-clubes',  nombre: 'Google Noticias',  pais: 'BO', tipo: 'gnews', base: ['bolivia'], url: GN('"The Strongest" OR "Club Bolívar" OR "Always Ready" OR Blooming OR "Oriente Petrolero" OR Wilstermann') },
  { id: 'gn-verde',   nombre: 'Google Noticias',  pais: 'BO', tipo: 'gnews', base: ['bolivia', 'seleccion'], url: GN('"selección boliviana" fútbol') },
  // Internacional (en español)
  { id: 'gn-liber',   nombre: 'Google Noticias',  pais: 'INT', tipo: 'gnews', base: ['futbol', 'copas'], url: GN('"Copa Libertadores" OR "Copa Sudamericana"') },
  { id: 'gn-mundial', nombre: 'Google Noticias',  pais: 'INT', tipo: 'gnews', base: ['futbol'], url: GN('Eliminatorias OR "Mundial 2030" OR "Copa América" OR "fecha FIFA" selección fútbol') },
  { id: 'as',         nombre: 'AS',               pais: 'INT', base: ['futbol'], url: 'https://feeds.as.com/mrss-s/pages/as/site/as.com/section/futbol/subsection/internacional/' },
  { id: 'espn',       nombre: 'ESPN Deportes',    pais: 'INT', url: 'https://espndeportes.espn.com/espn/rss/news' },
  { id: 'infobae',    nombre: 'Infobae',          pais: 'INT', url: 'https://www.infobae.com/arc/outboundfeeds/rss/category/deportes/' },
  { id: 'ole',        nombre: 'Olé',              pais: 'INT', url: 'https://www.ole.com.ar/rss/ultimas-noticias/' },
  { id: 'mundodep',   nombre: 'Mundo Deportivo',  pais: 'INT', base: ['futbol'], url: 'https://www.mundodeportivo.com/rss/futbol' },
  { id: 'depor',      nombre: 'Depor',            pais: 'INT', url: 'https://depor.com/arcio/rss/' },
  { id: 'eltiempo',   nombre: 'El Tiempo',        pais: 'INT', url: 'https://www.eltiempo.com/rss/deportes.xml' },
  { id: 'europapress',nombre: 'Europa Press',     pais: 'INT', url: 'https://www.europapress.es/rss/rss.aspx?ch=00067' },
  { id: '20minutos',  nombre: '20minutos',        pais: 'INT', url: 'https://www.20minutos.es/rss/deportes/' }
];
// Fuentes de Google Noticias que no son medios (se descartan)
export const BLOQUEADOS = /^(instagram|facebook|youtube|x|twitter|tiktok|threads|linkedin|pinterest|reddit|telegram|whatsapp|spotify|apple podcasts)$/i;
