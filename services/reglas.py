import re


SECCIONES_OBJETIVO = [
    ("Introducción", [r"\bintroducci[oó]n\b"]),
    ("Capítulo I. Unidad Receptora", [r"\bcap[ií]tulo\s*(i|1)\b.*unidad\s*receptora", r"\bcap[ií]tulo\s*(i|1)\b"]),
    ("Capítulo II. Acciones y resultados", [r"\bcap[ií]tulo\s*(ii|2)\b.*acciones", r"\bcap[ií]tulo\s*(ii|2)\b"]),
    ("Capítulo III. Evaluación de la Práctica", [r"\bcap[ií]tulo\s*(iii|3)\b.*evaluaci[oó]n", r"\bcap[ií]tulo\s*(iii|3)\b"]),
    ("Capítulo IV. Documentos probatorios", [r"\bcap[ií]tulo\s*(iv|4)\b.*probatorios", r"\bcap[ií]tulo\s*(iv|4)\b"]),
    ("Bibliografía", [r"\bbibliograf[ií]a\b", r"\breferencias\b"]),
    ("Anexos", [r"\banexos?\b"]),
]

LIMITES_PALABRAS_MAX = {
    "Introducción": 250,
    "Capítulo I. Unidad Receptora": 500,
    "Capítulo III. Evaluación de la Práctica": 500,
    "Anexos": 750,
}

# Encabezados generales para detectar dónde termina un bloque
PATRON_ENCABEZADO = re.compile(
    r"(?im)^\s*(?:introducci[oó]n|cap[ií]tulo\s*(?:i|ii|iii|iv|1|2|3|4)\b|bibliograf[ií]a\b|referencias\b|anexos?\b)"
)


def _contar_palabras_seccion(texto_completo: str, inicio_match: int) -> int:
    """Cuenta palabras desde el inicio de la sección hasta el siguiente encabezado detectado."""
    cuerpo_desde_inicio = texto_completo[inicio_match:]
    salto_linea = cuerpo_desde_inicio.find("\n")
    offset_busqueda = salto_linea + 1 if salto_linea != -1 else 0

    siguiente = PATRON_ENCABEZADO.search(cuerpo_desde_inicio, pos=offset_busqueda)
    if siguiente:
        bloque = cuerpo_desde_inicio[: siguiente.start()]
    else:
        bloque = cuerpo_desde_inicio[:15000]

    return len(bloque.split())


def evaluar_fuente(
    fuentes_detectadas: list[str],
    porcentaje_arial: float = 0.0,
    umbral_arial: float = 75.0,
) -> tuple[bool, str | None]:
    """Evalúa si Arial predomina ampliamente (casi todo) sin reprobar por detalles puntuales."""
    if not fuentes_detectadas:
        return False, "No se detectaron fuentes incrustadas en el PDF; verificar fuente Arial."

    tiene_arial = any("arial" in f.lower() for f in fuentes_detectadas)
    otras_fuentes = [f for f in fuentes_detectadas if "arial" not in f.lower()]

    if tiene_arial and porcentaje_arial >= umbral_arial:
        if otras_fuentes:
            return (
                True,
                f"Tipografía base Arial ({porcentaje_arial}% del texto); detalles puntuales en: {', '.join(otras_fuentes)}.",
            )
        return True, None

    if tiene_arial:
        return (
            False,
            f"Tipografía insuficiente en Arial ({porcentaje_arial}% del texto); predominan otras fuentes ({', '.join(otras_fuentes)}).",
        )

    return False, f"No se detectó fuente Arial (se encontraron: {', '.join(otras_fuentes)})."


def evaluar_reglas_ifrss(datos_pdf: dict) -> dict:
    paginas = datos_pdf.get("paginas", [])
    texto_completo = "\n".join(p.get("texto", "") for p in paginas)
    conteo_total = datos_pdf.get("total_palabras", len(texto_completo.split()))
    fuentes_detectadas = datos_pdf.get("fuentes_detectadas", [])
    porcentaje_arial = datos_pdf.get("porcentaje_arial", 0.0)

    detectadas: list[str] = []
    faltantes: list[str] = []
    posiciones: dict[str, int] = {}

    for nombre, patrones in SECCIONES_OBJETIVO:
        encontrado = False
        for pat in patrones:
            m = re.search(pat, texto_completo, flags=re.IGNORECASE | re.MULTILINE)
            if m:
                detectadas.append(nombre)
                posiciones[nombre] = m.start()
                encontrado = True
                break
        if not encontrado:
            faltantes.append(nombre)

    excede_limites: list[str] = []
    observaciones: list[str] = []

    for seccion, max_palabras in LIMITES_PALABRAS_MAX.items():
        if seccion in posiciones:
            palabras_sec = _contar_palabras_seccion(texto_completo, posiciones[seccion])
            if palabras_sec > max_palabras:
                excede_limites.append(
                    f"{seccion} (~{palabras_sec} palabras vs. ~{max_palabras} máx.)"
                )

    if excede_limites:
        observaciones.append(
            "Posible exceso de extensión respecto a la guía: " + "; ".join(excede_limites) + "."
        )

    fuente_arial_ok, obs_fuente = evaluar_fuente(fuentes_detectadas, porcentaje_arial)
    if obs_fuente:
        observaciones.append(obs_fuente)

    cumple_estructura = len(faltantes) == 0

    return {
        "secciones_detectadas": detectadas,
        "secciones_faltantes": faltantes,
        "conteo_palabras_aprox": conteo_total,
        "excede_limites_extension": excede_limites,
        "cumple_estructura_basica": cumple_estructura,
        "fuente_arial_ok": fuente_arial_ok,
        "porcentaje_arial": porcentaje_arial,
        "observaciones": observaciones,
    }