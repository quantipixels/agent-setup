import json
from pathlib import Path
import shutil
import tempfile
import tomllib
import unittest

import test_setup

ROOT = test_setup.ROOT


class ProjectToolchainTests(unittest.TestCase):
    # Reuse the existing temporary HOME and external-client harness.
    setUp = test_setup.SetupTests.setUp
    tearDown = test_setup.SetupTests.tearDown
    run_step = test_setup.SetupTests.run_step
    fake_clients = test_setup.SetupTests.fake_clients
    snapshot = test_setup.SetupTests.snapshot

    def project(self, name, **files):
        path = self.home / 'Projects' / name
        path.mkdir(parents=True, exist_ok=True)
        for filename, content in files.items(): (path / filename).write_text(content)
        return path

    def commands(self):
        path = Path(self.env['TEST_COMMANDS'])
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def installs(self):
        return [command[4:] for command in self.commands() if command[:2] == ['mise', 'install']]

    def test_maven_release_installs_jdk_and_maven_only_once(self):
        project = self.project('backend', **{'pom.xml': '<project xmlns="http://maven.apache.org/POM/4.0.0"><properties><maven.compiler.release>21</maven.compiler.release></properties></project>'})
        self.fake_clients('mise', 'shellcheck', 'jq', 'node', 'ruff')
        self.env['TEST_INSTALL_TOOLS'] = '1'
        output = self.run_step('apply', '--yes').stdout
        self.assertIn('Project: ' + str(project) + ' (pom.xml)', output)
        self.assertIn('Needs: java@21, maven@latest', output)
        self.assertEqual(self.installs(), [['java@21', 'maven@latest']])
        self.run_step('apply', '--yes')
        self.assertEqual(len(self.installs()), 1)

    def test_gradle_wrapper_uses_toolchain_and_never_installs_gradle(self):
        self.project('android', **{'gradlew': '#!/bin/sh\n', 'build.gradle.kts': 'java { toolchain { languageVersion.set(JavaLanguageVersion.of(17)) } }'})
        self.fake_clients('mise', 'shellcheck', 'jq', 'node', 'ruff')
        self.run_step('apply', '--yes')
        self.assertEqual(self.installs(), [['java@17']])

    def test_gradle_without_wrapper_needs_gradle_and_jdk(self):
        self.project('service', **{'build.gradle': 'java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }'})
        self.fake_clients('mise', 'shellcheck', 'jq', 'node', 'ruff')
        self.run_step('apply', '--yes')
        self.assertEqual(self.installs(), [['java@21', 'gradle@latest']])

    def test_nested_gradle_module_shares_parent_wrapper(self):
        project = self.project('android', **{'gradlew': '#!/bin/sh\n'})
        (project / 'app').mkdir()
        (project / 'app/build.gradle.kts').write_text('java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }')
        self.fake_clients('mise', 'shellcheck', 'jq', 'node', 'ruff')
        self.run_step('apply', '--yes')
        self.assertEqual(self.installs(), [['java@latest', 'java@21']])

    def test_project_mise_pins_override_tool_versions_and_build_versions(self):
        self.project('backend', **{'pom.xml': '<project><properties><java.version>17</java.version></properties></project>',
                                 '.tool-versions': 'java 19\nmaven 3.8.8\n',
                                 'mise.toml': '[tools]\njava = "21"\nmaven = { version = "3.9.9" }\n'})
        self.fake_clients('mise', 'shellcheck', 'jq', 'node', 'ruff')
        self.run_step('apply', '--yes')
        self.assertEqual(self.installs(), [['java@21', 'maven@3.9.9']])

    def test_disagreeing_pins_install_each_missing_version(self):
        self.project('first', **{'pom.xml': '<project/>', '.tool-versions': 'java 17\n'})
        self.project('second', **{'pom.xml': '<project/>', 'mise.toml': '[tools]\njava = ["21", "temurin-25"]\n'})
        self.fake_clients('mise', 'shellcheck', 'jq', 'node', 'ruff', 'java', 'mvn')
        self.env['TEST_MISE_INSTALLED'] = '["java@17"]'
        self.run_step('apply', '--yes')
        self.assertEqual(self.installs(), [['java@21', 'java@temurin-25']])

    def test_matching_jdk_on_path_is_kept_but_macos_launcher_is_missing(self):
        self.project('backend', **{'pom.xml': '<project><properties><maven.compiler.release>21</maven.compiler.release></properties></project>'})
        self.fake_clients('mise', 'shellcheck', 'jq', 'node', 'ruff', 'mvn', 'java')
        java = self.home / 'test-bin/java'
        java.write_text('#!/bin/sh\necho \'openjdk version "21.0.8"\' >&2\n')
        self.run_step('apply', '--yes')
        self.assertEqual(self.installs(), [])
        java.write_text('#!/bin/sh\necho "Unable to locate a Java Runtime" >&2\nexit 1\n')
        self.run_step('apply', '--yes')
        self.assertEqual(self.installs(), [['java@21']])

    def test_all_detection_rules_and_unrelated_pins(self):
        self.project('web', **{'package.json': '{}', 'pnpm-lock.yaml': '', 'mise.toml': '[tools]\nnode = "22"\npnpm = "10"\njava = "21"\n'})
        self.project('python', **{'pyproject.toml': '', 'uv.lock': '', '.tool-versions': 'uv 0.8.0\npython 3.12\n'})
        self.project('mobile', **{'pubspec.yaml': ''})
        self.project('rust', **{'Cargo.toml': ''})
        self.project('beam', **{'mix.exs': ''})
        self.fake_clients('mise', 'shellcheck', 'jq', 'node', 'ruff')
        self.run_step('apply', '--yes')
        self.assertEqual(set(self.installs()[0]), {'node@22', 'pnpm@10', 'uv@0.8.0', 'python@3.12', 'flutter@latest', 'rust@latest', 'elixir@latest', 'erlang@latest'})

    def test_maven_compiler_release_and_java_property(self):
        self.project('compiler', **{'pom.xml': '<project><properties><jdk>21</jdk></properties><build><plugins><plugin><artifactId>maven-compiler-plugin</artifactId><configuration><release>${jdk}</release></configuration></plugin></plugins></build></project>'})
        self.project('old', **{'pom.xml': '<project><properties><java.version>1.8</java.version></properties></project>'})
        self.fake_clients('mise', 'shellcheck', 'jq', 'node', 'ruff')
        self.run_step('apply', '--yes')
        self.assertEqual(self.installs(), [['java@21', 'maven@latest', 'java@8']])

    def test_empty_root_adds_no_toolchains(self):
        (self.home / 'Projects').mkdir()
        self.fake_clients('mise', 'shellcheck', 'jq', 'node', 'ruff')
        output = self.run_step('apply').stdout
        self.assertIn('No project toolchains detected.', output)
        self.assertEqual(self.installs(), [])

    def test_scan_is_shallow_skips_output_and_supports_repeatable_override(self):
        default = self.project('default', **{'pubspec.yaml': ''})
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            roots = [Path(first), Path(second)]
            for root in roots:
                (root / 'group/project').mkdir(parents=True)
                (root / 'group/project/package.json').write_text('{}')
                for ignored in ('node_modules', '.git', 'build', 'dist', 'target', 'group/project/nested'):
                    path = root / ignored
                    path.mkdir(parents=True, exist_ok=True)
                    (path / 'pom.xml').write_text('<project/>')
                (root / 'linked').symlink_to(default, target_is_directory=True)
            self.fake_clients('mise')
            output = self.run_step('diff', '--projects', first, '--projects', second).stdout
            self.assertIn('Project roots (up to two levels): ' + first + ', ' + second, output)
            self.assertEqual(output.count('Project: '), 2)
            self.assertIn('node@latest', output)
            self.assertNotIn('java@', output)
            self.assertNotIn('flutter@', output)
            self.assertEqual(self.installs(), [])

    def test_plan_and_dry_runs_do_not_write_or_install(self):
        self.project('backend', **{'pom.xml': '<project><properties><maven.compiler.release>21</maven.compiler.release></properties></project>'})
        self.fake_clients('mise')
        before = self.snapshot()
        for command, arguments in [('diff', []), ('apply', ['--dry-run']), ('setup', ['--dry-run'])]:
            with self.subTest(command=command):
                result = self.run_step(command, *arguments)
                self.assertIn('Needs: java@21, maven@latest', result.stdout)
                self.assertIn('mise install --cd ' + str(ROOT) + ' java@21 maven@latest', result.stdout)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.commands(), [])

    def test_real_mise_lookup_leaves_temporary_home_unchanged(self):
        mise = shutil.which('mise')
        self.assertIsNotNone(mise, 'mise is required for the read-only lookup regression')
        self.project('backend', **{'pom.xml': '<project><properties><maven.compiler.release>21</maven.compiler.release></properties></project>'})
        self.fake_clients('mise')
        binary = self.home / 'test-bin/mise'
        binary.unlink()
        binary.symlink_to(mise)
        before = self.snapshot()
        result = self.run_step('diff')
        self.assertIn('java@21 maven@latest', result.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_missing_yq_does_not_bootstrap_it_during_plan(self):
        self.fake_clients('mise')
        (self.home / 'test-bin/yq').unlink()
        before = self.snapshot()
        result = self.run_step('diff', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('yq is required', result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.commands(), [])

    def test_offline_skips_installs_and_approval_precedes_all_mutations(self):
        self.project('backend', **{'pom.xml': '<project/>'})
        self.fake_clients('mise', 'shellcheck', 'jq', 'node', 'ruff')
        before = self.snapshot()
        for command in ('apply', 'setup'):
            result = self.run_step(command, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('approval first', result.stderr)
            self.assertEqual(self.snapshot(), before)
        output = self.run_step('setup', '--offline', '--yes', '--no-login').stdout
        self.assertIn('Offline: project toolchain installation skipped.', output)
        self.assertEqual(self.installs(), [])

    def full_profile(self):
        self.run_step('setup', '--offline', '--yes', '--no-login')
        tools = tomllib.loads((ROOT / 'mise.toml').read_text())['tools']
        aliases = {'python': 'python3', 'ripgrep': 'rg', 'npm:vite-plus': 'vp', 'npm:oxfmt': 'oxfmt', 'npm:typescript': 'tsc', 'npm:pyright': 'pyright'}
        self.fake_clients('git', 'mise', 'npm', *(aliases.get(name, name) for name in tools if name not in ('python', 'yq')))
        settings = json.loads((self.home / '.claude/settings.json').read_text())
        cache = self.home / 'fixture-plugin-cache'
        cache.mkdir()
        inventory = {plugin: [{'scope': 'user', 'installPath': str(cache)}] for plugin in settings['enabledPlugins']}
        path = self.home / '.claude/plugins/installed_plugins.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'plugins': inventory}))
        self.run_step('skills')
        for command in self.commands():
            if command[0] != 'npx': continue
            path = self.home / '.agents/skills' / command[command.index('--skill') + 1] / 'SKILL.md'
            path.parent.mkdir(parents=True)
            path.write_text('Fixture installed skill.\n')
        (self.home / '.agent-setup/profile.json').write_text('{"profile":"full"}')
        self.env['TEST_CODEX_PLUGINS'] = '["qp-skills@qp-skills"]'

    def test_full_doctor_reports_missing_project_pin_with_fix_and_respects_roots(self):
        project = self.project('backend', **{'pom.xml': '<project><properties><maven.compiler.release>21</maven.compiler.release></properties></project>'})
        self.full_profile()
        result = self.run_step('doctor', '--dry-run', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing project toolchain: ' + str(project) + ' needs java@21; install: mise install --cd ' + str(ROOT) + ' java@21', result.stderr)
        self.assertIn('needs maven@latest', result.stderr)
        self.env['TEST_MISE_INSTALLED'] = '["java@21", "maven@3.9.9"]'
        self.assertIn('Doctor passed: full', self.run_step('doctor', '--dry-run').stdout)
        self.env['TEST_MISE_INSTALLED'] = '[]'
        with tempfile.TemporaryDirectory() as empty:
            self.assertIn('Doctor passed: full', self.run_step('doctor', '--dry-run', '--projects', empty).stdout)

    def test_setup_installs_project_node_pin_without_base_latest(self):
        self.project('web', **{'package.json': '{}', 'mise.toml': '[tools]\nnode = "22"\n'})
        self.full_profile()
        (self.home / 'test-bin/node').unlink()
        self.env['TEST_INSTALL_TOOLS'] = '1'
        result = self.run_step('setup', '--yes', '--no-login')
        self.assertIn('Doctor passed: full', result.stdout)
        self.assertEqual(self.installs(), [['node@22']])
