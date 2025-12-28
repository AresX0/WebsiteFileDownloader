import io
p='epstein_downloader_gui.py'
try:
    s=io.open(p,'r',encoding='utf-8-sig').read()
    io.open(p,'w',encoding='utf-8').write(s)
    print('fixed', p)
except Exception as e:
    print('error', e)
    raise
