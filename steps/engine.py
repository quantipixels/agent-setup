#!/usr/bin/env python3
"""Portable, dependency-free setup operations. Python 3.11 or later."""
import argparse
import datetime
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get('HOME', str(Path.home()))).absolute()
STATE = HOME / '.agent-setup'


def merge(host, base):
    if isinstance(host, dict) and isinstance(base, dict):
        out = dict(host)
        for key, value in base.items():
            out[key] = merge(out[key], value) if key in out else value
        return out
    return base


def toml_text(data):
    """Serialize the TOML value types supported by tomllib, without dependencies."""
    def key(k):
        return json.dumps(k, ensure_ascii=False)
    def val(v):
        if isinstance(v, str): return json.dumps(v, ensure_ascii=False)
        if isinstance(v, bool): return 'true' if v else 'false'
        if isinstance(v, (int, float)): return str(v).lower()
        if isinstance(v, (datetime.datetime, datetime.date, datetime.time)): return v.isoformat()
        if isinstance(v, list): return '[' + ', '.join(val(x) for x in v) + ']'
        if isinstance(v, dict): return '{' + ', '.join(key(k) + ' = ' + val(x) for k, x in v.items()) + '}'
        raise ValueError('Unsupported TOML type: ' + type(v).__name__)
    lines = []
    def table(obj, path):
        if path: lines.extend(['', '[' + '.'.join(key(k) for k in path) + ']'])
        for k, v in obj.items():
            if not isinstance(v, dict): lines.append(key(k) + ' = ' + val(v))
        for k, v in obj.items():
            if isinstance(v, dict): table(v, path + [k])
    table(data, [])
    return '\n'.join(lines).lstrip('\n') + '\n'


def parse(data, suffix):
    return json.loads(data) if suffix == '.json' else tomllib.loads(data)


def serial(data, suffix):
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n' if suffix == '.json' else toml_text(data)


def safe(path):
    """Reject any write target whose resolved parent or existing symlink leaves HOME."""
    path = Path(path).absolute()
    if not path.is_relative_to(HOME) or not path.resolve().is_relative_to(HOME.resolve()):
        raise ValueError('Unsafe path outside HOME: ' + str(path))
    cursor = path
    while cursor != HOME:
        if cursor.is_symlink(): raise ValueError('Refusing symlink write: ' + str(cursor))
        cursor = cursor.parent
    return path


def template(text):
    shared = ROOT / 'base/shared/instructions.md'
    return text.replace('${SHARED_INSTRUCTIONS}', shared.read_text() if shared.exists() else '').replace('${HOME}', str(HOME))


def desired():
    result = {}
    for client, instruction in [('claude', 'CLAUDE.md'), ('codex', 'AGENTS.md')]:
        directory = ROOT / 'base' / client
        if not directory.exists(): continue
        for source in sorted(directory.rglob('*')):
            if not source.is_file(): continue
            rel = source.relative_to(directory)
            if source.name in ('plugins.txt', 'marketplaces.txt', 'agents.pins.toml'): continue
            rel = Path(str(rel).removesuffix('.tmpl'))
            text = template(source.read_text())
            target = HOME / ('.' + client) / rel
            result[target] = text
    pins = ROOT / 'base/codex/agents.pins.toml'
    caches = sorted((HOME / '.codex/plugins/cache/alarina/alarina').glob('*/codex-agents'), key=lambda p: [int(x) if x.isdigit() else x for x in re.split(r'[.]', p.parent.name)])
    if pins.exists() and caches:
        entries = tomllib.loads(pins.read_text())
        for shipped in sorted(caches[-1].glob('*.toml')):
            lines = [line for line in shipped.read_text().splitlines(keepends=True) if not re.match(r'(model|model_reasoning_effort) = ', line)]
            pair = entries.get(shipped.stem, {})
            pinned = ''.join(f'{key} = "{value}"\n' for key, value in pair.items())
            result[HOME / '.codex/agents' / shipped.name] = ''.join(lines[:2]) + pinned + ''.join(lines[2:])
    return result


def plan():
    result = {}
    for path, data in desired().items():
        safe(path)
        old = path.read_text() if path.exists() else ''
        suffix = path.suffix
        if suffix in ('.json', '.toml'):
            data = serial(merge(parse(old, suffix) if old else {}, parse(data, suffix)), suffix)
        result[path] = (old, data)
    return result


def emit_diff(items):
    changed = False
    for path, (old, new) in items.items():
        if old == new: continue
        changed = True
        print(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile=str(path), tofile=str(path) + ' (base)')), end='')
    if not changed: print('Managed files already match the base.')


