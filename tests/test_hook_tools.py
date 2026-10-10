import argparse
from contextlib import redirect_stdout
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
        for filename in ('hooks.yaml', 'plugins.yaml'):
            self.engine.load_yaml(filename)
        self.args = argparse.Namespace(offline=False, dry_run=False, yes=True, no_login=True)

    def which_without(self, missing):
        return lambda program: None if program in missing else '/bin/' + program

    def installed_hooks(self):
        return json.loads((self.home / '.codex/hooks.json').read_text())['hooks']

    def install_fixture(self):
        self.args.offline = True
        with mock.patch.object(self.engine.shutil, 'which', self.which_without(set())), redirect_stdout(io.StringIO()):
            self.engine.setup(self.args)
        self.args.offline = False

    def test_failed_hook_tool_install_skips_hook_and_reports_fix(self):
        failure = subprocess.CalledProcessError(1, ['mise', 'install', 'shellcheck'])
        output = io.StringIO()
        with mock.patch.object(self.engine.shutil, 'which', self.which_without({'shellcheck'})), \
             mock.patch.object(self.engine, 'run', side_effect=failure) as run, redirect_stdout(output):
            self.engine.apply(self.args)
        run.assert_called_once_with(['mise', 'install', '--cd', str(ROOT), 'shellcheck'])
        self.assertEqual(self.installed_hooks()['PreToolUse'], [])
        self.assertTrue(self.installed_hooks()['Stop'])
        self.assertIn('Skipped hook PreToolUse (codex)', output.getvalue())
        self.assertIn('shellcheck is missing', output.getvalue())
        self.assertIn('install: mise install --cd ' + str(ROOT) + ' shellcheck', output.getvalue())

    def test_tool_is_installed_and_activated_before_hook_is_enabled(self):
        present = set()
        def which(program):
            return None if program == 'shellcheck' and program not in present else '/bin/' + program
        def activate():
            present.add('shellcheck')
            return mock.Mock(stdout='{}')
        with mock.patch.object(self.engine.shutil, 'which', which), \
             mock.patch.object(self.engine, 'run') as run, \
             mock.patch.object(self.engine.subprocess, 'run', side_effect=lambda *args, **kwargs: activate()) as env, \
             redirect_stdout(io.StringIO()):
            self.engine.apply(self.args)
        run.assert_called_once_with(['mise', 'install', '--cd', str(ROOT), 'shellcheck'])
        self.assertEqual(env.call_args.args[0], ['mise', 'env', '--json', '--cd', str(ROOT)])
        self.assertTrue(self.installed_hooks()['PreToolUse'])
        self.assertNotIn('requires', json.dumps(self.installed_hooks()))

    def test_successful_install_without_program_on_path_still_skips_hook(self):
        with mock.patch.object(self.engine.shutil, 'which', self.which_without({'shellcheck'})), \
             mock.patch.object(self.engine, 'run'), \
             mock.patch.object(self.engine.subprocess, 'run', return_value=mock.Mock(stdout='{}')), \
             redirect_stdout(io.StringIO()) as output:
            self.engine.apply(self.args)
        self.assertEqual(self.installed_hooks()['PreToolUse'], [])
        self.assertIn('not on PATH after installation', output.getvalue())

    def test_offline_reapply_disables_previously_installed_unusable_hook(self):
        self.install_fixture()
        self.assertTrue(self.installed_hooks()['PreToolUse'])
        self.args.offline = True
        with mock.patch.object(self.engine.shutil, 'which', self.which_without({'shellcheck'})), \
             mock.patch.object(self.engine, 'run') as run, redirect_stdout(io.StringIO()) as output:
            self.engine.apply(self.args)
            self.engine.doctor(self.args)
        run.assert_not_called()
        self.assertEqual(self.installed_hooks()['PreToolUse'], [])
        self.assertIn('offline; installation skipped', output.getvalue())
        self.assertTrue(list((self.home / '.agent-setup/backups').rglob('hooks.json')))

    def test_setup_defers_hook_tools_to_the_install_gate(self):
        with mock.patch.object(self.engine.shutil, 'which', self.which_without({'shellcheck'})), \
             mock.patch.object(self.engine, 'toolkit') as toolkit, \
             mock.patch.object(self.engine, 'run', side_effect=OSError('installer unavailable')), \
             mock.patch.object(self.engine, 'plugins'), mock.patch.object(self.engine, 'skills'), \
             mock.patch.object(self.engine, 'doctor'), mock.patch.object(self.engine, 'updates'), \
             redirect_stdout(io.StringIO()) as output:
            self.engine.setup(self.args)
        self.assertIn('shellcheck', toolkit.call_args.kwargs['exclude'])
        self.assertEqual(self.installed_hooks()['PreToolUse'], [])
        self.assertIn('installer unavailable', output.getvalue())

    def test_doctor_and_check_tools_flag_installed_hook_missing_program(self):
        self.install_fixture()
        for action in (self.engine.doctor, self.engine.check_tools):
            with self.subTest(action=action.__name__), \
                 mock.patch.object(self.engine.shutil, 'which', self.which_without({'shellcheck'})), \
                 redirect_stdout(io.StringIO()), self.assertRaises(ValueError) as error:
                action(self.args)
            self.assertIn('Installed hook codex PreToolUse requires missing program shellcheck', str(error.exception))
            self.assertIn('install: mise install --cd ' + str(ROOT) + ' shellcheck', str(error.exception))

    def test_plan_and_dry_runs_report_requirements_without_writes_or_installs(self):
        for command in ('diff', 'apply', 'setup'):
            with self.subTest(command=command), \
                 mock.patch.object(self.engine.shutil, 'which', self.which_without({'shellcheck'})), \
                 mock.patch.object(self.engine, 'run') as run, \
                 mock.patch('sys.argv', ['engine.py', command, '--dry-run']), \
                 redirect_stdout(io.StringIO()) as output:
                self.engine.main()
            run.assert_not_called()
            self.assertEqual(list(self.home.iterdir()), [])
            self.assertIn('Missing hook requirement: shellcheck; would install: mise install', output.getvalue())

    def test_unconfigured_required_program_skips_hook(self):
        self.engine._YAML['hooks.yaml']['hooks'][0]['requires'] = ['unknown-hook-program']
        with mock.patch.object(self.engine.shutil, 'which', self.which_without({'unknown-hook-program'})), \
             mock.patch.object(self.engine, 'run') as run, redirect_stdout(io.StringIO()) as output:
            self.engine.apply(self.args)
        run.assert_not_called()
        self.assertEqual(self.installed_hooks()['PreToolUse'], [])
        self.assertIn('no installer configured', output.getvalue())
        self.assertIn('add an installer for unknown-hook-program to mise.toml', output.getvalue())

    def test_requires_must_be_a_list_of_strings(self):
        for invalid in ('shellcheck', [True], ['']):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'list of non-empty program names'):
                self.engine._YAML['hooks.yaml']['hooks'][0]['requires'] = invalid
                self.engine.hook_rows()


