from pathlib import Path
p=Path('generate_icons.py')
s=p.read_text(encoding='utf-8')
s=s.replace('img = mk_canvas(); d = ImageDraw.Draw(img)','img = mk_canvas()\n d = ImageDraw.Draw(img)')
s=s.replace('ax = LARGE*0.8; ay = LARGE*0.25','ax = LARGE*0.8\nay = LARGE*0.25')
# Ensure spacing after newline is consistent (remove leading space before 'd =')
s=s.replace('\n d =','\nd =')
p.write_text(s,encoding='utf-8')
print('fixed generate_icons semicolons')
