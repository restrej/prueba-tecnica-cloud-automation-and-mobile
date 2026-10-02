"""
Genera el PDF entregable a partir de docs/entregable/Prueba_Tecnica_LogiTrack.md

Pasos: Markdown -> HTML (con imágenes y diagramas) -> PDF (con el navegador de Playwright).

Uso, desde la raíz del repositorio y con el entorno virtual activo:
    pip install markdown
    npm install mermaid@11          # dibuja los diagramas (opcional)
    sudo apt install poppler-utils  # pdfunite: une la portada con el contenido
    python docs/entregable/build_pdf.py --mermaid node_modules/mermaid/dist/mermaid.min.js
"""

import argparse
import base64
import html
import re
import subprocess
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

# Rutas: el Markdown de origen, la raíz del repo y el PDF de salida.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / "Prueba_Tecnica_LogiTrack.md"
OUTPUT = HERE / "Prueba_Tecnica_LogiTrack.pdf"

# Datos de la portada.
COVER = {
    "titulo": "Prueba Técnica",
    "cargo": "Senior QA Engineer — Cloud, Automation &amp; Mobile",
    "subtitulo": "Solución",
    "empresa": "LogiTrack",
    "autor": "Juan Carlos Restrepo",
    "fecha": "Octubre de 2026",
}
DOC_NAME = "Prueba Técnica Senior QA Engineer · LogiTrack · Solución"

# Paleta única: negro (títulos), azul oscuro (subtítulos y encabezados de tabla),
# grises (textos de apoyo y bordes).
CSS = """
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 9.8pt; color: #1d2433; line-height: 1.5; }
h1 { font-size: 17pt; font-weight: bold; color: #000; border-bottom: 2px solid #000; padding-bottom: 4px;
     margin: 26px 0 12px; }
body > h1:first-child, .junto > h1:first-child { margin-top: 0; }
h2 { font-size: 12.5pt; font-weight: bold; color: #0b2e59; margin-top: 22px; padding-bottom: 3px;
     border-bottom: 1px solid #d9dce1; }
h3 { font-size: 11pt; font-weight: bold; color: #0b2e59; margin-top: 18px; }
.junto { break-inside: avoid; }          /* el subtítulo no queda solo al final de una página */
.tabla-entera { break-inside: avoid; }   /* una tabla que cabe en una hoja no se parte */
thead { display: table-header-group; }   /* si una tabla es más alta que una hoja, repite el encabezado */
p em:only-child { color: #5f6670; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 12px; font-size: 8.4pt; line-height: 1.4; }
tr { break-inside: avoid; }
th { background: #0b2e59; color: #fff; text-align: left; padding: 5px 6px; border: 1px solid #0b2e59; }
td { border: 1px solid #d9dce1; padding: 4px 6px; vertical-align: top; }
tr:nth-child(even) td { background: #f6f7f9; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.3pt; background: #f1f3f5; padding: 0 2px; }
pre { background: #0f1b2d; color: #e6edf3; padding: 8px 10px; border-radius: 5px; font-size: 7.3pt;
      white-space: pre-wrap; word-break: break-word; break-inside: avoid; }
pre code { background: none; color: inherit; padding: 0; font-size: inherit; }
blockquote { border-left: 3px solid #0b2e59; margin: 8px 0; padding: 4px 12px; background: #f6f7f9;
             break-inside: avoid; }
a { color: #0b2e59; }
.mermaid { text-align: center; margin: 8px 0; break-inside: avoid; }
.mermaid svg { max-width: 100%; max-height: 100mm; height: auto; }
figure { margin: 10px 0 14px; text-align: center; break-inside: avoid; }
figure img { max-width: 100%; max-height: 95mm; border: 1px solid #d9dce1; border-radius: 4px; }
figure img.terminal { max-height: none; border: none; }
figcaption { font-size: 8.3pt; color: #5f6670; margin-top: 3px; }
.con-id td:first-child { white-space: nowrap; }
/* Matriz de casos (2.1): 9 columnas en hoja vertical. Ancho automático: cada columna toma al menos el
   ancho de su palabra más larga, así ningún encabezado ni palabra se corta. Celdas un poco más
   compactas y encabezado en 7.9 pt para que la tabla quepa en el ancho de la hoja. */
.matriz th, .matriz td { padding: 4px 3px; }
.matriz th { font-size: 7.9pt; }
.pendiente { border: 2px dashed #d29922; background: #fff8e6; padding: 14px;
             text-align: center; color: #7a5a00; }
"""

COVER_CSS = """
body { font-family: 'DejaVu Sans', Arial, sans-serif; margin: 0; color: #1d2433; }
.portada { height: 225mm; display: flex; flex-direction: column; justify-content: center;
           text-align: center; }
.portada .titulo { font-size: 30pt; font-weight: bold; color: #000; }
.portada .cargo { font-size: 14pt; color: #0b2e59; font-weight: bold; margin-top: 8px; }
.portada .linea { width: 70mm; border-top: 2px solid #000; margin: 26px auto; }
.portada .subtitulo { font-size: 20pt; font-weight: bold; color: #0b2e59; }
.portada .empresa { font-size: 12pt; color: #5f6670; margin-top: 6px; }
.portada .autor { font-size: 13pt; font-weight: bold; margin-top: 60mm; }
.portada .fecha { font-size: 11pt; color: #5f6670; margin-top: 6px; }
"""