def backup(path):
    if not path.exists(): return
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    dest = safe(STATE / 'backups' / stamp / path.relative_to(HOME))
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)


def write(path, content, executable=False):
    safe(path)
    if path.exists() and path.read_text() == content: return
    backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    if executable or path.suffix == '.sh': path.chmod(0o755)


def apply(args):
    items = plan()
    conflicts = [str(p) for p, (old, new) in items.items() if old and old != new and p.suffix not in ('.json', '.toml')]
    if conflicts and not args.yes:
        raise ValueError('Live-file conflicts require --yes: ' + ', '.join(conflicts))
    if args.dry_run: emit_diff(items); return
    for path, (_, data) in items.items(): write(path, data)
    print('Applied managed files with backups for overwritten files.')


def install_env():
    return dict(os.environ, HOME=str(HOME), CODEX_HOME=str(HOME / ".codex"), CLAUDE_CONFIG_DIR=str(HOME / ".claude"), MISE_DATA_DIR=str(HOME / ".local/share/mise"), MISE_CACHE_DIR=str(HOME / ".cache/mise"), MISE_STATE_DIR=str(HOME / ".local/state/mise"), MISE_CONFIG_DIR=str(HOME / ".config/mise"), npm_config_prefix=str(HOME / ".local"), npm_config_cache=str(HOME / ".cache/npm"))


def run(command):
    print('+ ' + ' '.join(command), flush=True)
    subprocess.run(command, check=True, env=install_env())


def manifest(name):
    path = ROOT / 'base' / name
    if not path.exists(): return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]


def tool_names():
    return ['git', 'python3', 'mise', 'node', 'npm', 'npx', 'claude', 'codex', 'gh', 'rg', 'fd', 'jq', 'ast-grep', 'lefthook', 'gitleaks', 'shellcheck', 'shfmt', 'vp', 'oxlint', 'oxfmt', 'ruff']


def check_tools(args):
    missing = [tool for tool in tool_names() if not shutil.which(tool)]
    for tool in tool_names(): print(tool + ': ' + (shutil.which(tool) or 'MISSING'))
    if missing: raise ValueError('Missing tools: ' + ', '.join(missing))


def plugins(args):
    if args.offline or args.dry_run:
        print('Offline structural profile: skipped plugin installation and authentication.'); return
    known_path = HOME / '.claude/plugins/known_marketplaces.json'
    known = json.loads(known_path.read_text()) if known_path.is_file() else {}
    for row in manifest('claude/marketplaces.txt'):
        name, source = row.split('\t', 1)
        if name not in known:
            run(['claude', 'plugin', 'marketplace', 'add', source])
        run(['claude', 'plugin', 'marketplace', 'update', name])
    for name in manifest('claude/plugins.txt'):
        run(['claude', 'plugin', 'install', name, '--scope', 'user'])
        run(['claude', 'plugin', 'update', name, '--scope', 'user'])
    (HOME / '.codex').mkdir(parents=True, exist_ok=True)
    run(['codex', 'plugin', 'marketplace', 'upgrade'])
    for name in manifest('codex/plugins.txt'):
        if name.endswith('@openai-curated') and args.no_login:
            print('Needs codex login first: ' + name); continue
        run(['codex', 'plugin', 'add', name])


def skills(args):
    if args.offline or args.dry_run:
        print('Offline structural profile: skipped skill installation.'); return
    for row in manifest('skills.txt'):
        source, name = row.split('\t', 1)
        run(['npx', '--yes', 'skills@latest', 'add', source, '--skill', name, '--global', '--agent', 'claude-code', '--agent', 'codex', '--yes'])


def toolkit(args):
    rows = manifest('toolkit.tsv')
    print('\n'.join(rows))
    if args.offline or args.dry_run:
        print('Toolkit shown only; install skipped.'); return
    wanted = mise_tools()
    missing = [name for name, binary in wanted.items() if not shutil.which(binary)]
    for name in wanted:
        if name not in missing: print('Skipped (already installed): ' + name + ' ' + tool_version(wanted[name]))
    if missing: run(['mise', 'install', '--cd', str(ROOT), *missing])
    proc = subprocess.run(['mise', 'env', '--json', '--cd', str(ROOT)], env=install_env(), text=True, capture_output=True, check=True)
    os.environ.update(json.loads(proc.stdout))


BINARIES = {'python': 'python3', 'ripgrep': 'rg', 'npm:vite-plus': 'vp', 'npm:oxfmt': 'oxfmt'}


def mise_tools():
    tools = tomllib.loads((ROOT / 'mise.toml').read_text()).get('tools', {})
    return {name: BINARIES.get(name, name) for name in tools}


