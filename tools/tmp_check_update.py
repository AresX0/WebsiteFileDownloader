import requests
url = "https://raw.githubusercontent.com/JosephThePlatypus/EpsteinFilesDownloader/main/VERSION.txt"
try:
    r = requests.get(url, timeout=10)
    print('status_code=', r.status_code)
    print('len_text=', len(r.text))
    print('snippet=', repr(r.text[:200]))
except Exception as e:
    print('exception:', e)
