import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { enableEngram, ENGRAM_TOOLS } from './engram-config.mjs';

const renderer = fileURLToPath(new URL('./assets.py', import.meta.url));
const quote = text => /^[A-Za-z0-9_./-]+$/.test(text) ? text : `'${text.replaceAll("'", "'\\''")}'`;

export function knowledgeExtension({ runtimeHome, runtimeConfig, environment = {}, server, permissions }) {
  return ({ document, instructions, assets, config, mock }) => {
    const bases = Object.fromEntries(assets.map(asset => [path.basename(asset.file, '.md'), asset.desired]));
    const rendered = spawnSync('python3', [renderer], {
      input: JSON.stringify({ config, runtime_home: runtimeHome, runtime_config: runtimeConfig, environment, agents: bases, mock: Boolean(mock) }),
      encoding: 'utf8', timeout: 10000, maxBuffer: 8 * 1024 * 1024,
      env: { PATH: process.env.PATH ?? '/usr/bin:/bin', PYTHONDONTWRITEBYTECODE: '1' },
    });
    assert(!rendered.error && rendered.status === 0, 'Knowledge asset rendering failed; no installation or backend access attempted');
    const plan = JSON.parse(rendered.stdout);
    const staged = plan.assets.map(item => ({ file: path.join(config, item.path), desired: Buffer.from(item.content_b64, 'base64'),
      ...(item.previous_b64 ? { previous: Buffer.from(item.previous_b64, 'base64'), backup: true } : {}), tag: 'knowledge' }));
    const next = enableEngram(document, { server, permissions });
    for (const role of ['plan', 'build']) next.agents[role] = { ...next.agents[role], disabled: false };
    const boundary = next.plugins.find(plugin => typeof plugin === 'object' && plugin.package.endsWith('/workshop-guard/'));
    assert(boundary, 'Expected explicit migration boundary');
    boundary.options.agents = plan.roles;
    boundary.options.additionalTools = ENGRAM_TOOLS;
    boundary.options.helperValidator = path.join(config, 'scripts/knowledge_runtime.py');
    for (const asset of staged) boundary.options.pinned[asset.file] = createHash('sha256').update(asset.desired).digest('hex');
    const commands = plan.helpers.flatMap(name => {
      const prefix = `bash ${quote(path.join(config, 'scripts', name))}`;
      return [prefix, prefix + ' *'];
    });
    for (const name of ['knowledge-search', 'knowledge-status']) {
      const prefix = `python3 ${quote(path.join(config, 'scripts/planner_shell.py'))} helper ${name}`;
      commands.push(prefix, prefix + ' *');
    }
    next.policies.push(...commands.map(command => ({ action: 'tool.use', resource: `shell:${command}`, effect: 'allow' })));
    return { document: next, assets: staged, roles: plan.roles, skills: plan.skills, tag: 'knowledge',
      instructions: instructions.replace(/Único MCP habilitado: Context7[^\n]+/, 'MCP habilitados: Context7 para documentación pública y Engram del addon Knowledge con permisos por rol.')
        .replace('No hay addons, MCP ni servicios reales.', 'Knowledge está habilitado con los backends seleccionados explícitamente; otros addons aún no están integrados.')
        + '\n## Knowledge V2\nConservá los contratos del addon: wrappers aprobados, scopes existentes, persistencia según autoridad del rol y ninguna indexación automática. Hay shims Knowledge y dos helpers de consulta/estado en el broker del planner. El piloto conserva el cierre de delegación de la base; eso no recorta las definiciones canónicas para la composición final.\n' };
  };
}
