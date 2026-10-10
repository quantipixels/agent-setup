import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
import tomllib
import unittest
from unittest import mock
import argparse
import importlib.util

ROOT = Path(__file__).resolve().parent.parent

class SetupTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.env = dict(os.environ, HOME=str(self.home), AGENT_SETUP_NAME='Test user')

    def tearDown(self):
        shutil.rmtree(self.home)

    def run_step(self, name, *args, check=True):
        return subprocess.run([str(ROOT / 'steps' / name), *args], env=self.env, capture_output=True, text=True, check=check)

    def test_hook_paths_expand_tilde(self):
        spec = importlib.util.spec_from_file_location('engine', ROOT / 'steps/engine.py')
        engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(engine)
        found = list(engine.hook_paths({'command': 'bash ~/.claude/statusline-command.sh'}))
        self.assertEqual(found, [engine.HOME / '.claude/statusline-command.sh'])

    def test_plan_has_no_writes(self):
        result = self.run_step('diff')
        self.assertIn('+++', result.stdout)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_hooks_render_in_each_host_format(self):
        out = self.run_step('render').stdout
        claude = json.loads(out.split('--- ' + str(self.home / '.claude/settings.json') + '\n')[1].split('\n--- ')[0])
        codex = json.loads(out.split('--- ' + str(self.home / '.codex/hooks.json') + '\n')[1].split('\n--- ')[0])
        self.assertEqual(claude['hooks']['PreToolUse'][0]['hooks'][0]['timeout'], 10)
        self.assertNotIn('statusMessage', json.dumps(claude['hooks']))
        self.assertEqual(codex['hooks']['Stop'][0]['hooks'][0]['statusMessage'], 'Design deep pass')
        self.assertNotIn('matcher', codex['hooks']['Stop'][0])
        self.assertIn(str(self.home), codex['hooks']['PreToolUse'][0]['hooks'][0]['command'])
        self.assertIn('symlink -> ' + str(self.home / '.agents/AGENTS.md'), out)
        self.assertIn('@~/.agents/AGENTS.md', out)

    def test_merge_backup_and_idempotency(self):
        target = self.home / '.claude/settings.json'
        target.parent.mkdir()
        target.write_text(json.dumps({'host_added': {'keep': True}, 'tui': 'old'}))
        self.run_step('setup', '--offline', '--no-login', '--yes')
        data = json.loads(target.read_text())
        self.assertTrue(data['host_added']['keep'])
        self.assertEqual(data['tui'], 'fullscreen')
        backups = list((self.home / '.agent-setup/backups').rglob('settings.json'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(json.loads(backups[0].read_text())['tui'], 'old')
        self.run_step('apply', '--offline', '--yes')
        self.assertEqual(len(list((self.home / '.agent-setup/backups').rglob('settings.json'))), 1)

    def test_toolkit_installs_only_missing_tools(self):
        spec = importlib.util.spec_from_file_location('engine', ROOT / 'steps/engine.py')
        engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(engine)
        present = {'git', 'rg', 'jq'}
        env_proc = mock.Mock(stdout='{}')
        with mock.patch.object(engine.shutil, 'which', lambda x: '/bin/' + x if x in present else None), \
             mock.patch.object(engine, 'tool_version', lambda x: '1.0'), \
             mock.patch.object(engine, 'load_yaml', return_value={}), \
             mock.patch.object(engine, 'run') as run, \
             mock.patch.object(engine.subprocess, 'run', return_value=env_proc):
            engine.toolkit(argparse.Namespace(offline=False, dry_run=False))
        command = run.call_args[0][0]
        self.assertIn('gh', command)
        self.assertNotIn('ripgrep', command)
        self.assertNotIn('jq', command)

    def snapshot(self):
        return {str(path.relative_to(self.home)): (os.readlink(path) if path.is_symlink() else path.read_bytes() if path.is_file() else None, path.lstat().st_mtime_ns)
                for path in self.home.rglob('*')}

    def instruction_paths(self):
        return self.home / '.agents/AGENTS.md', self.home / '.codex/AGENTS.md', self.home / '.claude/CLAUDE.md'

    def test_fresh_machine_seeds_one_source_and_links_hosts(self):
        self.run_step('setup', '--offline', '--no-login', '--yes')
        source, codex, claude = self.instruction_paths()
        text = source.read_text()
        self.assertEqual(text, (ROOT / 'base/shared/instructions.md').read_text())
        for retired in ('ASD-STE100', 'Subagents and resources', 'Members and effort', 'Codex workers', 'Opus advisor'):
            self.assertNotIn(retired, text)
        self.assertTrue(codex.is_symlink())
        self.assertEqual(codex.resolve(), source.resolve())
        self.assertEqual(claude.read_text(), '@~/.agents/AGENTS.md\n')
        config = tomllib.loads((self.home / '.codex/config.toml').read_text())
        self.assertEqual(config['model'], 'gpt-6-sol')
        self.assertEqual(config['agents']['default_subagent_model'], 'gpt-6-luna')
        self.assertIn('Doctor passed: offline-structural', self.run_step('doctor').stdout)

    def test_current_instruction_layout_is_untouched(self):
        source, codex, claude = self.instruction_paths()
        for path in (source, codex, claude): path.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('My own defaults, maintained by asami.\n')
        codex.symlink_to(source)
        claude.write_text('@~/.agents/AGENTS.md\n\nClaude-only rule.\n')
        before = {path: path.lstat().st_mtime_ns for path in (source, codex, claude)}
        self.run_step('setup', '--offline', '--no-login', '--yes')
        source.write_text('Changed by the user after setup.\n')
        before[source] = source.lstat().st_mtime_ns
        snapshot = self.snapshot()
        self.run_step('apply', '--offline')
        self.assertEqual(self.snapshot(), snapshot)
        self.assertIn('already match', self.run_step('diff').stdout)
        self.assertIn('Doctor passed', self.run_step('doctor').stdout)
        self.assertEqual(before, {path: path.lstat().st_mtime_ns for path in (source, codex, claude)})
        self.assertEqual(source.read_text(), 'Changed by the user after setup.\n')
        self.assertEqual(claude.read_text(), '@~/.agents/AGENTS.md\n\nClaude-only rule.\n')
        self.assertFalse((self.home / '.agent-setup/backups').exists())

    def test_old_instruction_files_require_approval_and_are_backed_up(self):
        source, codex, claude = self.instruction_paths()
        old = {codex: 'Old Codex managed rules.\n', claude: '# Working with Test user\n\n## Subagents and resources\nOld managed rules.\n'}
        for path, text in old.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        snapshot = self.snapshot()
        for command in ('diff', 'apply', 'setup'):
            output = self.run_step(command, '--dry-run', '--offline').stdout
            for path in old:
                self.assertIn('Would back up: ' + str(path), output)
                self.assertIn(str(self.home / '.agent-setup/backups/<timestamp>' / path.relative_to(self.home)), output)
            self.assertIn('replace file with symlink: ' + str(codex) + ' -> ' + str(source), output)
            self.assertIn('+@~/.agents/AGENTS.md', output)
            self.assertEqual(self.snapshot(), snapshot)
        refused = self.run_step('apply', '--offline', check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('require --yes', refused.stderr)
        self.assertEqual(self.snapshot(), snapshot)
        self.run_step('setup', '--offline', '--no-login', '--yes')
        self.assertTrue(source.is_file())
        self.assertEqual(codex.resolve(), source.resolve())
        self.assertTrue(codex.is_symlink())
        self.assertEqual(claude.read_text(), '@~/.agents/AGENTS.md\n')
        for path, text in old.items():
            backups = list((self.home / '.agent-setup/backups').glob('*/' + str(path.relative_to(self.home))))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), text)
        self.assertIn('Doctor passed', self.run_step('doctor').stdout)

    def test_doctor_checks_instruction_layout(self):
        self.run_step('setup', '--offline', '--no-login', '--yes')
        source, codex, claude = self.instruction_paths()
        for path, message in ((source, 'Missing instruction source'), (codex, 'Codex instructions must link'), (claude, 'Claude instructions must start')):
            with self.subTest(path=path):
                content = os.readlink(path) if path.is_symlink() else path.read_text()
                linked = path.is_symlink()
                path.unlink()
                output = self.run_step('doctor', '--dry-run', check=False)
                self.assertNotEqual(output.returncode, 0)
                self.assertIn(message, output.stderr)
                if linked: path.symlink_to(content)
                else: path.write_text(content)

    def test_only_the_canonical_codex_instruction_symlink_is_allowed(self):
        self.run_step('setup', '--offline', '--no-login', '--yes')
        source, codex, claude = self.instruction_paths()
        other = self.home / 'other.md'
        other.write_text('Other user data.\n')
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / 'instructions.md'
            external.write_text('Outside HOME.\n')
            for path, destination in ((codex, external), (codex, other), (claude, source), (source, other), (self.home / '.claude/settings.json', source)):
                with self.subTest(path=path, destination=destination):
                    linked = path.is_symlink()
                    original = os.readlink(path) if linked else path.read_text()
                    path.unlink()
                    path.symlink_to(destination)
                    snapshot = self.snapshot()
                    refused = self.run_step('apply', '--offline', '--yes', check=False)
                    self.assertNotEqual(refused.returncode, 0)
                    self.assertIn('symlink', refused.stderr.lower())
                    self.assertEqual(self.snapshot(), snapshot)
                    path.unlink()
                    if linked: path.symlink_to(original)
                    else: path.write_text(original)
            self.assertEqual(external.read_text(), 'Outside HOME.\n')
        codex.unlink()
        codex.symlink_to('../.agents/AGENTS.md')
        self.run_step('apply', '--offline')
        self.assertEqual(os.readlink(codex), '../.agents/AGENTS.md')
        self.assertIn('Doctor passed', self.run_step('doctor').stdout)

    def fake_clients(self, *programs):
        directory = self.home / 'test-bin'
        directory.mkdir(exist_ok=True)
        self.env['PATH'] = str(directory) + os.pathsep + self.env['PATH']
        self.env['TEST_COMMANDS'] = str(self.home / 'commands.jsonl')
        script = '#!' + sys.executable + '\n' + '''import json, os, sys
from pathlib import Path
program = Path(sys.argv[0]).name
with open(os.environ['TEST_COMMANDS'], 'a') as log:
    log.write(json.dumps([program, *sys.argv[1:]]) + '\\n')
if program == 'codex' and sys.argv[1:] == ['plugin', 'list', '--json']:
    print(json.dumps({'installed': json.loads(os.environ.get('TEST_CODEX_PLUGINS', '[]'))}))
else:
    print('1.0.0')
'''
        for program in {'claude', 'codex', 'npx', *programs}:
            path = directory / program
            path.write_text(script)
            path.chmod(0o755)

    def test_plugin_and_skill_lists_install_qp_skills_without_uninstalling(self):
        self.run_step('setup', '--offline', '--no-login', '--yes')
        settings = json.loads((self.home / '.claude/settings.json').read_text())
        expected = {'plugin-dev', 'typescript-lsp', 'pyright-lsp', 'rust-analyzer-lsp', 'jdtls-lsp', 'kotlin-lsp', 'swift-lsp', 'hookify', 'playwright', 'modern-web-guidance'}
        expected = {name + '@claude-plugins-official' for name in expected} | {'codex@openai-codex', 'ast-grep@ast-grep-marketplace', 'qp-skills@qp-skills'}
        self.assertEqual(set(settings['enabledPlugins']), expected)
        self.assertEqual(settings['extraKnownMarketplaces']['qp-skills']['source']['repo'], 'quantipixels/skills')
        self.assertNotIn('alarina', settings['extraKnownMarketplaces'])
        config = tomllib.loads((self.home / '.codex/config.toml').read_text())
        self.assertEqual(config['marketplaces'], {'qp-skills': {'source_type': 'git', 'source': 'https://github.com/quantipixels/skills.git'}})
        # Removed rows are no longer installed, but existing artifacts stay.
        removed = self.home / '.agents/skills/skill-doctor/SKILL.md'
        removed.parent.mkdir(parents=True)
        removed.write_text('User-owned existing skill.\n')
        settings['enabledPlugins']['alarina@alarina'] = True
        (self.home / '.claude/settings.json').write_text(json.dumps(settings))
        self.run_step('apply', '--offline')
        self.fake_clients()
        self.run_step('plugins', '--no-login')
        self.run_step('skills')
        commands = [json.loads(line) for line in Path(self.env['TEST_COMMANDS']).read_text().splitlines()]
        claude_plugins = {command[3] for command in commands if command[:3] == ['claude', 'plugin', 'install']}
        self.assertEqual(claude_plugins, expected)
        self.assertIn(['claude', 'plugin', 'marketplace', 'add', 'quantipixels/skills'], commands)
        self.assertIn(['codex', 'plugin', 'add', 'qp-skills@qp-skills'], commands)
        installed_skills = {command[command.index('--skill') + 1] for command in commands if command[0] == 'npx'}
        self.assertEqual(installed_skills, {'shadcn', 'agent-browser', 'vercel-react-best-practices', 'vercel-composition-patterns', 'frontend-design', 'impeccable', 'better-interface', 'swiftui-pro', 'appllama-app-design-skill', 'appllama-usage', 'animate', 'animation-vocabulary', 'apple-design', 'emil-design-eng', 'improve-animations', 'fframes-video', 'tech-stack'})
        self.assertFalse(any(word in command for command in commands for word in ('uninstall', 'remove')))
        self.assertEqual(removed.read_text(), 'User-owned existing skill.\n')
        self.assertTrue(json.loads((self.home / '.claude/settings.json').read_text())['enabledPlugins']['alarina@alarina'])

    def test_full_doctor_warns_about_retired_plugins_without_failing(self):
        self.run_step('setup', '--offline', '--no-login', '--yes')
        config = tomllib.loads((ROOT / 'mise.toml').read_text())
        binaries = {'python': 'python3', 'ripgrep': 'rg', 'npm:vite-plus': 'vp', 'npm:oxfmt': 'oxfmt', 'npm:typescript': 'tsc', 'npm:pyright': 'pyright'}
        self.fake_clients('git', 'mise', 'npm', *(binaries.get(name, name) for name in config['tools'] if name not in ('python', 'yq')))
        settings = json.loads((self.home / '.claude/settings.json').read_text())
        cache = self.home / 'fixture-plugin-cache'
        cache.mkdir()
        inventory = {plugin: [{'scope': 'user', 'installPath': str(cache)}] for plugin in settings['enabledPlugins']}
        inventory['alarina@alarina'] = [{'scope': 'user', 'installPath': str(cache)}]
        path = self.home / '.claude/plugins/installed_plugins.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'plugins': inventory}))
        # Use the installers' actual skill selectors, with only the external clients stubbed.
        self.run_step('skills')
        for line in Path(self.env['TEST_COMMANDS']).read_text().splitlines():
            command = json.loads(line)
            if command[0] != 'npx': continue
            path = self.home / '.agents/skills' / command[command.index('--skill') + 1] / 'SKILL.md'
            path.parent.mkdir(parents=True)
            path.write_text('Fixture installed skill.\n')
        (self.home / '.agent-setup/profile.json').write_text('{"profile": "full"}\n')
        self.env['TEST_CODEX_PLUGINS'] = json.dumps(['qp-skills@qp-skills', 'alarina@alarina'])
        output = self.run_step('doctor', '--dry-run').stdout
        self.assertIn('claude plugin uninstall alarina@alarina --scope user', output)
        self.assertIn('codex plugin remove alarina@alarina', output)
        self.assertIn('Doctor passed: full', output)
