p = r'C:\Projects\Website Downloader\epstein_downloader_gui.py'
with open(p,'r',encoding='utf-8') as f:
    lines=f.readlines()
stack=[]
for i,line in enumerate(lines, start=1):
    stripped=line.lstrip()
    indent=len(line)-len(stripped)
    if stripped.startswith('try:'):
        stack.append((i,indent))
    elif stripped.startswith('except') or stripped.startswith('finally'):
        # match to most recent try at same indent or less
        if stack:
            # find last try with indent <= this indent
            for j in range(len(stack)-1,-1,-1):
                if stack[j][1] <= indent:
                    stack.pop(j)
                    break
    elif stripped.startswith('def ') or stripped.startswith('class '):
        # any outstanding try with indent >= this indent is likely unclosed
        for tln, tind in stack:
            if tind >= indent:
                print(f'Possible unclosed try at line {tln} (indent {tind}) before {i}: {lines[tln-1].strip()}')
        # don't clear stack

print('Done')
