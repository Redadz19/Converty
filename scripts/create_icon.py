from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PIL import Image

root = Path(__file__).resolve().parents[1]
svg = root / "assets" / "waraqa.svg"
png = root / "assets" / "waraqa_icon.png"
ico = root / "assets" / "waraqa.ico"

renderer = QSvgRenderer(str(svg))
image = QImage(512, 512, QImage.Format_ARGB32)
image.fill(Qt.transparent)
painter = QPainter(image)
renderer.render(painter)
painter.end()
if not image.save(str(png), "PNG"):
    raise SystemExit("Could not render Waraqa SVG icon")
with Image.open(png) as source:
    source.save(ico, format="ICO", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(f"Created {ico}")
