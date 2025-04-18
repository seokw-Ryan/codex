import os

def write_atomic(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        f.write(data)
    os.replace(tmp, path)
