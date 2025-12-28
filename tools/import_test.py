import importlib, traceback, sys, os
# Ensure project root is on sys.path (simulate pytest import environment)
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root not in sys.path:
    sys.path.insert(0, root)

try:
    m = importlib.import_module('epstein_downloader_gui')
    print('Loaded module:', m)
    print('Has DownloaderGUI:', hasattr(m, 'DownloaderGUI'))
    if hasattr(m, 'DownloaderGUI'):
        print('DownloaderGUI object:', m.DownloaderGUI)
except Exception:
    traceback.print_exc()
    raise
else:
    # Additionally introspect source for class definitions
    import ast
    src = open(os.path.join(root, 'epstein_downloader_gui.py'), 'r', encoding='utf-8').read()
    src = src.lstrip('\ufeff')
    tree = ast.parse(src)
    classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    print('Classes in source AST:', classes)
