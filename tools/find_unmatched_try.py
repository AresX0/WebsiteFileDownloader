p = r'C:\Projects\Website Downloader\epstein_downloader_gui.py'
with open(p,'r',encoding='utf-8') as f:
    lines=f.readlines()
stack=[]
for i,line in enumerate(lines, start=1):
    stripped=line.lstrip()
    if stripped.startswith('try:'):
        stack.append((i,line))
    elif stripped.startswith('except') or stripped.startswith('finally'):
        if stack:
            stack.pop()
        else:
            print('Unmatched except/finally at', i, line.strip())
print('Unclosed try blocks:', stack[:10])
if stack:
    for s in stack[-5:]:
        print('try at',s[0], s[1].strip())
