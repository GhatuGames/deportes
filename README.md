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

## Agregar o quitar un medio
Edita `scripts/fuentes.mjs` (una línea por feed). Prueba local: `node scripts/actualizar.mjs data/noticias.json` y abre `python3 -m http.server` → http://localhost:8000

## Créditos
Tipografía Bebas Neue (Dharma Type), licencia SIL OFL 1.1 (`assets/fuentes/OFL-BebasNeue.txt`).
Hecho por [Ghatu Games](https://ghatugames.github.io/).
