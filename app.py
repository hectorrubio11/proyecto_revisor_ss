import asyncio
from pathlib import Path
from fastapi.staticfiles import StaticFiles
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

BASE_DIR = Path(__file__).resolve().parent
IMG_DIR = BASE_DIR / "img"
if IMG_DIR.is_dir():
    app.mount("/img", StaticFiles(directory=str(IMG_DIR)), name="img")
HTML_UI = """<!DOCTYPE html>

<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Revisor de Documentos de Servicio Social — UAS / FIMAZ</title>
  <style>
    :root {
      --azul-uas: #0a2b57;
      --azul-uas-hover: #071e3d;
      --oro-uas: #b58d2c;
      --bg: #f4f6f9;
      --card: #ffffff;
      --text: #1e293b;
      --muted: #64748b;
      --border: #d1d5db;
      --ok-bg: #dcfce7;
      --ok-border: #16a34a;
      --ok-text: #14532d;
      --warn-bg: #fef3c7;
      --warn-border: #d97706;
      --warn-text: #78350f;
    }

    *, *::before, *::after {
      box-sizing: border-box;
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    }

    body {
      margin: 0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      background: var(--bg);
      color: var(--text);
    }

    .topbar {
      background: var(--azul-uas);
      border-bottom: 3px solid var(--oro-uas);
      color: #ffffff;
      padding: 10px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }

    .topbar-left,
    .topbar-right {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .topbar-center {
      text-align: center;
      flex: 1;
    }

    .topbar-title {
      margin: 0;
      font-size: 1.25rem;
      font-weight: 700;
      line-height: 1.25;
    }

    .topbar-subtitle {
      margin: 2px 0 0;
      font-size: 0.8rem;
      color: #dbeafe;
    }

    .logo-uas {
      height: 44px;
      width: auto;
      object-fit: contain;
    }

    .logo-der {
      height: 42px;
      width: auto;
      object-fit: contain;
      background: #ffffff;
      padding: 3px 6px;
      border-radius: 4px;
    }

    .main-wrap {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 2rem 1rem;
    }

    .container {
      width: 100%;
      max-width: 780px;
    }

    .card {
      background: var(--card);
      border: 1px solid #e2e8f0;
      border-top: 4px solid var(--oro-uas);
      border-radius: 10px;
      padding: 1.5rem 1.75rem;
      box-shadow: 0 8px 24px rgba(10, 43, 87, 0.08);
      margin-bottom: 1.25rem;
    }

    .form-group {
      margin-bottom: 1.15rem;
    }

    .form-label {
      display: block;
      font-weight: 700;
      font-size: 0.92rem;
      margin-bottom: 0.45rem;
      color: var(--text);
    }

    .sub {
      margin: 0.35rem 0 0;
      color: var(--muted);
      font-size: 0.85rem;
    }

    select.form-select {
      width: 100%;
      padding: 0.6rem 0.75rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: #ffffff;
      color: var(--text);
      font-size: 0.95rem;
    }

    .file-input-hidden {
      display: none;
    }

    .file-picker {
      display: flex;
      align-items: center;
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 6px;
      overflow: hidden;
      background: #ffffff;
    }

    .file-btn {
      background: #f3f4f6;
      color: var(--text);
      border: none;
      border-right: 1px solid var(--border);
      padding: 0.6rem 0.95rem;
      font-size: 0.88rem;
      font-weight: 500;
      cursor: pointer;
      white-space: nowrap;
    }

    .file-btn:hover {
      background: #e5e7eb;
    }

    .file-name {
      padding: 0.6rem 0.85rem;
      font-size: 0.88rem;
      color: var(--muted);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .help-text {
      margin: 0.35rem 0 0;
      font-size: 0.78rem;
      color: var(--muted);
    }

    .action-row {
      display: flex;
      align-items: center;
      gap: 0.85rem;
      flex-wrap: wrap;
      margin-top: 0.5rem;
    }

    button.btn-submit {
      flex: 1;
      min-width: 180px;
      background: var(--azul-uas);
      color: #ffffff;
      border: none;
      padding: 0.7rem 1.25rem;
      border-radius: 6px;
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
    }

    button.btn-submit:hover {
      background: var(--azul-uas-hover);
    }

    button.btn-submit:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }

    #estado-tiempo {
      color: var(--muted);
      font-size: 0.88rem;
    }

    .banner {
      padding: 1rem 1.2rem;
      border-radius: 8px;
      border-left: 5px solid;
      font-weight: 600;
      margin-bottom: 1rem;
    }

    .banner.cumple {
      background: var(--ok-bg);
      border-color: var(--ok-border);
      color: var(--ok-text);
    }

    .banner.observaciones {
      background: var(--warn-bg);
      border-color: var(--warn-border);
      color: var(--warn-text);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 0.75rem;
      margin-bottom: 1rem;
    }

    .stat {
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 0.75rem;
      background: #f8fafc;
    }

    .stat small {
      display: block;
      color: var(--muted);
      margin-bottom: 0.2rem;
    }

    ul {
      margin: 0.4rem 0 0;
      padding-left: 1.2rem;
    }

    li {
      margin-bottom: 0.35rem;
    }

    #resultado {
      display: none;
    }

    .footer-text {
      margin-top: 0.75rem;
      font-size: 0.8rem;
      color: var(--muted);
      text-align: center;
    }

    @media (max-width: 640px) {
      .topbar {
        padding: 10px 12px;
      }
      .topbar-title {
        font-size: 1rem;
      }
      .topbar-subtitle {
        font-size: 0.72rem;
      }
      .logo-izq,
      .logo-der {
        height: 34px;
      }
      .card {
        padding: 1.2rem 1rem;
      }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-left">
      <img src="img/Logo_Uas.svg.webp" alt="Escudo UAS" class="logo-uas" />
    </div>

    <div class="topbar-center">
      <h1 class="topbar-title">Revisor de Documentos de Servicio Social</h1>
      <p class="topbar-subtitle">Universidad Autónoma de Sinaloa · Facultad de Informática Mazatlán</p>
    </div>

    <div class="topbar-right">
      <!-- Pon aquí las imágenes derechas -->
      <img src="img/Uas_logo.jpg" alt="Logo UAS" class="logo-der" />
      <img src="img/fimaz-color.png" alt="Logo FIMAZ" class="logo-der" />
    </div>
  </header>

  <main class="main-wrap">
    <div class="container">
      <div class="card">
        <form id="form-ifrss">
          <div class="form-group">
            <label for="tipo-documento" class="form-label">¿Qué documento quieres revisar?</label>
            <select id="tipo-documento" name="tipo_documento" class="form-select" aria-label="Tipo de documento">
              <option value="ifrss" selected>Informe Final IFRSS</option>
              <option value="carta_asignacion">Carta de Asignación</option>
            </select>
            <p id="subtitulo" class="sub">Validación de estructura, extensión, tipografía y elementos visuales.</p>
          </div>

          <div class="form-group">
            <label for="archivo" class="form-label">Documento a revisar (PDF)</label>
            <input type="file" id="archivo" name="archivo" accept="application/pdf,.pdf" class="file-input-hidden" required />
            <div class="file-picker">
              <button type="button" id="btn-seleccionar" class="file-btn">Seleccionar archivo</button>
              <span id="nombre-archivo" class="file-name">Ningún archivo seleccionado</span>
            </div>
            <p class="help-text">Solo PDF, máximo 10 MB.</p>
          </div>

          <div class="action-row">
            <button type="submit" id="btn-enviar" class="btn-submit">Revisar documento</button>
            <span id="estado-tiempo"></span>
          </div>
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

      <footer class="footer-text">
        Universidad Autónoma de Sinaloa · FIMAZ
      </footer>
    </div>
  </main>

  <script>
    const MAX_BYTES = 10 * 1024 * 1024;
    const ENDPOINTS = {
      ifrss: "/revisar-ifrss",
      carta_asignacion: "/revisar-carta-asignacion",
    };

    const SUBTITULOS = {
      ifrss: "Validación de estructura, extensión, tipografía y elementos visuales.",
      carta_asignacion: "Revisión de 1 sola hoja, tamaño regular, presencia de firma y calidad/legibilidad del escaneo.",
    };

    const form = document.getElementById("form-ifrss");
    const tipoDoc = document.getElementById("tipo-documento");
    const subtitulo = document.getElementById("subtitulo");
    const inputArchivo = document.getElementById("archivo");
    const btnSeleccionar = document.getElementById("btn-seleccionar");
    const spanNombre = document.getElementById("nombre-archivo");
    const btn = document.getElementById("btn-enviar");
    const estadoTiempo = document.getElementById("estado-tiempo");
    const resBox = document.getElementById("resultado");
    const banner = document.getElementById("banner");
    const metricas = document.getElementById("metricas");
    const listaObs = document.getElementById("lista-obs");

    tipoDoc.addEventListener("change", () => {
      subtitulo.textContent = SUBTITULOS[tipoDoc.value] || SUBTITULOS.ifrss;
    });

    btnSeleccionar.addEventListener("click", () => inputArchivo.click());

    inputArchivo.addEventListener("change", () => {
      const file = inputArchivo.files[0];
      spanNombre.textContent = file ? file.name : "Ningún archivo seleccionado";
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!inputArchivo.files.length) return;

      const file = inputArchivo.files[0];
      if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
        resBox.style.display = "block";
        banner.className = "banner observaciones";
        banner.textContent = "Error: Solo se permiten archivos en formato PDF.";
        metricas.innerHTML = "";
        listaObs.innerHTML = "";
        estadoTiempo.textContent = "";
        return;
      }

      if (file.size > MAX_BYTES) {
        resBox.style.display = "block";
        banner.className = "banner observaciones";
        banner.textContent = "Error: El archivo supera el límite máximo de 10 MB.";
        metricas.innerHTML = "";
        listaObs.innerHTML = "";
        estadoTiempo.textContent = "";
        return;
      }

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
      fd.append("archivo", file);

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
        btn.textContent = "Revisar documento";
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