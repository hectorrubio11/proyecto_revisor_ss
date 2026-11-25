import pymupdf



import pymupdf

CLAVES_PROBATORIOS = (
    "documentos probatorios",
    "constancia de terminación",
    "constancia de terminacion",
    "carta de terminación",
    "carta de terminacion",
    "terminación satisfactoria",
    "recibo de pago",
)

FORMATOS_ESTANDAR_PT = {
    "Carta": (612.0, 792.0),
    "A4": (595.28, 841.89),
}


def obtener_dimensiones_pagina(
    pdf_bytes: bytes,
    indice_pagina: int = 0,
    tolerancia_pt: float = 15.0,
) -> dict:
    """Devuelve ancho/alto en puntos y cm, y si coincide con Carta o A4."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    if indice_pagina < 0 or indice_pagina >= len(doc):
        doc.close()
        return {
            "ancho_pt": 0.0,
            "alto_pt": 0.0,
            "ancho_cm": 0.0,
            "alto_cm": 0.0,
            "formato": "Desconocido",
            "es_tamano_regular": False,
        }

    rect = doc[indice_pagina].rect
    doc.close()

    ancho_pt = float(rect.width)
    alto_pt = float(rect.height)
    w, h = min(ancho_pt, alto_pt), max(ancho_pt, alto_pt)

    formato_detectado = None
    for nombre, (fw, fh) in FORMATOS_ESTANDAR_PT.items():
        if abs(w - fw) <= tolerancia_pt and abs(h - fh) <= tolerancia_pt:
            formato_detectado = nombre
            break

    return {
        "ancho_pt": round(ancho_pt, 2),
        "alto_pt": round(alto_pt, 2),
        "ancho_cm": round((ancho_pt / 72.0) * 2.54, 2),
        "alto_cm": round((alto_pt / 72.0) * 2.54, 2),
        "formato": formato_detectado or "No estándar",
        "es_tamano_regular": formato_detectado is not None,
    }

def _parece_indice(texto_norm: str) -> bool:
    return ("índice" in texto_norm or "indice" in texto_norm or "tabla de contenido" in texto_norm)


def obtener_indices_paginas_relevantes(pdf_bytes: bytes, max_paginas: int = 3) -> list[int]:
    """Devuelve índices (0-based) priorizando portada y la sección real de probatorios/constancias."""
    if max_paginas <= 0:
        return []

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    if total == 0:
        doc.close()
        return []

    indices: list[int] = [0]
    coincidencias_reales: list[int] = []
    coincidencias_en_indice: list[int] = []

    for idx, pagina in enumerate(doc):
        texto_norm = " ".join(pagina.get_text("text").lower().split())
        if any(clave in texto_norm for clave in CLAVES_PROBATORIOS):
            if _parece_indice(texto_norm):
                coincidencias_en_indice.append(idx)
            else:
                coincidencias_reales.append(idx)

    objetivos_clave = coincidencias_reales if coincidencias_reales else coincidencias_en_indice

    if objetivos_clave:
        # Tomamos la última ocurrencia (más cercana al apartado final de probatorios)
        idx_objetivo = objetivos_clave[-1]
        for candidato in (idx_objetivo, idx_objetivo + 1):
            if 0 <= candidato < total and candidato not in indices and len(indices) < max_paginas:
                indices.append(candidato)
    else:
        for candidato in (total - 1, total - 2):
            if 0 <= candidato < total and candidato not in indices and len(indices) < max_paginas:
                indices.append(candidato)

    while len(indices) < max_paginas:
        agregado = False
        for candidato in range(total - 1, -1, -1):
            if candidato not in indices:
                indices.append(candidato)
                agregado = True
                break
        if not agregado:
            break

    doc.close()
    seleccionados = sorted(indices[:max_paginas])
    print("[DEBUG] Índices seleccionados (0-based):", seleccionados)
    print("[DEBUG] Páginas seleccionadas (1-based):", [i + 1 for i in seleccionados])
    return seleccionados


def extraer_texto_y_conteo(pdf_bytes: bytes) -> dict:
    """Extrae texto, fuentes embebidas, proporción real de Arial y conteos por página."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    paginas = []
    total_palabras = 0
    fuentes_set: set[str] = set()
    chars_totales = 0
    chars_arial = 0

    for indice, pagina in enumerate(doc):
        texto = pagina.get_text("text").strip()
        palabras = len(texto.split())
        total_palabras += palabras

        for fuente in pagina.get_fonts(full=True):
            nombre_fuente = str(fuente[3]).split("+")[-1].strip()
            if nombre_fuente:
                fuentes_set.add(nombre_fuente)

        bloques = pagina.get_text("dict").get("blocks", [])
        for bloque in bloques:
            for linea in bloque.get("lines", []):
                for span in linea.get("spans", []):
                    contenido = span.get("text", "").strip()
                    if not contenido:
                        continue
                    largo = len(contenido)
                    chars_totales += largo
                    fuente_span = str(span.get("font", "")).lower()
                    if "arial" in fuente_span:
                        chars_arial += largo

        paginas.append({
            "pagina": indice + 1,
            "texto": texto,
            "palabras": palabras,
        })

    total_paginas = len(doc)
    doc.close()

    porcentaje_arial = round((chars_arial / chars_totales) * 100, 1) if chars_totales > 0 else 0.0

    return {
        "total_paginas": total_paginas,
        "total_palabras": total_palabras,
        "fuentes_detectadas": sorted(fuentes_set),
        "porcentaje_arial": porcentaje_arial,
        "paginas": paginas,
    }


""" 
def obtener_indices_paginas_relevantes(pdf_bytes: bytes, max_paginas: int = 3) -> list[int]:
    ##Devuelve índices de página (0-based) priorizando portada y probatorios/constancias.
    if max_paginas <= 0:
        return []

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    if total == 0:
        doc.close()
        return []

    indices: list[int] = [0]

    for idx, pagina in enumerate(doc):
        texto = pagina.get_text("text").lower()
        if any(clave in texto for clave in CLAVES_PROBATORIOS):
            if idx not in indices and len(indices) < max_paginas:
                indices.append(idx)
            if idx + 1 < total and (idx + 1) not in indices and len(indices) < max_paginas:
                indices.append(idx + 1)
            break

    if len(indices) < max_paginas and (total - 1) not in indices:
        indices.append(total - 1)

    doc.close()
    return sorted(indices[:max_paginas])
"""

def renderizar_paginas_a_png(
    pdf_bytes: bytes,
    max_paginas: int = 3,
    dpi: int = 120,
    indices_paginas: list[int] | None = None,
) -> list[bytes]:
    """Renderiza a PNG las páginas indicadas o las más relevantes (portada y probatorios)."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    if total == 0:
        doc.close()
        return []

    if indices_paginas is not None:
        objetivos = sorted({i for i in indices_paginas if 0 <= i < total})[:max_paginas]
    else:
        doc.close()
        objetivos = obtener_indices_paginas_relevantes(pdf_bytes, max_paginas=max_paginas)
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

    imagenes: list[bytes] = []
    for idx in objetivos:
        pagina = doc[idx]
        pix = pagina.get_pixmap(dpi=dpi)
        imagenes.append(pix.tobytes("png"))

    doc.close()
    return imagenes