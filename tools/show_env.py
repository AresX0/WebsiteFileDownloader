import sys, os
print('cwd=', os.getcwd())
print('sys.path[0]=', sys.path[0])
print('len(sys.path)=', len(sys.path))
print('\n'.join(sys.path[:10]))
