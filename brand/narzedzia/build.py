import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(__file__).resolve().parent / "strony"


def geometry():
    return (ROOT / "logo" / "logo-geometry.json").read_text()


def data_uri(path):
    return "data:image/svg+xml;base64," + base64.b64encode(path.read_bytes()).decode()


def inline(html):
    kit = SRC / "kit.js"
    if kit.exists():
        html = html.replace('<script src="kit.js"></script>', "<script>\n" + kit.read_text() + "\n</script>")
    html = html.replace("/*LOGO_GEOMETRY*/null", geometry())
    for svg in sorted((ROOT / "logo").rglob("*.svg")):
        rel = svg.relative_to(ROOT).as_posix()
        html = html.replace(f'"{rel}"', f'"{data_uri(svg)}"')
    return html


def build():
    for page in SRC.glob("*.html"):
        (ROOT / page.name).write_text(inline(page.read_text()))
        print(page.name)


if __name__ == "__main__":
    build()
