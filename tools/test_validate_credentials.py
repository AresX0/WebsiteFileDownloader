import os
import json
import pytest

# Allow skipping this test in CI/dev when Google Drive credentials are not provided
if os.environ.get('EPISTEIN_SKIP_GDRIVE_VALIDATION', '0') == '1':
    pytest.skip('Skipping Google Drive credential validation (EPSTEIN_SKIP_GDRIVE_VALIDATION=1)', allow_module_level=True)

CRED = os.path.join(os.path.dirname(__file__), 'credentials.json')
print('Using credentials file:', CRED)
if not os.path.exists(CRED):
    print('credentials.json not found')
    raise SystemExit(1)

try:
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
except Exception as e:
    print('Required google auth libraries not installed:', e)
    raise

print('Loading credentials via from_service_account_file...')
creds = service_account.Credentials.from_service_account_file(CRED)
print('Credential object type:', type(creds))
# Check .valid attribute
valid_attr = getattr(creds, 'valid', None)
print('.valid before refresh:', valid_attr)

# Attempt to refresh credentials (obtain access token)
req = Request()
try:
    creds.refresh(req)
    print('Refresh succeeded. token:', getattr(creds, 'token', None)[:20] + '...')
    print('.valid after refresh:', getattr(creds, 'valid', None))
    print('Scopes:', getattr(creds, 'scopes', None))
except Exception as e:
    print('Refresh failed with exception:', e)
    # Some credentials require scopes; try with drive scope
    try:
        scopes = ['https://www.googleapis.com/auth/drive.readonly']
        creds2 = service_account.Credentials.from_service_account_file(CRED, scopes=scopes)
        print('Loaded with scopes, attempting refresh...')
        creds2.refresh(req)
        print('Refresh with scopes succeeded. token:', getattr(creds2, 'token', None)[:20] + '...')
    except Exception as e2:
        print('Refresh with scopes failed:', e2)

print('Test complete')
