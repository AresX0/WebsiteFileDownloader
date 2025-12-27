p = r'C:\Projects\Website Downloader\epstein_downloader_gui.py'
with open(p,'rb') as f:
    b = f.read()
# UTF-8 BOM
if b.startswith(b'\xef\xbb\xbf'):
    print('Found UTF-8 BOM, removing')
    b = b[3:]
else:
    print('No UTF-8 BOM found')
with open(p,'wb') as f:
    f.write(b)
print('done')
