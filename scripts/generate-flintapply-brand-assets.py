#!/usr/bin/env python3
"""Generate FlintApply OG/social icons and dark wordmark from canonical PNGs.

Run from repo root:
  python3 scripts/generate-flintapply-brand-assets.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
BRAND = REPO / "frontend" / "public" / "brand"
APP = REPO / "frontend" / "app"
ARCHIVE = BRAND / "archive" / "talio-cv"
WORDMARK_LIGHT = BRAND / "flintapply-wordmark-light.png"
WORDMARK_DARK = BRAND / "flintapply-wordmark-dark.png"
MARK = BRAND / "mark.png"

OG_SIZE = (1200, 630)
OG_BG = (251, 248, 245)  # warm off-white
# Light-mode “pply” is ~rgb(32,47,67). Dark UI uses a lighter tint of the same blue.
DARK_TEXT_TARGET = (148, 186, 220)


def _is_apply_navy(r: int, g: int, b: int) -> bool:
    """Dark navy used for the “pply” letters in the light wordmark."""
    return r < 90 and g < 110 and b < 120 and b >= r and (r + g + b) < 220


def _is_brand_accent(r: int, g: int, b: int) -> bool:
    if r > 200 and 100 < g < 180 and b < 120:
        return True  # orange “Flint”
    if g > 150 and r < 120 and b < 150:
        return True  # green “A” / sparkles
    return False


def build_dark_wordmark(src: Path, dest: Path) -> None:
    im = Image.open(src).convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 32:
                continue
            if _is_apply_navy(r, g, b):
                px[x, y] = (*DARK_TEXT_TARGET, a)
    im.save(dest, optimize=True)
    print(f"wrote {dest.relative_to(REPO)}")


def build_og_image(wordmark: Path, dest: Path) -> None:
    wm = Image.open(wordmark).convert("RGBA")
    canvas = Image.new("RGB", OG_SIZE, OG_BG)
    max_w = int(OG_SIZE[0] * 0.82)
    scale = min(max_w / wm.width, (OG_SIZE[1] * 0.55) / wm.height)
    nw, nh = int(wm.width * scale), int(wm.height * scale)
    wm = wm.resize((nw, nh), Image.Resampling.LANCZOS)
    x = (OG_SIZE[0] - nw) // 2
    y = (OG_SIZE[1] - nh) // 2
    canvas.paste(wm, (x, y), wm)
    canvas.save(dest, optimize=True)
    print(f"wrote {dest.relative_to(REPO)}")


def build_square_icon(mark: Path, size: int, dest: Path) -> None:
    src = Image.open(mark).convert("RGBA")
    side = min(src.size)
    left = (src.width - side) // 2
    top = (src.height - side) // 2
    cropped = src.crop((left, top, left + side, top + side))
    out = cropped.resize((size, size), Image.Resampling.LANCZOS)
    # Flatten on white for favicon-style icons (browsers expect opaque).
    flat = Image.new("RGB", (size, size), (255, 255, 255))
    flat.paste(out, (0, 0), out)
    flat.save(dest, optimize=True)
    print(f"wrote {dest.relative_to(REPO)} ({size}px)")


def archive_talio_app_assets() -> None:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    for name in ("opengraph-image.png", "icon.png", "apple-icon.png"):
        src = APP / name
        if not src.is_file():
            continue
        archived = ARCHIVE / name
        if not archived.exists():
            shutil.copy2(src, archived)
            print(f"archived {src.relative_to(REPO)} -> {archived.relative_to(REPO)}")


def main() -> None:
    if not WORDMARK_LIGHT.is_file():
        raise SystemExit(f"missing {WORDMARK_LIGHT}")
    if not MARK.is_file():
        raise SystemExit(f"missing {MARK}")

    archive_talio_app_assets()
    build_dark_wordmark(WORDMARK_LIGHT, WORDMARK_DARK)
    build_og_image(WORDMARK_LIGHT, APP / "opengraph-image.png")
    build_square_icon(MARK, 512, APP / "icon.png")
    build_square_icon(MARK, 180, APP / "apple-icon.png")

    # Regenerate common public sizes from mark (keeps favicon/PWA paths stable).
    for size in (16, 32, 48, 64, 96, 128, 192, 256, 512):
        build_square_icon(MARK, size, BRAND / f"mark-{size}.png")

    readme = ARCHIVE / "README.md"
    readme.write_text(
        "# TalioCV-era assets (archived)\n\n"
        "Superseded by FlintApply wordmark and regenerated `frontend/app/` "
        "Open Graph / favicon files. Kept for reference only.\n",
        encoding="utf-8",
    )
    print("done")


if __name__ == "__main__":
    main()
