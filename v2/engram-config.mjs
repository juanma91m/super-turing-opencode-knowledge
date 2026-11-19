import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const contract = JSON.parse(fs.readFileSync(new URL('./engram-tools.json', import.meta.url), 'utf8'));
export const ENGRAM_TOOLS = Object.freeze(contract.tools.map(name => `engram_${name}`));
export const READER_DENIED = Object.freeze(contract.readerDenied.map(name => `engram_${name}`));
export const adapterPackage = fileURLToPath(new URL('./plugins/engram/', import.meta.url)).replace(/\/$/, '');

function matches(pattern, value) {
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, '\\$&').replaceAll('*', '.*').replaceAll('?', '.');
  return new RegExp(`^${escaped}$`).test(value);
}

// Translate a selected V1 local MCP definition; never discover/read active
// configuration, guess HOME/data/project, or change autosync behind the caller.
export function translateEngram(server) {
  assert.equal(server?.type, 'local', 'Expected existing local Engram definition');
  assert(Array.isArray(server.command) && server.command.length > 0 && server.command.every(value => typeof value === 'string' && value.length), 'Engram command must be an argv array');
  const { enabled, timeout, ...rest } = structuredClone(server);
  assert(!Object.hasOwn(rest, 'disabled') && !Object.hasOwn(rest, 'codemode'), 'Expected V1 Engram definition');
  if (enabled !== undefined) assert.equal(typeof enabled, 'boolean');
  if (timeout !== undefined) assert(Number.isSafeInteger(timeout) && timeout > 0, 'Invalid legacy MCP timeout');
  return { ...rest, ...(enabled !== undefined ? { disabled: !enabled } : {}), codemode: false,
    ...(timeout !== undefined ? { timeout: { execution: timeout } } : {}) };
}

// Explicit opt-in composition for a deny-baseline migration profile. Canonical
// agent-specific denies remain in their agent definitions and are not rewritten.
export function enableEngram(base, { server, permissions, packagePath = adapterPackage }) {
  assert(path.isAbsolute(packagePath), 'Local adapter package must be absolute');
  assert(server?.type === 'local' && server.codemode === false, 'Direct native MCP definition required');
  assert(!Object.hasOwn(base.mcp?.servers ?? {}, 'engram'), 'Do not replace an existing Engram definition implicitly');
  assert(Array.isArray(permissions), 'Pass the intended current tool effects explicitly');
  assert.deepEqual(permissions.map(rule => rule.action).sort(), [...ENGRAM_TOOLS].sort(), 'Classify every current Engram tool, without wildcards or omissions');
  assert(permissions.every(rule => rule.resource === '*' && ['allow', 'ask', 'deny'].includes(rule.effect)), 'Invalid Engram tool effects');
  assert(!(base.permissions ?? []).some(rule => rule.action !== '*' && ENGRAM_TOOLS.some(name => matches(rule.action, name))), 'Existing Engram-specific rules require explicit reconciliation, not appended grants');
  assert(!(base.policies ?? []).some(rule => rule.resource !== '*' && (
    rule.action === 'mcp.use' && matches(rule.resource, 'engram')
    || rule.action === 'tool.use' && ENGRAM_TOOLS.some(name => matches(rule.resource, `${name}:*`))
  )), 'Existing Engram policies require explicit reconciliation');
  const document = structuredClone(base);
  document.mcp ??= { servers: {} };
  document.mcp.servers ??= {};
  document.mcp.servers.engram = structuredClone(server);
  document.permissions = [...(document.permissions ?? []), ...structuredClone(permissions)];
  document.policies = [...(document.policies ?? []), { action: 'mcp.use', resource: 'engram', effect: 'allow' },
    ...ENGRAM_TOOLS.map(name => ({ action: 'tool.use', resource: `${name}:*`, effect: 'allow' }))];
  document.plugins = [...(document.plugins ?? []), packagePath];
  return document;
}
