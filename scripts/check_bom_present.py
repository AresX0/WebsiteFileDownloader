import pathlib
root = pathlib.Path(__file__).resolve().parents[1]
issues = []
for p in root.glob('**/*.py'):
    try:
        b = p.open('rb').read(3)
        if b == b"\xef\xbb\xbf":
            issues.append(str(p.relative_to(root)))
    except Exception as e:
        print('skip', p, e)
if issues:
    print('Files with UTF-8 BOM:')
    for f in issues:
        print('  ', f)
else:
    print('No BOMs found')
