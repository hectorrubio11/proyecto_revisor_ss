from pydantic import BaseModel


class RevisionVisual(BaseModel):
    tiene_firma_asesor: bool
    tiene_sello_o_membrete_probatorio: bool
    sin_enmarcados_ni_adornos: bool
    apariencia_fuente_arial: bool
    observacion_visual: str
    revision_visual_pendiente: bool = False


class DictamenIFRSS(BaseModel):
    secciones_detectadas: list[str]
    secciones_faltantes: list[str]
    conteo_palabras_aprox: int
    excede_limites_extension: list[str]
    cumple_estructura_basica: bool
    fuentes_detectadas: list[str]
    cumple_fuente_arial: bool
    tiene_firma_asesor: bool
    tiene_sello_o_membrete_probatorio: bool
    sin_enmarcados_ni_adornos: bool
    observacion_visual: str
    estado_final: str
    observaciones: list[str]