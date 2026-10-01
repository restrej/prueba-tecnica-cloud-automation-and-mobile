"""
Genera el documento entregable (PDF) a partir de las respuestas en Markdown.

Flujo:
    docs/respuestas/*.md  --(markdown)-->  HTML  --(Chromium/Playwright)-->  PDF

Uso (desde la raíz del repo, con el entorno virtual activo):
    pip install markdown
    npm install mermaid@11            # opcional: dibuja los diagramas
    python docs/entregable/build_pdf.py --mermaid node_modules/mermaid/dist/mermaid.min.js

Salida: docs/entregable/Prueba_Tecnica_Senior_QA_LogiTrack.pdf
"""

# argparse: leer opciones de la línea de comandos.
import argparse

# base64: incrustar las imágenes dentro del HTML (el PDF queda autocontenido).
import base64

# html: escapar texto para el HTML; re: expresiones regulares.
import html
import re

# date: fecha en la portada.
from datetime import date
from pathlib import Path

# markdown: convierte Markdown a HTML.
import markdown

# Playwright: abre el HTML en Chromium y lo "imprime" como PDF.
from playwright.sync_api import sync_playwright

# Rutas del proyecto.
ROOT = Path(__file__).resolve().parents[2]
ANSWERS_DIR = ROOT / "docs" / "respuestas"
IMG_DIR = ROOT / "docs" / "img"
OUTPUT = ROOT / "docs" / "entregable" / "Prueba_Tecnica_Senior_QA_LogiTrack.pdf"

# Estilos del documento (tamaño carta, tipografía legible, tablas y código).
CSS = """
@page { size: Letter; margin: 16mm 14mm 18mm 14mm; }
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 9.6pt; color: #1d2433; line-height: 1.42; }
h1 { font-size: 19pt; color: #14365d; border-bottom: 3px solid #1f6feb; padding-bottom: 4px;
     page-break-before: always; margin-top: 0; }
h2 { font-size: 13pt; color: #14365d; margin-top: 18px; border-bottom: 1px solid #c9d4e3; padding-bottom: 2px; }
h3 { font-size: 11pt; color: #1f3a5f; margin-top: 14px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 8.4pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th { background: #14365d; color: #fff; text-align: left; padding: 4px 5px; }
td { border: 1px solid #d0d7e2; padding: 3px 5px; vertical-align: top; }
tr:nth-child(even) td { background: #f5f8fc; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.2pt; background: #eef2f7; padding: 0 2px; border-radius: 2px; }
pre { background: #0f1b2d; color: #e6edf3; padding: 8px 10px; border-radius: 5px; font-size: 7.8pt;
      line-height: 1.35; white-space: pre-wrap; word-break: break-word; page-break-inside: avoid; }
pre code { background: none; color: inherit; padding: 0; font-size: inherit; }
blockquote { border-left: 4px solid #1f6feb; margin: 8px 0; padding: 4px 12px; background: #f0f6ff; }
.mermaid { text-align: center; margin: 10px 0; page-break-inside: avoid; }
.mermaid svg { max-width: 100%; max-height: 190mm; height: auto; }
img.evidence { max-width: 100%; max-height: 95mm; display: block; margin-left: auto; margin-right: auto; border: 1px solid #c9d4e3; border-radius: 4px; margin: 6px 0; }
figure { margin: 8px 0 14px; page-break-inside: avoid; }
figcaption { font-size: 8.4pt; color: #55627a; text-align: center; }
.cover { height: 235mm; display: flex; flex-direction: column; justify-content: center; }
.cover h1 { page-break-before: avoid; border: none; font-size: 28pt; }
.cover .sub { font-size: 14pt; color: #1f6feb; margin-bottom: 30px; }
.cover table { width: 75%; font-size: 10pt; }
.toc h1 { page-break-before: always; }
.toc ol { font-size: 11pt; line-height: 1.9; }
"""

# Orden y títulos de las secciones del documento.
SECTIONS = [
    ("01_estrategia.md", "Parte 1. Estrategia de calidad y factibilidad (20 pts)"),
    ("02_casos_de_prueba.md", "Parte 2. Diseño de casos de prueba (15 pts)"),
    ("03_cicd.md", "Parte 3. Automatización y CI/CD (15 pts)"),
    ("04_automatizacion.md", "Parte 4. Automatización técnica (25 pts)"),
    ("05_rendimiento_seguridad.md", "Parte 5. Rendimiento y seguridad (10 pts)"),
    ("06_cloud_troubleshooting.md", "Parte 6. Cloud y troubleshooting (10 pts)"),
    ("07_comunicacion.md", "Parte 7. Comunicación (5 pts)"),
    ("08_bonus_arquitectura.md", "Bonus. Arquitectura y riesgos (20 pts)"),
]

# Capturas de evidencia (archivo, descripción).
EVIDENCE = [
    ("web-login.png", "Pantalla de login del Centro de Control (objetivo del Ejercicio B)."),
    ("web-login-error.png", "Credenciales inválidas: mensaje genérico (prueba automatizada)."),
    ("web-login-validaciones.png", "Validaciones de campos: caracteres especiales y contraseña vacía."),
    ("web-dashboard.png", "Landing page tras login exitoso (verificada por el happy path)."),
    ("pytest-html-report.png", "Reporte HTML de pytest: 148 pruebas ejecutadas, 0 fallidas."),
    ("zap-report.png", "Reporte de OWASP ZAP (DAST) sobre la API: 0 alertas FAIL."),
]


