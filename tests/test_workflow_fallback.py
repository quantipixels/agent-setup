import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


class WorkflowFallbackTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        spec = importlib.util.spec_from_file_location('engine', ROOT / 'steps/engine.py')
        self.engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.engine)
        self.engine.HOME = Path(self.directory.name)
        self.engine.STATE = self.engine.HOME / '.agent-setup'
        self.row = next(row for row in self.engine.load_yaml('plugins.yaml')['plugins'] if row.get('preferred'))

    def install(self, host, access=True, fail=()):
        commands = []
        def run(command):
            commands.append(command)
            if any(selector in command for selector in fail):
                raise subprocess.CalledProcessError(1, command)
        response = subprocess.CompletedProcess([], 0 if access else 1, 'true\n' if access else '', '')
        with mock.patch.object(self.engine.subprocess, 'run', return_value=response), mock.patch.object(self.engine, 'run', side_effect=run):
            self.engine.install_workflow(host, self.row)
        return commands

    def test_preferred_success_is_per_host_and_drives_rendering(self):
        initial = json.loads(self.engine.claude_settings('{}', []))
        self.assertNotIn('qp-skills@qp-skills', initial['enabledPlugins'])
        commands = self.install('claude')
        self.assertTrue(any('alarina@alarina' in command for command in commands))
        self.assertTrue(any('software-eng@alarina' in command for command in commands))
        self.assertTrue(any('productivity@alarina' in command for command in commands))
        self.assertFalse(any('qp-skills@qp-skills' in command for command in commands))
        self.assertEqual(self.engine.workflow_selections(), {'claude': 'alarina@alarina'})
        self.assertEqual(next(row for row in self.engine.plugin_rows('claude') if row.get('preferred'))['claude'], 'alarina@alarina')
        self.assertEqual(next(row for row in self.engine.plugin_rows('codex') if row.get('preferred'))['codex'], 'qp-skills@qp-skills')
        settings = json.loads(self.engine.claude_settings('{}', []))
        self.assertTrue(settings['enabledPlugins']['alarina@alarina'])
        for pack in self.row['preferred']['packs']:
            self.assertTrue(any(pack + '@alarina' in command for command in commands))
            self.assertTrue(settings['enabledPlugins'][pack + '@alarina'])
        self.assertEqual(settings['extraKnownMarketplaces']['alarina']['source']['repo'], 'quantipixels/alarina')
        commands = self.install('codex')
        self.assertIn(['codex', 'plugin', 'add', 'software-eng@alarina'], commands)
        self.assertIn(['codex', 'plugin', 'add', 'productivity@alarina'], commands)
        config = self.engine.desired([])[self.engine.HOME / '.codex/config.toml']
        self.assertIn('https://github.com/quantipixels/alarina.git', config)

    def test_no_access_uses_public_fallback_on_both_hosts(self):
        for host in ('claude', 'codex'):
            commands = self.install(host, access=False)
            self.assertTrue(any('qp-skills@qp-skills' in command for command in commands))
            self.assertFalse(any('@alarina' in ' '.join(command) for command in commands))
            self.assertEqual(self.engine.workflow_selections()[host], 'qp-skills@qp-skills')

    def test_preferred_install_failure_replaces_previous_selection_with_fallback(self):
        for host in ('claude', 'codex'):
            self.install(host)
            commands = self.install(host, fail=('alarina@alarina',))
            self.assertTrue(any('qp-skills@qp-skills' in command for command in commands))
            self.assertEqual(self.engine.workflow_selections()[host], 'qp-skills@qp-skills')
            self.assertEqual(next(row for row in self.engine.plugin_rows(host) if row.get('preferred'))[host], 'qp-skills@qp-skills')

    def test_optional_pack_failure_keeps_preferred_workflow(self):
        pack = self.row['preferred']['packs'][0] + '@alarina'
        for host in ('claude', 'codex'):
            commands = self.install(host, fail=(pack,))
            self.assertFalse(any('qp-skills@qp-skills' in command for command in commands))
            self.assertTrue(any(self.row['preferred']['packs'][-1] + '@alarina' in command for command in commands))
            self.assertEqual(self.engine.workflow_selections()[host], 'alarina@alarina')

    def test_preferred_marketplace_refresh_failure_falls_back(self):
        config = self.engine.HOME / '.codex/config.toml'
        config.parent.mkdir()
        config.write_text('[marketplaces.alarina]\nsource_type = "git"\nsource = "https://github.com/quantipixels/alarina.git"\n')
        commands = self.install('codex', fail=('alarina',))
        self.assertIn(['codex', 'plugin', 'marketplace', 'upgrade', 'alarina'], commands)
        self.assertEqual(self.engine.workflow_selections()['codex'], 'qp-skills@qp-skills')

    def test_fallback_failure_does_not_record_success(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.install('codex', fail=('alarina@alarina', 'qp-skills@qp-skills'))
        self.assertEqual(self.engine.workflow_selections(), {})

    def test_offline_and_dry_run_skip_access_and_installation(self):
        with mock.patch.object(self.engine.subprocess, 'run') as process, mock.patch.object(self.engine, 'run') as run:
            for offline, dry_run in ((True, False), (False, True)):
                self.engine.plugins(argparse.Namespace(offline=offline, dry_run=dry_run))
        process.assert_not_called()
        run.assert_not_called()
        self.assertEqual(list(self.engine.HOME.iterdir()), [])
