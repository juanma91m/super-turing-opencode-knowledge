import assert from 'node:assert/strict';
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import { stripTypeScriptTypes } from 'node:module';
import { test } from 'node:test';
import hintsV1 from '../../plugins/engram-memory-hints.ts';
import summaryV1 from '../../plugins/engram-session-context.ts';
import { MEMORY_HINT, needsMemoryHint, injectSummarySession } from '../../lib/memory-contract.mjs';
import { addMemoryHints, register } from '../plugins/engram/hooks.mjs';
import { translateEngram, enableEngram, ENGRAM_TOOLS, READER_DENIED } from '../engram-config.mjs';

const loadOriginal = async name => {
  const text = execFileSync('git', ['show', `HEAD:plugins/${name}.ts`], { cwd: new URL('../../', import.meta.url), encoding: 'utf8' });
  // The committed V1 fixture can already import the shared helper. Resolve
  // that specifier before loading from a non-hierarchical data URL.
  const source = stripTypeScriptTypes(text, { mode: 'transform' }).replace(
    /(['"])\.\.\/lib\/memory-contract\.mjs\1/g, JSON.stringify(new URL('../../lib/memory-contract.mjs', import.meta.url).href),
  );
  return (await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))).default;
};

test('shared hint extraction preserves the committed V1 behavior and synthetic exclusions', async () => {
  const before = await (await loadOriginal('engram-memory-hints'))();
  const after = await hintsV1();
  for (const parts of [[], [{ type: 'text', text: 'ordinary question' }], [{ type: 'text', text: 'remember fixture' }],
    [{ type: 'text', text: "DON'T forget fixture" }], [{ type: 'text', text: 'save this fixture', synthetic: true }],
    [{ type: 'text', text: 'recordá esto' }], [{ type: 'file', text: 'remember attachment' }]]) {
    const a = { message: { id: 'msg-fixture' }, parts: structuredClone(parts) }, b = structuredClone(a);
    await before['chat.message']({ sessionID: 'ses_fixture' }, a);
    await after['chat.message']({ sessionID: 'ses_fixture' }, b);
    assert.deepEqual(a.parts.map(({ id, ...part }) => part), b.parts.map(({ id, ...part }) => part));
  }
  assert.equal(needsMemoryHint('ordinary question'), false);
});

test('shared summary extraction preserves explicit IDs, blank handling and unrelated calls', async () => {
  const before = await (await loadOriginal('engram-session-context'))();
  const after = await summaryV1();
  for (const tool of ['engram_mem_save', 'engram_mem_session_summary']) for (const sessionID of ['', '   ', 'ses_fixture']) {
    for (const session_id of [undefined, '', ' ', 'explicit', null, 0]) {
      const a = { args: { content: 'fixture', session_id } }, b = structuredClone(a);
      await before['tool.execute.before']({ tool, sessionID }, a);
      await after['tool.execute.before']({ tool, sessionID }, b);
      assert.deepEqual(a, b);
    }
  }
  assert.doesNotThrow(() => injectSummarySession('engram_mem_session_summary', 'ses_fixture', null));
});

test('native hints use original user IDs, never synthetic/tool/attachment content, and are idempotent', () => {
  const originals = [
    { id: 'msg_user', type: 'user', text: 'remember fixture' },
    { id: 'msg_attachment', type: 'user', text: 'ordinary question', files: [{ text: 'remember fixture' }] },
    { id: 'msg_synthetic', type: 'synthetic', text: 'remember fixture' },
  ];
  const messages = ['msg_user', 'msg_attachment', 'msg_synthetic', 'msg_unknown'].map(id => ({ id, role: 'user', content: [{ type: 'text', text: 'remember rendered content' }] }));
  messages.push({ id: 'msg_tool', role: 'tool', content: [{ type: 'text', text: 'remember tool output' }] });
  const original = structuredClone(messages), event = { messages };
  addMemoryHints(event, originals);
  addMemoryHints(event, originals);
  assert.equal(event.messages[0].content.filter(part => part.text === MEMORY_HINT).length, 1);
  assert.deepEqual(event.messages.slice(1), original.slice(1));
  assert.deepEqual(messages, original, 'Never mutate durable/native objects passed by the caller');
});

