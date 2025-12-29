import json, base64, sys
p = r'C:\Projects\Website Downloader\tools\credentials.json'
try:
    data = json.load(open(p, 'r', encoding='utf-8'))
    pk = data.get('private_key', '')
    lines = pk.strip().split('\n')
    b = ''.join([ln.strip() for ln in lines if 'BEGIN' not in ln and 'END' not in ln])
    print('b64_len', len(b))
    try:
        base64.b64decode(b, validate=True)
        print('b64_ok')
    except Exception as e:
        print('b64_err', repr(e))
except Exception as e:
    print('error', e)
    sys.exit(2)
