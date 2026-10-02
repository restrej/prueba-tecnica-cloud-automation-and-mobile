"""
Genera el PDF entregable a partir de docs/entregable/Prueba_Tecnica_LogiTrack.md

Pasos: Markdown -> HTML (con imágenes y diagramas) -> PDF (con el navegador de Playwright).

Uso, desde la raíz del repositorio y con el entorno virtual activo:
    pip install markdown
    npm install mermaid@11          # dibuja los diagramas (opcional)
    python docs/entregable/build_pdf.py --mermaid node_modules/mermaid/dist/mermaid.min.js
"""

import argparse
import base64
import html
import re
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

# Rutas: el Markdown de origen, la raíz del repo y el PDF de salida.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / "Prueba_Tecnica_LogiTrack.md"
OUTPUT = HERE / "Prueba_Tecnica_LogiTrack.pdf"

# Estilos: letra legible, tablas compactas, código con fondo oscuro.
CSS = """
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 9.8pt; color: #1d2433; line-height: 1.45; }
h1 { font-size: 17pt; font-weight: bold; color: #000; border-bottom: 2px solid #000; padding-bottom: 4px;
     margin-top: 26px; page-break-after: avoid; }
h2 { font-size: 12.5pt; font-weight: bold; color: #0b2e59; margin-top: 18px; border-bottom: 1px solid #c9d4e3; }
h3 { font-size: 11pt; font-weight: bold; color: #0b2e59; }
p em:only-child { color: #55627a; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 12px; font-size: 8.4pt; }
tr { page-break-inside: avoid; }
th { background: #14365d; color: #fff; text-align: left; padding: 4px 5px; }
td { border: 1px solid #d0d7e2; padding: 3px 5px; vertical-align: top; }
tr:nth-child(even) td { background: #f5f8fc; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.3pt; background: #eef2f7; padding: 0 2px; }
pre { background: #0f1b2d; color: #e6edf3; padding: 8px 10px; border-radius: 5px; font-size: 7.9pt;
      white-space: pre-wrap; word-break: break-word; }
pre code { background: none; color: inherit; padding: 0; }
blockquote { border-left: 4px solid #1f6feb; margin: 8px 0; padding: 4px 12px; background: #f0f6ff; }
.mermaid { text-align: center; margin: 8px 0; page-break-inside: avoid; }
.mermaid svg { max-width: 100%; max-height: 100mm; height: auto; }
figure { margin: 8px 0 12px; text-align: center; page-break-inside: avoid; }
figure img { max-width: 100%; max-height: 85mm; border: 1px solid #c9d4e3; border-radius: 4px; }
figcaption { font-size: 8.3pt; color: #55627a; }
.con-id td:first-child { white-space: nowrap; }
.matriz { font-size: 7.6pt; }
.pendiente { border: 2px dashed #d29922; background: #fff8e6; padding: 14px;
             text-align: center; color: #7a5a00; }
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


def image_html(match: re.Match) -> str:
    """Convierte ![texto](ruta) en una figura con la imagen incrustada (o un aviso si falta)."""
    caption, relative = match.group(1), match.group(2)
    path = (SOURCE.parent / relative).resolve()
    if not path.exists():
        return (f'\n<div class="pendiente">Captura pendiente: <b>{html.escape(caption)}</b><br>'
                f"(agregar <code>{html.escape(path.name)}</code> en <code>docs/img/</code>)</div>\n")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return (f'\n<figure><img src="data:image/png;base64,{data}">'
            f"<figcaption>{html.escape(caption)}</figcaption></figure>\n")


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
    body = body.replace("<table>\n<thead>\n<tr>\n<th>ID</th>", '<table class="con-id">\n<thead>\n<tr>\n<th>ID</th>')
    # La matriz de casos (2.1) tiene 9 columnas: letra un poco más pequeña para que quepa.
    body = re.sub(r'<table class="con-id">(?=(?:(?!</table>).)*?TC-01)', '<table class="con-id matriz">', body, flags=re.S)
    script = ""
    if mermaid_js:
        script = (f"<script>{Path(mermaid_js).read_text(encoding='utf-8')}</script>"
                  "<script>mermaid.initialize({startOnLoad: true, theme: 'default'});</script>")
    return f"<!doctype html><html lang='es'><head><meta charset='utf-8'><style>{CSS}</style></head>" \
           f"<body>{body}{script}</body></html>"


def main() -> None:
    """Genera el HTML, lo abre en el navegador y lo guarda como PDF."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mermaid", help="Ruta a mermaid.min.js para dibujar los diagramas")
    args = parser.parse_args()

    compose_mobile_strip()
    html_path = OUTPUT.with_suffix(".html")
    html_path.write_text(build_html(args.mermaid), encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.as_uri())
        if args.mermaid:
            # Esperamos a que todos los diagramas estén dibujados.
            page.wait_for_function(
                "[...document.querySelectorAll('.mermaid')].every(d => d.querySelector('svg'))", timeout=30000
            )
        page.pdf(
            path=str(OUTPUT), format="Letter", print_background=True, display_header_footer=True,
            header_template="<div></div>",
            footer_template=("<div style='font-size:7pt;width:100%;text-align:center;color:#7a869a'>"
                             "Prueba Técnica Senior QA · LogiTrack · <span class='pageNumber'></span>"
                             " / <span class='totalPages'></span></div>"),
            margin={"top": "14mm", "bottom": "16mm", "left": "14mm", "right": "14mm"},
        )
        browser.close()
    html_path.unlink()
    print(f"PDF generado: {OUTPUT}")


if __name__ == "__main__":
    main()