def tool_version(binary):
    try:
        proc = subprocess.run([binary, '--version'], text=True, capture_output=True, timeout=20)
        match = re.search(r'\d+\.\d+(?:\.\d+)?', proc.stdout + proc.stderr)
        return match.group(0) if match else 'unknown'
    except (OSError, subprocess.SubprocessError): return 'unknown'


def update_command(name, binary):
    path = shutil.which(binary) or ''
    if '/mise/' in path: return 'mise upgrade ' + name
    if '/Cellar/' in path or path.startswith('/opt/homebrew'): return 'brew upgrade ' + name
    if 'node_modules' in path or path.startswith(str(HOME / '.local/bin')): return 'npm install -g ' + {'codex': '@openai/codex', 'claude': '@anthropic-ai/claude-code'}.get(name, name)
    return 'unknown'


def updates():
    rows = []
    for name, binary in mise_tools().items():
        installed, latest = tool_version(binary), 'unknown'
        try: latest = subprocess.run(['mise', 'latest', name], text=True, capture_output=True, timeout=30, env=install_env()).stdout.strip() or 'unknown'
        except (OSError, subprocess.SubprocessError): pass
        if latest == 'unknown' or installed == 'unknown' or not latest.startswith(installed):
            rows.append(' | '.join([name, installed, latest, update_command(name, binary)]))
    print('Updates available' if rows else 'No updates found')
    if rows: print('\n'.join(['tool | installed | latest | update command', *rows]))


def profile():
    path = STATE / 'profile.json'
    return json.loads(path.read_text()).get('profile', 'full') if path.exists() else 'full'


