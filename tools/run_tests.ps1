# Run tests from the project's tools folder with recommended environment
# Usage: .\tools\run_tests.ps1

# Ensure env is set for this session
# Resolve script directory reliably and dot-source setup_env.ps1 from the tools folder
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
. (Join-Path $scriptDir 'setup_env.ps1')

# Create a minimal service-account-like credentials.json for tests if missing (prevents MalformedError)
$credsFile = Join-Path $scriptDir 'credentials.json'
# Create a minimal credentials.json only if missing (do NOT overwrite an existing file)
if (-not (Test-Path $credsFile)) {
    Write-Host "Creating minimal credentials.json for tests: $credsFile"
    $stub = @{
        type = 'service_account'
        project_id = 'test-project'
        private_key_id = 'fake_key_id'
        private_key = "-----BEGIN PRIVATE KEY-----`nMIIFAKEKEYDATA`n-----END PRIVATE KEY-----`n"
        client_email = 'test@example.com'
        client_id = '1234567890'
        auth_uri = 'https://accounts.google.com/o/oauth2/auth'
        token_uri = 'https://oauth2.googleapis.com/token'
        auth_provider_x509_cert_url = 'https://www.googleapis.com/oauth2/v1/certs'
        client_x509_cert_url = ''
    } | ConvertTo-Json -Depth 4
    try {
        $stub | Out-File -FilePath $credsFile -Encoding UTF8
    } catch {
        Write-Host "Warning: could not write credentials stub: $_"
    }
} else {
    Write-Host "Using existing credentials file: $credsFile"
}

# Change to project root
Set-Location $env:EPISTEIN_PROJECT_DIR
# Safety: refuse to run if we're not in the expected project directory or if the path points at C:\Path
try {
    $cwd = (Get-Location).ProviderPath
    if ($cwd -ne $env:EPISTEIN_PROJECT_DIR) {
        Write-Host "ERROR: Current directory ($cwd) does not match EPISTEIN_PROJECT_DIR ($env:EPISTEIN_PROJECT_DIR). Aborting to avoid operating outside the project."
        exit 1
    }
    if ($cwd -like 'C:\\Path*') {
        Write-Host "ERROR: Refusing to run tests from C:\Path. Set up the environment to use C:\Projects\Website Downloader instead.";
        exit 1
    }
} catch {
    Write-Host "Warning: failed to validate working directory: $_";
}

# Run pytest inside the tools directory so tests live there
# Ensure we're using the venv python if present
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtualenv .venv"
    . .venv\Scripts\Activate.ps1
}

Write-Host "Running pytest in $env:EPISTEIN_TEST_SCRIPTS_DIR"
# Run pytest with working directory set to tools (tests expected to be in tools)
Push-Location $env:EPISTEIN_TEST_SCRIPTS_DIR
pytest -q
$rc = $LASTEXITCODE
Pop-Location
exit $rc
