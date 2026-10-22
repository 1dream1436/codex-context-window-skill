"""Exercise a packaged executable using only isolated synthetic configuration."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    executable = Path(sys.argv[1]).resolve()
    if not executable.is_file():
        raise ValueError('Executable is missing')
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        config = root / 'config.toml'
        initial = 'model = "example-main"\n# preserve comment\n'
        config.write_text(initial, encoding='utf-8')
        cache = root / 'models_cache.json'
        cache.write_text(json.dumps({'models': [{
            'slug': 'example-main', 'context_window': 500000,
            'max_context_window': 872000,
            'effective_context_window_percent': 95,
        }]}), encoding='utf-8')
        original_cache = cache.read_bytes()
        environment = dict(os.environ, PATH='', PYTHONHOME='', PYTHONPATH='')

        def invoke(*args, success=True):
            result = subprocess.run(
                [str(executable), '--home', str(root), *args],
                env=environment, cwd=root, capture_output=True,
                encoding='utf-8', timeout=60, check=False)
            if (result.returncode == 0) != success:
                raise AssertionError(f'Unexpected exit: {result.returncode}: {result.stdout} {result.stderr}')
            return json.loads(result.stdout)

        status = invoke('status')
        assert status['models'][0]['expected_effective_window'] == 475000
        preview = invoke('set', '--scope', 'global-model', '--model', 'example-main',
                         '--tokens', '60万', '--preview')
        assert preview['status'] == 'preview'
        assert config.read_text(encoding='utf-8') == initial
        result = invoke('set', '--scope', 'global-model', '--model', 'example-main',
                        '--tokens', '600k', '--effective-percent', '90',
                        '--auto-compact-limit', '500k')
        assert result['status'] == 'saved_requires_reload'
        assert invoke('status')['models'][0]['expected_effective_window'] == 540000
        rejected = invoke('set', '--scope', 'global-model', '--model', 'missing',
                          '--tokens', '600k', success=False)
        assert rejected['status'] == 'error'
        restored = invoke('restore', result['backup_manifest'])
        assert restored['status'] == 'restored_requires_reload'
        assert config.read_text(encoding='utf-8') == initial
        assert cache.read_bytes() == original_cache
    print('Standalone smoke checks passed with empty PATH: status, Unicode preview, set, rejection, restore.')


if __name__ == '__main__':
    main()
