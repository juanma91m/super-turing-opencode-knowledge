import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { enableEngram, ENGRAM_TOOLS } from './engram-config.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
export function knowledgeContribution({ runtimeHome, runtimeConfig, environment = {}, server, permissions }) {
  return { id: 'knowledge', apply(ctx) {
    assert(ctx.version === 1 && ctx.kind === 'general');
    const result = spawnSync('python3', [path.join(root, 'v2/general-assets.py')], { input: JSON.stringify({ config: ctx.config, runtime_home: runtimeHome, runtime_config: runtimeConfig, environment }),
      encoding: 'utf8', timeout: 10000, maxBuffer: 8 * 1024 * 1024, env: { PATH: '/usr/local/bin:/usr/bin:/bin', PYTHONDONTWRITEBYTECODE: '1' } });
    assert(!result.error && result.status === 0, 'Native Knowledge assets unavailable; no backend access attempted');
    const plan = JSON.parse(result.stdout);
    for (const asset of plan.assets) ctx.addConfig(asset.path, Buffer.from(asset.content_b64, 'base64'));
    const fallbacks = ctx.compileAgents(plan.agentTexts);
    for (const [name, agent] of Object.entries(fallbacks)) if (!ctx.agents[name]) ctx.agents[name] = agent;
    for (const [name, rule] of Object.entries(plan.autonomy)) {
      const agent = ctx.agents[name]; if (!agent) continue;
      if (!agent.permissions.some(item => item.action === 'subagent' && item.resource === rule.task_target)) agent.permissions.push({ action: 'subagent', resource: rule.task_target, effect: 'allow' });
      if (!agent.system.includes('<!-- KNOWLEDGE_AUTONOMY_START -->')) agent.system += '\n\n<!-- KNOWLEDGE_AUTONOMY_START -->\n' + rule.block + '\n<!-- KNOWLEDGE_AUTONOMY_END -->\n';
    }
    for (const role of ['plan', 'build']) ctx.document.agents[role] = { ...ctx.document.agents[role], disabled: false, hidden: true };
    ctx.copyBundleTree('knowledge', path.join(root, 'v2/plugins/engram'), 'v2/plugins/engram');
    ctx.copyBundleTree('knowledge', path.join(root, 'v2/plugins/runtime-env'), 'v2/plugins/runtime-env');
    ctx.addBundle('knowledge', 'lib/memory-contract.mjs', ctx.readAsset(path.join(root, 'lib/memory-contract.mjs')));
    Object.assign(ctx.document, enableEngram(ctx.document, { server, permissions, packagePath: ctx.bundlePath('knowledge', 'v2/plugins/engram') }));
    ctx.document.plugins.push({ package: ctx.bundlePath('knowledge', 'v2/plugins/runtime-env'), options: { matcher: path.join(ctx.config, 'scripts/knowledge_native_env.py'), runtimeEnvironment: plan.runtimeEnvironment } });
    ctx.closeTools('engram_*', ENGRAM_TOOLS);
    ctx.appendInstructions('## Knowledge general V2\nMismos backends/settings por binding explícito y wrappers aprobados; sin indexación automática. Persistencia según autoridad; los read-only conservan sus denies. No sourcear ni copiar overrides locales desde el modelo. Los helpers canónicos del perfil usan entorno existente seleccionado sin despachar recursivamente a sí mismos.');
    ctx.metadata.knowledge = { helpers: 7, commands: 5, runtime: 'existing explicit identity; canonical wrappers; no backend copied' };
  } };
}
