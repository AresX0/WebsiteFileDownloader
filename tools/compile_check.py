import traceback
p = r'C:\Projects\Website Downloader\epstein_downloader_gui.py'
try:
    with open(p, 'r', encoding='utf-8') as f:
        s = f.read()
    compile(s, p, 'exec')
    print('ok')
except Exception as e:
    traceback.print_exc()
    import sys
    sys.exit(1)
