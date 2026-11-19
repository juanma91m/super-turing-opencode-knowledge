import { Plugin } from '@opencode/plugin';
import { spawnSync } from 'node:child_process';
import assert from 'node:assert/strict';

export default Plugin.define({ id: 'opencode-knowledge.runtime-env', async setup(ctx) {
  const options = ctx.options as any;
  await ctx.shell.hook('create.before', event => {
    // Do not change environment of unrelated shell, even if its data mentions a
    // helper. Canonical broker/permissions validate role and argv independently.
    if (!/^\s*(?:bash|python3)\s/.test(event.command) || !/(?:knowledge_(?:search|status|status_engram|status_qdrant|inventory|store|seed_global)\.sh|helper\s+knowledge-(?:search|status))/.test(event.command)) return;
    const result = spawnSync('python3', [options.matcher], { input: JSON.stringify({ command: event.command }), cwd: event.cwd,
      env: { PATH: '/usr/local/bin:/usr/bin:/bin', HOME: process.env.HOME, PYTHONDONTWRITEBYTECODE: '1' }, encoding: 'utf8', timeout: 10000 });
    assert(!result.error && result.status === 0, 'Knowledge call could not be recognized safely');
    if (JSON.parse(result.stdout) === true) {
      const basic = Object.fromEntries(['PATH', 'USER', 'LOGNAME', 'LANG', 'TERM', 'TMPDIR', 'TMP', 'TEMP'].filter(key => event.env[key] !== undefined).map(key => [key, event.env[key]]));
      event.env = { ...basic, ...options.runtimeEnvironment };
    }
  });
} });