def image_tag(path: Path, caption: str) -> str:
    """Devuelve un <figure> con la imagen incrustada en base64 (si existe)."""
    if not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return (f'<figure><img class="evidence" src="data:image/png;base64,{data}">'
            f"<figcaption>{html.escape(caption)}</figcaption></figure>")


def md_to_html(text: str) -> str:
    """
    Convierte Markdown a HTML. Los bloques ```mermaid se transforman en
    <div class="mermaid"> para que la librería Mermaid los dibuje.
    """
    def mermaid_block(match: re.Match) -> str:
        return f'\n<div class="mermaid">\n{html.escape(match.group(1))}\n</div>\n'

    text = re.sub(r"```mermaid\n(.*?)```", mermaid_block, text, flags=re.S)
    return markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists", "md_in_html"])


def build_html(mermaid_js: str | None) -> str:
    """Arma el HTML completo: portada, índice, secciones y anexo de evidencias."""
    cover = f"""
    <section class="cover">
      <h1>Prueba Técnica: Senior QA Engineer</h1>
      <div class="sub">Cloud, Automation &amp; Mobile · LogiTrack</div>
      <table>
        <tr><td><b>Formato</b></td><td>Respuestas, diagramas, código y capturas</td></tr>
        <tr><td><b>Repositorio</b></td>
            <td>github.com/restrej/prueba-tecnica-cloud-automation-and-mobile</td></tr>
        <tr><td><b>Stack</b></td><td>Python + pytest · Playwright · Appium · k6 · OWASP ZAP · GitHub Actions</td></tr>
        <tr><td><b>Fecha</b></td><td>{date.today().isoformat()}</td></tr>
      </table>
    </section>"""

    toc_items = "".join(f"<li>{html.escape(title)}</li>" for _, title in SECTIONS)
    toc = f"""
    <section class="toc"><h1>Contenido</h1><ol>{toc_items}<li>Anexo A. Implementación y cómo ejecutarla</li>
    <li>Anexo B. Evidencias de ejecución</li></ol>
    <p>Todo el código citado está en el repositorio y se ejecutó localmente: 148 pruebas automatizadas en verde,
    prueba de carga k6 de 5 minutos, escaneo DAST con OWASP ZAP y SAST con Bandit. La guía
    <code>docs/PASO_A_PASO.md</code> explica cómo reproducir cada resultado.</p></section>"""

    body = ""
    for filename, _title in SECTIONS:
        body += md_to_html((ANSWERS_DIR / filename).read_text(encoding="utf-8"))

    annex_a = md_to_html("# Anexo A. Implementación y cómo ejecutarla\n\n" + _readme_excerpt())
    annex_b = "<h1>Anexo B. Evidencias de ejecución</h1>" + "".join(
        image_tag(IMG_DIR / name, caption) for name, caption in EVIDENCE
    )

    script = ""
    if mermaid_js:
        script = (f"<script>{Path(mermaid_js).read_text(encoding='utf-8')}</script>"
                  "<script>mermaid.initialize({startOnLoad:true, theme:'default', "
                  "flowchart:{htmlLabels:true, useMaxWidth:true}});</script>")

    return (f"<!doctype html><html lang='es'><head><meta charset='utf-8'><style>{CSS}</style></head>"
            f"<body>{cover}{toc}{body}{annex_a}{annex_b}{script}</body></html>")


def _readme_excerpt() -> str:
    """Toma del README las secciones de stack, estructura, mapa y resultados."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    wanted = ["## Stack tecnológico", "## Estructura del repositorio", "## Mapa: partes del PDF",
              "## Resultados de la ejecución local", "## Limitaciones conocidas"]
    chunks = re.split(r"(?m)^(?=## )", readme)
    return "\n".join(c.replace("## ", "## ", 1) for c in chunks if any(c.startswith(w) for w in wanted))


def main() -> None:
    """Genera el HTML, lo renderiza en Chromium y guarda el PDF."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mermaid", help="Ruta a mermaid.min.js para dibujar los diagramas")
    args = parser.parse_args()

    html_doc = build_html(args.mermaid)
    html_path = OUTPUT.with_suffix(".html")
    html_path.write_text(html_doc, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.as_uri())
        if args.mermaid:
            # Esperamos a que Mermaid termine de dibujar TODOS los diagramas.
            page.wait_for_function(
                "[...document.querySelectorAll('.mermaid')].every(d => d.querySelector('svg'))",
                timeout=30000,
            )
        page.pdf(
            path=str(OUTPUT), format="Letter", print_background=True,
            display_header_footer=True,
            header_template="<div></div>",
            footer_template=("<div style='font-size:7pt;width:100%;text-align:center;color:#7a869a'>"
                             "LogiTrack · Prueba Técnica Senior QA · Página <span class='pageNumber'></span>"
                             " de <span class='totalPages'></span></div>"),
            margin={"top": "16mm", "bottom": "18mm", "left": "14mm", "right": "14mm"},
        )
        browser.close()
    html_path.unlink()
    print(f"PDF generado: {OUTPUT}")


if __name__ == "__main__":
    main()
