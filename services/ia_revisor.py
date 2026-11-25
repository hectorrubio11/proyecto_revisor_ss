import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError
from models.esquemas import RevisionVisual

load_dotenv()


def _obtener_cliente_gemini() -> genai.Client:
    """Crea el cliente de Gemini usando GEMINI_API_KEY desde el entorno."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "No se encontró GEMINI_API_KEY en las variables de entorno ni en el archivo .env."
        )
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=18000),  # 18 segundos en milisegundos
    )


def _visual_pendiente(motivo: str) -> RevisionVisual:
    return RevisionVisual(
        tiene_firma_asesor=False,
        tiene_sello_o_membrete_probatorio=False,
        sin_enmarcados_ni_adornos=True,
        apariencia_fuente_arial=False,
        observacion_visual=motivo,
        revision_visual_pendiente=True,
    )


def revisar_visualmente_ifrss(
    imagenes_png: list[bytes],
    max_reintentos: int = 1,
    espera_base_seg: float = 0.5,
) -> RevisionVisual:
    """Envía páginas renderizadas en PNG a Gemini con corte rápido ante lentitud o 503."""
    if not imagenes_png:
        return _visual_pendiente("No se generaron imágenes de páginas para la revisión visual.")

    client = _obtener_cliente_gemini()

    prompt = (
        "Eres un revisor técnico de Informes Finales de Resultados de Servicio Social (IFRSS) "
        "de la Universidad Autónoma de Sinaloa (UAS), basado en la Guía Versión 05 (mayo 2026). "
        "Se te envían páginas clave del documento (habitualmente portada y páginas de documentos probatorios/constancias). "
        "Analiza las imágenes y responde exclusivamente con el esquema solicitado:\n"
        "1. tiene_firma_asesor: true si se aprecia una firma manuscrita o digital del asesor en portada o sección correspondiente; false si no se observa.\n"
        "2. tiene_sello_o_membrete_probatorio: true si se observa membrete institucional o sello en documentos probatorios/constancias; false en caso contrario (probablemente venga en una página que empiece con V. Documentos Probatorios).\n"
        "3. sin_enmarcados_ni_adornos: true si las páginas mantienen un diseño limpio (los encabezados, pies de página, líneas divisorias simples y logotipos institucionales de la UAS SÍ están permitidos); false únicamente si toda la página está rodeada por un marco/borde ornamental o tiene ilustraciones decorativas ajenas al formato oficial.\n"
        "4. apariencia_fuente_arial: true si la gran mayoría del texto principal y portada tiene apariencia sans-serif limpia tipo Arial (aunque haya detalles puntuales, encabezados o tablas con otra fuente); false ÚNICAMENTE si casi todo el cuerpo o portada está escrito en otra tipografía (por ejemplo monoespaciada tipo Courier o serif tipo Times).\n"
        "5. observacion_visual: resumen breve y concreto en español de lo encontrado."
    )

    contenidos: list = [prompt]
    for idx, img_bytes in enumerate(imagenes_png, start=1):
        contenidos.append(f"Página muestreada {idx}:")
        contenidos.append(
            types.Part.from_bytes(
                data=img_bytes,
                mime_type="image/png",
            )
        )

    for intento in range(1, max_reintentos + 2):
        try:
            respuesta = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=contenidos,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RevisionVisual,
                    temperature=0.1,
                ),
            )
            if respuesta and respuesta.parsed and isinstance(respuesta.parsed, RevisionVisual):
                parsed = respuesta.parsed
                parsed.revision_visual_pendiente = False
                return parsed
            return _visual_pendiente("No se pudo estructurar la respuesta visual de Gemini.")

        except APIError as exc:
            codigo = getattr(exc, "code", None)
            if codigo == 503 and intento <= max_reintentos:
                time.sleep(espera_base_seg)
                continue
            if codigo == 503:
                return _visual_pendiente(
                    "Revisión visual pendiente: el modelo de Gemini reportó 503 (alta demanda temporal)."
                )
            return _visual_pendiente(f"Revisión visual pendiente por error de API ({codigo}).")

        except Exception as exc:
            msg = str(exc).lower()
            if ("timeout" in msg or "timed out" in msg or "deadline" in msg) and intento <= max_reintentos:
                time.sleep(espera_base_seg)
                continue
            return _visual_pendiente(
                "Revisión visual pendiente: el modelo tardó demasiado en responder."
            )

    return _visual_pendiente("Revisión visual pendiente tras agotar reintentos.")