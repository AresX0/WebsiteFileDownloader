from pathlib import Path
p=Path('epstein_downloader_gui.py')
s=p.read_text(encoding='utf-8')
old='                        eta = "--"\n                        speed = "--"\n                        with open(local_path, "wb") as f:'
new='                        eta = "--"\n                        speed = "--"\n                        speed_limit = int(self.config.get("speed_limit_kbps", 0))\n                        with open(local_path, "wb") as f:'
if old in s:
    s=s.replace(old,new,1)
    p.write_text(s,encoding='utf-8')
    print('inserted speed_limit')
else:
    print('pattern not found')
