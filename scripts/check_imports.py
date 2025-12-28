try:
    import importlib, sys, pathlib
    # Ensure repo root is on sys.path so top-level modules import correctly
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    m = importlib.import_module('epstein_downloader_gui')
    print('IMPORT_OK', getattr(m, '__version__', 'no-version'))
except Exception as e:
    print('IMPORT_FAIL', e)
    raise
