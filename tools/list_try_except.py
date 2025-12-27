p = r'C:\Projects\Website Downloader\epstein_downloader_gui.py'
with open(p,'r',encoding='utf-8') as f:
    lines=f.readlines()
for i,line in enumerate(lines, start=1):
    if 'try:' in line or line.lstrip().startswith('except') or line.lstrip().startswith('finally'):
        print(f'{i}: {line.rstrip()}')