test('native hooks use the executing session, survive reload and do not register grants or backend calls', async () => {
  const tools = new Map(), sessions = new Map();
  const ctx = { tool: { async hook(kind, fn) { tools.set(kind, fn); } }, session: {
    async hook(kind, fn) { sessions.set(kind, fn); },
    async context({ sessionID }) { assert.equal(sessionID, 'ses_executor'); return [{ id: 'msg_user', type: 'user', text: 'remember fixture' }]; },
  } };
  await register(ctx);
  assert.deepEqual([...sessions.keys()], ['context', 'compaction', 'generate']);
  const call = { tool: 'engram_mem_session_summary', sessionID: 'ses_executor', input: { content: 'fixture' } };
  tools.get('execute.before')(call);
  assert.equal(call.input.session_id, 'ses_executor');
  const event = { sessionID: 'ses_executor', messages: [{ id: 'msg_user', role: 'user', content: [{ type: 'text', text: 'remember fixture' }] }] };
  await sessions.get('context')(event);
  assert.equal(event.messages[0].content.at(-1).text, MEMORY_HINT);
  await register(ctx); // no session-local in-memory marker required after reload
  const replay = { sessionID: 'ses_executor', messages: [{ id: 'msg_user', role: 'user', content: [] }] };
  await sessions.get('compaction')(replay);
  assert.equal(replay.messages[0].content.at(-1).text, MEMORY_HINT);
});

test('native wiring preserves command/env/cwd/disabled state without adding backend flags', () => {
  const old = { type: 'local', command: ['/fixture/engram', 'mcp', '--tools=fixture'], cwd: '/fixture/project',
    environment: { HOME: '/fixture/home', ENGRAM_CLOUD_AUTOSYNC: '1' }, enabled: false, timeout: 1234 };
  const before = structuredClone(old), next = translateEngram(old);
  assert.deepEqual(old, before);
  assert.deepEqual(next.command, old.command);
  assert.deepEqual(next.environment, old.environment);
  assert.equal(next.cwd, old.cwd); assert.equal(next.disabled, true); assert.equal(next.codemode, false);
  assert.deepEqual(next.timeout, { execution: 1234 });
  assert.equal(translateEngram({ type: 'local', command: ['/fixture/engram', 'mcp'] }).disabled, undefined);
  assert.throws(() => translateEngram({ type: 'remote' }));
});

test('explicit composition preserves existing rules and requires the entire reviewed tool inventory', () => {
  const base = { permissions: [{ action: '*', resource: '*', effect: 'deny' }], policies: [], plugins: ['existing'], mcp: { servers: { docs: { type: 'remote', url: 'https://example.invalid' } } } };
  const previous = structuredClone(base);
  const server = translateEngram({ type: 'local', command: ['/fixture/engram', 'mcp'] });
  const permissions = ENGRAM_TOOLS.map(action => ({ action, resource: '*', effect: 'allow' }));
  const next = enableEngram(base, { server, permissions });
  assert.deepEqual(base, previous);
  assert.deepEqual(next.permissions.slice(0, 1), base.permissions);
  assert.deepEqual(next.mcp.servers.docs, base.mcp.servers.docs);
  assert.equal(next.permissions.length, 12);
  assert.equal(READER_DENIED.length, 5);
  assert(!ENGRAM_TOOLS.includes('engram_mem_delete'));
  assert.throws(() => enableEngram(base, { server, permissions: permissions.slice(1) }), /Classify/);
  assert.throws(() => enableEngram(next, { server, permissions }), /implicitly/);
  assert.throws(() => enableEngram({ ...base, permissions: [...base.permissions, { action: 'engram_*', resource: '*', effect: 'deny' }] }, { server, permissions }), /reconciliation/);
  assert.throws(() => enableEngram({ ...base, policies: [{ action: 'mcp.use', resource: 'engram', effect: 'deny' }] }, { server, permissions }), /reconciliation/);
});

test('shared module is distributed with V1; native package uses only the public plugin API', () => {
  const manifest = JSON.parse(fs.readFileSync(new URL('../../KNOWLEDGE-MANIFEST.json', import.meta.url)));
  assert(manifest.managedFiles.includes('lib/memory-contract.mjs'));
  const entry = fs.readFileSync(new URL('../plugins/engram/index.ts', import.meta.url), 'utf8');
  assert(entry.includes('"@opencode/plugin"'));
  assert(!entry.includes('@opencode/core'));
});
