"""Check repository for UTF-8 BOM (U+FEFF) at start of text files and fail if any found."""
import os
import sys

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
bad = []
for dirpath, dirs, files in os.walk(root):
    # Skip virtual environments and .git
    if any(part in ('.venv', 'venv', '.git') for part in dirpath.split(os.sep)):
        continue
    for f in files:
        if f.endswith(('.py', '.md', '.txt')):
            p = os.path.join(dirpath, f)
            try:
                with open(p, 'rb') as fh:
                    head = fh.read(3)
                    if head == b'\xef\xbb\xbf':
                        bad.append(os.path.relpath(p, root))
            except Exception:
                pass

if bad:
    print('ERROR: Found files with UTF-8 BOM (U+FEFF):')
    for p in bad:
        print(' -', p)
    print('\nRemove the BOM from the listed files (e.g., `python -c "open(\'file\',\'rb\').read()[3:]\" > file`) or use your editor to re-save as UTF-8 without BOM.')
    sys.exit(1)

print('No UTF-8 BOMs found.')
sys.exit(0)
