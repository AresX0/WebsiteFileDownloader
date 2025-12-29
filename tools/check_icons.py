from PIL import Image
import os
assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
files = [f for f in os.listdir(assets_dir) if f.lower().endswith(('.png','.gif','.ico'))]
print('Found assets:', files)
for fn in files:
    p = os.path.join(assets_dir, fn)
    try:
        im = Image.open(p).convert('RGBA')
        w,h = im.size
        datas = list(im.getdata())
        alphas = [a for (_,_,_,a) in datas]
        max_alpha = max(alphas) if alphas else 0
        min_alpha = min(alphas) if alphas else 0
        unique_colors = len(set((r,g,b,a) for (r,g,b,a) in datas))
        print(fn, 'size=',(w,h),'min_alpha=',min_alpha,'max_alpha=',max_alpha,'unique_colors=',unique_colors)
        # print corner pixel samples
        corners = [(0,0),(w-1,0),(0,h-1),(w-1,h-1)]
        samples = {c: im.getpixel(c) for c in corners}
        print('  corners:', samples)
    except Exception as e:
        print('  failed to open', fn, 'error:', e)
