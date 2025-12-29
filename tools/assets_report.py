import os
import json
from PIL import Image

ROOT = os.path.dirname(__file__)
ASSETS_DIR = os.path.join(ROOT, "assets")
REPORT_PATH = os.path.join(ROOT, "assets_report.json")
PREVIEW_DIR = os.path.join(ASSETS_DIR, "previews")

os.makedirs(PREVIEW_DIR, exist_ok=True)

FILES = []
for fn in sorted(os.listdir(ASSETS_DIR)):
    if fn.startswith("."):
        continue
    path = os.path.join(ASSETS_DIR, fn)
    if os.path.isfile(path) and fn.lower().endswith(
        (".png", ".jpg", ".jpeg", ".gif", ".bmp")
    ):
        FILES.append(fn)

report = {"assets": []}


def luminance(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b


# Parameters roughly matching GUI processing
DARK_MAX = 100
FADE = 80

for fn in FILES:
    path = os.path.join(ASSETS_DIR, fn)
    try:
        im = Image.open(path).convert("RGBA")
    except Exception as e:
        report["assets"].append(
            {
                "file": fn,
                "error": str(e),
            }
        )
        continue

    w, h = im.size
    pixels = list(im.getdata())
    total = w * h
    transparent = 0
    opaque = 0
    partial = 0
    black_pixels = 0
    dark_by_lum = 0
    sum_lum = 0.0
    nontrans_pixels = 0

    # Preview image for converted black-on-transparent
    preview = Image.new("RGBA", (w, h))
    preview_pixels = []

    for r, g, b, a in pixels:
        if a == 0:
            transparent += 1
            preview_pixels.append((0, 0, 0, 0))
            continue
        if a == 255:
            opaque += 1
        else:
            partial += 1

        lum = luminance(r, g, b)
        sum_lum += lum
        nontrans_pixels += 1

        if r <= 50 and g <= 50 and b <= 50:
            black_pixels += 1

        if lum <= DARK_MAX:
            dark_by_lum += 1
            alpha = 255
        elif lum <= DARK_MAX + FADE:
            alpha = int(255 * (1 - (lum - DARK_MAX) / FADE))
        else:
            alpha = 0

        if alpha == 0:
            preview_pixels.append((0, 0, 0, 0))
        else:
            preview_pixels.append((0, 0, 0, alpha))

    preview.putdata(preview_pixels)
    preview_name = os.path.join(PREVIEW_DIR, fn)
    try:
        preview.save(preview_name)
        preview_saved = True
    except Exception:
        preview_saved = False

    avg_lum = (sum_lum / nontrans_pixels) if nontrans_pixels else None

    report["assets"].append(
        {
            "file": fn,
            "width": w,
            "height": h,
            "total_pixels": total,
            "transparent_pixels": transparent,
            "opaque_pixels": opaque,
            "partial_alpha_pixels": partial,
            "black_pixel_count_rgb": black_pixels,
            "dark_by_luminance": dark_by_lum,
            "avg_luminance_nontransparent": avg_lum,
            "preview_saved": preview_saved,
            "preview_path": os.path.relpath(preview_name, ROOT)
            if preview_saved
            else None,
        }
    )

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

# Print a short summary to stdout
print("Asset diagnostic complete. Report written to", REPORT_PATH)
for a in report["assets"]:
    if "error" in a:
        print(f"- {a['file']}: ERROR {a['error']}")
    else:
        pct_trans = (
            100.0 * a["transparent_pixels"] / a["total_pixels"]
            if a["total_pixels"]
            else 0
        )
        pct_dark = (
            100.0 * a["dark_by_luminance"] / a["total_pixels"]
            if a["total_pixels"]
            else 0
        )
        print(
            f"- {a['file']}: {a['width']}x{a['height']}, {pct_trans:.1f}% transparent, {pct_dark:.1f}% dark-by-luminance, preview={'yes' if a['preview_saved'] else 'no'})"
        )

print("\nPreviews saved to", PREVIEW_DIR)
