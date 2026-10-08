import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import argparse
import importlib.util

ROOT = Path(__file__).resolve().parent.parent

class SetupTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.env = dict(os.environ, HOME=str(self.home))

    def tearDown(self):
        shutil.rmtree(self.home)

    def run_step(self, name, *args):
        return subprocess.run([str(ROOT / 'steps' / name), *args], env=self.env, capture_output=True, text=True, check=True)

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
        self.run_step('apply', '--yes')
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
