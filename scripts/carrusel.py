#!/usr/bin/env python3
# Ghatu Deportes — carrusel diario de fútbol (1080×1350) para Facebook e Instagram.
# Solo usa titular y resumen del feed: no inventa datos, goles ni citas, y no usa fotos de los medios.
# Uso: python3 scripts/carrusel.py [--json RUTA] [--salida DIR] [--fecha YYYY-MM-DD]
from __future__ import annotations

import argparse, io, json, math, os, re, sys, unicodedata, zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
FUENTES = AQUI / "carrusel-fuentes"
ICONO = RAIZ / "assets" / "icono-512.png"
SELLO = RAIZ / "assets" / "ghatu-128.webp"
URL_WEB = "https://ghatugames.github.io/deportes/"
URL_CARRUSEL = URL_WEB + "carrusel/"
URL_JSON = URL_WEB + "data/noticias.json"
UA = "Mozilla/5.0 (compatible; GhatuDeportes/1.0; +https://ghatugames.github.io/deportes/)"
TZ_BO = timezone(timedelta(hours=-4))  # America/La_Paz, sin horario de verano

# Lienzo de publicación (retratos de Instagram/Facebook). Se dibuja al doble y se reduce.
ANCHO, ALTO = 1080, 1350
ESCALA = 2
W, H = ANCHO * ESCALA, ALTO * ESCALA
M = 84 * ESCALA  # margen lateral
ARCHIVO_DIAS = 14
MIN_NOTICIAS, MAX_NOTICIAS = 5, 6

FONDO = (11, 15, 20)
PANEL = (18, 24, 32)
TEXTO = (238, 242, 246)
SUAVE = (147, 161, 177)
ACENTO = (22, 193, 114)
ACENTO2 = (15, 163, 95)
ROJO = (230, 57, 70)
AMARILLO = (255, 210, 63)
BLANCO = (255, 255, 255)
OSCURO = (4, 19, 11)

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

# Clasificación (texto ya sin tildes). Independiente de scripts/reglas.mjs a propósito.
R_CLUBES = re.compile(
    r"\b(club bolivar|bolivar|the strongest|always ready|blooming|oriente petrolero|"
    r"wilstermann|real potosi|nacional potosi|guabira|royal pari|universitario de vinto|"
    r"real tomayapo|tomayapo|gv san jose|independiente petrolero|academia del balompie|"
    r"fbf|federacion boliviana de futbol|division profesional|futbol boliviano|"
    r"liga boliviana|todos contra todos|primera a|san antonio|siempre ready)\b"
)
R_VERDE = re.compile(
    r"\b(seleccion boliviana|la verde|seleccion nacional de bolivia|"
    r"bolivia (vs\.?|ante|frente a|contra|enfrenta|empata|gana|pierde|cae|vence|golea|derrota)|"
    r"(vs\.?|ante|frente a|contra) bolivia|hinchas bolivianos)\b"
)
R_COPAS = re.compile(
    r"\b(libertadores|sudamericana|champions|liga de campeones|europa league|"
    r"conference league|mundial de clubes|recopa|concachampions|conmebol)\b"
)
R_FUTBOL = re.compile(
    r"\b(futbol|gol|goles|golazo|liga|laliga|premier league|serie a|bundesliga|ligue 1|"
    r"champions|libertadores|sudamericana|real madrid|barcelona|manchester|liverpool|"
    r"arsenal|chelsea|psg|bayern|juventus|inter|milan|boca|river|flamengo|palmeiras|"
    r"messi|cristiano|mbappe|haaland|vinicius|lamine|seleccion|mundial|eliminatoria|"
    r"fichaje|var|hincha|hinchas|estadio|clasico|liga mx|conmebol|uefa|fifa|"
    r"entrenador|tecnico|delantero|arquero|portero|penal)\b"
)
R_OTROS = re.compile(
    r"\b(tenis|atp|wta|nba|basquet|baloncesto|formula 1|\bf1\b|motogp|nascar|ciclismo|"
    r"atletismo|boxeo|ufc|mma|voley|voleibol|nfl|super bowl|mlb|beisbol|golf|natacion|"
    r"rally|dakar|ajedrez|olimpiad|futsal|handball|balonmano|rugby|hockey|padel|"
    r"automovilismo|motociclismo|wrestling|wwe|esports|futbol americano)\b"
)
R_EN_VIVO = re.compile(
    r"\b(en vivo|minuto a minuto|ver en vivo|donde ver|donde verlo|a que hora|alineaciones|"
    r"asi forman|hora y donde|formaciones)\b"
)