def compose_mobile_strip() -> None:
    """
    Si existen capturas de Appium (01-login.png ... 05-guia-generada.png) en docs/img/mobile/ o en docs/img/,
    las une en una sola imagen horizontal docs/img/mobile-flujo.png (requiere Pillow).
    """
    img_dir = ROOT / "docs" / "img"
    # Se aceptan en docs/img/mobile/ o directamente en docs/img/ (01-login.png ... 05-guia-generada.png).
    shots = sorted((img_dir / "mobile").glob("0*.png")) or sorted(img_dir.glob("0[1-5]-*.png"))
    if not shots:
        return
    from PIL import Image  # import local: sólo se necesita si hay capturas móviles

    height = 900
    images = [Image.open(path) for path in shots]
    images = [img.resize((int(img.width * height / img.height), height)) for img in images]
    strip = Image.new("RGB", (sum(img.width for img in images) + 20 * (len(images) - 1), height), "white")
    x = 0
    for img in images:
        strip.paste(img, (x, 0))
        x += img.width + 20
    strip.save(ROOT / "docs" / "img" / "mobile-flujo.png")


def insert_files(text: str) -> str:
    """Reemplaza {{archivo:ruta}} por el contenido COMPLETO de ese archivo, como bloque de código."""
    def replace(match: re.Match) -> str:
        path = ROOT / match.group(1)
        language = "yaml" if path.suffix in (".yml", ".yaml") else ""
        return f"```{language}\n{path.read_text(encoding='utf-8').rstrip()}\n```"
    return re.sub(r"\{\{archivo:(.+?)\}\}", replace, text)


FIGURE_COUNTER = {"n": 0}


def image_html(match: re.Match) -> str:
    """Convierte ![texto](ruta) en una figura numerada con la imagen incrustada (o un aviso si falta)."""
    caption, relative = match.group(1), match.group(2)
    path = (SOURCE.parent / relative).resolve()
    if not path.exists():
        return (f'\n<div class="pendiente">Captura pendiente: <b>{html.escape(caption)}</b><br>'
                f"(agregar <code>{html.escape(path.name)}</code> en <code>docs/img/</code>)</div>\n")
    FIGURE_COUNTER["n"] += 1
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    attrs = ""
    if path.name.startswith("term-"):
        # Capturas de terminal (dibujadas al doble de resolución): ancho fijo para que la letra
        # quede de unos 7 puntos en el papel, legible sin hacer zoom.
        from PIL import Image  # import local: sólo para medir la imagen
        width_mm = min(Image.open(path).width / 2 * 0.176, 172)
        attrs = f' class="terminal" style="width:{width_mm:.0f}mm"'
    number = FIGURE_COUNTER["n"]
    return (f'\n<figure><img{attrs} src="data:image/png;base64,{data}">'
            f"<figcaption><b>Figura {number}.</b> {html.escape(caption)}</figcaption></figure>\n")


def build_html(mermaid_js: str | None) -> str:
    """Arma el HTML completo del documento."""
    text = insert_files(SOURCE.read_text(encoding="utf-8"))
    # Bloques ```mermaid -> <div class="mermaid"> (los dibuja la librería Mermaid).
    text = re.sub(r"```mermaid\n(.*?)```",
                  lambda m: f'\n<div class="mermaid">\n{html.escape(m.group(1))}\n</div>\n', text, flags=re.S)
    # Imágenes en su propia línea -> figuras incrustadas.
    text = re.sub(r"(?m)^!\[(.*?)\]\((.*?)\)\s*$", image_html, text)
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    # Tablas cuya primera columna es "ID": el ID no se parte en dos líneas.
    id_header = "<table>\n<thead>\n<tr>\n<th>ID</th>"
    body = body.replace(id_header, id_header.replace("<table>", '<table class="con-id">'))
    # La matriz de casos (2.1) lleva su propio estilo (ver .matriz en CSS).
    body = re.sub(r'<table class="con-id">(?=(?:(?!</table>).)*?TC-01)', '<table class="con-id matriz">',
                  body, flags=re.S)
    script = ""
    if mermaid_js:
        script = (f"<script>{Path(mermaid_js).read_text(encoding='utf-8')}</script>"
                  "<script>mermaid.initialize({startOnLoad: true, theme: 'default'});</script>")
    return f"<!doctype html><html lang='es'><head><meta charset='utf-8'><style>{CSS}</style></head>" \
           f"<body>{body}{script}</body></html>"


