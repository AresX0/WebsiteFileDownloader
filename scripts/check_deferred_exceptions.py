"""Detect lambda callbacks that reference ephemeral exception variables like `e` in f-strings
which will be evaluated later (e.g. via `root.after`) and thus raise NameError.

This check finds lines containing both `lambda` and an f-string referring to `{e` where the
lambda parameter list does not capture `e` explicitly (e.g., `lambda e=e: ...`), or where
`e` appears unbound inside the lambda body.

Exit code: 0 when no issues, 1 when issues are found.
"""
import re
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
py_files = list(repo.glob('**/*.py'))
# Avoid scanning virtualenv and hidden folders
py_files = [p for p in py_files if '.venv' not in str(p) and '/.venv' not in str(p)]
# Avoid scanning the check script itself to prevent self-matches in examples
py_files = [p for p in py_files if p.name != Path(__file__).name]

PROBLEMS = []
# Pattern to detect f-strings referencing e inside a single line
f_e_pattern = re.compile(r'''f["'].*\{[^}]*\be\b.*["']''')
# Pattern for lambda with parameter list (between lambda and colon)
lambda_param_pat = re.compile(r'lambda\s*(?P<params>[^:]*):')

for p in py_files:
    try:
        text = p.read_text(encoding='utf-8')
    except Exception:
        continue
    for i, line in enumerate(text.splitlines(), start=1):
        if 'lambda' not in line:
            continue
        if 'f"' in line or "f'" in line:
            if f_e_pattern.search(line):
                m = lambda_param_pat.search(line)
                params = m.group('params') if m else ''
                # If params contain 'e=' or 'e,' or 'e ' as parameter name, it's OK
                safe = False
                if 'e=' in params or 'e,' in params or params.strip() == 'e' or params.strip().startswith('e '):
                    safe = True
                if not safe:
                    PROBLEMS.append((str(p.relative_to(repo)), i, line.strip()))

if PROBLEMS:
    print("Detected potential deferred-exception usage in lambdas (f-strings referencing {e} without capturing it):\n")
    for path, ln, l in PROBLEMS:
        print(f"{path}:{ln}: {l}")
    print("\nPlease capture exception messages (e) into a local variable or capture it as a default parameter, e.g. `msg = f'...{{e}}'` and `lambda m=msg: ...` or `lambda e=e: ...`.")
    sys.exit(1)

print("No deferred-exception lambda issues found.")
sys.exit(0)
