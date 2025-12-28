import ast
p='epstein_downloader_gui.py'
try:
    s=open(p,'r',encoding='utf-8').read()
    ast.parse(s)
    print('PARSE_OK')
except Exception as e:
    print('PARSE_FAIL', e)
    raise
