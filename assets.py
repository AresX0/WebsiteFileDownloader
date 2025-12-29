"""Assets helper utilities (placeholder images, size normalization).

Lightweight, dependency-aware helpers for creating placeholder PNGs and
resizing existing assets to target sizes. Designed to be import-safe and used
from `epstein_downloader_gui` where needed.
"""
import os
from typing import Iterable


def create_placeholder_asset(path: str, name: str, logger=None) -> bool:
    """Create a small placeholder PNG for `name` at `path`.

    Tries to use Pillow to draw an icon; falls back to writing a tiny
    transparent PNG blob on failure. Returns True on success, False on failure.
    """
    try:
        from PIL import Image, ImageDraw

        size_px = 24
        size = (size_px, size_px)
        im = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)
        symbol_map = {
            "start": {"color": (255, 255, 255, 255), "type": "triangle"},
            "pause": {"color": (255, 255, 255, 255), "type": "bars"},
            "resume": {"color": (255, 255, 255, 255), "type": "triangle"},
            "schedule": {"color": (255, 255, 255, 255), "type": "clock"},
            "json": {"color": (255, 255, 255, 255), "type": "braces"},
            "skipped": {"color": (255, 255, 255, 255), "type": "x"},
            "stop": {"color": (255, 255, 255, 255), "type": "square"},
            "download": {"color": (255, 255, 255, 255), "type": "downarrow"},
        }
        cfg = symbol_map.get(name, {"color": (255, 255, 255, 255), "type": "letter"})
        symbol_color = cfg["color"]
        bg = (240, 240, 240, 255)
        r = max(3, size_px // 8)
        draw.rounded_rectangle((0, 0, size[0], size[1]), radius=r, fill=bg)
        symbol_type = cfg["type"]
        cx, cy = size[0] // 2, size[1] // 2
        if symbol_type == "triangle":
            pts = [(cx - 5, cy - 6), (cx - 5, cy + 6), (cx + 7, cy)]
            draw.polygon(pts, fill=symbol_color)
        elif symbol_type == "bars":
            w = 3
            h = 12
            draw.rectangle((cx - 6 - w // 2, cy - h // 2, cx - 6 + w // 2, cy + h // 2), fill=symbol_color)
            draw.rectangle((cx + 6 - w // 2, cy - h // 2, cx + 6 + w // 2, cy + h // 2), fill=symbol_color)
        elif symbol_type == "clock":
            draw.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), outline=symbol_color, width=2)
            draw.line((cx, cy, cx, cy - 4), fill=symbol_color, width=2)
            draw.line((cx, cy, cx + 3, cy), fill=symbol_color, width=2)
        elif symbol_type == "braces":
            draw.line((cx - 8, cy - 8, cx - 5, cy - 5), fill=symbol_color, width=2)
            draw.line((cx - 5, cy - 5, cx - 8, cy - 2), fill=symbol_color, width=2)
            draw.line((cx + 8, cy - 8, cx + 5, cy - 5), fill=symbol_color, width=2)
            draw.line((cx + 5, cy - 5, cx + 8, cy - 2), fill=symbol_color, width=2)
            draw.line((cx - 8, cy + 8, cx - 5, cy + 5), fill=symbol_color, width=2)
            draw.line((cx - 5, cy + 5, cx - 8, cy + 2), fill=symbol_color, width=2)
            draw.line((cx + 8, cy + 8, cx + 5, cy + 5), fill=symbol_color, width=2)
            draw.line((cx + 5, cy + 5, cx + 8, cy + 2), fill=symbol_color, width=2)
        elif symbol_type == "x":
            draw.line((cx - 6, cy - 6, cx + 6, cy + 6), fill=symbol_color, width=3)
            draw.line((cx - 6, cy + 6, cx + 6, cy - 6), fill=symbol_color, width=3)
        elif symbol_type == "downarrow":
            draw.polygon([(cx, cy + 7), (cx - 6, cy), (cx - 2, cy), (cx - 2, cy - 6), (cx + 2, cy - 6), (cx + 2, cy), (cx + 6, cy)], fill=symbol_color)
        elif symbol_type == "square":
            s = 10
            draw.rectangle((cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2), fill=symbol_color)
        else:
            from PIL import ImageFont
            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except Exception:
                font = ImageFont.load_default()
            letter = name[0].upper()
            w, h = draw.textsize(letter, font=font)
            draw.text((cx - w // 2, cy - h // 2), letter, fill=symbol_color, font=font)
        im.save(path, format="PNG")
        try:
            if logger:
                logger.info(f"Created placeholder asset: {path}")
        except Exception:
            pass
        return True
    except Exception:
        try:
            tiny_png = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(tiny_png)
            if logger:
                try:
                    logger.info(f"Wrote fallback placeholder asset: {path}")
                except Exception:
                    pass
        except Exception:
            try:
                if logger:
                    logger.warning(f"Failed to create placeholder asset {path}")
            except Exception:
                pass
            return False
        return True

def ensure_asset_sizes(assets_dir: str, target_px: int = 24, logger=None):
    """Resize existing assets in `assets_dir` to `target_px` x `target_px` preserving aspect ratio and padding.

    Non-fatal: on any failure this function attempts to continue so that it does not crash GUI startup.
    """
    try:
        for fname in os.listdir(assets_dir):
            if not fname.lower().endswith('.png'):
                continue
            path = os.path.join(assets_dir, fname)
            try:
                im = Image.open(path).convert('RGBA')
                if im.size != (target_px, target_px):
                    im.thumbnail((target_px, target_px), Image.LANCZOS)
                    new_im = Image.new('RGBA', (target_px, target_px), (0, 0, 0, 0))
                    x = (target_px - im.width) // 2
                    y = (target_px - im.height) // 2
                    new_im.paste(im, (x, y), im)
                    new_im.save(path, format='PNG')
                    if logger:
                        try:
                            logger.info(f"Resized asset {fname} to {target_px}x{target_px}")
                        except Exception:
                            pass
            except Exception:
                # Ignore per-file errors
                continue
    except Exception:
        # Non-fatal overall
        pass