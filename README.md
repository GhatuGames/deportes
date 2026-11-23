# Ghatu Deportes

Titulares deportivos al día, pensados para el celular: **fútbol boliviano** (División Profesional, Bolívar, The Strongest, la Verde…), **copas** (Libertadores, Sudamericana, Champions), **selecciones / Mundial** y **otros deportes**.

👉 https://ghatugames.github.io/deportes/

## Cómo funciona
- `.github/workflows/actualizar.yml` corre **cada hora** (y al hacer push, o a mano con *Actions → Actualizar noticias → Run workflow*).
- `scripts/actualizar.mjs` (Node 20, sin dependencias) lee los RSS públicos de `scripts/fuentes.mjs`, se queda con titular, medio, fecha, un resumen corto (si el feed lo trae) y la miniatura (si el feed la trae), quita duplicados, ordena de la más nueva a la más antigua, clasifica por secciones con palabras clave y escribe `data/noticias.json`.
- Mezcla con las noticias ya publicadas (últimos 5 días), así que si un medio falla en una pasada no se pierde nada.
- La web (`index.html`, `assets/`) es estática: filtros, buscador, "actualizado hace X", modo claro/oscuro.
- **Nunca** se copia el artículo completo: cada tarjeta enlaza a la nota original y muestra el nombre del medio. Los textos e imágenes son de cada medio.
- Sin anuncios, sin cookies, sin estadísticas, sin claves ni secretos.

## Feeds para Facebook (IFTTT)
- `feed.xml`: titulares top de fútbol boliviano y la Verde, solo de medios con enlace directo (El Deber, Opinión, Red Uno, El Diario…). Máx. 2 por pasada, 2 cada 3 h y 8 cada 24 h; nada entre 0:00 y 7:00 (Bolivia). Sin repetir el mismo partido/historia en 24 h.
- `feed-ligero.xml`: los mismos, máx. 1 cada 12 h (≈2 por día ≈ 60 al mes) → plan Starter de IFTTT.
- `feed-gratis.xml`: máx. 1 cada 56 h (≈13 al mes) → entra en los 1.000 créditos mensuales del plan Free de IFTTT (≈70 créditos por publicación).
- `scripts/feed.mjs` guarda lo elegido en `data/feed-estado.json` (publicado con la web) y lo relee en cada pasada: los GUID no cambian nunca, así IFTTT no repite.

## Agregar o quitar un medio
Edita `scripts/fuentes.mjs` (una línea por feed). Prueba local: `node scripts/actualizar.mjs data/noticias.json` y abre `python3 -m http.server` → http://localhost:8000


## Carrusel diario
- Cada día a las 08:00 (Bolivia, `12:00` UTC) `.github/workflows/carrusel.yml` arma un carrusel de 6–8 imágenes (1080×1350) con lo más importante del fútbol, pensado para Facebook e Instagram.
- Lámina de portada, 5 o 6 noticias (prioridad: fútbol boliviano y la Verde, luego Libertadores / Sudamericana y el mundo) y un cierre. Los textos salen solo del titular y el resumen del feed: no se inventan datos, goles ni citas, y no se usan fotos de los medios.
- Se publica en https://ghatugames.github.io/deportes/carrusel/ (láminas de hoy, un ZIP y un archivo de 14 días). Tipografías: Bebas Neue (Dharma Type) y Outfit (Outfit Type Foundry), ambas SIL OFL 1.1, en `scripts/carrusel-fuentes/`.
- Prueba local: `python3 scripts/carrusel.py` (hace falta Pillow).

## Créditos
Tipografía Bebas Neue (Dharma Type), licencia SIL OFL 1.1 (`assets/fuentes/OFL-BebasNeue.txt`).
Hecho por [Ghatu Games](https://ghatugames.github.io/).
