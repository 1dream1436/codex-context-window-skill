"""Offline publication checks, not an exhaustive security audit or official validator."""
import ast
from pathlib import Path
import re
from build_release import FILES, ROOT, SKILL, build, version

REQUIRED = {
    'README.md', 'LICENSE', 'CHANGELOG.md', 'CONTRIBUTING.md', 'SECURITY.md',
    '.gitignore', '.gitattributes', 'docs/VALIDATION.md', 'docs/MAINTENANCE.md',
    'tests/test_context_window.py', 'tools/build_release.py', 'tools/release_check.py',
    '.github/workflows/ci.yml', '.github/ISSUE_TEMPLATE/bug_report.md',
    '.github/pull_request_template.md', '.github/workflows/release.yml',
    'tools/smoke_executable.py',
} | {f'skills/context-window/{name}' for name in FILES}
SKIP = {'.git', '__pycache__', 'dist'}
FORBIDDEN_NAMES = {'auth.json', 'config.toml', 'models_cache.json', '.env', 'manifest.json'}
PATTERNS = [
    re.compile(r'[A-Za-z]:[\\/]Users[\\/][^\s`]+', re.I),
    re.compile(r'/(?:home|Users)/[A-Za-z0-9_.-]+/'),
    re.compile(r'gh[pousr]_[A-Za-z0-9]{20,}'),
    re.compile(r'github_pat_[A-Za-z0-9_]{30,}'),
    re.compile(r'sk-[A-Za-z0-9_-]{24,}'),
    re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
]

def main():
    found = set()
    for path in ROOT.rglob('*'):
        relative = path.relative_to(ROOT)
        if not path.is_file() or any(part in SKIP for part in relative.parts):
            continue
        name = relative.as_posix()
        if path.is_symlink() or path.name in FORBIDDEN_NAMES or path.suffix in {'.jsonl', '.log'}:
            raise ValueError(f'Private or unexpected file: {name}')
        if name not in REQUIRED:
            raise ValueError(f'File is not on the publication allowlist: {name}')
        found.add(name)
        text = path.read_text(encoding='utf-8')
        if any(pattern.search(text) for pattern in PATTERNS):
            raise ValueError(f'Possible personal path or credential: {name}')
        if path.suffix == '.py':
            ast.parse(text, filename=name)
        if path.suffix == '.md':
            for link in re.findall(r'\]\(([^)]+)\)', text):
                if '://' in link or link.startswith('#'):
                    continue
                if not (path.parent / link.split('#')[0]).exists():
                    raise ValueError(f'Missing local documentation link: {name}: {link}')
    if found != REQUIRED:
        raise ValueError(f'Missing publication files: {sorted(REQUIRED - found)}')
    skill_text = (SKILL / 'SKILL.md').read_text(encoding='utf-8')
    if not skill_text.startswith('---\nname: context-window\ndescription: '):
        raise ValueError('Unexpected skill frontmatter')
    if f'  version: {version()}\n' not in skill_text or f'## [{version()}]' not in (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8'):
        raise ValueError('Version metadata does not match')
    if 'allow_implicit_invocation: true' not in (SKILL / 'agents/openai.yaml').read_text(encoding='utf-8'):
        raise ValueError('Unexpected invocation policy')
    build()
    print(f'Publication checks passed: {len(found)} source files; metadata, links, privacy patterns, archive.')

if __name__ == '__main__':
    main()
