#!/usr/bin/env node
// Validate Bash commands with shellcheck before execution.
import { execFileSync } from 'child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

async function readStdin() {
  return await new Promise((resolve) => {
    const chunks = [];
    process.stdin.on('data', (chunk) => chunks.push(chunk));
    process.stdin.on('end', () => resolve(Buffer.concat(chunks).toString()));
  });
}

async function main() {
  let data = {};
  try {
    data = JSON.parse(await readStdin());
  } catch {}

  const command = data?.tool_input?.command;
  if (!command) {
    console.log(JSON.stringify({ continue: true }));
    return;
  }

  let tempDir;
  try {
    tempDir = mkdtempSync(join(tmpdir(), 'ccx-shellcheck-'));
    const tmp = join(tempDir, 'command.sh');
    writeFileSync(tmp, command);
    execFileSync('shellcheck', ['-s', 'bash', '-S', 'warning', tmp], { stdio: 'pipe' });
    console.log(JSON.stringify({ continue: true }));
  } catch (error) {
    const diagnostics = error.code === 'ENOENT'
      ? 'shellcheck is not installed; run `brew install shellcheck` or `mise run setup`'
      : [error.stdout, error.stderr]
      .filter(Boolean)
      .map((output) => output.toString().trim())
      .filter(Boolean)
      .join('\n');
    console.log(
      JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          permissionDecision: 'deny',
          permissionDecisionReason: diagnostics || 'shellcheck blocked this command'
        }
      })
    );
  } finally {
    if (tempDir) {
      try {
        rmSync(tempDir, { recursive: true, force: true });
      } catch {}
    }
  }
}

main();
