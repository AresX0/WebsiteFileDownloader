import os
import json
from PIL import Image

ROOT = os.path.dirname(__file__)
ASSETS_DIR = os.path.join(ROOT, 'assets')
OUT_DIR = os.path.join(ASSETS_DIR, 'tune_outputs')
os.makedirs(OUT_DIR, exist_ok=True)

FILES = []
for fn in sorted(os.listdir(ASSETS_DIR)):
    if fn.startswith('.'):
        continue
    path = os.path.join(ASSETS_DIR, fn)
    if os.path.isfile(path) and fn.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
        FILES.append(fn)


def luminance(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b

# Settings to try (DARK_MAX, FADE)
SETTINGS = [ (120, 100), (140, 120), (180, 120) ]

summary = {}

for dark_max, fade in SETTINGS:
    out_sub = os.path.join(OUT_DIR, f'dm{dark_max}_f{fade}')
    previews = os.path.join(out_sub, 'previews')
    os.makedirs(previews, exist_ok=True)
    report = {'settings': {'DARK_MAX': dark_max, 'FADE': fade}, 'assets': []}

    for fn in FILES:
        path = os.path.join(ASSETS_DIR, fn)
        try:
            im = Image.open(path).convert('RGBA')
        except Exception as e:
            report['assets'].append({'file': fn, 'error': str(e)})
            continue

        w, h = im.size
        pixels = list(im.getdata())
        total = w * h
        transparent = 0
        opaque = 0
        partial = 0
        dark_by_lum = 0
        sum_lum = 0.0
        nontrans = 0

        preview = Image.new('RGBA', (w, h))
        pp = []

        for (r, g, b, a) in pixels:
            if a == 0:
                transparent += 1
                pp.append((0,0,0,0))
                continue
            if a == 255:
                opaque += 1
            else:
                partial += 1

            lum = luminance(r,g,b)
            sum_lum += lum
            nontrans += 1

            if lum <= dark_max:
                dark_by_lum += 1
                alpha = 255
            elif lum <= dark_max + fade:
                alpha = int(255 * (1 - (lum - dark_max) / fade))
            else:
                alpha = 0

            if alpha == 0:
                pp.append((0,0,0,0))
            else:
                pp.append((0,0,0,alpha))

        preview.putdata(pp)
        preview_path = os.path.join(previews, fn)
        try:
            preview.save(preview_path)
            saved = True
        except Exception:
            saved = False

        avg_lum = (sum_lum / nontrans) if nontrans else None
        report['assets'].append({
            'file': fn,
            'width': w,
            'height': h,
            'total_pixels': total,
            'transparent_pixels': transparent,
            'opaque_pixels': opaque,
            'partial_alpha_pixels': partial,
            'dark_by_luminance': dark_by_lum,
            'avg_luminance_nontransparent': avg_lum,
            'preview_saved': saved,
            'preview_path': os.path.relpath(preview_path, ROOT) if saved else None,
        })

    report_path = os.path.join(out_sub, 'assets_report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    # Summarize for quick review
    summary_key = f'dm{dark_max}_f{fade}'
    summary[summary_key] = {}
    summary[summary_key]['report'] = os.path.relpath(report_path, ROOT)
    summary[summary_key]['previews'] = os.path.relpath(previews, ROOT)

    # compute aggregate metrics
    agg = []
    for a in report['assets']:
        if 'error' in a:
            continue
        pct_trans = 100.0 * a['transparent_pixels'] / a['total_pixels'] if a['total_pixels'] else 0
        pct_dark = 100.0 * a['dark_by_luminance'] / a['total_pixels'] if a['total_pixels'] else 0
        agg.append({'file': a['file'], 'pct_trans': pct_trans, 'pct_dark': pct_dark})

    summary[summary_key]['per_asset'] = agg

# Write overall summary
summary_path = os.path.join(OUT_DIR, 'tune_summary.json')
with open(summary_path, 'w', encoding='utf-8') as f:
    json.dump({'settings_tried': SETTINGS, 'summary': summary}, f, indent=2)

print('Tuning complete. Outputs in', OUT_DIR)
for k, v in summary.items():
    print('-', k, 'report->', v['report'], 'previews->', v['previews'])

print('\nYou can inspect assets/tune_outputs/* for per-setting previews and reports.')
