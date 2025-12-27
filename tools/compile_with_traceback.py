import traceback
from pathlib import Path

p = Path(r'C:\Projects\Website Downloader\epstein_downloader_gui.py')
src = p.read_text(encoding='utf-8')
try:
    compile(src, str(p), 'exec')
    print('OK')
except Exception as e:
    traceback.print_exc()
    if isinstance(e, SyntaxError):
        lineno = e.lineno
        lines = src.splitlines()
        start = max(0, lineno - 6)
        end = min(len(lines), lineno + 6)
        print('\nContext around syntax error:')
        for i in range(start, end):
            mark = '>>' if i+1 == lineno else '  '
            print(f"{mark} {i+1}: {lines[i]!r}")
    raise
