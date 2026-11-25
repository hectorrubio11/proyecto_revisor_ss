import os
from typing import Literal

import pymupdf
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from services.pdf_parser import obtener_dimensiones_pagina, renderizar_paginas_a_png


class RevisionCartaAsignacion(BaseModel):
    es_una_sola_hoja: bool = Field(
        description="True si el PDF tiene exactamente 1 página."
    )
    tiene_firma: bool = Field(
        description="True si se observa al menos una firma manuscrita, rúbrica o digital en el documento."
    )
    calidad_escaneo: Literal["buena", "regular", "deficiente"] = Field(
        description="Calidad visual del escaneo: 'buena' solo si es nítido y sin recortes/borrones notables; 'regular' si tiene fallos leves o parciales; 'deficiente' si está borroso, lavado o con recortes críticos."
    )
    escaneo_correcto: bool = Field(
        description="True si el documento se ve nítido, legible y bien escaneado sin borrones graves ni recortes críticos."
    )
    observacion: str = Field(
        description="Explicación breve y clara sobre la firma y la calidad del escaneo."
    )


def _es_una_sola_pagina(pdf_bytes: bytes) -> bool:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    doc.close()
    return total == 1


def revisar_carta_asignacion_bytes(pdf_bytes: bytes) -> RevisionCartaAsignacion:
    if not _es_una_sola_pagina(pdf_bytes):
        return RevisionCartaAsignacion(
            es_una_sola_hoja=False,
            tiene_firma=False,
            calidad_escaneo="deficiente",
            escaneo_correcto=False,
            observacion="La carta de asignación debe ser de exactamente 1 hoja.",
        )

    dims = obtener_dimensiones_pagina(pdf_bytes, indice_pagina=0)
    if not dims["es_tamano_regular"]:
        return RevisionCartaAsignacion(
            es_una_sola_hoja=True,
            tiene_firma=False,
            calidad_escaneo="deficiente",
            escaneo_correcto=False,
            observacion=(
                f"La hoja no tiene tamaño regular (Carta o A4); "
                f"mide {dims['ancho_cm']} x {dims['alto_cm']} cm."
            ),
        )

    imagenes_png = renderizar_paginas_a_png(
        pdf_bytes,
        max_paginas=1,
        dpi=200,
    )
    if not imagenes_png:
        return RevisionCartaAsignacion(
            es_una_sola_hoja=True,
            tiene_firma=False,
            calidad_escaneo="deficiente",
            escaneo_correcto=False,
            observacion="No se pudo renderizar la página del documento.",
        )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta configurar GEMINI_API_KEY en el entorno.")

    client = genai.Client(api_key=api_key)

    prompt = (
        "Revisa esta carta de asignación (1 sola hoja) evaluando específicamente:\n"
        "1. Alineación / orientación: ¿la hoja está derecha o está inclinada/rotada/chueca?\n"
        "2. Bordes: ¿se ven los cuatro bordes de la hoja completos o hay bordes cortados/recortados?\n"
        "3. Firma y calidad general: ¿se distingue firma y el texto/sellos se ven legibles y sin "
        "borrones o zonas lavadas graves?\n\n"
        "Reglas para el JSON:\n"
        "- tiene_firma: true solo si se observa firma o rúbrica.\n"
        "- calidad_escaneo: usa 'regular' o 'deficiente' si la hoja está chueca/inclinada, tiene "
        "bordes cortados o presenta borrosidad/desvanecimiento notable; usa 'buena' solo si está "
        "derecha, completa y clara.\n"
        "- escaneo_correcto: true ÚNICAMENTE si calidad_escaneo es 'buena'.\n"
        "- observacion: indica claramente si está derecha o inclinada, si los bordes están completos "
        "o cortados, y qué viste en firma y legibilidad."
    )

    contents: list = [prompt]
    for img_bytes in imagenes_png:
        contents.append(
            types.Part.from_bytes(
                data=img_bytes,
                mime_type="image/png",
            )
        )

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RevisionCartaAsignacion,
            temperature=0.1,
        ),
    )

    if response.parsed:
        resultado = response.parsed
        resultado.es_una_sola_hoja = True
        if resultado.calidad_escaneo != "buena":
            resultado.escaneo_correcto = False
        print("[DEBUG] Carta revisión:", resultado.model_dump())
        return resultado

    return RevisionCartaAsignacion(
        es_una_sola_hoja=True,
        tiene_firma=False,
        calidad_escaneo="deficiente",
        escaneo_correcto=False,
        observacion="No fue posible interpretar la respuesta visual del modelo.",
    )