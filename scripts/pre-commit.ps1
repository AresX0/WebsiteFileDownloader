# Run quick checks before committing: BOM check and unit tests (optional)
try {
    python tools/check_bom.py
} catch {
    Write-Error "BOM check failed. Fix files listed by tools/check_bom.py before committing."
    exit 1
}

# Optional: run a subset of tests quickly
# python -m pytest -q tests/smoke_test.py

Write-Host "Pre-commit checks passed."