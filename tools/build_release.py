"""Build a deterministic, allowlisted skill archive using only the standard library."""
import argparse
import hashlib
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/context-window'
FILES = ('SKILL.md', 'agents/openai.yaml', 'scripts/context_window.py')

def version():
    return re.search(r'^VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"$',
                     (SKILL / 'scripts/context_window.py').read_text(encoding='utf-8'), re.M)[1]

def build(executable=None):
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    suffix = '-windows-x64' if executable else ''
    target = output / f'context-window-{version()}{suffix}.zip'
    contents = {f'context-window/{name}': (SKILL / name).read_bytes() for name in FILES}
    contents['context-window/LICENSE'] = (ROOT / 'LICENSE').read_bytes()
    if executable:
        executable = Path(executable)
        data = executable.read_bytes()
        if not data.startswith(b'MZ'):
            raise ValueError('Expected a Windows executable')
        contents['context-window/bin/context_window.exe'] = data
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(contents.items()):
            entry = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() or set(archive.namelist()) != set(contents):
            raise ValueError('Release archive verification failed')
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / 'SHA256SUMS.txt').write_text(f'{checksum}  {target.name}\n', encoding='utf-8')
    print(f'Built {target.name}; {len(contents)} allowlisted files; SHA-256 {checksum}')
    return target

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, help='Include a built Windows x64 executable')
    build(parser.parse_args().executable)
