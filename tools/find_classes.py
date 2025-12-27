p='C:/Projects/Website Downloader/epstein_downloader_gui.py'
with open(p,'r',encoding='utf-8') as f:
    s=f.read()
for i,line in enumerate(s.splitlines(),1):
    if line.strip().startswith('class '):
        print(i,line)
