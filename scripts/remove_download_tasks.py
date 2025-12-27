from pathlib import Path
p=Path('playwright_epstein_downloader.py')
lines=p.read_text(encoding='utf-8').splitlines()
out=[]
for line in lines:
    if line.strip()=="download_tasks = []":
        continue
    out.append(line)
p.write_text('\n'.join(out),encoding='utf-8')
print('removed download_tasks lines')
