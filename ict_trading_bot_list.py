import os

root = os.path.join(os.getcwd(), 'ict_trading_bot')
entries = []
for dirpath, dirnames, filenames in os.walk(root):
    rel_dir = os.path.relpath(dirpath, root)
    if rel_dir == '.':
        entries.append('./')
    else:
        entries.append(rel_dir.replace('\\', '/') + '/')
    dirnames[:] = [d for d in dirnames if d not in ('.venv', '__pycache__', '.pytest_cache')]
    for fn in sorted(filenames):
        if rel_dir == '.':
            entries.append(fn)
        else:
            entries.append(os.path.join(rel_dir, fn).replace('\\', '/'))

with open('ict_trading_bot_tree_clean.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(entries))
