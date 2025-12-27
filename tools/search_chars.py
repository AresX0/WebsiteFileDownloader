p = r'C:\Projects\Website Downloader\epstein_downloader_gui.py'
with open(p,'r',encoding='utf-8') as f:
    s=f.read()
if '/*' in s or '*/' in s:
    for i, line in enumerate(s.splitlines(), start=1):
        if '/*' in line or '*/' in line:
            print(i, line)
else:
    print('no_c_style_comments')
