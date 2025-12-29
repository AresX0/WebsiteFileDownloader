import re
old='c:/Path/epstein_downloader_gui (1).py'
new='c:/Projects/Website Downloader/epstein_downloader_gui.py'

def funcs(path):
    s=open(path,'r',encoding='utf-8',errors='ignore').read()
    return set(re.findall(r"def\s+([a-zA-Z0-9_]+)\s*\(", s))

oldf=funcs(old)
newf=funcs(new)
only_old=sorted(oldf-newf)
only_new=sorted(newf-oldf)
print('Functions only in old (count=%d):' % len(only_old))
for f in only_old:
    print(f)
print('\nFunctions only in new (count=%d):' % len(only_new))
for f in only_new:
    print(f)
