p = r'C:\Projects\Website Downloader\epstein_downloader_gui.py'
with open(p,'rb') as f:
    lines=f.read().splitlines()
start=1060
end=1100
for i in range(start-1,end):
    print(f"{i+1}: {lines[i]!r}")
