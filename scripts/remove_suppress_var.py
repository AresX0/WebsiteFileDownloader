from pathlib import Path
p=Path('epstein_downloader_gui.py')
lines=p.read_text(encoding='utf-8').splitlines()
out=[]
skip_next=0
for i,line in enumerate(lines):
    if skip_next>0:
        skip_next-=1
        continue
    if 'suppress_startup_dialog' in line:
        # skip this line and the next two lines if they are part of the tuple assignment
        skip_next=2
        continue
    out.append(line)
p.write_text('\n'.join(out),encoding='utf-8')
print('removed suppress_startup_dialog assignment (if present)')