class ShellcheckHookTests(unittest.TestCase):
    def run_hook(self, path, command):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'node must be installed to run the hook regression')
        result = subprocess.run([node, str(ROOT / 'base/codex/hooks/shellcheck-validate.mjs')],
                                env=dict(os.environ, PATH=path), input=json.dumps({'tool_input': {'command': command}}),
                                text=True, capture_output=True, check=True)
        return json.loads(result.stdout)

    def test_missing_shellcheck_denies_with_install_message(self):
        with tempfile.TemporaryDirectory() as empty_path:
            result = self.run_hook(empty_path, 'echo okay')['hookSpecificOutput']
        self.assertEqual(result['permissionDecision'], 'deny')
        self.assertEqual(result['permissionDecisionReason'],
                         'shellcheck is not installed; run `brew install shellcheck` or `mise run setup`')

    def test_real_shellcheck_warnings_are_still_denied(self):
        shellcheck = shutil.which('shellcheck')
        self.assertIsNotNone(shellcheck, 'shellcheck must be installed for the warning regression')
        with tempfile.TemporaryDirectory() as path:
            (Path(path) / 'shellcheck').symlink_to(shellcheck)
            denied = self.run_hook(path, 'echo $missing')['hookSpecificOutput']
            allowed = self.run_hook(path, 'echo okay')
        self.assertEqual(denied['permissionDecision'], 'deny')
        self.assertIn('SC2154', denied['permissionDecisionReason'])
        self.assertEqual(allowed, {'continue': True})