def normal(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower()


def fecha_texto(dt: datetime) -> str:
    return f"{DIAS[dt.weekday()]} {dt.day} de {MESES[dt.month - 1]} de {dt.year}"


def cargar_json(path_local: Path, url: str) -> dict[str, Any]:
    errores = []
    try:
        req = Request(url, headers={"User-Agent": UA})
        with urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        if isinstance(data, dict) and data.get("noticias"):
            return data
        errores.append("JSON remoto vacío")
    except Exception as e:
        errores.append(f"remoto: {e}")
    if path_local.exists():
        data = json.loads(path_local.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("noticias"):
            return data
        errores.append("JSON local vacío")
    raise SystemExit("No pude leer las noticias (" + "; ".join(errores) + ")")


def texto_plano(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = unicodedata.normalize("NFC", s)
    s = s.replace("\u00a0", " ").replace("\u2026", "…")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def titular_limpio(t: str, medio: str = "") -> str:
    t = texto_plano(t)
    t = re.sub(r"\s*[\|–—-]\s*(en vivo|minuto a minuto)\s*$", "", t, flags=re.I)
    if medio:
        suf = " - " + medio
        if t.endswith(suf):
            t = t[: -len(suf)].strip()
    t = re.sub(r"\s+", " ", t).strip(" .")
    # Recapitaliza nombres propios si el titular viene en MAYÚSCULAS o quedó en minúsculas
    nombres = (
        "Always Ready", "The Strongest", "San Antonio", "Oriente Petrolero",
        "Independiente Petrolero", "Independiente", "La Verde", "Real Potosí",
        "Nacional Potosí", "Bolívar", "Blooming", "Wilstermann", "Boca Juniors",
        "Atlético Mineiro", "Santa Cruz", "Cochabamba", "La Paz", "Bolivia",
        "México", "Mexico", "Francia", "Barranquilla", "Potosí", "Rabat",
        "Sudán", "Copa Sudamericana", "Copa Libertadores", "Sudamericana", "Libertadores",
    )
    def recap(t0: str) -> str:
        out = t0
        for nom in nombres:
            out = re.sub(r"\b" + re.escape(nom) + r"\b", nom, out, flags=re.I)
        return out
    if t.isupper() and len(t) > 8:
        t = t.capitalize()
        t = recap(t)
        t = t[0].upper() + t[1:] if t else t
    else:
        t = recap(t)
    return t


def primeras_frases(s: str, max_car: int = 220) -> str:
    s = texto_plano(s)
    if not s:
        return ""
    partes = re.split(r"(?<=[\.\!\?…])\s+", s)
    acc = ""
    for p in partes:
        if not p:
            continue
        cand = (acc + " " + p).strip() if acc else p
        if len(cand) <= max_car or not acc:
            acc = cand
        else:
            break
        if len(acc) >= max_car * 0.7 and acc[-1] in ".!?…":
            break
    if len(acc) > max_car:
        c = acc[:max_car]
        i = c.rfind(" ")
        acc = (c[:i] if i > max_car * 0.6 else c).rstrip(" ,;:–—-") + "…"
    return acc


def cortar_colgado(s: str) -> str:
    """Evita cortar en 'todos contra…' u otras palabras colgadas del feed."""
    if not s:
        return s
    ell = s.endswith("…") or s.endswith("...")
    t = re.sub(r"[.…]+$", "", s).rstrip(" ,;:–—-")
    colgados = {
        "el", "la", "los", "las", "de", "del", "al", "un", "una", "y", "o", "u",
        "en", "por", "para", "con", "contra", "sobre", "ante", "tras", "como",
        "su", "sus", "a", "que", "se", "lo", "le", "les", "todos", "todas",
        "este", "esta", "estos", "estas", "hacia", "siguiente", "siguientes", "primera", "segunda", "tercera", "cuarta",
    }
    words = t.split()
    while words and normal(re.sub(r"[^a-záéíóúüñ]+$", "", words[-1], flags=re.I)) in colgados:
        words.pop()
        ell = True
    if not words:
        return s
    t = " ".join(words)
    # Si la última frase quedó cortada (coma final, etc.) y hay una frase completa antes, se deja solo esa.
    if re.search(r"[,:;]\s*\.?$", t) or t.endswith(","):
        partes = re.split(r"(?<=[\.\!\?])\s+", t.rstrip(" ,;:."))
        if len(partes) > 1:
            t = " ".join(partes[:-1]).rstrip()
    if ell:
        if t and t[-1] not in ".!?":
            t += "."
    elif t and t[-1] not in ".!?…":
        t += "."
    return t


def solapamiento(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z0-9áéíóúüñ]{3,}", normal(a)))
    tb = set(re.findall(r"[a-z0-9áéíóúüñ]{3,}", normal(b)))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def limpiar_entrada(s: str) -> str:
    s = texto_plano(s)
    # Quita datelines tipo "BARRANQUILLA.-" o "SANTA CRUZ.-"
    s = re.sub(r"^[A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ .]{2,30}\.\s*[-–—]*\s*", "", s)
    # "2026 Con una actuación" (falta el punto entre año y la frase siguiente)
    s = re.sub(r"(\b20\d{2})\s+([A-ZÁÉÍÓÚÜÑ])", r"\1. \2", s)
    return s


def resumir(titulo: str, snippet: str) -> str:
    """Resumen corto, solo con datos que ya están en el titular o el snippet."""
    tit = limpiar_entrada(titulo)
    sn = primeras_frases(limpiar_entrada(snippet), 230)
    if sn:
        # Si el snippet repite el titular, nos quedamos con lo que añade.
        if solapamiento(sn, tit) > 0.85 or normal(sn).startswith(normal(tit)[:40]):
            resto = sn
            # recorta un prefijo muy parecido
            for n in range(min(len(tit.split()), 8), 2, -1):
                pref = " ".join(tit.split()[:n])
                if normal(sn).startswith(normal(pref)):
                    resto = sn[len(pref):].lstrip(" :-–,.")
                    break
            if resto and len(resto) >= 40:
                sn = resto[0].upper() + resto[1:] if resto else sn
        # Reescrituras mínimas, sin tocar cifras ni nombres
        sn = re.sub(r"(?i)\bse impuso por\b", "ganó", sn)
        sn = re.sub(r"(?i)\bse impuso\b", "ganó", sn)
        sn = cortar_colgado(sn)
        if not sn.endswith((".", "…", "!", "?")):
            sn += "."
        return sn
    # Sin snippet: no añadimos nada que el titular no diga.
    t = cortar_colgado(tit)
    if t and t[-1] not in ".!?…":
        t += "."
    return t



def _texto(n: dict) -> str:
    return " " + normal((n.get("t") or "") + " " + (n.get("s") or "")) + " "


def es_otro_deporte(x: str) -> bool:
    return bool(re.search(
        r"\b(nfl|49ers|vikings|super bowl|futbol americano|nba|mlb|nhl|ufc|mma|"
        r"formula 1|\bf1\b|motogp|tenis|\batp\b|\bwta\b|basquet|baloncesto|"
        r"beisbol|golf|boxeo|rally|dakar)\b", x
    ))


def es_futbol(n: dict) -> bool:
    x = _texto(n)
    if es_otro_deporte(x) and not (R_CLUBES.search(x) or R_VERDE.search(x)):
        return False
    if R_FUTBOL.search(x) or R_CLUBES.search(x) or R_VERDE.search(x) or R_COPAS.search(x):
        return True
    cats = n.get("c") or []
    if "futbol" in cats or "copas" in cats or "seleccion" in cats:
        # 'futbol' en la web a veces incluye falso positivo (NFL); ya filtrado arriba
        return not es_otro_deporte(x)
    return False


def etiqueta(n: dict) -> str:
    x = _texto(n)
    cats = n.get("c") or []
    if "talla baja" in x:
        return "La Verde · Talla baja"
    if R_VERDE.search(x) or ("seleccion" in cats and re.search(r"\b(bolivia|la verde|villegas)\b", x)):
        return "La Verde"
    if R_CLUBES.search(x):
        return "Fútbol boliviano"
    if R_COPAS.search(x) or "copas" in cats:
        return "Copas"
    return "Fútbol mundial"


def puntaje(n: dict, ahora: datetime) -> float:
    x = _texto(n)
    et = etiqueta(n)
    sc = 0.0
    if et == "Fútbol boliviano":
        sc += 100
    elif et.startswith("La Verde"):
        sc += 88
    elif et == "Copas" and re.search(r"\b(bolivia recibira|recibira la sudamericana|santa cruz sera sede|sede de la final 202[0-9]|sede de la final de la)\b", x):
        sc += 70
    elif et == "Copas":
        sc += 45
    elif et == "Fútbol mundial":
        sc += 18
    if n.get("s"):
        sc += 8
    if n.get("f") and "google" not in (n.get("f") or "").lower():
        sc += 4
    # Nombrar la competición evita titulares ambiguos (p. ej. Mundial de Talla Baja)
    if re.search(r"\b(talla baja|sudamericana|libertadores|division profesional|eliminatorias)\b", x):
        sc += 22
    # Laterales (festejo, desmayo, premio) ceden ante el hecho principal
    if re.search(r"\b(desmay|desplom|desvanec|auxiliaron|cuanto dinero|chicana|el dardo|caravana de festejos)\b", x):
        sc -= 35
    # Resultado con marcador vale más que una previa
    if re.search(r"\b\d+\s*[-–]\s*\d+\b", x) or re.search(r"\b(campeon|campeona|titulo|goleo|vence|derroto|clasific)\b", x):
        sc += 8
    if re.search(r"\b(lucha por el titulo|iguala a bolivar|primer lugar|en la punta|mete presion)\b", " " + normal(n.get("t") or "") + " "):
        sc += 10
    xt = " " + normal(n.get("t") or "") + " "
    if re.search(r"\b(campeon de la (copa )?(sudamericana|libertadores)|se corona en la|tricampeon|rompe la sequia|vuelve a conquistar)\b", xt):
        sc += 28
    if re.search(r"\b(ponen un pie|un pie en la|se acerca a un cupo|boleto a la)\b", x):
        sc -= 20
    if re.search(r"\b(la tarde de|se enfrentan|se miden|previa|alineaciones|asi forman|formaciones|donde ver)\b", x) and not re.search(r"\b\d+\s*[-–]\s*\d+\b", x):
        sc -= 45
    try:
        dt = datetime.fromisoformat((n.get("d") or "").replace("Z", "+00:00"))
        horas = max(0, (ahora - dt).total_seconds() / 3600)
        sc += max(0, 12 - horas * 0.25)
    except Exception:
        pass
    if R_EN_VIVO.search(x) and not re.search(r"\b\d+\s*[-–]\s*\d+\b", x):
        sc -= 40
    return sc


def clave_historia(n: dict) -> set[str]:
    x = normal((n.get("t") or "") + " " + (n.get("s") or ""))
    claves: set[str] = set()
    pares = [
        ("always ready", "always ready"),
        ("san antonio", "san antonio"),
        ("the strongest", "the strongest"),
        ("blooming", "blooming"),
        ("bolivar", "bolivar"),
        ("boca", "boca"),
        ("mineiro", "mineiro"),
        ("sudamericana", "sudamericana"),
        ("libertadores", "libertadores"),
        ("paredes", "paredes"),
        ("talla baja", "talla baja"),
        ("santa cruz", "santa cruz"),
        ("wilstermann", "wilstermann"),
        ("oriente petrolero", "oriente"),
        ("real potosi", "real potosi"),
        ("nacional potosi", "nacional potosi"),
        ("tomayapo", "tomayapo"),
    ]
    for needle, tag in pares:
        if needle in x:
            claves.add(tag)
    # Apodos habituales, solo cuando el rival también aparece (el Tigre = The Strongest)
    if re.search(r"\btigre\b", x) and "blooming" in x:
        claves.add("the strongest")
    if re.search(r"\boriente(\s+petrolero)?\b", x):
        claves.add("oriente")
    if re.search(r"\bindependiente\s+petrolero\b", x) or ("independiente" in x and "oriente" in x):
        claves.add("independiente petrolero")
    if "bolivia" in x and "mexico" in x:
        claves.add("bo-mx")
    m = re.search(r"\b(\d+)\s*[-–]\s*(\d+)\b", x)
    if m:
        a, b = m.group(1), m.group(2)
        claves.add("marcador:" + "-".join(sorted([a, b], key=int)))
    return claves


def misma_historia(a: dict, b: dict) -> bool:
    if solapamiento(a.get("t") or "", b.get("t") or "") >= 0.42:
        return True
    ca, cb = clave_historia(a), clave_historia(b)
    compartidas = ca & cb
    marc = {k for k in compartidas if k.startswith("marcador:")}
    temas = compartidas - marc
    if len(temas) >= 2:
        return True
    # Mismo club o copa + mismo marcador
    if marc and temas:
        return True
    # Un solo slide por el Mundial de Talla Baja en el carrusel del día
    if "talla baja" in ca and "talla baja" in cb:
        return True
    return False



def elegir(noticias: list[dict], ahora: datetime) -> list[dict]:
    corte = ahora - timedelta(hours=36)
    cand = []
    for n in noticias:
        if not es_futbol(n):
            continue
        try:
            dt = datetime.fromisoformat((n.get("d") or "").replace("Z", "+00:00"))
        except Exception:
            continue
        if dt < corte:
            continue
        if R_EN_VIVO.search(_texto(n)) and puntaje(n, ahora) < 50:
            continue
        cand.append(n)
    cand.sort(key=lambda n: puntaje(n, ahora), reverse=True)

    def calidad(n):
        x = _texto(n)
        sc = puntaje(n, ahora)
        if re.search(r"\b(talla baja|sudamericana|libertadores|division profesional)\b", x):
            sc += 30
        if n.get("s") and len(n.get("s") or "") > 80:
            sc += 10
        if re.search(r"\b(desmay|desplom|desvanec|auxiliaron|cuanto dinero|chicana|en vivo|teoria de|el mensaje que le)\b", x):
            sc -= 55
        if re.search(r"\b\d+\s*[-–]\s*\d+\b", x):
            sc += 55
        elif re.search(r"\b(goleo|vence|derroto|gano |cayo|empato|campeon|clasific)\b", x):
            sc += 20
        if re.search(r"\b(visitara|se enfrentan|este domingo|este sabado|la tarde de|previa|espera un tropiezo|defiende la cima|defiende la punta)\b", x) and not re.search(r"\b\d+\s*[-–]\s*\d+\b", x):
            sc -= 50
        return sc

    def mejor(n, pool):
        cluster = [n] + [x for x in pool if x is not n and misma_historia(n, x)]
        return max(cluster, key=calidad)

    def tomar(pool, ya, k):
        out = []
        for n in pool:
            if any(misma_historia(n, e) for e in ya + out):
                continue
            out.append(mejor(n, pool))
            if len(out) >= k:
                break
        return out

    elegidas = tomar(cand, [], MAX_NOTICIAS)

    # Si faltan y hay material un poco más viejo (48 h)
    if len(elegidas) < MIN_NOTICIAS:
        corte2 = ahora - timedelta(hours=48)
        extra = []
        for n in noticias:
            if n in elegidas or not es_futbol(n):
                continue
            try:
                dt = datetime.fromisoformat((n.get("d") or "").replace("Z", "+00:00"))
            except Exception:
                continue
            if dt < corte2:
                continue
            extra.append(n)
        extra.sort(key=lambda n: puntaje(n, ahora), reverse=True)
        elegidas += tomar(extra, elegidas, MIN_NOTICIAS - len(elegidas))

    # Equilibrio: si no quedó ninguna copa o La Verde, sustituye la de menor puntaje
    def grupo(n):
        e = etiqueta(n)
        if e.startswith("La Verde"):
            return "verde"
        if e == "Copas":
            return "copas"
        if e == "Fútbol boliviano":
            return "bolivia"
        return "mundo"

    grupos = {grupo(n) for n in elegidas}
    for faltante, pred in (
        ("verde", lambda n: grupo(n) == "verde"),
        ("copas", lambda n: grupo(n) == "copas"),
    ):
        if faltante in grupos or len(elegidas) < 2:
            continue
        reemplazo = next((n for n in cand if pred(n) and not any(misma_historia(n, e) for e in elegidas)), None)
        if not reemplazo:
            continue
        # Cede el puesto la noticia de menor puntaje que no sea la única de su grupo
        orden = sorted(elegidas, key=lambda n: puntaje(n, ahora))
        for debil in orden:
            resto = [x for x in elegidas if x is not debil]
            if grupo(debil) == "bolivia" and sum(1 for x in resto if grupo(x) == "bolivia") < 2:
                continue
            if grupo(debil) in ("verde", "copas"):
                continue
            elegidas = resto + [reemplazo]
            grupos = {grupo(n) for n in elegidas}
            break

    # Reordena: Bolivia, La Verde, copas, mundo; y dentro, por puntaje
    orden_g = {"bolivia": 0, "verde": 1, "copas": 2, "mundo": 3}
    elegidas.sort(key=lambda n: (orden_g[grupo(n)], -puntaje(n, ahora)))
    return elegidas[:MAX_NOTICIAS]


# ---------- dibujo ----------


def font(nombre: str, size: float) -> ImageFont.FreeTypeFont:
    path = FUENTES / nombre
    return ImageFont.truetype(str(path), int(round(size)))


def medir(draw: ImageDraw.ImageDraw, texto: str, fnt: ImageFont.FreeTypeFont, tracking: float = 0) -> float:
    if not texto:
        return 0
    if not tracking:
        return float(draw.textlength(texto, font=fnt))
    w = 0.0
    for i, ch in enumerate(texto):
        w += float(draw.textlength(ch, font=fnt))
        if i < len(texto) - 1:
            w += tracking
    return w


def dibujar_texto(draw: ImageDraw.ImageDraw, xy, texto, fnt, fill, tracking=0, anchor="lt"):
    x, y = xy
    if not tracking:
        draw.text((x, y), texto, font=fnt, fill=fill, anchor=anchor)
        return
    # Solo 'lt' y 'mt' de forma fiable con tracking
    ancho = medir(draw, texto, fnt, tracking)
    if anchor == "mt":
        x = x - ancho / 2
    elif anchor == "rt":
        x = x - ancho
    for ch in texto:
        draw.text((x, y), ch, font=fnt, fill=fill, anchor="lt")
        x += float(draw.textlength(ch, font=fnt)) + tracking


def envolver(draw, texto, fnt, max_w, tracking=0) -> list[str]:
    palabras = texto.split()
    if not palabras:
        return []
    lineas, actual = [], ""
    for p in palabras:
        prueba = (actual + " " + p).strip()
        if medir(draw, prueba, fnt, tracking) <= max_w or not actual:
            if medir(draw, p, fnt, tracking) > max_w and not actual:
                # Parte una palabra demasiado larga
                trozo = ""
                for ch in p:
                    if medir(draw, trozo + ch, fnt, tracking) <= max_w or not trozo:
                        trozo += ch
                    else:
                        lineas.append(trozo)
                        trozo = ch
                actual = trozo
            else:
                actual = prueba
        else:
            lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas


def ajustar_bloque(draw, texto, archivo, size_max, size_min, max_w, max_h,
                   interlinea=1.05, tracking=0, uppercase=False) -> tuple[list[str], ImageFont.FreeTypeFont, float]:
    texto = texto.strip()
    if uppercase:
        texto = texto.upper()
    size = size_max
    while size >= size_min:
        fnt = font(archivo, size)
        lineas = envolver(draw, texto, fnt, max_w, tracking)
        # altura de una línea
        bbox = draw.textbbox((0, 0), "Áy", font=fnt)
        lh = (bbox[3] - bbox[1]) * interlinea
        alto = lh * len(lineas)
        if alto <= max_h and lineas:
            return lineas, fnt, lh
        size -= 2 * ESCALA / 2 if ESCALA else 2
        size -= 2
    fnt = font(archivo, size_min)
    lineas = envolver(draw, texto, fnt, max_w, tracking)
    bbox = draw.textbbox((0, 0), "Áy", font=fnt)
    lh = (bbox[3] - bbox[1]) * interlinea
    # Si aún no cabe, recorta líneas y añade …
    max_lineas = max(1, int(max_h // lh))
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        if not lineas[-1].endswith("…"):
            lineas[-1] = lineas[-1].rstrip(".,;:") + "…"
    return lineas, fnt, lh


class LayoutError(RuntimeError):
    pass


def comprobar_caja(draw, x, y, texto, fnt, tracking, caja):
    x0, y0, x1, y1 = caja
    w = medir(draw, texto, fnt, tracking)
    bbox = draw.textbbox((0, 0), texto, font=fnt)
    h = bbox[3] - bbox[1]
    # textbbox with default anchor lt: bbox relative to origin includes maybe negative left
    # Usamos x,y como esquina superior izquierda del texto
    left, top, right, bottom = x + bbox[0], y + bbox[1], x + bbox[0] + w, y + bbox[1] + h
    # Con tracking el ancho real es w, no bbox
    right = x + w
    margen = 2
    if left < x0 - margen or right > x1 + margen or top < y0 - margen or bottom > y1 + margen:
        raise LayoutError(
            f"Texto fuera de caja: «{texto[:40]}» ({left:.0f},{top:.0f})-({right:.0f},{bottom:.0f}) "
            f"caja ({x0},{y0})-({x1},{y1})"
        )


def glow(w, h, cx, cy, radio, rgb, amax=100):
    if np is not None:
        yy, xx = np.ogrid[:h, :w]
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        t = np.clip(1 - d / radio, 0, 1) ** 2
        capa = np.zeros((h, w, 4), np.uint8)
        capa[..., 0] = rgb[0]
        capa[..., 1] = rgb[1]
        capa[..., 2] = rgb[2]
        capa[..., 3] = (t * amax).astype(np.uint8)
        return Image.fromarray(capa, "RGBA")
    # Respaldo sin numpy: círculos concéntricos
    capa = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    pasos = 40
    for i in range(pasos, 0, -1):
        r = int(radio * i / pasos)
        a = int(amax * (i / pasos) ** 2)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*rgb, a))
    return capa


def tricolor(draw, y=0, alto=None):
    alto = alto or 16 * ESCALA
    w3 = W // 3
    draw.rectangle((0, y, w3, y + alto), fill=ROJO)
    draw.rectangle((w3, y, 2 * w3, y + alto), fill=AMARILLO)
    draw.rectangle((2 * w3, y, W, y + alto), fill=ACENTO)


def icono_redondo(size: int) -> Image.Image:
    im = Image.open(ICONO).convert("RGBA")
    im = im.resize((size, size), Image.Resampling.LANCZOS)
    r = int(size * 0.22)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size, size), radius=r, fill=255)
    im.putalpha(mask)
    return im


def sello_redondo(size: int) -> Image.Image:
    im = Image.open(SELLO).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    # respeta la transparencia original, recortada en círculo
    a = im.split()[-1]
    out = im.copy()
    out.putalpha(Image.composite(a, Image.new("L", (size, size), 0), mask))
    return out


def base_lienzo() -> Image.Image:
    img = Image.new("RGBA", (W, H), (*FONDO, 255))
    # Resplandor verde a la derecha / abajo
    g1 = glow(W, H, int(W * 0.88), int(H * 0.22), int(H * 0.55), ACENTO, 55)
    img = Image.alpha_composite(img, g1)
    g2 = glow(W, H, int(W * 0.15), int(H * 0.92), int(H * 0.45), ROJO, 28)
    img = Image.alpha_composite(img, g2)
    # Puntos de trama (estadio / LED)
    d = ImageDraw.Draw(img)
    paso = 28 * ESCALA
    for y in range(40 * ESCALA, H, paso):
        for x in range(20 * ESCALA, W, paso):
            d.ellipse((x, y, x + 3, y + 3), fill=(255, 255, 255, 14))
    # Barra tricolor
    tricolor(d, 0, 18 * ESCALA)
    return img


def marca(img: Image.Image, draw: ImageDraw.ImageDraw, y: int | None = None) -> int:
    y = y if y is not None else 48 * ESCALA
    size = 72 * ESCALA
    ico = icono_redondo(size)
    img.paste(ico, (M, y), ico)
    fnt = font("BebasNeue-Regular.ttf", 52 * ESCALA)
    tx = M + size + 18 * ESCALA
    ty = y + size // 2
    # "GHATU" blanco + "DEPORTES" verde, anclados al centro vertical
    w1 = medir(draw, "GHATU ", fnt, tracking=2 * ESCALA)
    # mide altura
    bb = draw.textbbox((0, 0), "GHATU", font=fnt)
    th = bb[3] - bb[1]
    ty_lt = ty - th / 2 - bb[1]
    dibujar_texto(draw, (tx, ty_lt), "GHATU ", fnt, TEXTO, tracking=2 * ESCALA)
    dibujar_texto(draw, (tx + w1, ty_lt), "DEPORTES", fnt, ACENTO, tracking=2 * ESCALA)
    return y + size


def anillo(draw, cx, cy, r, color, ancho, meridians=True):
    caja = (cx - r, cy - r, cx + r, cy + r)
    draw.ellipse(caja, outline=color, width=ancho)
    draw.ellipse((cx - r * 0.62, cy - r * 0.62, cx + r * 0.62, cy + r * 0.62), outline=color, width=max(2, ancho // 2))
    if meridians:
        # Arcos tipo meridiano, abstractos (no el patrón de un balón oficial)
        for dx in (-0.45, 0, 0.45):
            rx = r * 0.35
            draw.arc((cx + dx * r - rx, cy - r * 0.85, cx + dx * r + rx, cy + r * 0.85),
                     start=200, end=340, fill=color, width=max(2, ancho // 2))


def pie_marca(draw, pagina: str | None = None):
    y = H - 70 * ESCALA
    draw.rectangle((0, H - 18 * ESCALA, W, H), fill=ACENTO)
    fnt = font("Outfit-Medium.ttf", 22 * ESCALA)
    txt = "ghatugames.github.io/deportes"
    if pagina:
        txt = f"{pagina}   ·   {txt}"
    dibujar_texto(draw, (W / 2, y), txt, fnt, SUAVE, anchor="mt")


def render_portada(fecha: datetime, n_noticias: int) -> Image.Image:
    img = base_lienzo()
    draw = ImageDraw.Draw(img)
    # Forma diagonal
    poly = [
        (int(W * 0.35), H),
        (W, int(H * 0.38)),
        (W, H),
    ]
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.polygon(poly, fill=(*ACENTO, 28))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    anillo(draw, int(W * 0.84), int(H * 0.80), int(360 * ESCALA), (*ACENTO, 90), 10 * ESCALA)
    anillo(draw, int(W * 0.84), int(H * 0.80), int(270 * ESCALA), (*BLANCO, 28), 4 * ESCALA)

    y_marca = marca(img, draw)
    caja = (M, y_marca + 80 * ESCALA, W - M, H - 280 * ESCALA)
    titulo = "Lo más importante del fútbol hoy"
    lineas, fnt, lh = ajustar_bloque(
        draw, titulo, "BebasNeue-Regular.ttf",
        128 * ESCALA, 84 * ESCALA,
        caja[2] - caja[0], caja[3] - caja[1],
        interlinea=0.92, tracking=2 * ESCALA, uppercase=True,
    )
    y = caja[1]
    for ln in lineas:
        comprobar_caja(draw, M, y, ln, fnt, 2 * ESCALA, caja)
        dibujar_texto(draw, (M, y), ln, fnt, BLANCO, tracking=2 * ESCALA)
        y += lh

    # Pastilla de fecha
    fecha_t = fecha_texto(fecha)
    ffecha = font("Outfit-SemiBold.ttf", 30 * ESCALA)
    pad_x, pad_y = 28 * ESCALA, 14 * ESCALA
    tw = medir(draw, fecha_t, ffecha)
    th = draw.textbbox((0, 0), fecha_t, font=ffecha)
    th = th[3] - th[1]
    y += 36 * ESCALA
    rx1, ry1 = M, int(y)
    rx2, ry2 = int(M + tw + pad_x * 2), int(y + th + pad_y * 2)
    draw.rounded_rectangle((rx1, ry1, rx2, ry2), radius=40 * ESCALA, fill=AMARILLO)
    dibujar_texto(draw, (M + pad_x, ry1 + pad_y - 2 * ESCALA), fecha_t, ffecha, OSCURO)

    fsub = font("Outfit-Medium.ttf", 28 * ESCALA)
    sub = "Bolivia y el mundo, en un vistazo"
    dibujar_texto(draw, (M, ry2 + 28 * ESCALA), sub, fsub, SUAVE)

    pie_marca(draw)
    return img


def color_etiqueta(et: str):
    if "Verde" in et:
        return ACENTO, OSCURO
    if "boliviano" in et.lower():
        return ROJO, BLANCO
    if "Copas" in et:
        return AMARILLO, OSCURO
    return (40, 90, 160), BLANCO


def render_noticia(n: dict, idx: int, total: int, fecha: datetime) -> Image.Image:
    img = base_lienzo()
    draw = ImageDraw.Draw(img)
    # Número enorme de fondo
    num = f"{idx:02d}"
    fnum = font("BebasNeue-Regular.ttf", 380 * ESCALA)
    dibujar_texto(draw, (W - 40 * ESCALA, 720 * ESCALA), num, fnum, (*BLANCO, 18), tracking=-8, anchor="rt")

    y_marca = marca(img, draw)
    # Contador a la derecha de la marca
    fpag = font("Outfit-SemiBold.ttf", 24 * ESCALA)
    pag = f"{idx} / {total}"
    dibujar_texto(draw, (W - M, 70 * ESCALA), pag, fpag, SUAVE, anchor="rt")

    et = n["etiqueta"]
    bg, fg = color_etiqueta(et)
    fet = font("Outfit-Bold.ttf", 24 * ESCALA)
    et_txt = et.upper()
    tw = medir(draw, et_txt, fet)
    pad_x, pad_y = 22 * ESCALA, 10 * ESCALA
    y = y_marca + 56 * ESCALA
    draw.rounded_rectangle((M, y, M + tw + pad_x * 2, y + 48 * ESCALA), radius=24 * ESCALA, fill=bg)
    dibujar_texto(draw, (M + pad_x, y + 8 * ESCALA), et_txt, fet, fg)

    y_tit = y + 48 * ESCALA + 28 * ESCALA
    caja_tit = (M, y_tit, W - M, y_tit + 430 * ESCALA)
    # El guion corto de Bebas Neue se lee mal en un marcador; usamos el signo menos (U+2212).
    titular_dibujo = re.sub(r"(\d)\s*[-–—]\s*(\d)", lambda m: m.group(1) + " a " + m.group(2), n["titular"])
    lineas, fnt, lh = ajustar_bloque(
        draw, titular_dibujo, "BebasNeue-Regular.ttf",
        86 * ESCALA, 56 * ESCALA,
        caja_tit[2] - caja_tit[0], caja_tit[3] - caja_tit[1],
        interlinea=0.95, tracking=1 * ESCALA, uppercase=True,
    )
    y = y_tit
    for ln in lineas:
        comprobar_caja(draw, M, y, ln, fnt, 1 * ESCALA, caja_tit)
        dibujar_texto(draw, (M, y), ln, fnt, BLANCO, tracking=1 * ESCALA)
        y += lh

    # Línea de acento
    y += 18 * ESCALA
    draw.rectangle((M, y, M + 160 * ESCALA, y + 8 * ESCALA), fill=ACENTO)
    y += 32 * ESCALA

    caja_res = (M, y, W - M, H - 220 * ESCALA)
    rlineas, rfnt, rlh = ajustar_bloque(
        draw, n["resumen"], "Outfit-Regular.ttf",
        34 * ESCALA, 26 * ESCALA,
        caja_res[2] - caja_res[0], min(caja_res[3] - caja_res[1], 280 * ESCALA),
        interlinea=1.28, tracking=0, uppercase=False,
    )
    for ln in rlineas:
        comprobar_caja(draw, M, y, ln, rfnt, 0, caja_res)
        dibujar_texto(draw, (M, y), ln, rfnt, TEXTO)
        y += rlh

    # Crédito del medio
    y += 28 * ESCALA
    medio = n["medio"]
    fmed = font("Outfit-SemiBold.ttf", 24 * ESCALA)
    credito = f"Según {medio}"
    cw = medir(draw, credito, fmed)
    ch = 46 * ESCALA
    if y + ch > H - 100 * ESCALA:
        y = H - 100 * ESCALA - ch
    draw.rounded_rectangle((M, y, M + cw + 40 * ESCALA, y + ch), radius=12 * ESCALA, fill=PANEL)
    draw.rectangle((M, y, M + 8 * ESCALA, y + ch), fill=ACENTO)
    dibujar_texto(draw, (M + 24 * ESCALA, y + 8 * ESCALA), credito, fmed, SUAVE)

    pie_marca(draw, f"{idx} de {total}")
    return img


def render_cierre(fecha: datetime, total: int) -> Image.Image:
    img = base_lienzo()
    draw = ImageDraw.Draw(img)
    anillo(draw, int(W * 0.82), int(H * 0.30), int(280 * ESCALA), (*ACENTO, 60), 8 * ESCALA)
    marca(img, draw)

    caja = (M, 280 * ESCALA, W - M, 560 * ESCALA)
    lineas, fnt, lh = ajustar_bloque(
        draw, "Síguenos", "BebasNeue-Regular.ttf",
        140 * ESCALA, 90 * ESCALA,
        caja[2] - caja[0], caja[3] - caja[1],
        interlinea=0.9, tracking=4 * ESCALA, uppercase=True,
    )
    y = caja[1]
    for ln in lineas:
        comprobar_caja(draw, M, y, ln, fnt, 4 * ESCALA, caja)
        dibujar_texto(draw, (M, y), ln, fnt, BLANCO, tracking=4 * ESCALA)
        y += lh

    f1 = font("Outfit-SemiBold.ttf", 36 * ESCALA)
    f2 = font("BebasNeue-Regular.ttf", 56 * ESCALA)
    f3 = font("Outfit-Regular.ttf", 30 * ESCALA)
    y += 20 * ESCALA
    dibujar_texto(draw, (M, y), "Busca la página en Facebook", f1, SUAVE)
    y += 58 * ESCALA
    dibujar_texto(draw, (M, y), "GHATU DEPORTES", f2, ACENTO, tracking=3 * ESCALA)
    y += 90 * ESCALA
    dibujar_texto(draw, (M, y), "Y entra cada día a", f3, SUAVE)
    y += 50 * ESCALA
    url = "ghatugames.github.io/deportes"
    fu = font("Outfit-Bold.ttf", 36 * ESCALA)
    # Outfit en minúsculas: el punto de Bebas Neue se lee mal en una URL
    ulineas, fu, ulh = ajustar_bloque(
        draw, url, "Outfit-Bold.ttf",
        36 * ESCALA, 26 * ESCALA,
        W - 2 * M, 140 * ESCALA,
        interlinea=1.15, tracking=0, uppercase=False,
    )
    for ln in ulineas:
        dibujar_texto(draw, (M, y), ln, fu, AMARILLO, tracking=0)
        y += ulh

    # Sello Ghatu Games
    size = 110 * ESCALA
    sello = sello_redondo(size)
    sy = H - 200 * ESCALA
    img.paste(sello, (M, sy), sello)
    draw = ImageDraw.Draw(img)
    fs = font("Outfit-Medium.ttf", 22 * ESCALA)
    fb = font("BebasNeue-Regular.ttf", 44 * ESCALA)
    dibujar_texto(draw, (M + size + 24 * ESCALA, sy + 22 * ESCALA), "HECHO POR", fs, SUAVE, tracking=3 * ESCALA)
    dibujar_texto(draw, (M + size + 24 * ESCALA, sy + 52 * ESCALA), "GHATU GAMES", fb, (255, 95, 162), tracking=2 * ESCALA)

    pie_marca(draw)
    return img


def a_png(img: Image.Image) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    # Aplana sobre el fondo y reduce al tamaño de publicación
    fondo = Image.new("RGB", img.size, FONDO)
    fondo.paste(img, mask=img.split()[-1])
    if img.size != (ANCHO, ALTO):
        fondo = fondo.resize((ANCHO, ALTO), Image.Resampling.LANCZOS)
    return fondo


def guardar_png(img: Image.Image, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    a_png(img).save(path, "PNG", optimize=True, compress_level=9)


def hashtags(items: list[dict]) -> list[str]:
    tags = ["#GhatuDeportes", "#Fútbol"]
    blob = " ".join(normal(i["titular"] + " " + i["resumen"] + " " + i["etiqueta"]) for i in items)
    if "boliv" in blob or "always ready" in blob or "the strongest" in blob or "bolivar" in blob:
        tags.append("#FútbolBoliviano")
    if "verde" in blob or "talla baja" in blob or "seleccion boliviana" in blob:
        tags.append("#LaVerde")
    if "division" in blob or "always ready" in blob or "the strongest" in blob or "blooming" in blob:
        tags.append("#DivisiónProfesional")
    if "libertadores" in blob:
        tags.append("#CopaLibertadores")
    if "sudamericana" in blob:
        tags.append("#CopaSudamericana")
    for nombre, tag in (
        ("always ready", "#AlwaysReady"),
        ("the strongest", "#TheStrongest"),
        ("bolivar", "#Bolívar"),
        ("blooming", "#Blooming"),
        ("boca", "#BocaJuniors"),
        ("san antonio", "#SanAntonio"),
    ):
        if nombre in blob:
            tags.append(tag)
    # únicos, orden de inserción
    vistos, out = set(), []
    for t in tags:
        if t.lower() not in vistos:
            vistos.add(t.lower())
            out.append(t)
    return out


def epigrafe(fecha: datetime, items: list[dict]) -> str:
    lineas = [
        "Lo más importante del fútbol hoy",
        fecha_texto(fecha),
        "",
    ]
    for i, n in enumerate(items, 1):
        lineas.append(f"{i}️⃣ {n['titular']}")
    lineas += [
        "",
        "Lee las notas y descarga el carrusel en:",
        URL_CARRUSEL,
        "",
        "Síguenos en Facebook: Ghatu Deportes",
        "Hecho por Ghatu Games",
        "",
        " ".join(hashtags(items)),
    ]
    return "\n".join(lineas)


def podar(carpeta: Path, hoy: str):
    dirs = sorted(p for p in carpeta.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name))
    # Conserva los 14 más recientes (incluye hoy)
    for p in dirs[:-ARCHIVO_DIAS]:
        for f in p.iterdir():
            f.unlink()
        p.rmdir()


def escribir_zip(carpeta: Path, nombre: str, n_slides: int, pie: str):
    zpath = carpeta / nombre
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for i in range(1, n_slides + 1):
            z.write(carpeta / f"{i}.png", f"{i}.png")
        z.writestr("pie.txt", pie)
    return zpath


def html_slides(items_meta: list[dict], fecha: datetime, pie: str, zip_name: str, n: int) -> str:
    figs = []
    for s in items_meta:
        desc = s.get("alt") or f"Lámina {s['n']}"
        figs.append(
            f'<figure class="lamina">\n'
            f'  <img src="hoy/{s["archivo"]}" alt="{esc(desc)}" width="1080" height="1350">\n'
            f'  <figcaption><span>Lámina {s["n"]} de {n}</span>'
            f'<a class="boton" href="hoy/{s["archivo"]}" download="ghatu-deportes-{fecha.date()}-{s["n"]}.png">Descargar</a></figcaption>\n'
            f'</figure>'
        )
    slides_html = "\n".join(figs)
    pie_esc = esc(pie)
    fecha_t = fecha_texto(fecha)
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Carrusel del día · Ghatu Deportes</title>
<meta name="description" content="Lo más importante del fútbol hoy, en imágenes listas para Facebook e Instagram. {fecha_t}.">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; font-src 'self'; base-uri 'self'; form-action 'none'">
<meta name="theme-color" content="#0b0f14">
<meta property="og:title" content="Carrusel del día · Ghatu Deportes">
<meta property="og:description" content="Lo más importante del fútbol hoy, en imágenes para compartir.">
<meta property="og:type" content="website">
<meta property="og:url" content="{URL_CARRUSEL}">
<meta property="og:image" content="{URL_CARRUSEL}hoy/1.png">
<link rel="canonical" href="{URL_CARRUSEL}">
<link rel="icon" href="../assets/icono-32.png" type="image/png">
<link rel="apple-touch-icon" href="../assets/icono-180.png">
<link rel="preload" href="../assets/fuentes/bebas-neue.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="../assets/estilo.css">
<link rel="stylesheet" href="estilo.css">
<script src="../assets/tema.js"></script>
</head>
<body class="pag-carrusel">
<a class="saltar" href="#laminas">Saltar a las láminas</a>
<header class="cabecera">
  <div class="envoltura barra">
    <a class="marca" href="../" aria-label="Ghatu Deportes, inicio">
      <img src="../assets/icono-64.png" alt="" width="34" height="34"><span>Ghatu <b>Deportes</b></span>
    </a>
    <a class="volver" href="../">← Noticias</a>
    <button class="tema" id="tema" type="button" aria-label="Cambiar a modo claro" title="Modo claro / oscuro"><span aria-hidden="true"></span></button>
  </div>
</header>
<main class="envoltura">
  <p class="migas"><a href="../">Ghatu Deportes</a> · Carrusel</p>
  <h1>Carrusel del día</h1>
  <p class="fecha-dia">{esc(fecha_t)}</p>
  <p class="intro">Imágenes listas para subir a Facebook o Instagram, en este orden. El diseño es nuestro: no usamos fotos de los medios. Cada noticia cita al medio y se basa solo en su titular y resumen.</p>
  <p class="acciones">
    <a class="boton" href="hoy/{esc(zip_name)}" download>Descargar todo (ZIP)</a>
  </p>
  <section id="laminas" class="laminas" aria-label="Láminas de hoy">
{slides_html}
  </section>
  <section class="epigrafe" aria-labelledby="epi-t">
    <h2 id="epi-t">Texto para copiar</h2>
    <p>Pégalo junto al carrusel en Facebook o Instagram.</p>
    <textarea id="pie" readonly rows="16">{pie_esc}</textarea>
    <p class="acciones"><button type="button" class="boton" id="copiar">Copiar texto</button> <span id="copiado" hidden>Listo, ya está copiado.</span></p>
  </section>
</main>
<footer class="pie">
  <div class="envoltura">
    <p>Se actualiza solo cada mañana. Las notas completas están en cada medio; aquí solo preparamos el carrusel.</p>
    <a class="sello" href="https://ghatugames.github.io/" target="_blank" rel="noopener"><img src="../assets/ghatu-128.webp" alt="" width="44" height="44" loading="lazy"><span><small>Hecho por</small><b>Ghatu Games</b></span></a>
  </div>
</footer>
<script src="app.js"></script>
</body>
</html>
"""


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


CSS = """/* Estilos propios de la página del carrusel. El resto sale de assets/estilo.css. */
.pag-carrusel h1{font:400 48px/1 "Bebas Neue",Impact,"Arial Narrow",sans-serif;letter-spacing:.04em;margin:8px 0 4px}
.pag-carrusel .fecha-dia{color:var(--acento);font-weight:800;margin:0 0 10px;text-transform:capitalize}
.pag-carrusel .intro{max-width:40rem;color:var(--suave);margin:0 0 16px}
.pag-carrusel .migas{font-size:13px;color:var(--suave);margin:18px 0 0}
.pag-carrusel .migas a{color:var(--acento);font-weight:800;text-decoration:none}
.pag-carrusel .volver{margin-left:auto;margin-right:8px;color:var(--acento);font-weight:800;text-decoration:none;font-size:14px;white-space:nowrap}
.pag-carrusel .acciones{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:12px 0 22px}
.pag-carrusel .boton{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:8px 16px;border-radius:10px;background:var(--acento);color:#04130b;font:800 14px/1 system-ui,sans-serif;text-decoration:none;border:0;cursor:pointer}
.pag-carrusel .boton:hover{background:var(--acento2);color:#04130b}
.pag-carrusel .laminas{display:grid;gap:22px;margin:0 0 32px}
@media (min-width:800px){.pag-carrusel .laminas{grid-template-columns:repeat(2,minmax(0,1fr))}}
.pag-carrusel .lamina{margin:0;background:var(--panel);border:1px solid var(--linea);border-radius:14px;overflow:hidden}
.pag-carrusel .lamina img{display:block;width:100%;height:auto;background:#0b0f14}
.pag-carrusel .lamina figcaption{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 12px}
.pag-carrusel .lamina figcaption span{color:var(--suave);font-size:13px;font-weight:700}
.pag-carrusel .epigrafe{margin:0 0 24px;padding:16px;border-radius:14px;background:var(--panel);border:1px solid var(--linea)}
.pag-carrusel .epigrafe h2{font:400 32px/1 "Bebas Neue",Impact,sans-serif;letter-spacing:.04em;margin:0 0 6px}
.pag-carrusel .epigrafe p{margin:0 0 10px;color:var(--suave)}
.pag-carrusel textarea{width:100%;box-sizing:border-box;min-height:280px;padding:12px;border-radius:10px;border:1px solid var(--linea);background:var(--fondo);color:var(--texto);font:15px/1.45 system-ui,sans-serif;resize:vertical}
.pag-carrusel #copiado{color:var(--acento);font-weight:800;font-size:14px}
@media (max-width:480px){.pag-carrusel h1{font-size:38px}.pag-carrusel .volver{font-size:13px}}
"""

JS = """(function(){
  var b = document.getElementById("copiar");
  var t = document.getElementById("pie");
  var ok = document.getElementById("copiado");
  if (!b || !t) return;
  b.addEventListener("click", function(){
    var texto = t.value;
    function listo(){
      if (ok){ ok.hidden = false; setTimeout(function(){ ok.hidden = true; }, 2200); }
    }
    if (navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(texto).then(listo).catch(function(){ t.select(); document.execCommand("copy"); listo(); });
    } else { t.select(); document.execCommand("copy"); listo(); }
  });
})();
"""


def main():
    ap = argparse.ArgumentParser(description="Genera el carrusel diario de Ghatu Deportes.")
    ap.add_argument("--json", default=str(RAIZ / "data" / "noticias.json"))
    ap.add_argument("--salida", default=str(RAIZ / "carrusel"))
    ap.add_argument("--fecha", default="")
    args = ap.parse_args()

    ahora_utc = datetime.now(timezone.utc)
    fecha = datetime.strptime(args.fecha, "%Y-%m-%d").replace(tzinfo=TZ_BO) if args.fecha else datetime.now(TZ_BO)
    fecha_iso = fecha.strftime("%Y-%m-%d")

    datos = cargar_json(Path(args.json), URL_JSON)
    items_raw = elegir(datos.get("noticias") or [], ahora_utc)
    if not items_raw:
        raise SystemExit("No encontré noticias de fútbol recientes para el carrusel.")

    items = []
    for n in items_raw:
        tit = titular_limpio(n.get("t") or "", n.get("f") or "")
        res = resumir(n.get("t") or "", n.get("s") or "")
        # Evita un resumen idéntico al titular
        if normal(res.rstrip(".")) == normal(tit.rstrip(".")):
            res = res  # se deja; es honesto cuando no hay snippet
        items.append({
            "id": n.get("id"),
            "titular": tit,
            "resumen": res,
            "medio": n.get("f") or "Medio",
            "url": n.get("u") or "",
            "fecha": n.get("d") or "",
            "etiqueta": etiqueta(n),
            "raw": n,
        })

    print("Noticias elegidas:")
    for i, it in enumerate(items, 1):
        print(f"  {i}. [{it['etiqueta']}] {it['titular']} — {it['medio']}")
        print(f"     {it['resumen']}")

    total = 2 + len(items)  # portada + noticias + cierre
    # Los números de lámina de noticia empiezan en 2 (después de la portada)
    laminas: list[tuple[str, Image.Image, dict]] = []
    portada = render_portada(fecha, len(items))
    laminas.append(("portada", portada, {
        "n": 1, "archivo": "1.png", "tipo": "portada",
        "alt": f"Portada: lo más importante del fútbol hoy, {fecha_texto(fecha)}",
    }))
    for i, it in enumerate(items, 1):
        num = i + 1
        img = render_noticia(it, num, total, fecha)
        laminas.append(("noticia", img, {
            "n": num, "archivo": f"{num}.png", "tipo": "noticia",
            "titular": it["titular"], "resumen": it["resumen"],
            "medio": it["medio"], "url": it["url"], "etiqueta": it["etiqueta"],
            "alt": f"{it['titular']} (según {it['medio']})",
        }))
    cierre = render_cierre(fecha, total)
    laminas.append(("cierre", cierre, {
        "n": total, "archivo": f"{total}.png", "tipo": "cierre",
        "alt": "Cierre: sigue a Ghatu Deportes en Facebook y en la web. Hecho por Ghatu Games.",
    }))

    salida = Path(args.salida)
    hoy_dir = salida / "hoy"
    arch_dir = salida / fecha_iso
    # Limpia "hoy" para no dejar láminas viejas si hoy hay menos
    if hoy_dir.exists():
        for f in hoy_dir.iterdir():
            if f.is_file():
                f.unlink()
    hoy_dir.mkdir(parents=True, exist_ok=True)
    arch_dir.mkdir(parents=True, exist_ok=True)

    metas = []
    for _, img, meta in laminas:
        guardar_png(img, hoy_dir / meta["archivo"])
        guardar_png(img, arch_dir / meta["archivo"])
        metas.append(meta)
        print(f"  escrita {meta['archivo']} ({(hoy_dir / meta['archivo']).stat().st_size} bytes)")

    pie = epigrafe(fecha, items)
    zip_name = f"ghatu-deportes-carrusel-{fecha_iso}.zip"
    escribir_zip(hoy_dir, zip_name, total, pie)
    escribir_zip(arch_dir, zip_name, total, pie)
    (hoy_dir / "pie.txt").write_text(pie + "\n", encoding="utf-8")
    (arch_dir / "pie.txt").write_text(pie + "\n", encoding="utf-8")

    indice = {
        "fecha": fecha_iso,
        "fechaTexto": fecha_texto(fecha),
        "generado": ahora_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "zona": "America/La_Paz",
        "slides": metas,
        "epigrafe": pie,
        "zip": zip_name,
    }
    (hoy_dir / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (arch_dir / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (salida / "estilo.css").write_text(CSS, encoding="utf-8")
    (salida / "app.js").write_text(JS, encoding="utf-8")
    (salida / "index.html").write_text(html_slides(metas, fecha, pie, zip_name, total), encoding="utf-8")

    podar(salida, fecha_iso)
    print(f"Listo: {total} láminas en {hoy_dir} y {arch_dir}")
    print("--- pie ---")
    print(pie)


if __name__ == "__main__":
    main()
