from pathlib import Path
p = Path(r'C:/Projects/Website Downloader/epstein_downloader_gui.py')
src = p.read_text(encoding='utf-8')
lines = src.splitlines()
# Find first top-level def that has 'self' as first parameter
first_method = None
main_line = None
for i,l in enumerate(lines):
    stripped = l.lstrip()
    if stripped.startswith('def '):
        # find params inside parentheses
        import re
        m = re.match(r'def\s+\w+\s*\(([^)]*)\)\s*:', stripped)
        if m:
            params = m.group(1).strip()
            if params.startswith('self'):
                first_method = i
                break
for i,l in enumerate(lines):
    if l.lstrip().startswith('def main('):
        main_line = i
        break
if first_method is None or main_line is None or first_method >= main_line:
    print('Could not determine wrap region: first_method=', first_method, 'main_line=', main_line)
    raise SystemExit(1)
# Backup
bak = p.with_suffix('.py.bak')
bak.write_text(src, encoding='utf-8')
print(f'Backup written to {bak}')
# Insert class header
indent = ' ' * 4
new_lines = lines[:first_method]
new_lines.append('class DownloaderGUI:')
# If next line is blank, keep a blank after class
# Now indent the region from first_method to main_line-1
for l in lines[first_method:main_line]:
    if l.strip() == '':
        new_lines.append('')
    else:
        new_lines.append(indent + l)
# Append the rest unchanged
new_lines.extend(lines[main_line:])
new_src = '\n'.join(new_lines) + '\n'
p.write_text(new_src, encoding='utf-8')
print('Wrapped methods into class and wrote file')