def hook_paths(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == 'command' and isinstance(item, str):
                for match in re.findall(r'(?:\$HOME|\$\{HOME\}|/[^\s"\']+)[^\s"\']*\.sh', item):
                    yield Path(match.replace('${HOME}', str(HOME)).replace('$HOME', str(HOME)))
            yield from hook_paths(item)
    elif isinstance(value, list):
        for item in value: yield from hook_paths(item)


def doctor(args):
    errors = []
    mode = profile()
    for path, wanted in desired().items():
        try:
            safe(path)
            if not path.exists(): errors.append('Missing managed file: ' + str(path)); continue
            actual = path.read_text()
            if path.suffix in ('.json', '.toml'):
                obj, expected = parse(actual, path.suffix), parse(wanted, path.suffix)
                if merge(obj, expected) != obj: errors.append('Base keys differ: ' + str(path))
                for hook in hook_paths(obj):
                    safe(hook)
                    if not hook.is_file() or not os.access(hook, os.X_OK): errors.append('Missing executable hook: ' + str(hook))
            elif actual != wanted: errors.append('Managed content differs: ' + str(path))
        except (ValueError, OSError) as exc: errors.append(str(exc))
    if mode == 'full':
        errors.extend('Missing tool: ' + x for x in tool_names() if not shutil.which(x))
        for row in manifest('skills.txt'):
            name = row.split('\t', 1)[1]
            if not (HOME / '.agents/skills' / name / 'SKILL.md').is_file(): errors.append('Missing skill: ' + name)
        claude_path = HOME / '.claude/plugins/installed_plugins.json'
        claude_installed = json.loads(claude_path.read_text()).get('plugins', {}) if claude_path.is_file() else {}
        for plugin in manifest('claude/plugins.txt'):
            records = claude_installed.get(plugin, [])
            if not any(record.get('scope') == 'user' and Path(record.get('installPath', '')).is_dir() for record in records):
                errors.append('Missing Claude user plugin: ' + plugin)
        proc = subprocess.run(['codex', 'plugin', 'list', '--json'], env=install_env(), text=True, capture_output=True)
        if proc.returncode:
            errors.append('Cannot list Codex plugins: ' + proc.stderr.strip())
        else:
            codex_installed = json.loads(proc.stdout).get('installed', [])
            for plugin in manifest('codex/plugins.txt'):
                # Confirm this selector in the CLI's installed inventory, not its cache.
                if not any(plugin in json.dumps(record) for record in codex_installed):
                    if plugin.endswith('@openai-curated'): print('Pending codex login: ' + plugin)
                    else: errors.append('Missing Codex plugin: ' + plugin)
    if errors: raise ValueError('Doctor failed:\n' + '\n'.join(errors))
    print('Doctor passed: ' + mode + (' (managed files only; tools, plugins, skills and login were skipped).' if mode == 'offline-structural' else ' (managed files, tools, plugins and skills checked).'))
    if mode != 'full': return
    lock = {'profile': mode, 'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': {str(p.relative_to(HOME)): hashlib.sha256(p.read_bytes()).hexdigest() for p in desired()}, 'versions': {}, 'plugins': {'claude': claude_installed, 'codex': codex_installed}, 'skills': {name: {'source': source, 'revision': subprocess.run(['git', '-C', str(HOME / '.agents/skills' / name), 'rev-parse', 'HEAD'], text=True, capture_output=True).stdout.strip()} for source, name in (row.split('\t', 1) for row in manifest('skills.txt'))}}
    if mode == 'full':
        for name in tool_names():
            proc = subprocess.run([name, '--version'], text=True, capture_output=True)
            lock['versions'][name] = (proc.stdout or proc.stderr).strip().splitlines()[:1]
    if not args.dry_run: write(STATE / 'last-good.lock', json.dumps(lock, indent=2) + '\n')


def setup(args):
    if args.dry_run: emit_diff(plan()); print('Plan only: no writes, installs or authentication.'); return
    if not args.yes:
        raise ValueError('Setup requires diff approval first; use --yes after approval.')
    plan()  # Validate malformed live files before installs.
    if not args.offline:
        toolkit(args)
        check_tools(args)
    apply(args)
    if not args.offline:
        plugins(args)
        skills(args)
        apply(args)  # Codex agent roles come from the plugin cache, which exists only after plugins().
        if not args.no_login:
            print('Login pause: run ! gh auth login, claude auth login, and codex login by hand.')
    else: print('Offline structural profile: skipped all network installation and login.')
    write(STATE / 'profile.json', json.dumps({'profile': 'offline-structural' if args.offline else 'full'}) + '\n')
    doctor(args)
    if not args.offline:
        try: updates()
        except Exception as exc: print('Update check skipped: ' + str(exc))


def capture(args):
    if not args.output: raise ValueError('capture requires --output <directory inside this repo>')
    dest = Path(args.output).absolute()
    if not dest.resolve().is_relative_to(ROOT.resolve()) or dest.is_symlink(): raise ValueError('Capture destination must be inside this repo.')
    # Capture only known base-owned paths; no broad traversal of the user's configuration.
    captures = {}
    for target, base_text in desired().items():
        if not target.is_file(): continue
        text = target.read_text()
        if target.suffix in ('.json', '.toml'):
            current, allowed = parse(text, target.suffix), parse(base_text, target.suffix)
            def restrict(obj, keys):
                return {k: restrict(obj[k], v) if isinstance(v, dict) and isinstance(obj.get(k), dict) else obj[k] for k, v in keys.items() if k in obj and not re.search(r'token|secret|password|credential|auth|api.?key', k, re.I)}
            text = serial(restrict(current, allowed), target.suffix)
        text = text.replace(str(HOME), '${HOME}')
        rel = target.relative_to(HOME)
        captures[dest / str(rel.parts[0]).lstrip('.') / Path(*rel.parts[1:])] = text
    if args.dry_run:
        for path in captures: print('Would capture: ' + str(path))
        return
    if any(p.exists() for p in captures) and not args.yes: raise ValueError('Capture overwrites require --yes')
    for path, text in captures.items():
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()): raise ValueError('Unsafe capture path: ' + str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    print('Captured allowlisted managed files only: ' + str(dest))


def cleanup(args):
    # No deletions are implicit. Backup pruning is the only supported removal.
    print('Cleanup target: ' + str(STATE / 'backups'))
    if not args.approve_removals or args.dry_run:
        print('No files removed. Use --approve-removals to remove setup backups.'); return
    target = safe(STATE / 'backups')
    if target.exists(): shutil.rmtree(target)
    print('Removed setup backups.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'render', 'diff', 'apply', 'setup', 'check-tools', 'plugins', 'skills', 'codex-agents', 'toolkit', 'doctor', 'capture', 'cleanup'])
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--no-login', action='store_true', help='Skip login prompts; public installs still run')
    parser.add_argument('--offline', action='store_true', help='Structural profile only; skip network installs')
    parser.add_argument('--yes', action='store_true', help='Approve overwrites of conflicting managed text files')
    parser.add_argument('--approve-removals', action='store_true')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.command in ('plan', 'diff', 'render'):
        if args.command == 'render':
            if args.output: raise ValueError('Render writes are disabled; redirect stdout to an explicit destination.')
            for path, (_, value) in plan().items(): print('--- ' + str(path) + '\n' + value)
        else: emit_diff(plan())
        return
    actions = {'apply': apply, 'setup': setup, 'check-tools': check_tools, 'plugins': plugins, 'skills': skills, 'codex-agents': apply, 'toolkit': toolkit, 'doctor': doctor, 'capture': capture, 'cleanup': cleanup}
    actions[args.command](args)

if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
