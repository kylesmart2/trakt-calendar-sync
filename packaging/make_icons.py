"""Generates the platform-specific icon files PyInstaller needs from the one
source image (resources/appIcon.png) - a Windows .ico and a macOS .icns.
Re-run this whenever appIcon.png changes; the generated files are committed
alongside it so a build doesn't depend on Pillow being installed.
"""

import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PNG = REPO_ROOT / "resources" / "appIcon.png"
ICO_PATH = REPO_ROOT / "resources" / "app_icon.ico"
ICNS_PATH = REPO_ROOT / "resources" / "app_icon.icns"

ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
ICNS_SIZES = [(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512)]


def main() -> None:
    if not SOURCE_PNG.exists():
        print(f"error: {SOURCE_PNG} not found", file=sys.stderr)
        sys.exit(1)

    image = Image.open(SOURCE_PNG).convert("RGBA")

    image.save(ICO_PATH, format="ICO", sizes=ICO_SIZES)
    print(f"wrote {ICO_PATH}")

    image.save(ICNS_PATH, format="ICNS", sizes=ICNS_SIZES)
    print(f"wrote {ICNS_PATH}")


if __name__ == "__main__":
    main()
