from PIL import Image, ImageDraw
import os

ROOT = os.path.dirname(__file__)
ASSETS = os.path.join(ROOT, 'assets')
if not os.path.isdir(ASSETS):
    raise SystemExit('assets directory not found')

SIZE = 24
SCALE = 4
LARGE = SIZE * SCALE

def save(name, img):
    path = os.path.join(ASSETS, name)
    img.save(path)
    print('Wrote', path)

def mk_canvas():
    return Image.new('RGBA', (LARGE, LARGE), (0,0,0,0))

def downsample(img):
    return img.resize((SIZE, SIZE), Image.LANCZOS)

# start (triangle)
img = mk_canvas(); d = ImageDraw.Draw(img)
d.polygon([(LARGE*0.4, LARGE*0.25), (LARGE*0.4, LARGE*0.75), (LARGE*0.75, LARGE*0.5)], fill=(0,0,0,255))
save('start.png', downsample(img))

# stop (square)
img = mk_canvas(); d = ImageDraw.Draw(img)
pad = LARGE*0.2
d.rectangle([pad, pad, LARGE-pad, LARGE-pad], fill=(0,0,0,255))
save('stop.png', downsample(img))

# pause (two bars)
img = mk_canvas(); d = ImageDraw.Draw(img)
w = LARGE*0.15
gap = LARGE*0.12
d.rectangle([LARGE*0.25-w, LARGE*0.2, LARGE*0.25, LARGE*0.8], fill=(0,0,0,255))
d.rectangle([LARGE*0.75-w, LARGE*0.2, LARGE*0.75, LARGE*0.8], fill=(0,0,0,255))
save('pause.png', downsample(img))

# resume (play inside circle)
img = mk_canvas(); d = ImageDraw.Draw(img)
d.ellipse([LARGE*0.05, LARGE*0.05, LARGE*0.95, LARGE*0.95], outline=None, fill=(0,0,0,0))
d.polygon([(LARGE*0.37, LARGE*0.28), (LARGE*0.37, LARGE*0.72), (LARGE*0.72, LARGE*0.5)], fill=(0,0,0,255))
save('resume.png', downsample(img))

# download (arrow to tray)
img = mk_canvas(); d = ImageDraw.Draw(img)
d.polygon([(LARGE*0.5, LARGE*0.7), (LARGE*0.35, LARGE*0.5), (LARGE*0.65, LARGE*0.5)], fill=(0,0,0,255))
d.rectangle([LARGE*0.3, LARGE*0.55, LARGE*0.7, LARGE*0.6], fill=(0,0,0,255))
d.rectangle([LARGE*0.2, LARGE*0.75, LARGE*0.8, LARGE*0.82], fill=(0,0,0,255))
save('download.png', downsample(img))

# schedule (clock)
img = mk_canvas(); d = ImageDraw.Draw(img)
d.ellipse([LARGE*0.15, LARGE*0.12, LARGE*0.85, LARGE*0.88], outline=(0,0,0,255), width=int(SCALE*1.2))
d.line([(LARGE*0.5, LARGE*0.45), (LARGE*0.5, LARGE*0.65)], fill=(0,0,0,255), width=int(SCALE*1.2))
d.line([(LARGE*0.5, LARGE*0.5), (LARGE*0.65, LARGE*0.5)], fill=(0,0,0,255), width=int(SCALE*1.2))
save('schedule.png', downsample(img))

# skipped (circle with diagonal slash)
img = mk_canvas(); d = ImageDraw.Draw(img)
d.ellipse([LARGE*0.12, LARGE*0.12, LARGE*0.88, LARGE*0.88], outline=(0,0,0,255), width=int(SCALE*1.2))
d.line([(LARGE*0.22, LARGE*0.78), (LARGE*0.78, LARGE*0.22)], fill=(0,0,0,255), width=int(SCALE*1.6))
save('skipped.png', downsample(img))

# json (stylized braces)
img = mk_canvas(); d = ImageDraw.Draw(img)
# left brace
x = LARGE*0.25
d.line([(x+LARGE*0.02, LARGE*0.2), (x+LARGE*0.02, LARGE*0.35)], fill=(0,0,0,255), width=int(SCALE*1.2))
d.line([(x+LARGE*0.02, LARGE*0.35), (x, LARGE*0.45)], fill=(0,0,0,255), width=int(SCALE*1.2))
d.line([(x, LARGE*0.45), (x+LARGE*0.02, LARGE*0.55)], fill=(0,0,0,255), width=int(SCALE*1.2))
d.line([(x+LARGE*0.02, LARGE*0.55), (x+LARGE*0.02, LARGE*0.8)], fill=(0,0,0,255), width=int(SCALE*1.2))
# right brace (mirrored)
x2 = LARGE*0.75
d.line([(x2-LARGE*0.02, LARGE*0.2), (x2-LARGE*0.02, LARGE*0.35)], fill=(0,0,0,255), width=int(SCALE*1.2))
d.line([(x2-LARGE*0.02, LARGE*0.35), (x2, LARGE*0.45)], fill=(0,0,0,255), width=int(SCALE*1.2))
d.line([(x2, LARGE*0.45), (x2-LARGE*0.02, LARGE*0.55)], fill=(0,0,0,255), width=int(SCALE*1.2))
d.line([(x2-LARGE*0.02, LARGE*0.55), (x2-LARGE*0.02, LARGE*0.8)], fill=(0,0,0,255), width=int(SCALE*1.2))
save('json.png', downsample(img))

# reset (circular arrow)
img = mk_canvas(); d = ImageDraw.Draw(img)
d.arc([LARGE*0.12, LARGE*0.12, LARGE*0.88, LARGE*0.88], start=200, end=340, fill=(0,0,0,255), width=int(SCALE*1.6))
# arrowhead at end
ax = LARGE*0.8; ay = LARGE*0.25
d.polygon([(ax, ay), (ax- LARGE*0.06, ay + LARGE*0.04), (ax + LARGE*0.01, ay + LARGE*0.04)], fill=(0,0,0,255))
save('reset.png', downsample(img))

# platypus (simple silhouette: circle with beak)
img = mk_canvas(); d = ImageDraw.Draw(img)
d.ellipse([LARGE*0.18, LARGE*0.18, LARGE*0.68, LARGE*0.62], fill=(0,0,0,255))
d.polygon([(LARGE*0.68, LARGE*0.4), (LARGE*0.9, LARGE*0.36), (LARGE*0.68, LARGE*0.44)], fill=(0,0,0,255))
save('platypus.png', downsample(img))

print('Generation complete')
