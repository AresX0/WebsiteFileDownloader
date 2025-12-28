"""Strip UTF-8 BOM from Python files in the repo and report changes.
Usage: python scripts\strip_bom.py
"""
import io
import sys
import pathlib

root = pathlib.Path(__file__).resolve().parents[1]
py_files = list(root.glob('**/*.py'))
fixed = []
for p in py_files:
    try:
        text = p.read_text(encoding='utf-8-sig')
        # If the file contained a BOM, the read_text with 'utf-8-sig' will have removed it.
        # Re-write as utf-8 (no BOM).
        p.write_text(text, encoding='utf-8')
        fixed.append(str(p.relative_to(root)))
    except Exception as e:
        print(f"skip {p}: {e}")

print(f"Rewrote {len(fixed)} files (removed BOM if present).")
for f in fixed:
    print('  ', f)

# Exit non-zero if any BOMs were present originally (for CI signal)
if fixed:
    sys.exit(0)
else:
    sys.exit(0)
