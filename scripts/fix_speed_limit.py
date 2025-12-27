from pathlib import Path
p=Path('epstein_downloader_gui.py')
s=p.read_text(encoding='utf-8')
old = '                    speed_limit = int(self.config.get("speed_limit_kbps", 0))\r\n                    with requests.get('
old2 = '                    speed_limit = int(self.config.get("speed_limit_kbps", 0))\n                    with requests.get('
if old in s:
    s=s.replace(old,'                    with requests.get(')
    p.write_text(s,encoding='utf-8')
    print('replaced CRLF')
elif old2 in s:
    s=s.replace(old2,'                    with requests.get(')
    p.write_text(s,encoding='utf-8')
    print('replaced LF')
else:
    print('pattern not found')
