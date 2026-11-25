import asyncio
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from models.esquemas import DictamenIFRSS
from services.ia_revisor import revisar_visualmente_ifrss
from services.pdf_parser import extraer_texto_y_conteo, renderizar_paginas_a_png
from services.reglas import evaluar_reglas_ifrss
from services.carta_asignacion import revisar_carta_asignacion_bytes

app = FastAPI(
    title="Revisor de Documentos de Servicio Social - UAS",
    description="API y visor para revisar Informes Finales de Resultados de Servicio Social (Guía v05, mayo 2026).",
    version="0.2.0",
)

HTML_UI = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Revisor Servicio Social — FIMAZ</title>
  <style>
    :root {
      --bg: #f4f6f9;
      --card: #ffffff;
      --text: #1e293b;
      --muted: #64748b;
      --border: #e2e8f0;
      --accent: #0f4c81;
      --ok-bg: #dcfce7;
      --ok-border: #16a34a;
      --ok-text: #14532d;
      --warn-bg: #fef3c7;
      --warn-border: #d97706;
      --warn-text: #78350f;
    }
    * { box-sizing: border-box; font-family: system-ui, -apple-system, sans-serif; }
    body { margin: 0; background: var(--bg); color: var(--text); padding: 2rem 1rem; }
    .container { max-width: 780px; margin: 0 auto; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.04); margin-bottom: 1.25rem; }
    h1 { margin: 0 0 0.25rem; font-size: 1.5rem; color: var(--accent); }
    p.sub { margin: 0 0 1.25rem; color: var(--muted); font-size: 0.95rem; }
    .form-row { display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
    select { padding: 0.55rem 0.75rem; border: 1px solid var(--border); border-radius: 8px; background: #f8fafc; color: var(--text); font-size: 0.95rem; }
    input[type="file"] { flex: 1; min-width: 220px; padding: 0.5rem; border: 1px solid var(--border); border-radius: 8px; background: #f8fafc; }
    button { background: var(--accent); color: #fff; border: none; padding: 0.65rem 1.25rem; border-radius: 8px; font-weight: 600; cursor: pointer; }
    button:hover { opacity: 0.92; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    #estado-tiempo { color: var(--muted); font-size: 0.9rem; }
    .banner { padding: 1rem 1.2rem; border-radius: 10px; border-left: 5px solid; font-weight: 600; margin-bottom: 1rem; }
    .banner.cumple { background: var(--ok-bg); border-color: var(--ok-border); color: var(--ok-text); }
    .banner.observaciones { background: var(--warn-bg); border-color: var(--warn-border); color: var(--warn-text); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.75rem; margin-bottom: 1rem; }
    .stat { border: 1px solid var(--border); border-radius: 8px; padding: 0.75rem; background: #f8fafc; }
    .stat small { display: block; color: var(--muted); margin-bottom: 0.2rem; }
    ul { margin: 0.4rem 0 0; padding-left: 1.2rem; }
    li { margin-bottom: 0.35rem; }
    #resultado { display: none; }
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      <h1>Revisor IFRSS — UAS</h1>
      <p id="subtitulo" class="sub">Validación de estructura, extensión, tipografía y elementos visuales.</p>
      <form id="form-ifrss" class="form-row">
        <select id="tipo-documento" name="tipo_documento" aria-label="Tipo de documento">
          <option value="ifrss" selected>Informe Final</option>
          <option value="carta_asignacion">Carta de Asignación</option>
        </select>
        <input type="file" id="archivo" name="archivo" accept="application/pdf,.pdf" required />
        <button type="submit" id="btn-enviar">Revisar PDF</button>
        <span id="estado-tiempo"></span>
      </form>
    </div>

    <div id="resultado" class="card">
      <div id="banner" class="banner"></div>
      <div class="grid" id="metricas"></div>
      <div>
        <strong>Observaciones y detalles</strong>
        <ul id="lista-obs"></ul>
      </div>
    </div>
  </div>

  <script>
    const ENDPOINTS = {
      ifrss: "/revisar-ifrss",
      carta_asignacion: "/revisar-carta-asignacion",
    };

    const SUBTITULOS = {
      ifrss: "Validación de estructura, extensión, tipografía y elementos visuales.",
      carta_asignacion: "Revisión de 1 sola hoja: presencia de firma y calidad/legibilidad del escaneo.",
    };

    const form = document.getElementById("form-ifrss");
    const tipoDoc = document.getElementById("tipo-documento");
    const subtitulo = document.getElementById("subtitulo");
    const btn = document.getElementById("btn-enviar");
    const estadoTiempo = document.getElementById("estado-tiempo");
    const resBox = document.getElementById("resultado");
    const banner = document.getElementById("banner");
    const metricas = document.getElementById("metricas");
    const listaObs = document.getElementById("lista-obs");

    tipoDoc.addEventListener("change", () => {
      subtitulo.textContent = SUBTITULOS[tipoDoc.value] || SUBTITULOS.ifrss;
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const input = document.getElementById("archivo");
      if (!input.files.length) return;

      const tipo = tipoDoc.value;
      const endpoint = ENDPOINTS[tipo] || ENDPOINTS.ifrss;

      btn.disabled = true;
      btn.textContent = "Revisando...";
      resBox.style.display = "none";

      let segundos = 0;
      estadoTiempo.textContent = "Esto puede tardar unos segundos... (0s)";

      const intervalo = setInterval(() => {
        segundos += 1;
        if (segundos >= 10) {
          estadoTiempo.textContent = `Esto puede tardar un poco más si hay alta demanda... (${segundos}s)`;
        } else {
          estadoTiempo.textContent = `Esto puede tardar unos segundos... (${segundos}s)`;
        }
      }, 1000);

      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 60000);

      const fd = new FormData();
      fd.append("archivo", input.files[0]);

      try {
        const resp = await fetch(endpoint, {
          method: "POST",
          body: fd,
          signal: controller.signal,
        });
        clearTimeout(timer);
        clearInterval(intervalo);

        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "Error al revisar el archivo");

        if (tipo === "carta_asignacion") {
          const esValido = Boolean(
            data.es_una_sola_hoja && data.tiene_firma && data.escaneo_correcto
          );
          banner.className = "banner " + (esValido ? "cumple" : "observaciones");
          banner.textContent = esValido
            ? "Carta de asignación válida: 1 hoja, con firma y escaneo legible."
            : "Carta de asignación con observaciones: revisa los puntos señalados.";

          metricas.innerHTML = `
            <div class="stat"><small>Una sola hoja</small><strong>${data.es_una_sola_hoja ? "Sí" : "No"}</strong></div>
            <div class="stat"><small>Firma</small><strong>${data.tiene_firma ? "Detectada" : "No detectada"}</strong></div>
            <div class="stat"><small>Calidad de escaneo</small><strong>${data.escaneo_correcto ? "Correcto" : "Revisar"}</strong></div>
          `;

          listaObs.innerHTML = "";
          const li = document.createElement("li");
          li.textContent = data.observacion || "Sin observaciones adicionales.";
          listaObs.appendChild(li);
        } else {
          const esValido = data.estado_final === "CUMPLE";
          banner.className = "banner " + (esValido ? "cumple" : "observaciones");
          banner.textContent = esValido
            ? "Archivo válido: el documento cumple con los criterios evaluados."
            : "Archivo con observaciones: revisa los puntos señalados a continuación.";

          metricas.innerHTML = `
            <div class="stat"><small>Palabras aprox.</small><strong>${data.conteo_palabras_aprox}</strong></div>
            <div class="stat"><small>Fuente Arial</small><strong>${data.cumple_fuente_arial ? "Sí" : "Revisar"} (${(data.fuentes_detectadas || []).join(", ") || "N/D"})</strong></div>
            <div class="stat"><small>Firma asesor</small><strong>${data.tiene_firma_asesor ? "Detectada" : "No detectada"}</strong></div>
            <div class="stat"><small>Sin adornos/marcos</small><strong>${data.sin_enmarcados_ni_adornos ? "Sí" : "No"}</strong></div>
          `;

          listaObs.innerHTML = "";
          const obs = data.observaciones && data.observaciones.length
            ? data.observaciones
            : ["Sin observaciones pendientes."];
          for (const item of obs) {
            const li = document.createElement("li");
            li.textContent = item;
            listaObs.appendChild(li);
          }
        }

        estadoTiempo.textContent = `Listo en ${segundos}s`;
        resBox.style.display = "block";
      } catch (err) {
        clearTimeout(timer);
        clearInterval(intervalo);
        const msg = err.name === "AbortError"
          ? "La revisión tardó demasiado y se canceló. Intenta de nuevo."
          : err.message;
        banner.className = "banner observaciones";
        banner.textContent = "Error: " + msg;
        metricas.innerHTML = "";
        listaObs.innerHTML = "";
        estadoTiempo.textContent = "";
        resBox.style.display = "block";
      } finally {
        btn.disabled = false;
        btn.textContent = "Revisar PDF";
      }
    });
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def inicio() -> str:
    return HTML_UI


@app.post("/revisar-ifrss", response_model=DictamenIFRSS)
async def revisar_ifrss(archivo: UploadFile = File(...)) -> DictamenIFRSS:
    if not archivo.filename or not archivo.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe tener extensión .pdf.")

    pdf_bytes = await archivo.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="El archivo PDF está vacío.")

    try:
        datos_pdf = extraer_texto_y_conteo(pdf_bytes)
        resultado_reglas = evaluar_reglas_ifrss(datos_pdf)
        
        imagenes_png = await asyncio.to_thread(
            renderizar_paginas_a_png,
            pdf_bytes,
            3,
            85,
        )
        resultado_visual = await asyncio.to_thread(revisar_visualmente_ifrss, imagenes_png)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al procesar el documento: {exc}") from exc

    fuentes_ok = resultado_reglas.get("fuente_arial_ok", False)
    cumple_fuente_arial = fuentes_ok or resultado_visual.apariencia_fuente_arial
    observaciones = list(resultado_reglas["observaciones"])

    if resultado_visual.observacion_visual:
        observaciones.append(f"Revisión visual: {resultado_visual.observacion_visual}")

    if resultado_visual.revision_visual_pendiente:
        observaciones.append(
            "Firma del asesor y sello/membrete probatorio no verificados por revisión visual pendiente."
        )
    else:
        if not resultado_visual.tiene_firma_asesor:
            observaciones.append("No se detectó firma del asesor en las páginas revisadas.")
        if not resultado_visual.tiene_sello_o_membrete_probatorio:
            observaciones.append(
                "No se detectó sello o membrete en documentos probatorios/constancias."
            )
        if not resultado_visual.sin_enmarcados_ni_adornos:
            observaciones.append(
                "Se detectaron posibles enmarcados o adornos en el diseño de las páginas."
            )

    firma_ok = True if resultado_visual.revision_visual_pendiente else resultado_visual.tiene_firma_asesor
    adornos_ok = True if resultado_visual.revision_visual_pendiente else resultado_visual.sin_enmarcados_ni_adornos

    cumple_todo = (
        resultado_reglas["cumple_estructura_basica"]
        and len(resultado_reglas["excede_limites_extension"]) == 0
        and cumple_fuente_arial
        and firma_ok
        and adornos_ok
    )

    estado_final = "CUMPLE" if cumple_todo else "OBSERVACIONES"

    return DictamenIFRSS(
        secciones_detectadas=resultado_reglas["secciones_detectadas"],
        secciones_faltantes=resultado_reglas["secciones_faltantes"],
        conteo_palabras_aprox=resultado_reglas["conteo_palabras_aprox"],
        excede_limites_extension=resultado_reglas["excede_limites_extension"],
        cumple_estructura_basica=resultado_reglas["cumple_estructura_basica"],
        fuentes_detectadas=datos_pdf.get("fuentes_detectadas", []),
        cumple_fuente_arial=cumple_fuente_arial,
        tiene_firma_asesor=resultado_visual.tiene_firma_asesor,
        tiene_sello_o_membrete_probatorio=resultado_visual.tiene_sello_o_membrete_probatorio,
        sin_enmarcados_ni_adornos=resultado_visual.sin_enmarcados_ni_adornos,
        observacion_visual=resultado_visual.observacion_visual,
        estado_final=estado_final,
        observaciones=observaciones,
    )

@app.post("/revisar-carta-asignacion")
async def revisar_carta_asignacion(archivo: UploadFile = File(...)):
    nombre = (archivo.filename or "").lower()
    es_pdf = (
        archivo.content_type in ("application/pdf", "application/octet-stream")
        or nombre.endswith(".pdf")
    )
    if not es_pdf:
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF.")

    pdf_bytes = await archivo.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")

    try:
        resultado = await asyncio.to_thread(revisar_carta_asignacion_bytes, pdf_bytes)
        return resultado
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Error al revisar la carta de asignación: {exc}",
        ) from exc