# Organiza las páginas antes de imprimir (sin dejar grandes espacios en blanco):
#  - cada subtítulo (h2/h3) se agrupa con su "Qué piden" y el primer bloque si es corto; si un h2 va
#    seguido de un h3 (Ejercicio C -> C.1) o un h1 de un h2 (Parte -> 1.1), van juntos;
#  - cada tabla que cabe en una hoja se mantiene entera (pasa completa a la hoja siguiente si no cabe).
KEEP_TOGETHER_JS = """
() => {
  const PAGE_PX = 880;  // alto útil aproximado de una hoja, en píxeles de la ventana
  const isAsk = (n) => n.tagName === 'P' && n.querySelector('em')
    && n.textContent.trim().startsWith('Qué piden');
  document.querySelectorAll('table').forEach((table) => {
    if (table.offsetHeight < PAGE_PX) {
      const wrap = document.createElement('div');
      wrap.className = 'tabla-entera';
      table.before(wrap);
      wrap.appendChild(table);
    }
  });
  document.querySelectorAll('h2, h3').forEach((h) => {
    if (h.parentNode.classList.contains('junto')) return;  // ya quedó agrupado con su título superior
    const box = document.createElement('div');
    box.className = 'junto';
    h.before(box);
    const previous = box.previousElementSibling;
    if (previous && previous.tagName === 'H1') box.appendChild(previous);
    box.appendChild(h);
    let next = box.nextElementSibling;
    if (h.tagName === 'H2' && next && next.tagName === 'H3') {
      box.appendChild(next);
      next = box.nextElementSibling;
    }
    while (next && isAsk(next)) { box.appendChild(next); next = box.nextElementSibling; }
    const short = next && (next.offsetHeight < 160 || next.tagName === 'BLOCKQUOTE'
      || next.classList.contains('tabla-entera'));
    if (short && !/^H[1-3]$/.test(next.tagName)) box.appendChild(next);
  });
}
"""


# Márgenes amplios: el texto respira más.
MARGIN = {"top": "22mm", "bottom": "20mm", "left": "20mm", "right": "20mm"}
HEADER = ("<div style='font-size:7pt;width:100%;margin:0 20mm;padding-bottom:3px;color:#8a9099;"
          f"border-bottom:0.5px solid #d9dce1;text-align:right'>{DOC_NAME}</div>")
FOOTER = ("<div style='font-size:7pt;width:100%;text-align:center;color:#8a9099'>"
          "Página <span class='pageNumber'></span> de <span class='totalPages'></span></div>")


def cover_html() -> str:
    """Portada sencilla: título, cargo, "Solución", autor y fecha, centrados."""
    c = COVER
    return (f"<!doctype html><html lang='es'><head><meta charset='utf-8'><style>{COVER_CSS}</style>"
            f"</head><body><div class='portada'><div class='titulo'>{c['titulo']}</div>"
            f"<div class='cargo'>{c['cargo']}</div>"
            f"<div class='linea'></div><div class='subtitulo'>{c['subtitulo']}</div>"
            f"<div class='empresa'>{c['empresa']}</div><div class='autor'>{c['autor']}</div>"
            f"<div class='fecha'>{c['fecha']}</div></div></body></html>")


def main() -> None:
    """Genera la portada y el contenido como PDF y los une (la portada no lleva encabezado ni número)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mermaid", help="Ruta a mermaid.min.js para dibujar los diagramas")
    args = parser.parse_args()

    compose_mobile_strip()
    html_path = OUTPUT.with_suffix(".html")
    html_path.write_text(build_html(args.mermaid), encoding="utf-8")
    cover_pdf, body_pdf = OUTPUT.with_name("_portada.pdf"), OUTPUT.with_name("_contenido.pdf")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # Ancho de la ventana = ancho útil de la hoja (Carta menos márgenes),
        # para medir los bloques como en el papel.
        page = browser.new_page(viewport={"width": 665, "height": 900})
        page.set_content(cover_html())
        page.pdf(path=str(cover_pdf), format="Letter", print_background=True, margin=MARGIN)
        page.goto(html_path.as_uri())
        if args.mermaid:
            # Esperamos a que todos los diagramas estén dibujados.
            page.wait_for_function(
                "[...document.querySelectorAll('.mermaid')].every(d => d.querySelector('svg'))", timeout=30000
            )
        page.evaluate(KEEP_TOGETHER_JS)
        page.pdf(path=str(body_pdf), format="Letter", print_background=True, display_header_footer=True,
                 header_template=HEADER, footer_template=FOOTER, margin=MARGIN)
        browser.close()
    # Une portada + contenido (pdfunite viene con poppler-utils).
    # Las rutas son archivos que este mismo script acaba de crear (no hay datos externos).
    subprocess.run(["pdfunite", str(cover_pdf), str(body_pdf), str(OUTPUT)], check=True)  # noqa: S603, S607
    for temp in (html_path, cover_pdf, body_pdf):
        temp.unlink()
    print(f"PDF generado: {OUTPUT}")


if __name__ == "__main__":
    main()
