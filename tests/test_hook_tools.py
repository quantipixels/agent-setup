import argparse
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


class HookToolsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        env = mock.patch.dict(os.environ, HOME=str(self.home), AGENT_SETUP_NAME='Test user')
        env.start()
        self.addCleanup(env.stop)
        spec = importlib.util.spec_from_file_location('engine', ROOT / 'steps/engine.py')
        self.engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.engine)
        # Read the actual YAML through yq before replacing PATH discovery or installers.
        for filename in ('hooks.yaml', 'plugins.yaml', 'project-toolchains.yaml'):
            self.engine.load_yaml(filename)
        self.args = argparse.Namespace(offline=False, dry_run=False, yes=True, no_login=True)

    def which_without(self, missing):
        return lambda program: None if program in missing else '/bin/' + program

    def installed_hooks(self):
        return json.loads((self.home / '.claude/settings.json').read_text())['hooks']

    def install_fixture(self):
        self.args.offline = True
        with mock.patch.object(self.engine.shutil, 'which', self.which_without(set())), redirect_stdout(io.StringIO()):
            self.engine.setup(self.args)
        self.args.offline = False

    def test_failed_hook_tool_install_skips_hook_and_reports_fix(self):
        failure = subprocess.CalledProcessError(1, ['mise', 'install', 'ruff'])
        output = io.StringIO()
        with mock.patch.object(self.engine.shutil, 'which', self.which_without({'ruff'})), \
             mock.patch.object(self.engine, 'run', side_effect=failure) as run, redirect_stdout(output):
            self.engine.apply(self.args)
        run.assert_called_once_with(['mise', 'install', '--cd', str(ROOT), 'ruff'])
        self.assertEqual(self.installed_hooks()['PostToolUse'], [])
        self.assertTrue(self.installed_hooks()['PreToolUse'])
        self.assertIn('Skipped hook PostToolUse (claude)', output.getvalue())
        self.assertIn('ruff is missing', output.getvalue())
        self.assertIn('install: mise install --cd ' + str(ROOT) + ' ruff', output.getvalue())

    def test_tool_is_installed_and_activated_before_hook_is_enabled(self):
        present = set()
        def which(program):
            return None if program == 'ruff' and program not in present else '/bin/' + program
        def activate():
            present.add('ruff')
            return mock.Mock(stdout='{}')
        with mock.patch.object(self.engine.shutil, 'which', which), \
             mock.patch.object(self.engine, 'run') as run, \
             mock.patch.object(self.engine.subprocess, 'run', side_effect=lambda *args, **kwargs: activate()) as env, \
             redirect_stdout(io.StringIO()):
            self.engine.apply(self.args)
        run.assert_called_once_with(['mise', 'install', '--cd', str(ROOT), 'ruff'])
        self.assertEqual(env.call_args.args[0], ['mise', 'env', '--json', '--cd', str(ROOT)])
        self.assertTrue(self.installed_hooks()['PostToolUse'])
        self.assertNotIn('requires', json.dumps(self.installed_hooks()))

    def test_successful_install_without_program_on_path_still_skips_hook(self):
        with mock.patch.object(self.engine.shutil, 'which', self.which_without({'ruff'})), \
             mock.patch.object(self.engine, 'run'), \
             mock.patch.object(self.engine.subprocess, 'run', return_value=mock.Mock(stdout='{}')), \
             redirect_stdout(io.StringIO()) as output:
            self.engine.apply(self.args)
        self.assertEqual(self.installed_hooks()['PostToolUse'], [])
        self.assertIn('not on PATH after installation', output.getvalue())

    def test_offline_reapply_disables_previously_installed_unusable_hook(self):
        self.install_fixture()
        self.assertTrue(self.installed_hooks()['PostToolUse'])
        self.args.offline = True
        with mock.patch.object(self.engine.shutil, 'which', self.which_without({'ruff'})), \
             mock.patch.object(self.engine, 'run') as run, redirect_stdout(io.StringIO()) as output:
            self.engine.apply(self.args)
            self.engine.doctor(self.args)
        run.assert_not_called()
        self.assertEqual(self.installed_hooks()['PostToolUse'], [])
        self.assertIn('offline; installation skipped', output.getvalue())
        self.assertTrue(list((self.home / '.agent-setup/backups').rglob('settings.json')))

    def test_setup_defers_hook_tools_to_the_install_gate(self):
        with mock.patch.object(self.engine.shutil, 'which', self.which_without({'ruff'})), \
             mock.patch.object(self.engine, 'toolkit') as toolkit, \
             mock.patch.object(self.engine, 'run', side_effect=OSError('installer unavailable')), \
             mock.patch.object(self.engine, 'plugins'), mock.patch.object(self.engine, 'skills'), \
             mock.patch.object(self.engine, 'doctor'), mock.patch.object(self.engine, 'updates'), \
             redirect_stdout(io.StringIO()) as output:
            self.engine.setup(self.args)
        self.assertIn('ruff', toolkit.call_args.kwargs['exclude'])
        self.assertEqual(self.installed_hooks()['PostToolUse'], [])
        self.assertIn('installer unavailable', output.getvalue())

    def test_doctor_and_check_tools_flag_installed_hook_missing_program(self):
        self.install_fixture()
        for action in (self.engine.doctor, self.engine.check_tools):
            with self.subTest(action=action.__name__), \
                 mock.patch.object(self.engine.shutil, 'which', self.which_without({'ruff'})), \
                 redirect_stdout(io.StringIO()), self.assertRaises(ValueError) as error:
                action(self.args)
            self.assertIn('Installed hook claude PostToolUse requires missing program ruff', str(error.exception))
            self.assertIn('install: mise install --cd ' + str(ROOT) + ' ruff', str(error.exception))

    def test_plan_and_dry_runs_report_requirements_without_writes_or_installs(self):
        for command in ('diff', 'apply', 'setup'):
            with self.subTest(command=command), \
                 mock.patch.object(self.engine.shutil, 'which', self.which_without({'ruff'})), \
                 mock.patch.object(self.engine, 'run') as run, \
                 mock.patch('sys.argv', ['engine.py', command, '--dry-run']), \
                 redirect_stdout(io.StringIO()), \
                 redirect_stderr(io.StringIO()) as output:
                self.engine.main()
            run.assert_not_called()
            self.assertEqual(list(self.home.iterdir()), [])
            self.assertIn('Missing hook requirement: ruff; would install: mise install', output.getvalue())

    def test_unconfigured_required_program_skips_hook(self):
        self.engine._YAML['hooks.yaml']['hooks'][0]['requires'] = ['unknown-hook-program']
        with mock.patch.object(self.engine.shutil, 'which', self.which_without({'unknown-hook-program'})), \
             mock.patch.object(self.engine, 'run') as run, redirect_stdout(io.StringIO()) as output:
            self.engine.apply(self.args)
        run.assert_not_called()
        self.assertEqual(self.installed_hooks()['PostToolUse'], [])
        self.assertIn('no installer configured', output.getvalue())
        self.assertIn('add an installer for unknown-hook-program to mise.toml', output.getvalue())

    def test_requires_must_be_a_list_of_strings(self):
        for invalid in ('ruff', [True], ['']):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'list of non-empty program names'):
                self.engine._YAML['hooks.yaml']['hooks'][0]['requires'] = invalid
                self.engine.hook_rows()

    def test_doctor_warns_but_passes_for_retired_shellcheck_hook(self):
        self.install_fixture()
        path = self.home / '.codex/hooks.json'
        data = json.loads(path.read_text())
        data['hooks']['PreToolUse'] = [{'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'node "' + str(self.home) + '/.codex/hooks/shellcheck-validate.mjs"'}]}]
        path.write_text(json.dumps(data))
        with mock.patch.object(self.engine.shutil, 'which', self.which_without(set())), redirect_stdout(io.StringIO()) as output:
            self.engine.doctor(self.args)
        self.assertIn('Warning: installed retired shellcheck-validate hook (codex)', output.getvalue())
        self.assertIn('remove', output.getvalue())

    def test_shipped_hooks_use_impeccable_executable_and_drop_shellcheck_gate(self):
        text = (ROOT / 'base/hooks.yaml').read_text()
        self.assertNotIn('shellcheck', text)
        self.assertNotIn('hook.mjs', text)
        self.assertFalse((ROOT / 'base/codex/hooks').exists())
        command = '[ ! -f "${HOME}/.agents/skills/impeccable/scripts/impeccable" ] || "${HOME}/.agents/skills/impeccable/scripts/impeccable" hook'
        commands = [row['command'] for row in self.engine.hook_rows() if 'impeccable' in row['command']]
        self.assertEqual(commands, [command, command])
